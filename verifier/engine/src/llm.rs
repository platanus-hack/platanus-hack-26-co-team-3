//! Shared LLM client. Supports Anthropic (Claude) and OpenAI-compatible (UsePod) hosts.
//! Used by the rule compiler and the request normalizer — both OUTSIDE the decision boundary.

enum Provider {
    /// Anthropic Messages API (x-api-key + anthropic-version; content is an array).
    Anthropic,
    /// OpenAI-compatible chat/completions (UsePod: token in URL; others: Bearer).
    OpenAiCompat { bearer: Option<String> },
}

pub struct LlmClient {
    provider: Provider,
    endpoint: String,
    model: String,
    api_key: String,
}

impl LlmClient {
    /// Prefers Claude when ANTHROPIC_API_KEY is set; else UsePod/OpenAI-compatible.
    pub fn from_env() -> anyhow::Result<Self> {
        if let Ok(key) = std::env::var("ANTHROPIC_API_KEY") {
            return Ok(Self {
                provider: Provider::Anthropic,
                endpoint: "https://api.anthropic.com/v1/messages".to_string(),
                model: std::env::var("ANTHROPIC_MODEL")
                    .unwrap_or_else(|_| "claude-haiku-4-5-20251001".to_string()),
                api_key: key,
            });
        }
        let key = std::env::var("POD_API_KEY").map_err(|_| anyhow::anyhow!("no LLM key set"))?;
        let (endpoint, bearer) = match std::env::var("POD_BASE_URL") {
            Ok(base) => (format!("{}/chat/completions", base.trim_end_matches('/')), Some(key.clone())),
            Err(_) => (format!("https://api.usepod.ai/proxy/{key}/v1/chat/completions"), None),
        };
        Ok(Self {
            provider: Provider::OpenAiCompat { bearer },
            endpoint,
            model: std::env::var("POD_MODEL").unwrap_or_else(|_| "gpt-4o-mini".to_string()),
            api_key: key,
        })
    }

    /// One completion at temperature 0; returns the assistant text. Errors are redacted
    /// (never surface the endpoint/key).
    pub fn chat(&self, system: &str, user: &str) -> anyhow::Result<String> {
        match &self.provider {
            Provider::Anthropic => self.chat_anthropic(system, user),
            Provider::OpenAiCompat { bearer } => self.chat_openai(system, user, bearer.as_deref()),
        }
    }

    fn chat_anthropic(&self, system: &str, user: &str) -> anyhow::Result<String> {
        let body = serde_json::json!({
            "model": self.model,
            "max_tokens": 2048,
            "temperature": 0,
            "system": system,
            "messages": [{ "role": "user", "content": user }],
        });
        let resp = ureq::post(&self.endpoint)
            .set("x-api-key", &self.api_key)
            .set("anthropic-version", "2023-06-01")
            .set("content-type", "application/json")
            .send_json(body);
        let v = handle(resp, "Claude")?;
        v["content"][0]["text"]
            .as_str()
            .map(|s| s.to_string())
            .ok_or_else(|| anyhow::anyhow!("Claude response missing text"))
    }

    fn chat_openai(&self, system: &str, user: &str, bearer: Option<&str>) -> anyhow::Result<String> {
        let mut req = ureq::post(&self.endpoint).set("content-type", "application/json");
        if let Some(k) = bearer {
            req = req.set("authorization", &format!("Bearer {k}"));
        }
        let body = serde_json::json!({
            "model": self.model,
            "temperature": 0,
            "messages": [
                { "role": "system", "content": system },
                { "role": "user", "content": user },
            ],
        });
        let v = handle(req.send_json(body), "LLM")?;
        v["choices"][0]["message"]["content"]
            .as_str()
            .map(|s| s.to_string())
            .ok_or_else(|| anyhow::anyhow!("LLM response missing content"))
    }

    pub fn model(&self) -> &str {
        &self.model
    }
}

/// Redact HTTP/transport errors so the endpoint and key never leak.
fn handle(resp: Result<ureq::Response, ureq::Error>, who: &str) -> anyhow::Result<serde_json::Value> {
    match resp {
        Ok(r) => r.into_json().map_err(|_| anyhow::anyhow!("{who} response was not valid JSON")),
        Err(ureq::Error::Status(code, r)) => {
            let kind = r
                .into_json::<serde_json::Value>()
                .ok()
                .and_then(|v| v["error"]["type"].as_str().map(|s| s.to_string()))
                .unwrap_or_default();
            Err(anyhow::anyhow!("{who} provider returned HTTP {code} {kind}"))
        }
        Err(ureq::Error::Transport(_)) => Err(anyhow::anyhow!("{who} provider unreachable")),
    }
}

/// Isolate the outermost JSON array from a possibly-fenced/prosey reply.
pub fn extract_json_array(s: &str) -> String {
    let s = s.trim();
    if let (Some(a), Some(b)) = (s.find('['), s.rfind(']')) {
        if b >= a {
            return s[a..=b].to_string();
        }
    }
    s.to_string()
}

/// Isolate the outermost JSON object.
pub fn extract_json_object(s: &str) -> String {
    let s = s.trim();
    if let (Some(a), Some(b)) = (s.find('{'), s.rfind('}')) {
        if b >= a {
            return s[a..=b].to_string();
        }
    }
    s.to_string()
}
