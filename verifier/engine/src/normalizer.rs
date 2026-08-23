//! Request normalizer — natural language → structured attributes. OUTSIDE the boundary.
//!
//! The agent's free-text `intent` (and `action`/`payload`) are understood by the LLM,
//! which infers `opClass` + `collection`. That NormalizedRequest is frozen + hashed; the
//! deterministic evaluator and Z3 then decide on it. Fail-safe: if normalization fails or
//! is invalid, the caller denies. Cached by hash(action + payload).

use crate::hashing::{canonical_string, sha256_hex};
use crate::llm::{extract_json_object, LlmClient};
use crate::model::{Mcp, McpRequest, NormalizedRequest, Operation, OpClass};
use std::collections::HashMap;
use std::sync::Mutex;

pub trait RequestNormalizer: Send + Sync {
    fn normalize(&self, req: &McpRequest, mcp: &Mcp) -> anyhow::Result<NormalizedRequest>;
}

impl RequestNormalizer for Box<dyn RequestNormalizer> {
    fn normalize(&self, req: &McpRequest, mcp: &Mcp) -> anyhow::Result<NormalizedRequest> {
        (**self).normalize(req, mcp)
    }
}

/// Validate + parse the LLM's normalization JSON (serde enforces opClass is a valid class).
/// Rejects an empty operation list (fail-safe: "couldn't identify any operation" → deny).
pub fn parse_normalized(json: &str) -> anyhow::Result<NormalizedRequest> {
    let n: NormalizedRequest = serde_json::from_str(json)
        .map_err(|e| anyhow::anyhow!("normalized request does not match schema: {e}"))?;
    anyhow::ensure!(!n.operations.is_empty(), "no operations identified in the request");
    Ok(n)
}

fn cache_key(req: &McpRequest) -> String {
    let v = serde_json::json!({ "action": req.action, "payload": req.payload });
    sha256_hex(&canonical_string(&v))
}

pub struct CachingNormalizer<N: RequestNormalizer> {
    inner: N,
    cache: Mutex<HashMap<String, NormalizedRequest>>,
}

impl<N: RequestNormalizer> CachingNormalizer<N> {
    pub fn new(inner: N) -> Self {
        Self { inner, cache: Mutex::new(HashMap::new()) }
    }

    /// Returns (normalized, cache_hit).
    pub fn normalize(&self, req: &McpRequest, mcp: &Mcp) -> anyhow::Result<(NormalizedRequest, bool)> {
        let key = cache_key(req);
        if let Some(n) = self.cache.lock().unwrap().get(&key) {
            return Ok((n.clone(), true));
        }
        let n = self.inner.normalize(req, mcp)?;
        self.cache.lock().unwrap().insert(key, n.clone());
        Ok((n, false))
    }
}

// ---------------------------------------------------------------------------
// LLM normalizer (UsePod)
// ---------------------------------------------------------------------------

pub struct LlmNormalizer {
    client: LlmClient,
}

impl LlmNormalizer {
    pub fn from_env() -> anyhow::Result<Self> {
        Ok(Self { client: LlmClient::from_env()? })
    }
}

impl RequestNormalizer for LlmNormalizer {
    fn normalize(&self, req: &McpRequest, mcp: &Mcp) -> anyhow::Result<NormalizedRequest> {
        // NOTE: `action` is the caller's internal record id — NOT a semantic signal.
        // We infer purely from the payload/intent, so it is deliberately omitted here.
        let user = serde_json::json!({
            "payload": req.payload,
            "mcpName": mcp.name,
            "mcpDescription": mcp.description,
        })
        .to_string();
        let content = self.client.chat(NORM_PROMPT, &user)?;
        parse_normalized(&extract_json_object(&content))
    }
}

const NORM_PROMPT: &str = r#"You extract EVERY operation an MCP access request performs.
Input JSON: { payload, mcpName, mcpDescription }. The payload contains an `intent` in
natural language (any language) describing what the agent wants to do.
Output ONLY a JSON object (no prose, no markdown):
  { "operations": [ { "opClass": <class>, "collection": <string|null> }, ... ] }
where class ∈ read | write | destructive | refund | admin | unknown.

CRITICAL: a request may do SEVERAL things at once (e.g. "write orders AND read secrets").
List EVERY distinct operation — one entry per operation. Be exhaustive; NEVER drop or
merge an operation, even if it looks secondary or is buried in the text. When in doubt,
include it.

opClass per operation (judge by what it actually does):
    reads/queries/lookups/consultar/ver/leer → "read"
    inserts/updates/creates/escribir/registrar → "write"
    drop/truncate/delete-all/wipe/borrar/eliminar/aniquilar/vaciar → "destructive"
    refunds/reembolsos → "refund"; grant/revoke permissions → "admin"
    if genuinely unclear → "unknown"
collection: the target collection/table for that operation (e.g. "borra orders" → "orders",
"consulta secrets" → "secrets"). If none, use null.
Output the JSON object and nothing else."#;

// ---------------------------------------------------------------------------
// Mock normalizer (deterministic, for tests)
// ---------------------------------------------------------------------------

pub struct MockNormalizer;

impl RequestNormalizer for MockNormalizer {
    fn normalize(&self, req: &McpRequest, _mcp: &Mcp) -> anyhow::Result<NormalizedRequest> {
        // `action` is an internal record id, not a signal — infer from the intent only.
        let hay = req
            .payload
            .get("intent")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_lowercase();

        let op_class = if ["drop", "truncate", "wipe", "delete_all", "destroy", "borra", "elimina", "aniquila", "vaciar"].iter().any(|k| hay.contains(k)) {
            OpClass::Destructive
        } else if ["refund", "reembolso"].iter().any(|k| hay.contains(k)) {
            OpClass::Refund
        } else if ["grant", "revoke"].iter().any(|k| hay.contains(k)) {
            OpClass::Admin
        } else if ["insert", "update", "create", "write", "modify", "delete", "registra", "escribe", "actualiza"].iter().any(|k| hay.contains(k)) {
            OpClass::Write
        } else if ["read", "get", "find", "list", "query", "consulta", "select", "count", "leer", "ver"].iter().any(|k| hay.contains(k)) {
            OpClass::Read
        } else {
            OpClass::Unknown
        };

        let collection = req
            .payload
            .get("collection")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string())
            .or_else(|| {
                if hay.contains("orders") || hay.contains("pedido") {
                    Some("orders".to_string())
                } else if hay.contains("product") || hay.contains("producto") {
                    Some("products".to_string())
                } else if hay.contains("secret") {
                    Some("secrets".to_string())
                } else if hay.contains("user") || hay.contains("usuario") {
                    Some("users".to_string())
                } else {
                    None
                }
            });

        // Mock returns a single dominant operation; the deterministic scanner catches
        // multi-operation misses in the real (LLM) path.
        Ok(NormalizedRequest { operations: vec![Operation { op_class, collection }] })
    }
}
