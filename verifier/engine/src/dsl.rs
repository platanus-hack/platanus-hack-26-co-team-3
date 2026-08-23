//! Deterministic evaluation of the DSL against a request's attributes.
//!
//! This is the reference/oracle evaluator. R2 encodes the SAME semantics in Z3 and
//! cross-checks (Z3 decision must agree with this on every request), then uses Z3 for
//! the proofs a concrete evaluator cannot do (over ALL possible requests).

use crate::attributes::Attributes;
use crate::model::Condition;

pub fn eval(cond: &Condition, attr: &Attributes) -> bool {
    match cond {
        Condition::Always => true,
        Condition::Never => false,
        Condition::OpClassIn { classes } => classes.contains(&attr.op_class),
        Condition::ActionEq { action } => attr.action == action.to_lowercase(),
        Condition::CollectionEq { collection } => attr.collection.as_deref() == Some(collection),
        Condition::AccessedByGlob { pattern } => glob_match(pattern, &attr.accessed_by),
        Condition::WithinWorkingHours => attr.within_working_hours,
        Condition::OutsideWorkingHours => !attr.within_working_hours,
        Condition::And { all } => all.iter().all(|c| eval(c, attr)),
        Condition::Or { any } => any.iter().any(|c| eval(c, attr)),
        Condition::Not { cond } => !eval(cond, attr),
    }
}

/// Minimal glob: `*` matches any run (including empty). Supports multiple wildcards,
/// e.g. "external-*", "*-readonly", "svc-*-prod".
fn glob_match(pattern: &str, s: &str) -> bool {
    let parts: Vec<&str> = pattern.split('*').collect();
    if parts.len() == 1 {
        return pattern == s; // no wildcard → exact
    }
    let mut pos = 0usize;
    // First segment must be a prefix.
    let first = parts[0];
    if !s[pos..].starts_with(first) {
        return false;
    }
    pos += first.len();
    // Middle segments must appear in order.
    for seg in &parts[1..parts.len() - 1] {
        if seg.is_empty() {
            continue;
        }
        match s[pos..].find(seg) {
            Some(i) => pos += i + seg.len(),
            None => return false,
        }
    }
    // Last segment must be a suffix of the remainder.
    let last = parts[parts.len() - 1];
    s[pos..].len() >= last.len() && s.ends_with(last) && s.len() - last.len() >= pos
}
