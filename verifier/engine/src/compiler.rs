//! Rule compiler — natural language → formal DSL. OUTSIDE the decision boundary.
//!
//! This is the ONLY non-deterministic step. An LLM translates each `instruction` into a
//! `CompiledRule`. The output crosses a strict trust boundary: `parse_compiled_rules`
//! validates it against the DSL schema (serde's tagged enum rejects unknown ops) plus a
//! depth bound. Anything invalid → error → the caller fail-safe denies.
//!
//! The compiled artifact is frozen and hashed (`policy_hash`); the deterministic evaluator
//! and Z3 decide only on it, so decisions stay reproducible even though compilation isn't.

use crate::defaults;
use crate::hashing::rules_source_hash;
use crate::model::{CompiledPolicy, CompiledRule, Condition, Effect, Mcp, Rule};
use std::collections::HashMap;
use std::sync::Mutex;

const MAX_CONDITION_DEPTH: usize = 8;

pub trait RuleCompiler: Send + Sync {
    /// Compile raw NL rules into formal DSL rules (same count, priorities preserved).
    fn compile(&self, rules: &[Rule]) -> anyhow::Result<Vec<CompiledRule>>;
}

impl RuleCompiler for Box<dyn RuleCompiler> {
    fn compile(&self, rules: &[Rule]) -> anyhow::Result<Vec<CompiledRule>> {
        (**self).compile(rules)
    }
}

/// Validate + parse an LLM's JSON output into CompiledRules. THE trust boundary.
pub fn parse_compiled_rules(json: &str) -> anyhow::Result<Vec<CompiledRule>> {
    let rules: Vec<CompiledRule> = serde_json::from_str(json)
        .map_err(|e| anyhow::anyhow!("compiled rules do not match the DSL schema: {e}"))?;
    for r in &rules {
        check_depth(&r.condition, 0)?;
    }
    Ok(rules)
}

fn check_depth(c: &Condition, depth: usize) -> anyhow::Result<()> {
    if depth > MAX_CONDITION_DEPTH {
        anyhow::bail!("condition nesting exceeds max depth {MAX_CONDITION_DEPTH}");
    }
    match c {
        Condition::And { all } | Condition::Or { any: all } => {
            for x in all {
                check_depth(x, depth + 1)?;
            }
        }
        Condition::Not { cond } => check_depth(cond, depth + 1)?,
        _ => {}
    }
    Ok(())
}

/// Assemble a full CompiledPolicy from compiled rules + deterministic config defaults.
pub fn assemble_policy(rules: Vec<CompiledRule>) -> CompiledPolicy {
    CompiledPolicy {
        rules,
        action_classes: defaults::action_classes(),
        working_hours: defaults::working_hours(),
        // Default ALLOW: a request no rule speaks to is permitted. (Compile/normalize
        // FAILURES still fail-safe deny in the service — that's "couldn't understand",
        // not "no rule matched".)
        default_effect: Effect::Allow,
    }
}

/// Caches compiled policies by `rules_source_hash`, so the same NL rules compile once.
pub struct CachingCompiler<C: RuleCompiler> {
    inner: C,
    cache: Mutex<HashMap<String, CompiledPolicy>>,
}

impl<C: RuleCompiler> CachingCompiler<C> {
    pub fn new(inner: C) -> Self {
        Self { inner, cache: Mutex::new(HashMap::new()) }
    }

    /// Returns (policy, cache_hit). On compile failure, the error propagates and the
    /// caller must fail-safe deny.
    pub fn compile_policy(&self, mcp: &Mcp) -> anyhow::Result<(CompiledPolicy, bool)> {
        let key = rules_source_hash(&mcp.rules)?;
        if let Some(p) = self.cache.lock().unwrap().get(&key) {
            return Ok((p.clone(), true));
        }
        let rules = self.inner.compile(&mcp.rules)?;
        let policy = assemble_policy(rules);
        self.cache.lock().unwrap().insert(key, policy.clone());
        Ok((policy, false))
    }
}

// ---------------------------------------------------------------------------
// LLM compiler (UsePod / OpenAI-compatible)
// ---------------------------------------------------------------------------

pub struct LlmCompiler {
    client: crate::llm::LlmClient,
}

impl LlmCompiler {
    pub fn from_env() -> anyhow::Result<Self> {
        Ok(Self { client: crate::llm::LlmClient::from_env()? })
    }
}

/// Only the effect + condition — the priority is set by US from the input rule, so the
/// LLM cannot renumber or drop rules.
#[derive(serde::Deserialize)]
struct CompiledBody {
    effect: Effect,
    condition: Condition,
}

/// Max concurrent LLM calls when compiling rules (keeps under provider rate limits).
const COMPILE_CONCURRENCY: usize = 6;

impl LlmCompiler {
    fn compile_one(&self, r: &Rule) -> anyhow::Result<CompiledRule> {
        let user = serde_json::json!({ "instruction": r.instruction }).to_string();
        let content = self.client.chat(SINGLE_RULE_PROMPT, &user)?;
        let body: CompiledBody = serde_json::from_str(&crate::llm::extract_json_object(&content))
            .map_err(|e| anyhow::anyhow!("rule (priority {}) did not compile to valid DSL: {e}", r.priority))?;
        check_depth(&body.condition, 0)?;
        Ok(CompiledRule { priority: r.priority, effect: body.effect, condition: body.condition })
    }
}

impl RuleCompiler for LlmCompiler {
    fn compile(&self, rules: &[Rule]) -> anyhow::Result<Vec<CompiledRule>> {
        // ONE LLM call per rule — the iteration is OUR deterministic code, so the LLM
        // cannot skip/merge/renumber rules. Calls run in PARALLEL (bounded), since Claude
        // handles concurrency; order is preserved. Any single failure fails the whole
        // compile (fail-safe): you never run with a partial policy.
        let mut out: Vec<CompiledRule> = Vec::with_capacity(rules.len());
        for chunk in rules.chunks(COMPILE_CONCURRENCY) {
            let chunk_results: Vec<anyhow::Result<CompiledRule>> = std::thread::scope(|s| {
                let handles: Vec<_> = chunk.iter().map(|r| s.spawn(|| self.compile_one(r))).collect();
                handles.into_iter().map(|h| h.join().expect("compile thread panicked")).collect()
            });
            for res in chunk_results {
                out.push(res?);
            }
        }
        anyhow::ensure!(out.len() == rules.len(), "rule count mismatch after compilation");
        Ok(out)
    }
}

const SINGLE_RULE_PROMPT: &str = r#"You compile ONE natural-language MCP access rule into a strict JSON DSL object.
Input JSON: { "instruction": string }.
Output ONLY this JSON object (no prose, no markdown, no array):
  { "effect": "allow"|"deny", "condition": <Condition> }

Condition grammar (use EXACTLY these shapes):
  {"op":"always"}
  {"op":"never"}
  {"op":"op_class_in","classes":[<class>...]}   class ∈ read|write|destructive|refund|admin|unknown
  {"op":"action_eq","action":"<string>"}
  {"op":"collection_eq","collection":"<string>"}
  {"op":"accessed_by_glob","pattern":"<glob with * >"}
  {"op":"within_working_hours"}
  {"op":"outside_working_hours"}
  {"op":"and","all":[<Condition>...]}
  {"op":"or","any":[<Condition>...]}
  {"op":"not","cond":<Condition>}

Mapping guidance:
  - "write operation" / "writes" → op_class_in ["write","destructive","refund"]
  - "read" / "read-only" / "queries" → op_class_in ["read"]
  - destructive verbs (drop, truncate, delete_all, wipe, borrar, aniquilar) → op_class_in ["destructive"]
  - "on the 'X' collection" → collection_eq "X"
  - "outside/after working hours" → outside_working_hours; "during working hours" → within_working_hours
  - "external agents" / agent-id patterns → accessed_by_glob

CRITICAL — classify by BEHAVIOUR, not by literal wording. When the instruction names an
operation VERB (drop, truncate, delete, wipe, destroy, insert, update, create, write,
read, query, select, refund, grant, revoke, and their translations), you MUST compile it
to op_class_in with the matching class(es) — NEVER to action_eq. action_eq is ONLY for an
opaque, non-semantic identifier the caller defined (e.g. action_eq "svc_job_42"); it must
never carry a verb. Example: "deny drop table" → {"effect":"deny","condition":{"op":
"op_class_in","classes":["destructive"]}}. Compiling such a rule to action_eq is WRONG and
lets the operation bypass the gate.
If the rule targets a specific collection too, AND it with collection_eq; otherwise leave
the op_class_in unqualified so every collection is covered.
Prefer op_class_in over naming a single action, so gaps (e.g. truncate vs drop) are covered.
Output the JSON object and nothing else."#;

// ---------------------------------------------------------------------------
// Mock compiler (deterministic, for tests)
// ---------------------------------------------------------------------------

/// A deterministic stand-in used in tests: maps a few known instructions to DSL.
pub struct MockCompiler;

impl RuleCompiler for MockCompiler {
    fn compile(&self, rules: &[Rule]) -> anyhow::Result<Vec<CompiledRule>> {
        rules
            .iter()
            .map(|r| {
                let i = r.instruction.to_lowercase();
                let condition = if i.contains("write") && i.contains("working hours") {
                    Condition::And {
                        all: vec![
                            Condition::OpClassIn {
                                classes: vec![
                                    crate::model::OpClass::Write,
                                    crate::model::OpClass::Destructive,
                                    crate::model::OpClass::Refund,
                                ],
                            },
                            Condition::OutsideWorkingHours,
                        ],
                    }
                } else if i.contains("read") && i.contains("orders") {
                    Condition::And {
                        all: vec![
                            Condition::OpClassIn { classes: vec![crate::model::OpClass::Read] },
                            Condition::CollectionEq { collection: "orders".into() },
                        ],
                    }
                } else {
                    anyhow::bail!("mock compiler cannot compile: {}", r.instruction);
                };
                let effect = if i.starts_with("deny") { Effect::Deny } else { Effect::Allow };
                Ok(CompiledRule { priority: r.priority, effect, condition })
            })
            .collect()
    }
}
