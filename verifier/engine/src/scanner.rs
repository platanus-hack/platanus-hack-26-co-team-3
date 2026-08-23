//! Deterministic safety scanner over the RAW intent text.
//!
//! The LLM extracts operations, but the raw prompt is our ground truth for "what was
//! mentioned". This scanner cross-checks: if the text mentions a policy-relevant
//! collection or a dangerous verb that the LLM's operation list does NOT cover, we do not
//! trust the extraction → fail-safe. This catches "the LLM dropped a dangerous operation"
//! WITHOUT needing structured operations — using only the prompt.
//!
//! Honest limit: free text can be obfuscated; this is defense-in-depth (dictionary +
//! coverage + fail-closed), not a mathematical guarantee. The dictionaries are configurable
//! and expandable (multi-language, synonyms).

use crate::model::{CompiledPolicy, Condition, NormalizedRequest, OpClass};
use std::collections::BTreeSet;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ScanResult {
    pub passed: bool,
    pub reason: Option<String>,
}

impl ScanResult {
    fn ok() -> Self {
        ScanResult { passed: true, reason: None }
    }
    fn flag(reason: impl Into<String>) -> Self {
        ScanResult { passed: false, reason: Some(reason.into()) }
    }
}

/// Danger rank: higher = more dangerous. Used to compare "what the text implies" vs
/// "what the LLM reported".
fn severity(c: OpClass) -> u8 {
    match c {
        OpClass::Read => 0,
        OpClass::Refund | OpClass::Write => 1,
        OpClass::Admin | OpClass::Unknown => 2,
        OpClass::Destructive => 3,
    }
}

/// Verb keywords (multi-language) → the opClass they imply. Expandable.
const VERBS: &[(&str, OpClass)] = &[
    // destructive
    ("drop", OpClass::Destructive),
    ("truncate", OpClass::Destructive),
    ("delete_all", OpClass::Destructive),
    ("delete all", OpClass::Destructive),
    ("wipe", OpClass::Destructive),
    ("destroy", OpClass::Destructive),
    ("purge", OpClass::Destructive),
    ("borra", OpClass::Destructive),
    ("borrar", OpClass::Destructive),
    ("elimina", OpClass::Destructive),
    ("eliminar", OpClass::Destructive),
    ("aniquila", OpClass::Destructive),
    ("vaciar", OpClass::Destructive),
    ("vacia", OpClass::Destructive),
    // admin
    ("grant", OpClass::Admin),
    ("revoke", OpClass::Admin),
    ("otorga", OpClass::Admin),
    // refund
    ("refund", OpClass::Refund),
    ("reembolso", OpClass::Refund),
    // write
    ("insert", OpClass::Write),
    ("update", OpClass::Write),
    ("create", OpClass::Write),
    ("write", OpClass::Write),
    ("modify", OpClass::Write),
    ("registra", OpClass::Write),
    ("escribe", OpClass::Write),
    ("actualiza", OpClass::Write),
    ("agrega", OpClass::Write),
    // read
    ("read", OpClass::Read),
    ("find", OpClass::Read),
    ("query", OpClass::Read),
    ("select", OpClass::Read),
    ("consulta", OpClass::Read),
    ("leer", OpClass::Read),
    ("ver ", OpClass::Read),
];

/// Collection literals referenced anywhere in the compiled policy — the collections we
/// actually have rules about, so those are the ones we must not miss.
pub fn policy_collections(policy: &CompiledPolicy) -> Vec<String> {
    let mut set = BTreeSet::new();
    for r in &policy.rules {
        collect(&r.condition, &mut set);
    }
    set.into_iter().collect()
}

fn collect(c: &Condition, set: &mut BTreeSet<String>) {
    match c {
        Condition::CollectionEq { collection } => {
            set.insert(collection.to_lowercase());
        }
        Condition::And { all } | Condition::Or { any: all } => {
            for x in all {
                collect(x, set);
            }
        }
        Condition::Not { cond } => collect(cond, set),
        _ => {}
    }
}

/// Cross-check the raw intent text against the LLM's extracted operations.
pub fn scan(intent: &str, normalized: &NormalizedRequest, policy_collections: &[String]) -> ScanResult {
    let text = intent.to_lowercase();

    // 1. Severity coverage: the most dangerous verb in the text must be <= the most
    //    dangerous opClass the LLM reported. If the text screams "borra" but the LLM only
    //    reported reads, it under-reported → flag.
    let text_max = VERBS
        .iter()
        .filter(|(kw, _)| text.contains(kw))
        .map(|(_, c)| severity(*c))
        .max()
        .unwrap_or(0);
    let llm_max = normalized
        .operations
        .iter()
        .map(|o| severity(o.op_class))
        .max()
        .unwrap_or(0);
    if text_max > llm_max {
        return ScanResult::flag(format!(
            "intent text implies a more dangerous operation (severity {text_max}) than the extracted operations (severity {llm_max}); denied for safety"
        ));
    }

    // 2. Collection coverage: every policy-relevant collection mentioned in the text must
    //    appear in the extracted operations. A mentioned-but-missing collection means the
    //    LLM dropped an operation on something a rule cares about → flag.
    let llm_colls: BTreeSet<String> = normalized
        .operations
        .iter()
        .filter_map(|o| o.collection.as_ref().map(|c| c.to_lowercase()))
        .collect();
    for coll in policy_collections {
        if text.contains(coll.as_str()) && !llm_colls.contains(coll) {
            return ScanResult::flag(format!(
                "intent text mentions collection '{coll}' (which a rule governs) but it is not in the extracted operations; denied for safety"
            ));
        }
    }

    ScanResult::ok()
}
