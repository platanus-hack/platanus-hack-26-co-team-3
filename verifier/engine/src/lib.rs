//! Aegis Gate — deterministic MCP access-policy evaluator.
//!
//! The decision is a pure function over a frozen, hashed CompiledPolicy. Natural-language
//! rules are compiled to the DSL out of band (R3); the decision path never sees text.
//! Z3 (R2) is the decision kernel + the policy prover.

pub mod attributes;
pub mod compiler;
pub mod dsl;
pub mod engine;
pub mod hashing;
pub mod llm;
pub mod model;
pub mod normalizer;
pub mod scanner;
pub mod service;
pub mod z3enc;

pub use engine::evaluate;

/// Default action classifier and a sane working-hours default, used by tests and by the
/// compiler as a starting point. Part of the policy (hashed) once attached.
pub mod defaults {
    use crate::model::{ActionClassMap, OpClass, WorkingHours};

    pub fn action_classes() -> ActionClassMap {
        // Order matters: destructive keywords before generic write keywords.
        let kw = |s: &str, c: OpClass| (s.to_string(), c);
        ActionClassMap {
            keywords: vec![
                kw("drop", OpClass::Destructive),
                kw("truncate", OpClass::Destructive),
                kw("delete_all", OpClass::Destructive),
                kw("wipe", OpClass::Destructive),
                kw("purge", OpClass::Destructive),
                kw("refund", OpClass::Refund),
                kw("grant", OpClass::Admin),
                kw("revoke", OpClass::Admin),
                kw("insert", OpClass::Write),
                kw("update", OpClass::Write),
                kw("delete", OpClass::Write),
                kw("upsert", OpClass::Write),
                kw("create", OpClass::Write),
                kw("write", OpClass::Write),
                kw("modify", OpClass::Write),
                kw("read", OpClass::Read),
                kw("find", OpClass::Read),
                kw("get", OpClass::Read),
                kw("list", OpClass::Read),
                kw("query", OpClass::Read),
                kw("count", OpClass::Read),
                kw("aggregate", OpClass::Read),
            ],
        }
    }

    /// Mon–Fri, 09:00–18:00, Mexico City (UTC-6).
    pub fn working_hours() -> WorkingHours {
        WorkingHours {
            tz_offset_minutes: -360,
            start_minute: 9 * 60,
            end_minute: 18 * 60,
            days: vec![1, 2, 3, 4, 5],
        }
    }
}
