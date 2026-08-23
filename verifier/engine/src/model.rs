//! Data model for the MCP access-policy evaluator.
//!
//! Two worlds:
//!   - INPUT (from Roxy): `EvalInput` = the MCP with natural-language rules + the request.
//!   - COMPILED (frozen, hashed): `CompiledPolicy` = formal DSL rules + config. The LLM
//!     compiler (R3) turns NL rules into this; the deterministic evaluator + Z3 decide on it.
//!
//! The decision path never sees natural language — only the compiled DSL.

use serde::{Deserialize, Serialize};

// ---------------------------------------------------------------------------
// INPUT — exactly the JSON Roxy sends
// ---------------------------------------------------------------------------

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct EvalInput {
    pub mcp: Mcp,
    pub request: McpRequest,
    /// UTC RFC3339 timestamp of the attempt.
    pub time: String,
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct Mcp {
    pub id: String,
    pub name: String,
    pub description: String,
    pub rules: Vec<Rule>,
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct Rule {
    pub priority: i64,
    pub instruction: String,
}

/// A single operation the request performs.
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq, Eq)]
pub struct Operation {
    #[serde(rename = "opClass")]
    pub op_class: OpClass,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub collection: Option<String>,
}

/// ALL operations inferred from a raw request by the LLM normalizer. A request can do
/// several things at once (e.g. write orders AND read secrets); every one is evaluated
/// (deny-if-any). Non-deterministic to produce, but frozen + hashed; the decision is
/// deterministic on it.
#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct NormalizedRequest {
    pub operations: Vec<Operation>,
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct McpRequest {
    #[serde(rename = "accessedBy")]
    pub accessed_by: String,
    /// Free-text operation: read, drop_table, refund, …
    pub action: String,
    /// Agent-supplied JSON (intent, collection, units, …).
    pub payload: serde_json::Value,
}

// ---------------------------------------------------------------------------
// COMPILED POLICY — the frozen, hashed artifact the evaluator decides on
// ---------------------------------------------------------------------------

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct CompiledPolicy {
    /// Formal rules. Priority ordering is applied at evaluation, not storage.
    pub rules: Vec<CompiledRule>,
    /// Deterministic action → opClass classification (keyword-based).
    pub action_classes: ActionClassMap,
    pub working_hours: WorkingHours,
    /// Verdict when no rule matches. Fail-safe default: Deny.
    pub default_effect: Effect,
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct CompiledRule {
    pub priority: i64,
    pub effect: Effect,
    pub condition: Condition,
}

#[derive(Serialize, Deserialize, Clone, Copy, Debug, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum Effect {
    Allow,
    Deny,
}

/// Operation risk class derived from the raw action string.
#[derive(Serialize, Deserialize, Clone, Copy, Debug, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum OpClass {
    Read,
    Write,
    Destructive,
    Refund,
    Admin,
    Unknown,
}

/// Keyword-based action classifier. Longest/most-specific match wins; unmatched → Unknown.
/// Part of the policy, so it is covered by `policy_hash`.
#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct ActionClassMap {
    /// (substring keyword, class). Checked in order; first hit classifies the action.
    pub keywords: Vec<(String, OpClass)>,
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct WorkingHours {
    /// Timezone offset from UTC in minutes (e.g. Mexico City = -360).
    pub tz_offset_minutes: i32,
    /// Minutes from local midnight, inclusive start.
    pub start_minute: u32,
    /// Minutes from local midnight, exclusive end.
    pub end_minute: u32,
    /// Working days, Mon=1 … Sun=7.
    pub days: Vec<u8>,
}

// ---------------------------------------------------------------------------
// DSL — the condition language (formal, deterministic, Z3-encodable)
// ---------------------------------------------------------------------------

/// A boolean condition over a request's extracted attributes.
#[derive(Serialize, Deserialize, Clone, Debug)]
#[serde(tag = "op", rename_all = "snake_case")]
pub enum Condition {
    Always,
    Never,
    /// opClass ∈ set.
    OpClassIn { classes: Vec<OpClass> },
    /// raw action equals (case-insensitive).
    ActionEq { action: String },
    /// payload.collection equals.
    CollectionEq { collection: String },
    /// accessedBy matches a simple glob (`*` wildcard).
    AccessedByGlob { pattern: String },
    WithinWorkingHours,
    OutsideWorkingHours,
    And { all: Vec<Condition> },
    Or { any: Vec<Condition> },
    Not { cond: Box<Condition> },
}

// ---------------------------------------------------------------------------
// OUTPUT — the contract Roxy consumes (+ reproducibility extras)
// ---------------------------------------------------------------------------

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct Verdict {
    pub allowed: bool,
    /// Priority of the deny rule that governed, or null (allow / default / unmapped).
    #[serde(rename = "violatedPriority")]
    pub violated_priority: Option<i64>,
    pub reason: String,

    // --- reproducibility extras (Roxy ignores these) ---
    /// sha256 of the canonical request (mcp.id, request, time).
    pub request_hash: String,
    /// sha256 of the canonical CompiledPolicy.
    pub policy_hash: String,
    /// sha256 of the raw NL rules (traces which text produced the compiled policy).
    pub rules_source_hash: String,
    pub engine_version: String,
}
