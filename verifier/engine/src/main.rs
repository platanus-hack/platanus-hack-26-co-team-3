//! Aegis Gate — MCP access-policy evaluator server (:8080).
//!
//! Uses the live UsePod LLM compiler when POD_API_KEY is set (loaded from engine/.env),
//! otherwise falls back to the deterministic mock compiler.

use std::sync::Arc;

use aegis_gate_engine::compiler::{CachingCompiler, LlmCompiler, MockCompiler, RuleCompiler};
use aegis_gate_engine::hashing::ENGINE_VERSION;
use aegis_gate_engine::normalizer::{CachingNormalizer, LlmNormalizer, MockNormalizer, RequestNormalizer};
use aegis_gate_engine::service::{router, AppState};

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let _ = dotenvy::dotenv(); // load engine/.env if present

    // Provider label for /health + response provenance.
    let llm_kind: &'static str = if std::env::var("ANTHROPIC_API_KEY").is_ok() {
        "claude"
    } else {
        "usepod"
    };

    let (compiler, kind): (Box<dyn RuleCompiler>, &'static str) = match LlmCompiler::from_env() {
        Ok(llm) => (Box::new(llm), llm_kind),
        Err(_) => (Box::new(MockCompiler), "mock"),
    };
    let (normalizer, nkind): (Box<dyn RequestNormalizer>, &'static str) = match LlmNormalizer::from_env() {
        Ok(llm) => (Box::new(llm), llm_kind),
        Err(_) => (Box::new(MockNormalizer), "mock"),
    };

    let state = Arc::new(AppState {
        compiler: CachingCompiler::new(compiler),
        compiler_kind: kind,
        normalizer: CachingNormalizer::new(normalizer),
        normalizer_kind: nkind,
    });

    let addr = std::env::var("AEGIS_ENGINE_ADDR").unwrap_or_else(|_| "127.0.0.1:8080".to_string());
    println!("aegis-gate MCP evaluator  v{ENGINE_VERSION}");
    println!("  compiler: {kind}  normalizer: {nkind}");
    println!("  listening on http://{addr}  (POST /evaluate, POST /audit, GET /health)");

    let listener = tokio::net::TcpListener::bind(&addr).await?;
    axum::serve(listener, router(state)).await?;
    Ok(())
}
