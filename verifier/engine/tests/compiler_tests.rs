//! R3 acceptance tests: rule compiler (mock), DSL validation, fail-safe, cache.

use aegis_gate_engine::compiler::{
    assemble_policy, parse_compiled_rules, CachingCompiler, MockCompiler, RuleCompiler,
};
use aegis_gate_engine::evaluate;
use aegis_gate_engine::model::*;
use serde_json::json;

fn sample_mcp() -> Mcp {
    Mcp {
        id: "6a89974fe413c1e675df5b82".into(),
        name: "mongo-catalog-mcp".into(),
        description: "product catalog".into(),
        rules: vec![
            Rule { priority: 1, instruction: "deny any write operation outside working hours".into() },
            Rule { priority: 2, instruction: "allow read-only queries on the 'orders' collection".into() },
        ],
    }
}

// --- end-to-end: NL rules → compiled policy → verdict -----------------------

#[test]
fn compiles_and_evaluates_drop_table() {
    let mcp = sample_mcp();
    let rules = MockCompiler.compile(&mcp.rules).unwrap();
    let policy = assemble_policy(rules);

    let input = EvalInput {
        mcp,
        request: McpRequest {
            accessed_by: "agent-subtask-07".into(),
            action: "drop_table".into(),
            payload: json!({ "intent": "DROP TABLE orders" }),
        },
        time: "2026-08-22T12:00:00Z".into(),
    };
    let v = evaluate(&input, &policy).unwrap();
    assert!(!v.allowed);
    assert_eq!(v.violated_priority, Some(1));
}

// --- the trust boundary: LLM output validation ------------------------------

#[test]
fn parse_accepts_valid_dsl() {
    let json = r#"[
      {"priority":1,"effect":"deny","condition":{"op":"op_class_in","classes":["destructive"]}},
      {"priority":2,"effect":"allow","condition":{"op":"and","all":[
         {"op":"op_class_in","classes":["read"]},
         {"op":"collection_eq","collection":"orders"}]}}
    ]"#;
    let rules = parse_compiled_rules(json).unwrap();
    assert_eq!(rules.len(), 2);
    assert_eq!(rules[0].effect, Effect::Deny);
}

#[test]
fn parse_rejects_unknown_op() {
    // "op":"sql_injection" is not in the DSL → serde tagged-enum rejects it (fail-safe).
    let json = r#"[{"priority":1,"effect":"deny","condition":{"op":"sql_injection"}}]"#;
    assert!(parse_compiled_rules(json).is_err());
}

#[test]
fn parse_rejects_bad_effect() {
    let json = r#"[{"priority":1,"effect":"maybe","condition":{"op":"always"}}]"#;
    assert!(parse_compiled_rules(json).is_err());
}

#[test]
fn parse_rejects_malformed_json() {
    assert!(parse_compiled_rules("not json at all").is_err());
}

#[test]
fn parse_rejects_excessive_nesting() {
    // 10 levels of not() exceeds MAX_CONDITION_DEPTH (8).
    let mut cond = String::from(r#"{"op":"always"}"#);
    for _ in 0..10 {
        cond = format!(r#"{{"op":"not","cond":{cond}}}"#);
    }
    let json = format!(r#"[{{"priority":1,"effect":"deny","condition":{cond}}}]"#);
    assert!(parse_compiled_rules(&json).is_err());
}

// --- fail-safe: a rule the compiler can't handle -> error -------------------

#[test]
fn uncompilable_rule_errors() {
    let rules = vec![Rule { priority: 1, instruction: "do something vague and weird".into() }];
    assert!(MockCompiler.compile(&rules).is_err(), "caller must fail-safe deny on compile error");
}

// --- caching ----------------------------------------------------------------

#[test]
fn cache_hits_on_same_rules() {
    let cc = CachingCompiler::new(MockCompiler);
    let mcp = sample_mcp();
    let (_p1, hit1) = cc.compile_policy(&mcp).unwrap();
    let (_p2, hit2) = cc.compile_policy(&mcp).unwrap();
    assert!(!hit1, "first compile is a miss");
    assert!(hit2, "second compile of identical rules is a cache hit");
}

#[test]
fn cache_misses_on_changed_rules() {
    let cc = CachingCompiler::new(MockCompiler);
    let mut mcp = sample_mcp();
    let (_p1, hit1) = cc.compile_policy(&mcp).unwrap();
    mcp.rules[0].instruction = "deny any write operation outside working hours entirely".into();
    let (_p2, hit2) = cc.compile_policy(&mcp).unwrap();
    assert!(!hit1 && !hit2, "changed rule text → new source hash → cache miss");
}
