import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  Gate,
  type Action,
  type EvaluateResult,
  type Policy,
  type ProveResult,
  type Verdict,
} from "@sdk";

// ---------------------------------------------------------------------------
// Defaults (amounts are integers in the token's MINIMAL unit — e.g. USDC 6 decimals)
// ---------------------------------------------------------------------------

const DEFAULT_POLICY: Policy = {
  version: "1",
  payment: {
    max_amount: 1_000_000_000, // 1000 USDC
    allowlist: ["Alice", "Bob"],
    rate_limit: { max_per_window: 10, window_secs: 3600 },
    reserve_invariant: { min_reserve: 200_000_000 }, // 200 USDC
  },
  code: {
    blocked_calls: ["eval", "exec", "os.system", "subprocess", "__import__"],
    blocked_imports: ["subprocess", "shutil"],
    secret_patterns: ["sk-", "ghp_", "AKIA", "glpat-", "xox"],
    require_no_unbounded_loops: true,
    sql: { block_delete_without_where: true, block_drop: true },
  },
};

const CODE_SAMPLES: Record<string, string> = {
  python: "import subprocess\neval(user_input)\ntoken = 'sk-abc123'\n",
  javascript: "const cp = require('subprocess')\neval(userInput)\n",
  sql: "DELETE FROM users;",
};

type Tab = "Payment" | "Code" | "SMT";
const TAB_LABELS: Record<Tab, string> = {
  Payment: "Payment",
  Code: "Code",
  SMT: "Invariant (SMT)",
};

// ---------------------------------------------------------------------------

export function App() {
  const [engineUrl, setEngineUrl] = useState("http://127.0.0.1:8080");
  const [attestorUrl, setAttestorUrl] = useState("http://127.0.0.1:8090");
  const gate = useMemo(() => new Gate({ engineUrl, attestorUrl }), [engineUrl, attestorUrl]);

  // Reflect whether the engine has the Z3 proof compiled in (from /health).
  const [engineSmt, setEngineSmt] = useState<boolean | null>(null);
  useEffect(() => {
    let live = true;
    fetch(`${engineUrl}/health`)
      .then((r) => r.json())
      .then((h) => live && setEngineSmt(Boolean(h.smt)))
      .catch(() => live && setEngineSmt(null));
    return () => {
      live = false;
    };
  }, [engineUrl]);

  const [tab, setTab] = useState<Tab>("Payment");
  const [policyText, setPolicyText] = useState(JSON.stringify(DEFAULT_POLICY, null, 2));
  const [attestOn, setAttestOn] = useState(true);

  // Payment inputs
  const [amount, setAmount] = useState("200000000");
  const [token, setToken] = useState("USDC");
  const [recipient, setRecipient] = useState("Mallory");
  const [reserve, setReserve] = useState("300000000");
  const [spent, setSpent] = useState("2");

  // Code inputs
  const [language, setLanguage] = useState<"python" | "javascript" | "sql">("python");
  const [code, setCode] = useState(CODE_SAMPLES.python);

  // SMT inputs
  const [smtReserve0, setSmtReserve0] = useState("1000");
  const [smtMax, setSmtMax] = useState("400");
  const [smtMin, setSmtMin] = useState("200");
  const [smtN, setSmtN] = useState("3");
  const [smtResult, setSmtResult] = useState<ProveResult | null>(null);

  const [agentId] = useState("agent-1");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<EvaluateResult | null>(null);
  const [lastAction, setLastAction] = useState<Action | null>(null);
  const [rerun, setRerun] = useState<{ verdict: Verdict; identical: boolean } | null>(null);

  function buildAction(): Action {
    const ts = Math.floor(Date.now() / 1000);
    if (tab === "Payment") {
      return {
        id: crypto.randomUUID(),
        agent_id: agentId,
        action_type: "Payment",
        payload: { amount: Number(amount), token, recipient },
        context: { ts, state: { reserve: Number(reserve), spent_in_window: Number(spent) } },
      };
    }
    return {
      id: crypto.randomUUID(),
      agent_id: agentId,
      action_type: "CodeExec",
      payload: { language, code },
      context: { ts, state: {} },
    };
  }

  function parsePolicy(): Policy {
    return JSON.parse(policyText) as Policy;
  }

  async function onEvaluate() {
    setBusy(true);
    setError(null);
    setRerun(null);
    try {
      const policy = parsePolicy();
      const action = buildAction();
      const res = await gate.evaluate(action, policy, { attest: attestOn });
      setResult(res);
      setLastAction(action);
    } catch (e) {
      setError(String(e));
      setResult(null);
      setLastAction(null);
    } finally {
      setBusy(false);
    }
  }

  async function onProve() {
    setBusy(true);
    setError(null);
    setSmtResult(null);
    try {
      const r = await gate.prove({
        reserve0: Number(smtReserve0),
        max_amount: Number(smtMax),
        min_reserve: Number(smtMin),
        n: Number(smtN),
      });
      setSmtResult(r);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  // Re-run: evaluate the EXACT SAME action again (engine only) and prove the verdict
  // and hashes are byte-identical. This is the live reproducibility argument.
  async function onRerun() {
    if (!lastAction || !result) return;
    setBusy(true);
    setError(null);
    try {
      const policy = parsePolicy();
      const verdict = await gate.evaluateOnly(lastAction, policy);
      const identical =
        verdict.action_hash === result.verdict.action_hash &&
        verdict.policy_hash === result.verdict.policy_hash &&
        verdict.decision === result.verdict.decision;
      setRerun({ verdict, identical });
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="wrap">
      <header>
        <h1>Aegis&nbsp;Gate</h1>
        <p className="sub">Deterministic action firewall for autonomous agents · attested on Solana devnet</p>
        <p className="boundary">
          Asserts an action does not violate the declared policies. It does <b>not</b> prove code is
          correct. Same (action, policy) → same verdict &amp; hashes, always.
        </p>
      </header>

      <section className="endpoints">
        <label>engine <input value={engineUrl} onChange={(e) => setEngineUrl(e.target.value)} /></label>
        <label>attestor <input value={attestorUrl} onChange={(e) => setAttestorUrl(e.target.value)} /></label>
        <label className="chk">
          <input type="checkbox" checked={attestOn} onChange={(e) => setAttestOn(e.target.checked)} />
          attest on devnet
        </label>
        {engineSmt !== null && (
          <span className={engineSmt ? "z3badge on" : "z3badge off"}>
            Z3: {engineSmt ? "on" : "off"}
          </span>
        )}
      </section>

      <div className="tabs">
        {(["Payment", "Code", "SMT"] as Tab[]).map((t) => (
          <button key={t} className={t === tab ? "tab active" : "tab"} onClick={() => setTab(t)}>
            {TAB_LABELS[t]}
          </button>
        ))}
      </div>

      {tab === "SMT" ? (
        <SmtPanel
          reserve0={smtReserve0} setReserve0={setSmtReserve0}
          max={smtMax} setMax={setSmtMax}
          min={smtMin} setMin={setSmtMin}
          n={smtN} setN={setSmtN}
          busy={busy} onProve={onProve} result={smtResult} error={error}
        />
      ) : (
      <>
      <div className="grid">
        <section className="panel">
          {tab === "Payment" ? (
            <>
              <h3>Payment</h3>
              <Field label="amount (minimal units)"><input value={amount} onChange={(e) => setAmount(e.target.value)} /></Field>
              <Field label="token"><input value={token} onChange={(e) => setToken(e.target.value)} /></Field>
              <Field label="recipient"><input value={recipient} onChange={(e) => setRecipient(e.target.value)} /></Field>
              <Field label="state.reserve"><input value={reserve} onChange={(e) => setReserve(e.target.value)} /></Field>
              <Field label="state.spent_in_window"><input value={spent} onChange={(e) => setSpent(e.target.value)} /></Field>
            </>
          ) : (
            <>
              <h3>Code</h3>
              <Field label="language">
                <select
                  value={language}
                  onChange={(e) => {
                    const l = e.target.value as "python" | "javascript" | "sql";
                    setLanguage(l);
                    setCode(CODE_SAMPLES[l]);
                  }}
                >
                  <option value="python">python</option>
                  <option value="javascript">javascript</option>
                  <option value="sql">sql</option>
                </select>
              </Field>
              <Field label="code">
                <textarea className="code" rows={8} value={code} onChange={(e) => setCode(e.target.value)} />
              </Field>
            </>
          )}

          <button className="primary" disabled={busy} onClick={onEvaluate}>
            {busy ? "…" : "Evaluate"}
          </button>
        </section>

        <section className="panel">
          <h3>Active policy (editable, auditable)</h3>
          <textarea className="policy" value={policyText} onChange={(e) => setPolicyText(e.target.value)} />
        </section>
      </div>

      {error && <div className="err">{error}</div>}

      {result && (
        <section className="result">
          <Badge decision={result.verdict.decision} />

          <div className="reasons">
            <h4>reasons</h4>
            {result.verdict.reasons.length === 0 ? (
              <p className="muted">— none —</p>
            ) : (
              <ul>
                {result.verdict.reasons.map((r, i) => (
                  <li key={i}><code>{r.rule_id}</code> — {r.detail}</li>
                ))}
              </ul>
            )}
          </div>

          <div className="hashes">
            <Hash label="action_hash" value={result.verdict.action_hash} />
            <Hash label="policy_hash" value={result.verdict.policy_hash} />
            <Hash label="ruleset_hash" value={result.verdict.ruleset_hash} />
            <div className="kv"><span>engine_version</span><code>{result.verdict.engine_version}</code></div>
          </div>

          {result.verdict.smt && (
            <div className="smt-inline">
              <h4>Z3 reserve proof · horizon {result.verdict.smt.horizon_n} payments</h4>
              <div className="smt-row">
                <span className={result.verdict.smt.with_reserve_rule.holds ? "ok" : "bad"}>
                  {result.verdict.smt.with_reserve_rule.holds
                    ? "✓ reserve invariant proven — no approvable sequence can breach the floor"
                    : "✗ invariant NOT proven (unexpected!)"}
                </span>
              </div>
              {!result.verdict.smt.max_amount_only.holds && (
                <p className="smt-note">
                  Why the rule matters: with a per-payment cap alone, Z3 finds a draining
                  sequence <code>[{result.verdict.smt.max_amount_only.counterexample?.join(", ")}]</code>.
                  The reserve rule closes it.
                </p>
              )}
            </div>
          )}

          <div className="attest">
            {attestOn ? (
              result.attestation ? (
                <a href={result.attestation.explorerUrl} target="_blank" rel="noreferrer">
                  ↗ attestation on devnet ({result.attestation.decision})
                </a>
              ) : (
                <span className="err-inline">attestation failed: {result.attestationError}</span>
              )
            ) : (
              <span className="muted">attestation disabled</span>
            )}
          </div>

          <div className="rerun">
            <button disabled={busy} onClick={onRerun}>Re-run (prove reproducibility)</button>
            {rerun && (
              <span className={rerun.identical ? "match" : "nomatch"}>
                {rerun.identical
                  ? "✓ identical verdict & hashes"
                  : "✗ MISMATCH — determinism broken!"}
              </span>
            )}
          </div>
        </section>
      )}
      </>
      )}
    </div>
  );
}

function SmtPanel(props: {
  reserve0: string; setReserve0: (v: string) => void;
  max: string; setMax: (v: string) => void;
  min: string; setMin: (v: string) => void;
  n: string; setN: (v: string) => void;
  busy: boolean; onProve: () => void; result: ProveResult | null; error: string | null;
}) {
  const { result } = props;
  return (
    <>
      <section className="panel">
        <h3>Reserve invariant — bounded SMT proof (Z3)</h3>
        <p className="muted" style={{ fontSize: 13, marginTop: 0 }}>
          Over any sequence of up to N individually-approvable payments: does the gate keep
          the reserve at or above the floor? Z3 answers for real — a counterexample (SAT) or
          a proof (UNSAT).
        </p>
        <div className="smt-inputs">
          <Field label="reserve0"><input value={props.reserve0} onChange={(e) => props.setReserve0(e.target.value)} /></Field>
          <Field label="max_amount"><input value={props.max} onChange={(e) => props.setMax(e.target.value)} /></Field>
          <Field label="min_reserve"><input value={props.min} onChange={(e) => props.setMin(e.target.value)} /></Field>
          <Field label="N (payments, 1–32)"><input value={props.n} onChange={(e) => props.setN(e.target.value)} /></Field>
        </div>
        <button className="primary" disabled={props.busy} onClick={props.onProve}>
          {props.busy ? "proving…" : "Prove"}
        </button>
      </section>

      {props.error && <div className="err">{props.error}</div>}

      {result && (
        <section className="result">
          <ProofCard
            title="Gate with MAX_AMOUNT only"
            side={result.max_amount_only}
            note="A per-payment cap alone."
          />
          <div style={{ height: 16 }} />
          <ProofCard
            title="Gate with MAX_AMOUNT + RESERVE_INVARIANT"
            side={result.with_reserve_rule}
            note="The real gate rules."
          />
        </section>
      )}
    </>
  );
}

function ProofCard({ title, side, note }: { title: string; side: ProveResult["max_amount_only"]; note: string }) {
  return (
    <div className="proofcard">
      <div className={`badge ${side.holds ? "allow" : "block"}`}>
        {side.holds ? "UNSAT — proven" : "SAT — counterexample"}
      </div>
      <h4 style={{ margin: "10px 0 2px" }}>{title}</h4>
      <p className="muted" style={{ marginTop: 0, fontSize: 12 }}>{note}</p>
      {side.holds ? (
        <p style={{ fontSize: 13 }}>No approvable sequence can breach the floor.</p>
      ) : (
        <p style={{ fontSize: 13 }}>
          Z3 found amounts <code>[{side.counterexample?.join(", ")}]</code> that drain the reserve below the floor.
        </p>
      )}
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
    </label>
  );
}

function Badge({ decision }: { decision: string }) {
  return <div className={`badge ${decision.toLowerCase()}`}>{decision}</div>;
}

function Hash({ label, value }: { label: string; value: string }) {
  return (
    <div className="kv">
      <span>{label}</span>
      <code title={value}>{value}</code>
    </div>
  );
}
