//! R1 acceptance tests: deterministic evaluator + DSL + hashing.

use aegis_gate_engine::defaults;
use aegis_gate_engine::evaluate;
use aegis_gate_engine::hashing::canonical_string;
use aegis_gate_engine::model::*;
use serde_json::json;

fn policy(rules: Vec<CompiledRule>, default_effect: Effect) -> CompiledPolicy {
    CompiledPolicy {
        rules,
        action_classes: defaults::action_classes(),
        working_hours: defaults::working_hours(),
        default_effect,
    }
}

fn input(action: &str, payload: serde_json::Value, time: &str) -> EvalInput {
    EvalInput {
        mcp: Mcp {
            id: "mcp1".into(),
            name: "test".into(),
            description: "".into(),
            rules: vec![Rule { priority: 1, instruction: "src".into() }],
        },
        request: McpRequest { accessed_by: "agent-07".into(), action: action.into(), payload },
        time: time.into(),
    }
}

fn deny_write_outside() -> CompiledRule {
    CompiledRule {
        priority: 1,
        effect: Effect::Deny,
        condition: Condition::And {
            all: vec![
                Condition::OpClassIn {
                    classes: vec![OpClass::Write, OpClass::Destructive, OpClass::Refund],
                },
                Condition::OutsideWorkingHours,
            ],
        },
    }
}

fn allow_read_orders() -> CompiledRule {
    CompiledRule {
        priority: 2,
        effect: Effect::Allow,
        condition: Condition::And {
            all: vec![
                Condition::OpClassIn { classes: vec![OpClass::Read] },
                Condition::CollectionEq { collection: "orders".into() },
            ],
        },
    }
}

// --- the canonical Roxy example --------------------------------------------

#[test]
fn drop_table_denied_by_priority_1() {
    // 12:00Z in Mexico (UTC-6) = 06:00 local → outside working hours → rule 1 fires.
    let p = policy(vec![deny_write_outside(), allow_read_orders()], Effect::Deny);
    let v = evaluate(&input("drop_table", json!({ "intent": "DROP TABLE orders" }), "2026-08-22T12:00:00Z"), &p).unwrap();
    assert!(!v.allowed);
    assert_eq!(v.violated_priority, Some(1));
    assert!(v.reason.contains("priority 1"));
}

// --- priority resolution ----------------------------------------------------

#[test]
fn read_orders_allowed_within_hours() {
    // 20:00Z = 14:00 local (within 09-18) → rule 1 does not fire; read matches rule 2 allow.
    let p = policy(vec![deny_write_outside(), allow_read_orders()], Effect::Deny);
    let v = evaluate(&input("read", json!({ "collection": "orders" }), "2026-08-24T20:00:00Z"), &p).unwrap();
    assert!(v.allowed);
    assert_eq!(v.violated_priority, None);
}

#[test]
fn smaller_priority_wins() {
    // Rule 1 deny (matches everything), rule 2 allow (matches everything). Deny wins.
    let deny_all = CompiledRule { priority: 1, effect: Effect::Deny, condition: Condition::Always };
    let allow_all = CompiledRule { priority: 2, effect: Effect::Allow, condition: Condition::Always };
    let p = policy(vec![allow_all, deny_all], Effect::Deny);
    let v = evaluate(&input("read", json!({}), "2026-08-24T20:00:00Z"), &p).unwrap();
    assert!(!v.allowed);
    assert_eq!(v.violated_priority, Some(1));
}

#[test]
fn deny_wins_tie_at_same_priority() {
    let allow = CompiledRule { priority: 1, effect: Effect::Allow, condition: Condition::Always };
    let deny = CompiledRule { priority: 1, effect: Effect::Deny, condition: Condition::Always };
    let p = policy(vec![allow, deny], Effect::Deny);
    let v = evaluate(&input("read", json!({}), "2026-08-24T20:00:00Z"), &p).unwrap();
    assert!(!v.allowed, "tie at same priority: deny wins (fail-safe)");
    assert_eq!(v.violated_priority, Some(1));
}

#[test]
fn no_match_defaults_deny() {
    let p = policy(vec![allow_read_orders()], Effect::Deny);
    let v = evaluate(&input("refund", json!({}), "2026-08-24T20:00:00Z"), &p).unwrap();
    assert!(!v.allowed);
    assert_eq!(v.violated_priority, None);
    assert!(v.reason.contains("default deny"));
}

// --- attribute derivation ---------------------------------------------------

#[test]
fn working_hours_boundary() {
    // Isolate the boundary with default Allow: the only rule denies writes OUTSIDE hours.
    // 2026-08-24 is a Monday.
    let p = policy(vec![deny_write_outside()], Effect::Allow);
    // 15:00Z = 09:00 local exactly → inside (start inclusive) → rule does NOT fire → allow.
    let at_open = evaluate(&input("update", json!({}), "2026-08-24T15:00:00Z"), &p).unwrap();
    assert!(at_open.allowed, "09:00 local is within hours");
    // 14:59Z = 08:59 local → outside → write denied.
    let before_open = evaluate(&input("update", json!({}), "2026-08-24T14:59:00Z"), &p).unwrap();
    assert!(!before_open.allowed, "08:59 local is outside hours");
    assert_eq!(before_open.violated_priority, Some(1));
}

#[test]
fn weekend_is_outside_hours() {
    // 2026-08-22 is a Saturday → outside working days regardless of hour → write denied.
    let p = policy(vec![deny_write_outside()], Effect::Deny);
    let v = evaluate(&input("insert", json!({}), "2026-08-22T15:00:00Z"), &p).unwrap();
    assert!(!v.allowed);
    assert_eq!(v.violated_priority, Some(1));
}

#[test]
fn bad_time_fails_safe_deny() {
    let p = policy(vec![allow_read_orders()], Effect::Allow);
    let v = evaluate(&input("read", json!({ "collection": "orders" }), "not-a-time"), &p).unwrap();
    assert!(!v.allowed, "unparseable time → fail-safe deny even with default allow");
}

// --- determinism + hashing --------------------------------------------------

#[test]
fn verdict_is_deterministic_100x() {
    let p = policy(vec![deny_write_outside(), allow_read_orders()], Effect::Deny);
    let inp = input("drop_table", json!({ "intent": "x" }), "2026-08-22T12:00:00Z");
    let first = serde_json::to_string(&evaluate(&inp, &p).unwrap()).unwrap();
    for _ in 0..100 {
        assert_eq!(serde_json::to_string(&evaluate(&inp, &p).unwrap()).unwrap(), first);
    }
}

#[test]
fn canonical_is_key_order_independent() {
    let a = json!({ "b": 2, "a": 1 });
    let b = json!({ "a": 1, "b": 2 });
    assert_eq!(canonical_string(&a), canonical_string(&b));
}

#[test]
fn hashes_present_and_shaped() {
    let p = policy(vec![allow_read_orders()], Effect::Deny);
    let v = evaluate(&input("read", json!({ "collection": "orders" }), "2026-08-24T20:00:00Z"), &p).unwrap();
    for h in [&v.request_hash, &v.policy_hash, &v.rules_source_hash] {
        assert!(h.starts_with("0x") && h.len() == 66);
    }
}
