//! HTTP service (axum): compile → Z3 gate → decide → response envelope.
//!
//!   POST /evaluate  { rules: string[], prompt } -> slim verdict { allowed, reason, rules }
//!   POST /audit     { mcp }                      -> Z3 policy audit only
//!   GET  /health
//!
//! /evaluate returns only pass/fail + reason + the rules; the full verdict envelope
//! (hashes, Z3 audit, normalized request, meta) is still assembled internally by
//! `pipeline` and can be re-exposed if a caller needs it.

use axum::{extract::State, http::StatusCode, response::IntoResponse, routing::{get, post}, Json, Router};
use serde::Serialize;
use std::sync::Arc;
use std::time::Instant;
use tower_http::cors::CorsLayer;

use crate::attributes::{from_operation, within_working_hours, Attributes};
use crate::compiler::{CachingCompiler, RuleCompiler};
use crate::engine::evaluate_operations;
use crate::hashing::{normalized_request_hash, ENGINE_VERSION};
use crate::model::{CompiledPolicy, Effect, EvalInput, Mcp, McpRequest, Rule};
use crate::normalizer::{CachingNormalizer, RequestNormalizer};
use crate::scanner;
use crate::z3enc::{Enc, Proof};

pub struct AppState {
    pub compiler: CachingCompiler<Box<dyn RuleCompiler>>,
    pub compiler_kind: &'static str,
    pub normalizer: CachingNormalizer<Box<dyn RequestNormalizer>>,
    pub normalizer_kind: &'static str,
}

pub fn router(state: Arc<AppState>) -> Router {
    Router::new()
        .route("/health", get(health))
        .route("/evaluate", post(evaluate_handler))
        .route("/audit", post(audit_handler))
        .with_state(state)
        .layer(CorsLayer::permissive())
}

// ---------------------------------------------------------------------------
// Response envelope
// ---------------------------------------------------------------------------

#[derive(Serialize)]
struct EvalResponse {
    allowed: bool,
    #[serde(rename = "violatedPriority")]
    violated_priority: Option<i64>,
    reason: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    attributes: Option<AttrView>,
    #[serde(rename = "governingRule", skip_serializing_if = "Option::is_none")]
    governing_rule: Option<GovRuleView>,
    #[serde(rename = "policyAudit", skip_serializing_if = "Option::is_none")]
    policy_audit: Option<AuditView>,
    #[serde(rename = "compiledPolicy", skip_serializing_if = "Option::is_none")]
    compiled_policy: Option<CompiledPolicyView>,
    #[serde(rename = "normalizedRequest", skip_serializing_if = "Option::is_none")]
    normalized_request: Option<NormalizedView>,
    hashes: HashesView,
    attestation: Option<serde_json::Value>,
    meta: MetaView,
}

#[derive(Serialize)]
struct AttrView {
    #[serde(rename = "accessedBy")]
    accessed_by: String,
    #[serde(rename = "withinWorkingHours")]
    within_working_hours: bool,
}

#[derive(Serialize)]
struct OpView {
    #[serde(rename = "opClass")]
    op_class: String,
    collection: Option<String>,
}

#[derive(Serialize)]
struct ScanView {
    passed: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    note: Option<String>,
}

#[derive(Serialize)]
struct GovRuleView {
    priority: i64,
    effect: Effect,
    #[serde(rename = "sourceInstruction", skip_serializing_if = "Option::is_none")]
    source_instruction: Option<String>,
    condition: serde_json::Value,
}

#[derive(Serialize)]
struct RuleView {
    priority: i64,
    effect: Effect,
    #[serde(rename = "sourceInstruction", skip_serializing_if = "Option::is_none")]
    source_instruction: Option<String>,
    condition: serde_json::Value,
}

#[derive(Serialize)]
struct CompiledPolicyView {
    #[serde(rename = "compiledBy")]
    compiled_by: String,
    deterministic: bool,
    #[serde(rename = "defaultEffect")]
    default_effect: Effect,
    rules: Vec<RuleView>,
}

#[derive(Serialize)]
struct AuditView {
    engine: &'static str,
    #[serde(rename = "noDestructiveBypass")]
    no_destructive_bypass: BypassView,
    conflicts: Vec<ConflictView>,
    #[serde(rename = "deadRules")]
    dead_rules: Vec<usize>,
}

#[derive(Serialize)]
struct BypassView {
    holds: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    counterexample: Option<String>,
}

#[derive(Serialize)]
struct ConflictView {
    priority: i64,
    example: String,
}

#[derive(Serialize)]
struct NormalizedView {
    operations: Vec<OpView>,
    #[serde(rename = "inferredBy")]
    inferred_by: String,
    deterministic: bool,
    scanner: ScanView,
}

#[derive(Serialize)]
struct HashesView {
    #[serde(rename = "requestHash")]
    request_hash: String,
    #[serde(rename = "policyHash")]
    policy_hash: String,
    #[serde(rename = "rulesSourceHash")]
    rules_source_hash: String,
    #[serde(rename = "normalizedRequestHash", skip_serializing_if = "Option::is_none")]
    normalized_request_hash: Option<String>,
    #[serde(rename = "engineVersion")]
    engine_version: String,
}

#[derive(Serialize)]
struct MetaView {
    #[serde(rename = "policyCacheHit")]
    policy_cache_hit: bool,
    #[serde(rename = "evaluationMs")]
    evaluation_ms: u128,
    compiler: String,
}

// ---------------------------------------------------------------------------
// Assembly
// ---------------------------------------------------------------------------

fn op_class_str(c: crate::model::OpClass) -> String {
    serde_json::to_value(c).unwrap().as_str().unwrap().to_string()
}

fn audit_view(policy: &CompiledPolicy) -> AuditView {
    let enc = Enc::new(policy);
    let no_destructive_bypass = match enc.prove_no_destructive_bypass() {
        Proof::Holds => BypassView { holds: true, counterexample: None },
        Proof::Counterexample(m) => BypassView { holds: false, counterexample: Some(m.describe()) },
    };
    let conflicts = enc
        .find_conflicts()
        .into_iter()
        .map(|(p, m)| ConflictView { priority: p, example: m.describe() })
        .collect();
    AuditView {
        engine: "z3",
        no_destructive_bypass,
        conflicts,
        dead_rules: enc.find_dead_rules(),
    }
}

fn compiled_policy_view(policy: &CompiledPolicy, mcp: &Mcp, kind: &str) -> CompiledPolicyView {
    let rules = policy
        .rules
        .iter()
        .enumerate()
        .map(|(i, r)| RuleView {
            priority: r.priority,
            effect: r.effect,
            source_instruction: mcp.rules.get(i).map(|s| s.instruction.clone()),
            condition: serde_json::to_value(&r.condition).unwrap_or(serde_json::Value::Null),
        })
        .collect();
    CompiledPolicyView {
        compiled_by: kind.to_string(),
        deterministic: kind == "mock",
        default_effect: policy.default_effect,
        rules,
    }
}

/// Full synchronous pipeline (compile + Z3 + decide). Runs off the async runtime.
fn pipeline(state: &AppState, input: EvalInput) -> EvalResponse {
    let started = Instant::now();

    let fail_safe = |reason: String, cache_hit: bool| -> EvalResponse {
        EvalResponse {
            allowed: false,
            violated_priority: None,
            reason,
            attributes: None,
            governing_rule: None,
            policy_audit: None,
            compiled_policy: None,
            normalized_request: None,
            hashes: HashesView {
                request_hash: crate::hashing::request_hash(&input).unwrap_or_default(),
                policy_hash: String::new(),
                rules_source_hash: crate::hashing::rules_source_hash(&input.mcp.rules).unwrap_or_default(),
                normalized_request_hash: None,
                engine_version: ENGINE_VERSION.to_string(),
            },
            attestation: None,
            meta: MetaView {
                policy_cache_hit: cache_hit,
                evaluation_ms: started.elapsed().as_millis(),
                compiler: state.compiler_kind.to_string(),
            },
        }
    };

    // Compile rules and normalize the request in PARALLEL (independent LLM calls; Claude
    // handles concurrency). Both are cached, so warm calls are instant regardless.
    let (compile_res, norm_res) = std::thread::scope(|s| {
        let ch = s.spawn(|| state.compiler.compile_policy(&input.mcp));
        let n = state.normalizer.normalize(&input.request, &input.mcp);
        (ch.join().expect("compile thread panicked"), n)
    });
    let (policy, cache_hit) = match compile_res {
        Ok(x) => x,
        Err(e) => return fail_safe(format!("policy could not be compiled; denied for safety: {e}"), false),
    };
    let (normalized, _norm_hit) = match norm_res {
        Ok(x) => x,
        Err(e) => return fail_safe(format!("request could not be normalized; denied for safety: {e}"), cache_hit),
    };
    let norm_hash = normalized_request_hash(&normalized).ok();
    let intent = input.request.payload.get("intent").and_then(|x| x.as_str()).unwrap_or("");

    // 3. Deterministic scanner: cross-check the raw intent text against the extracted
    // operations. If the text mentions a policy-relevant collection or a dangerous verb the
    // LLM did not cover → don't trust it → fail-safe deny.
    let scan = scanner::scan(intent, &normalized, &scanner::policy_collections(&policy));
    if !scan.passed {
        eprintln!("[eval] SCANNER BLOCKED intent={:?} reason={:?}", intent, scan.reason);
        return fail_safe(scan.reason.clone().unwrap_or_else(|| "scanner flagged the request".into()), cache_hit);
    }

    // 4. Working hours once (shared across ops). Bad time → fail-safe deny.
    let within = match within_working_hours(&input.time, &policy.working_hours) {
        Ok(w) => w,
        Err(e) => return fail_safe(format!("input error, denied for safety: {e}"), cache_hit),
    };

    // 5. One Attributes per operation → deny-if-any.
    let ops_attrs: Vec<Attributes> = normalized
        .operations
        .iter()
        .map(|op| from_operation(op, &input.request, within))
        .collect();
    let detail = evaluate_operations(&input, &policy, &ops_attrs).expect("hashing infallible");
    let v = &detail.verdict;

    eprintln!(
        "[eval] intent={:?} -> ops={:?} | allowed={} reason={:?}",
        &intent.chars().take(80).collect::<String>(),
        normalized.operations,
        v.allowed,
        v.reason,
    );

    let attributes = Some(AttrView {
        accessed_by: input.request.accessed_by.clone(),
        within_working_hours: within,
    });

    let governing_rule = detail.governing_index.map(|i| GovRuleView {
        priority: policy.rules[i].priority,
        effect: policy.rules[i].effect,
        source_instruction: input.mcp.rules.get(i).map(|s| s.instruction.clone()),
        condition: serde_json::to_value(&policy.rules[i].condition).unwrap_or(serde_json::Value::Null),
    });

    EvalResponse {
        allowed: v.allowed,
        violated_priority: v.violated_priority,
        reason: v.reason.clone(),
        attributes,
        governing_rule,
        policy_audit: Some(audit_view(&policy)),
        compiled_policy: Some(compiled_policy_view(&policy, &input.mcp, state.compiler_kind)),
        normalized_request: Some(NormalizedView {
            operations: normalized
                .operations
                .iter()
                .map(|o| OpView { op_class: op_class_str(o.op_class), collection: o.collection.clone() })
                .collect(),
            inferred_by: state.normalizer_kind.to_string(),
            deterministic: state.normalizer_kind == "mock",
            scanner: ScanView { passed: scan.passed, note: scan.reason.clone() },
        }),
        hashes: HashesView {
            request_hash: v.request_hash.clone(),
            policy_hash: v.policy_hash.clone(),
            rules_source_hash: v.rules_source_hash.clone(),
            normalized_request_hash: norm_hash,
            engine_version: v.engine_version.clone(),
        },
        attestation: None, // wired to SAS devnet in R4b
        meta: MetaView {
            policy_cache_hit: cache_hit,
            evaluation_ms: started.elapsed().as_millis(),
            compiler: state.compiler_kind.to_string(),
        },
    }
}

// ---------------------------------------------------------------------------
// Handlers
// ---------------------------------------------------------------------------

async fn health(State(st): State<Arc<AppState>>) -> impl IntoResponse {
    Json(serde_json::json!({
        "status": "ok",
        "engineVersion": ENGINE_VERSION,
        "z3": true,
        "compiler": st.compiler_kind,
        "normalizer": st.normalizer_kind,
    }))
}

// ---------------------------------------------------------------------------
// /evaluate — minimal body { rules: string[], prompt: string }
// ---------------------------------------------------------------------------
//
// The endpoint the caller uses. It takes a list of natural-language rules and a single
// free-text prompt, builds a full EvalInput internally, and runs the same
// compile → Z3 → decide pipeline. The response is slim: pass/fail + reason + the rules.
//
// Semantics: every rule is given the SAME priority, so a matching Deny always wins over
// a matching Allow (deny-wins-ties in `engine::govern`) — the conservative firewall
// default. A prompt of the form "<action>: <intent>" is split into action + intent; with
// no colon the whole string is both.

#[derive(serde::Deserialize)]
struct GateRequest {
    rules: Vec<String>,
    prompt: String,
}

/// All rules share this priority so Deny wins ties (see `engine::govern`).
const GATE_RULE_PRIORITY: i64 = 1;

fn gate_to_eval_input(req: GateRequest) -> EvalInput {
    let rules = req
        .rules
        .into_iter()
        .filter(|s| !s.trim().is_empty())
        .map(|instruction| Rule { priority: GATE_RULE_PRIORITY, instruction })
        .collect();

    let mcp = Mcp {
        id: "gate".to_string(),
        name: "gate".to_string(),
        description: "ad-hoc gate policy".to_string(),
        rules,
    };

    // "<action>: <intent>" → (action, intent); no colon → the whole prompt is both.
    let (action, intent) = match req.prompt.split_once(':') {
        Some((a, rest)) => (a.trim().to_string(), rest.trim().to_string()),
        None => {
            let p = req.prompt.trim().to_string();
            (p.clone(), p)
        }
    };

    let request = McpRequest {
        accessed_by: "agent".to_string(),
        action,
        payload: serde_json::json!({ "intent": intent }),
    };

    // Real UTC now; irrelevant unless a rule references working hours, but kept correct so
    // time-based policies still work through this endpoint. Falls back to a fixed valid
    // RFC3339 instant if formatting somehow fails (keeps the request parseable, not denied).
    let time = time::OffsetDateTime::now_utc()
        .format(&time::format_description::well_known::Rfc3339)
        .unwrap_or_else(|_| "2025-01-01T12:00:00Z".to_string());

    EvalInput { mcp, request, time }
}

/// Slim verdict for /gate: pass/fail + reason + the rules (which one governed, and the
/// full list with its effect). No hashes/audit/meta — just what a caller needs to see.
#[derive(Serialize)]
struct GateResponse {
    allowed: bool,
    reason: String,
    #[serde(rename = "governingRule", skip_serializing_if = "Option::is_none")]
    governing_rule: Option<GateRuleView>,
    rules: Vec<GateRuleView>,
}

#[derive(Serialize)]
struct GateRuleView {
    #[serde(skip_serializing_if = "Option::is_none")]
    instruction: Option<String>,
    effect: Effect,
}

async fn evaluate_handler(
    State(st): State<Arc<AppState>>,
    Json(req): Json<GateRequest>,
) -> impl IntoResponse {
    let input = gate_to_eval_input(req);
    let full = tokio::task::spawn_blocking(move || pipeline(&st, input))
        .await
        .expect("evaluate pipeline task");

    let rules = full
        .compiled_policy
        .as_ref()
        .map(|c| {
            c.rules
                .iter()
                .map(|r| GateRuleView { instruction: r.source_instruction.clone(), effect: r.effect })
                .collect()
        })
        .unwrap_or_default();

    let governing_rule = full
        .governing_rule
        .as_ref()
        .map(|g| GateRuleView { instruction: g.source_instruction.clone(), effect: g.effect });

    Json(GateResponse { allowed: full.allowed, reason: full.reason, governing_rule, rules })
}

#[derive(serde::Deserialize)]
struct AuditRequest {
    mcp: Mcp,
}

async fn audit_handler(
    State(st): State<Arc<AppState>>,
    Json(req): Json<AuditRequest>,
) -> impl IntoResponse {
    let out = tokio::task::spawn_blocking(move || match st.compiler.compile_policy(&req.mcp) {
        Ok((policy, _)) => {
            let audit = audit_view(&policy);
            let view = compiled_policy_view(&policy, &req.mcp, st.compiler_kind);
            Ok((audit, view))
        }
        Err(e) => Err(e.to_string()),
    })
    .await
    .expect("audit task");

    match out {
        Ok((audit, policy)) => {
            (StatusCode::OK, Json(serde_json::json!({ "policyAudit": audit, "compiledPolicy": policy }))).into_response()
        }
        Err(e) => (
            StatusCode::UNPROCESSABLE_ENTITY,
            Json(serde_json::json!({ "error": format!("policy compilation failed: {e}") })),
        )
            .into_response(),
    }
}
