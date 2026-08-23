//! R6/R7 tests: normalizer (mock), multi-operation deny-if-any, deterministic scanner.

use aegis_gate_engine::attributes::from_operation;
use aegis_gate_engine::compiler::{assemble_policy, MockCompiler, RuleCompiler};
use aegis_gate_engine::engine::evaluate_operations;
use aegis_gate_engine::model::*;
use aegis_gate_engine::normalizer::{parse_normalized, CachingNormalizer, MockNormalizer, RequestNormalizer};
use aegis_gate_engine::scanner;
use serde_json::json;

fn mcp(rules: Vec<(i64, &str)>) -> Mcp {
    Mcp {
        id: "m".into(),
        name: "mongo-catalog-mcp".into(),
        description: "catalog".into(),
        rules: rules.into_iter().map(|(p, i)| Rule { priority: p, instruction: i.into() }).collect(),
    }
}

fn req(intent: &str) -> McpRequest {
    McpRequest { accessed_by: "agent-07".into(), action: "internal-id".into(), payload: json!({ "intent": intent }) }
}

fn op(op_class: OpClass, collection: Option<&str>) -> Operation {
    Operation { op_class, collection: collection.map(|s| s.into()) }
}

// --- normalizer produces an operations list -------------------------------

#[test]
fn mock_infers_from_intent_as_list() {
    let m = mcp(vec![(1, "deny writes")]);
    let n = MockNormalizer.normalize(&req("necesito una consulta de la coleccion orders"), &m).unwrap();
    assert_eq!(n.operations.len(), 1);
    assert_eq!(n.operations[0].op_class, OpClass::Read);
    assert_eq!(n.operations[0].collection.as_deref(), Some("orders"));
}

#[test]
fn parse_rejects_empty_operations() {
    assert!(parse_normalized(r#"{"operations":[]}"#).is_err(), "empty ops → fail-safe");
}

#[test]
fn parse_rejects_bad_opclass() {
    assert!(parse_normalized(r#"{"operations":[{"opClass":"nuke","collection":null}]}"#).is_err());
}

#[test]
fn parse_accepts_multi_op() {
    let n = parse_normalized(r#"{"operations":[{"opClass":"write","collection":"orders"},{"opClass":"read","collection":"secrets"}]}"#).unwrap();
    assert_eq!(n.operations.len(), 2);
}

// --- multi-operation deny-if-any -------------------------------------------

#[test]
fn deny_if_any_blocks_when_one_op_violates() {
    // Rule denies reading secrets. Request does {write orders, read secrets}.
    let m = mcp(vec![(1, "deny reading the secrets collection")]);
    let policy = assemble_policy(MockCompiler.compile(&[Rule {
        priority: 1,
        instruction: "deny reading secrets".into(),
    }]).unwrap_or_else(|_| vec![CompiledRule {
        priority: 1,
        effect: Effect::Deny,
        condition: Condition::And { all: vec![
            Condition::OpClassIn { classes: vec![OpClass::Read] },
            Condition::CollectionEq { collection: "secrets".into() },
        ]},
    }]));
    let input = EvalInput { mcp: m, request: req("x"), time: "2026-08-24T20:00:00Z".into() };
    let ops = vec![
        from_operation(&op(OpClass::Write, Some("orders")), &input.request, true),
        from_operation(&op(OpClass::Read, Some("secrets")), &input.request, true),
    ];
    let v = evaluate_operations(&input, &policy, &ops).unwrap().verdict;
    assert!(!v.allowed, "the read-secrets op must sink the whole request");
    assert!(v.reason.contains("operation 2"));
}

#[test]
fn all_ops_allowed_passes() {
    let policy = assemble_policy(vec![CompiledRule {
        priority: 1, effect: Effect::Deny,
        condition: Condition::CollectionEq { collection: "secrets".into() },
    }]);
    let input = EvalInput { mcp: mcp(vec![(1, "deny secrets")]), request: req("x"), time: "2026-08-24T20:00:00Z".into() };
    let ops = vec![
        from_operation(&op(OpClass::Read, Some("orders")), &input.request, true),
        from_operation(&op(OpClass::Write, Some("products")), &input.request, true),
    ];
    let v = evaluate_operations(&input, &policy, &ops).unwrap().verdict;
    assert!(v.allowed);
}

// --- deterministic scanner --------------------------------------------------

#[test]
fn scanner_flags_dropped_collection() {
    // Text mentions 'secrets' (a policy collection) but the LLM's ops don't → flag.
    let policy = assemble_policy(vec![CompiledRule {
        priority: 1, effect: Effect::Deny,
        condition: Condition::CollectionEq { collection: "secrets".into() },
    }]);
    let normalized = NormalizedRequest { operations: vec![op(OpClass::Write, Some("orders"))] };
    let r = scanner::scan(
        "registra un evento en orders y consulta la coleccion secrets",
        &normalized,
        &scanner::policy_collections(&policy),
    );
    assert!(!r.passed, "secrets mentioned but not extracted → must flag");
    assert!(r.reason.unwrap().contains("secrets"));
}

#[test]
fn scanner_flags_underclassified_severity() {
    // Text says "borra" (destructive) but the LLM only reported a read → flag.
    let policy = assemble_policy(vec![CompiledRule {
        priority: 1, effect: Effect::Deny, condition: Condition::Always,
    }]);
    let normalized = NormalizedRequest { operations: vec![op(OpClass::Read, Some("orders"))] };
    let r = scanner::scan("borra la coleccion orders", &normalized, &scanner::policy_collections(&policy));
    assert!(!r.passed, "destructive verb but only-read extraction → must flag");
}

#[test]
fn scanner_passes_when_consistent() {
    let policy = assemble_policy(vec![CompiledRule {
        priority: 1, effect: Effect::Deny,
        condition: Condition::CollectionEq { collection: "secrets".into() },
    }]);
    let normalized = NormalizedRequest {
        operations: vec![op(OpClass::Write, Some("orders")), op(OpClass::Read, Some("secrets"))],
    };
    let r = scanner::scan(
        "registra en orders y consulta secrets",
        &normalized,
        &scanner::policy_collections(&policy),
    );
    assert!(r.passed, "both ops extracted → consistent → pass");
}

// --- cache ------------------------------------------------------------------

#[test]
fn normalizer_cache_hits() {
    let cn = CachingNormalizer::new(MockNormalizer);
    let r = req("leer orders");
    let m = mcp(vec![(1, "deny writes")]);
    let (_n1, h1) = cn.normalize(&r, &m).unwrap();
    let (_n2, h2) = cn.normalize(&r, &m).unwrap();
    assert!(!h1 && h2);
}
