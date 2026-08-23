//! R2 acceptance tests: Z3 as decision kernel + policy prover.

use aegis_gate_engine::attributes;
use aegis_gate_engine::defaults;
use aegis_gate_engine::evaluate;
use aegis_gate_engine::model::*;
use aegis_gate_engine::z3enc::{Enc, Proof};
use serde_json::json;

fn base_policy(rules: Vec<CompiledRule>, default_effect: Effect) -> CompiledPolicy {
    CompiledPolicy {
        rules,
        action_classes: defaults::action_classes(),
        working_hours: defaults::working_hours(),
        default_effect,
    }
}

fn rule(priority: i64, effect: Effect, condition: Condition) -> CompiledRule {
    CompiledRule { priority, effect, condition }
}

fn writeish() -> Condition {
    Condition::OpClassIn { classes: vec![OpClass::Write, OpClass::Destructive, OpClass::Refund] }
}

// --- PITCH 1: destructive bypass -------------------------------------------

#[test]
fn detects_destructive_bypass() {
    // "deny drop_table" + "allow all writes on orders". truncate is destructive but not
    // named → slips into the allow. Z3 must find it.
    let p = base_policy(
        vec![
            rule(1, Effect::Deny, Condition::ActionEq { action: "drop_table".into() }),
            rule(2, Effect::Allow, Condition::And {
                all: vec![writeish(), Condition::CollectionEq { collection: "orders".into() }],
            }),
        ],
        Effect::Deny,
    );
    match Enc::new(&p).prove_no_destructive_bypass() {
        Proof::Counterexample(m) => {
            assert!(m.allowed);
            assert_eq!(m.op_class, OpClass::Destructive);
            // The named drop_table is NOT the hole; the hole is some other destructive action.
            assert_ne!(m.action_hint.as_deref(), Some("drop_table"));
        }
        Proof::Holds => panic!("Z3 missed the truncate-style bypass"),
    }
}

#[test]
fn safe_policy_proves_no_bypass() {
    // Deny ALL destructive ops outright → provably no bypass.
    let p = base_policy(
        vec![rule(1, Effect::Deny, Condition::OpClassIn { classes: vec![OpClass::Destructive] })],
        Effect::Deny,
    );
    assert_eq!(Enc::new(&p).prove_no_destructive_bypass(), Proof::Holds);
}

// --- PITCH 2: same-priority contradiction ----------------------------------

#[test]
fn detects_same_priority_conflict() {
    let p = base_policy(
        vec![
            rule(1, Effect::Allow, Condition::CollectionEq { collection: "orders".into() }),
            rule(1, Effect::Deny, Condition::CollectionEq { collection: "orders".into() }),
        ],
        Effect::Deny,
    );
    let conflicts = Enc::new(&p).find_conflicts();
    assert!(!conflicts.is_empty(), "should flag the contradiction at priority 1");
    assert_eq!(conflicts[0].0, 1);
}

#[test]
fn no_conflict_when_conditions_disjoint() {
    // Same priority, opposite effect, but conditions can't both hold (read vs write).
    let p = base_policy(
        vec![
            rule(1, Effect::Allow, Condition::OpClassIn { classes: vec![OpClass::Read] }),
            rule(1, Effect::Deny, Condition::OpClassIn { classes: vec![OpClass::Write] }),
        ],
        Effect::Deny,
    );
    assert!(Enc::new(&p).find_conflicts().is_empty());
}

// --- PITCH 3: dead rule -----------------------------------------------------

#[test]
fn detects_dead_rule() {
    // Rule 1 denies ALL writes; rule 2 tries to allow writes → can never govern.
    let p = base_policy(
        vec![
            rule(1, Effect::Deny, writeish()),
            rule(2, Effect::Allow, writeish()),
        ],
        Effect::Deny,
    );
    let dead = Enc::new(&p).find_dead_rules();
    assert!(dead.contains(&1), "rule at index 1 (priority 2 allow) is shadowed → dead");
    assert!(!dead.contains(&0), "rule 0 governs writes");
}

// --- Z3 as decision kernel: agrees with the deterministic evaluator ---------

#[test]
fn z3_decision_matches_deterministic() {
    let p = base_policy(
        vec![
            rule(1, Effect::Deny, Condition::And { all: vec![writeish(), Condition::OutsideWorkingHours] }),
            rule(2, Effect::Allow, Condition::And {
                all: vec![Condition::OpClassIn { classes: vec![OpClass::Read] },
                          Condition::CollectionEq { collection: "orders".into() }],
            }),
        ],
        Effect::Deny,
    );
    let enc = Enc::new(&p);

    let cases = [
        ("drop_table", json!({}), "2026-08-22T12:00:00Z"),  // sat outside hours → deny
        ("read", json!({ "collection": "orders" }), "2026-08-24T20:00:00Z"), // allow
        ("read", json!({ "collection": "users" }), "2026-08-24T20:00:00Z"),  // default deny
        ("update", json!({}), "2026-08-24T20:00:00Z"),      // write within hours → default deny
        ("refund", json!({}), "2026-08-22T12:00:00Z"),      // refund outside hours → deny
    ];

    for (action, payload, time) in cases {
        let input = EvalInput {
            mcp: Mcp { id: "m".into(), name: "".into(), description: "".into(),
                       rules: vec![Rule { priority: 1, instruction: "s".into() }] },
            request: McpRequest { accessed_by: "agent-07".into(), action: action.into(), payload },
            time: time.into(),
        };
        let attrs = attributes::extract(&input.request, &input.time, &p).unwrap();
        let z3_allowed = enc.decide(&attrs);
        let det_allowed = evaluate(&input, &p).unwrap().allowed;
        assert_eq!(z3_allowed, det_allowed, "Z3 and deterministic disagree on {action}@{time}");
    }
}
