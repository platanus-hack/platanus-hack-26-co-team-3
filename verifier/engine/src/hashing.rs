//! Canonical hashing — reproducibility anchors.
//!
//! Given the same CompiledPolicy + request, the verdict and these hashes are identical
//! on any machine. Canonical form = JCS-aligned subset (sorted ASCII keys, integer
//! numbers, minimal escaping); this reference implementation IS the definition.

use crate::model::{CompiledPolicy, EvalInput, Rule};
use serde_json::Value;
use sha2::{Digest, Sha256};

pub const ENGINE_VERSION: &str = "0.2.0";

/// Recursively serialize a Value into canonical form (keys sorted by UTF-8 bytes).
pub fn canonical_string(v: &Value) -> String {
    match v {
        Value::Null => "null".to_string(),
        Value::Bool(b) => b.to_string(),
        Value::Number(n) => n.to_string(),
        Value::String(s) => Value::String(s.clone()).to_string(),
        Value::Array(arr) => {
            let items: Vec<String> = arr.iter().map(canonical_string).collect();
            format!("[{}]", items.join(","))
        }
        Value::Object(map) => {
            let mut keys: Vec<&String> = map.keys().collect();
            keys.sort();
            let items: Vec<String> = keys
                .iter()
                .map(|k| {
                    let key = Value::String((*k).clone()).to_string();
                    let val = canonical_string(map.get(*k).expect("key exists"));
                    format!("{}:{}", key, val)
                })
                .collect();
            format!("{{{}}}", items.join(","))
        }
    }
}

pub fn sha256_hex(data: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(data.as_bytes());
    format!("0x{:x}", hasher.finalize())
}

/// Hash of the per-request payload: mcp id + request + time (not the rules).
pub fn request_hash(input: &EvalInput) -> anyhow::Result<String> {
    let v = serde_json::json!({
        "mcp_id": input.mcp.id,
        "accessedBy": input.request.accessed_by,
        "action": input.request.action,
        "payload": input.request.payload,
        "time": input.time,
    });
    Ok(sha256_hex(&canonical_string(&v)))
}

/// Hash of the frozen CompiledPolicy — the reproducibility anchor for the decision.
pub fn policy_hash(policy: &CompiledPolicy) -> anyhow::Result<String> {
    let v = serde_json::to_value(policy)?;
    Ok(sha256_hex(&canonical_string(&v)))
}

/// Hash of the raw NL rules — traces which source text produced the compiled policy.
pub fn rules_source_hash(rules: &[Rule]) -> anyhow::Result<String> {
    let v = serde_json::to_value(rules)?;
    Ok(sha256_hex(&canonical_string(&v)))
}

/// Hash of the LLM-normalized request — the deterministic decision is reproducible
/// against this frozen structured form.
pub fn normalized_request_hash(norm: &crate::model::NormalizedRequest) -> anyhow::Result<String> {
    let v = serde_json::to_value(norm)?;
    Ok(sha256_hex(&canonical_string(&v)))
}
