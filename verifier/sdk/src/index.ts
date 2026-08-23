/**
 * Aegis Gate SDK — thin client that orchestrates engine -> attestor.
 *
 *   const gate = new Gate();
 *   const { verdict, attestation } = await gate.evaluate(action, policy);
 *
 * The SDK holds no policy logic of its own: the engine decides, the attestor anchors.
 * Types here mirror the engine's canonical JSON exactly (amounts are integers in the
 * token's minimal unit — never floats).
 */

export type ActionType = "Payment" | "CodeExec";
export type Language = "python" | "javascript" | "sql";
export type DecisionValue = "Allow" | "Review" | "Block";

export interface PaymentPayload {
  amount: number; // minimal units, integer
  token: string;
  recipient: string;
  memo?: string;
}

export interface CodePayload {
  language: Language;
  code: string;
}

export interface Action {
  id: string;
  agent_id: string;
  action_type: ActionType;
  payload: PaymentPayload | CodePayload;
  context: { ts: number; state: Record<string, number> };
}

export interface Policy {
  version: string;
  payment: {
    max_amount: number;
    allowlist: string[];
    rate_limit: { max_per_window: number; window_secs: number };
    reserve_invariant: { min_reserve: number };
  };
  code: {
    blocked_calls: string[];
    blocked_imports: string[];
    secret_patterns: string[];
    require_no_unbounded_loops: boolean;
    sql: { block_delete_without_where: boolean; block_drop: boolean };
  };
}

export interface Reason {
  rule_id: string;
  detail: string;
}

export interface Verdict {
  decision: DecisionValue;
  reasons: Reason[];
  action_hash: string;
  policy_hash: string;
  engine_version: string;
  ruleset_hash: string;
  /** Present when the engine (built with `--features smt`) proved the reserve invariant. */
  smt?: SmtProof;
}

export interface SmtProof {
  horizon_n: number;
  max_amount_only: ProofSide;
  with_reserve_rule: ProofSide;
}

export interface Attestation {
  attestationPda: string;
  txSignature: string;
  explorerUrl: string;
  decision: DecisionValue;
  cluster: string;
}

export interface EvaluateResult {
  verdict: Verdict;
  attestation: Attestation | null;
  attestationError: string | null;
}

export interface GateOptions {
  engineUrl?: string;
  attestorUrl?: string;
}

export interface ProofSide {
  holds: boolean; // true = proven (UNSAT), false = counterexample exists (SAT)
  counterexample: number[] | null;
}

export interface ProveScenario {
  reserve0: number;
  max_amount: number;
  min_reserve: number;
  n: number;
}

export interface ProveResult {
  scenario: ProveScenario;
  max_amount_only: ProofSide;
  with_reserve_rule: ProofSide;
}

async function postJson<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  const text = await res.text();
  if (!res.ok) {
    throw new Error(`${url} -> ${res.status}: ${text}`);
  }
  return JSON.parse(text) as T;
}

export class Gate {
  readonly engineUrl: string;
  readonly attestorUrl: string;

  constructor(opts: GateOptions = {}) {
    this.engineUrl = opts.engineUrl ?? "http://127.0.0.1:8080";
    this.attestorUrl = opts.attestorUrl ?? "http://127.0.0.1:8090";
  }

  /** Evaluate against the engine only (pure, deterministic — no chain calls). */
  async evaluateOnly(action: Action, policy: Policy): Promise<Verdict> {
    return postJson<Verdict>(`${this.engineUrl}/evaluate`, { action, policy });
  }

  /**
   * Run the bounded SMT proof of the reserve invariant (engine must be built with
   * `--features smt`). Returns both modes: MAX_AMOUNT only vs. + RESERVE_INVARIANT.
   */
  async prove(scenario: ProveScenario): Promise<ProveResult> {
    return postJson<ProveResult>(`${this.engineUrl}/prove`, scenario);
  }

  /**
   * Evaluate, then attest the verdict on devnet. Attestation failures do NOT hide the
   * verdict — they surface in `attestationError` so the deterministic decision is always
   * returned. Pass `{ attest: false }` to skip the chain call (e.g. the "Re-run"
   * reproducibility check, which only needs to show the hashes are identical).
   */
  async evaluate(
    action: Action,
    policy: Policy,
    { attest = true }: { attest?: boolean } = {},
  ): Promise<EvaluateResult> {
    const verdict = await this.evaluateOnly(action, policy);
    if (!attest) {
      return { verdict, attestation: null, attestationError: null };
    }
    try {
      const attestation = await postJson<Attestation>(`${this.attestorUrl}/attest`, {
        verdict,
        agent_id: action.agent_id,
        ts: action.context.ts,
      });
      return { verdict, attestation, attestationError: null };
    } catch (e) {
      return { verdict, attestation: null, attestationError: String(e) };
    }
  }
}
