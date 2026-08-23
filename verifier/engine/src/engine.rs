//! Deterministic evaluator: `evaluate(input, policy) -> Verdict`.
//!
//! Governing rule = matching rule with the SMALLEST priority (Deny wins ties). No match
//! → policy default (Deny). Bad input → fail-safe Deny. Reproducible: same (input, policy)
//! → same verdict/hashes. Z3 mirrors this and adds the policy-level proofs.

use crate::attributes::{self, Attributes};
use crate::dsl;
use crate::hashing::{policy_hash, request_hash, rules_source_hash, ENGINE_VERSION};
use crate::model::{CompiledPolicy, Effect, EvalInput, OpClass, Verdict};

/// Richer result for the service layer: verdict + which rule governed + the attributes.
pub struct EvalDetail {
    pub verdict: Verdict,
    /// Index into `policy.rules` of the governing rule (None → default / bad input).
    pub governing_index: Option<usize>,
    /// None when attribute extraction failed (fail-safe deny).
    pub attributes: Option<Attributes>,
}

/// Index of the governing rule for these attributes (smallest priority; Deny wins ties).
pub fn govern(policy: &CompiledPolicy, attrs: &Attributes) -> Option<usize> {
    let mut best: Option<usize> = None;
    for (i, rule) in policy.rules.iter().enumerate() {
        if !dsl::eval(&rule.condition, attrs) {
            continue;
        }
        best = Some(match best {
            None => i,
            Some(g) => {
                let gp = policy.rules[g].priority;
                if rule.priority < gp {
                    i
                } else if rule.priority == gp && rule.effect == Effect::Deny {
                    i
                } else {
                    g
                }
            }
        });
    }
    best
}

pub fn evaluate(input: &EvalInput, policy: &CompiledPolicy) -> anyhow::Result<Verdict> {
    Ok(evaluate_full(input, policy)?.verdict)
}

pub fn evaluate_full(input: &EvalInput, policy: &CompiledPolicy) -> anyhow::Result<EvalDetail> {
    let request_hash = request_hash(input)?;
    let policy_hash = policy_hash(policy)?;
    let rules_source_hash = rules_source_hash(&input.mcp.rules)?;

    let mk = |allowed: bool, violated: Option<i64>, reason: String| Verdict {
        allowed,
        violated_priority: violated,
        reason,
        request_hash: request_hash.clone(),
        policy_hash: policy_hash.clone(),
        rules_source_hash: rules_source_hash.clone(),
        engine_version: ENGINE_VERSION.to_string(),
    };

    let attrs = match attributes::extract(&input.request, &input.time, policy) {
        Ok(a) => a,
        Err(e) => {
            return Ok(EvalDetail {
                verdict: mk(false, None, format!("input error, denied for safety: {e}")),
                governing_index: None,
                attributes: None,
            });
        }
    };
    Ok(decide(policy, attrs, mk))
}

/// Evaluate a LIST of operations with DENY-IF-ANY: if any single operation is denied,
/// the whole request is denied (naming that operation). Used by the LLM-normalized path.
pub fn evaluate_operations(
    input: &EvalInput,
    policy: &CompiledPolicy,
    ops: &[Attributes],
) -> anyhow::Result<EvalDetail> {
    let request_hash = request_hash(input)?;
    let policy_hash = policy_hash(policy)?;
    let rules_source_hash = rules_source_hash(&input.mcp.rules)?;
    let mk = |allowed: bool, violated: Option<i64>, reason: String| Verdict {
        allowed,
        violated_priority: violated,
        reason,
        request_hash: request_hash.clone(),
        policy_hash: policy_hash.clone(),
        rules_source_hash: rules_source_hash.clone(),
        engine_version: ENGINE_VERSION.to_string(),
    };

    if ops.is_empty() {
        return Ok(EvalDetail {
            verdict: mk(false, None, "no operations to evaluate; denied for safety".into()),
            governing_index: None,
            attributes: None,
        });
    }

    for (idx, attrs) in ops.iter().enumerate() {
        let gi = govern(policy, attrs);
        let denied = match gi {
            Some(i) => policy.rules[i].effect == Effect::Deny,
            None => policy.default_effect == Effect::Deny,
        };
        if denied {
            let reason = match gi {
                Some(i) => format!(
                    "operation {} ({}) is denied by rule priority {}",
                    idx + 1,
                    op_desc(attrs),
                    policy.rules[i].priority
                ),
                None => format!("operation {} ({}) matched no rule; default deny", idx + 1, op_desc(attrs)),
            };
            return Ok(EvalDetail {
                verdict: mk(false, gi.map(|i| policy.rules[i].priority), reason),
                governing_index: gi,
                attributes: Some(attrs.clone()),
            });
        }
    }

    Ok(EvalDetail {
        verdict: mk(true, None, format!("all {} operation(s) allowed", ops.len())),
        governing_index: None,
        attributes: ops.first().cloned(),
    })
}

fn op_desc(attrs: &Attributes) -> String {
    match &attrs.collection {
        Some(c) => format!("{} on '{}'", op_class_human(attrs.op_class), c),
        None => op_class_human(attrs.op_class).to_string(),
    }
}

fn decide(
    policy: &CompiledPolicy,
    attrs: Attributes,
    mk: impl Fn(bool, Option<i64>, String) -> Verdict,
) -> EvalDetail {
    let gi = govern(policy, &attrs);
    let verdict = match gi {
        Some(i) if policy.rules[i].effect == Effect::Deny => {
            mk(false, Some(policy.rules[i].priority), deny_reason(&attrs, policy.rules[i].priority))
        }
        Some(i) => mk(true, None, format!("allowed by rule priority {}", policy.rules[i].priority)),
        None => match policy.default_effect {
            Effect::Deny => mk(false, None, "no rule matched; default deny".to_string()),
            Effect::Allow => mk(true, None, "no rule matched; default allow".to_string()),
        },
    };
    EvalDetail { verdict, governing_index: gi, attributes: Some(attrs) }
}

fn deny_reason(attrs: &Attributes, priority: i64) -> String {
    let coll = attrs
        .collection
        .as_deref()
        .map(|c| format!(" on '{c}'"))
        .unwrap_or_default();
    format!(
        "request classified as {}{} is denied by rule priority {}",
        op_class_human(attrs.op_class),
        coll,
        priority
    )
}

fn op_class_human(c: OpClass) -> &'static str {
    match c {
        OpClass::Read => "read",
        OpClass::Write => "write",
        OpClass::Destructive => "write/destructive",
        OpClass::Refund => "refund",
        OpClass::Admin => "admin",
        OpClass::Unknown => "unclassified",
    }
}
