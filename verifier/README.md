# verifier — Bloque 10

La capa de verificación que Roxy consulta antes de dejar pasar una petición.

Hay **dos implementaciones** en esta carpeta y conviene no confundirlas:

| | qué es | contrato | estado |
|---|---|---|---|
| **`engine/`** (Rust) | El motor real: compila las reglas a una política formal, decide de forma determinista sobre ella y la audita con Z3. Ver [Aegis Gate](#aegis-gate) más abajo. | `{rules, prompt}` | **es el que corre en producción** |
| `evaluator.py` (Python) | Fallback mínimo para desarrollo local: dos comprobaciones escritas a mano para el escenario de facturas de la demo. | `{mcp, request, time}` | solo local, no es la implementación del bloque |

## Cuál está conectado

`roxy-gateway/internal/policy/remote.go` hace `POST` a `EVALUATOR_URL` con
`{rules: string[], prompt: string}`. Ese es el contrato vigente, y **`engine/`
es el que lo habla**.

Se puede comprobar sin leer configuración, mirando los logs de seguridad: cada
evaluador deja una firma distinta en `description`.

| origen | formato del motivo |
|---|---|
| `engine/` (Rust) | `operation 1 (write on 'invoices') is denied by rule priority 1` |
| `evaluator.py` | `proposedTotal (0) no coincide con computedSubtotalSum (600000)` |

```bash
curl -s "https://roxygt.lat/api/log?limit=40" | grep -o "operation [0-9].*"
```

⚠️ **`evaluator.py` NO habla el contrato actual del gateway.** Espera
`{mcp, request, time}` y responde `422` ante `{rules, prompt}`, que el gateway
traduce a `503`. Apuntar `EVALUATOR_URL` ahí rompe la mitad "con Roxy" de la
demo. Está pendiente hacerlo aceptar las dos formas — ver `research/ISSUES.md`.

## Correr el motor real

```bash
cd engine
cargo test        # incluye los tests de Z3
cargo run         # sirve POST /evaluate, POST /audit, GET /health
```

Y en el gateway: `EVALUATOR_URL=http://localhost:8080/evaluate`.

## Correr el fallback de Python

Solo si no hay toolchain de Rust a mano y alcanza con el escenario de
facturas. Requiere ajustar el contrato primero (ver el aviso de arriba).

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn evaluator:app --port 9000
python3 -m pytest tests/ -q     # 7 tests
```

## Dónde entra Z3

El LLM traduce las reglas en lenguaje natural a una política formal **una
sola vez** (compilada y cacheada). A partir de ahí no hay LLM en el camino de
la decisión: se evalúa sobre esa política congelada.

Z3 corre sobre esa política ya compilada y responde preguntas que un LLM no
puede responder — no sobre *esta* petición, sino sobre *el conjunto de reglas*:

- `noDestructiveBypass` — ¿existe alguna acción destructiva que se cuele por
  las reglas escritas? Si la hay, Z3 devuelve el **contraejemplo concreto**.
- `deadRules` — reglas que nunca se pueden activar.
- `conflicts` — reglas de igual prioridad que se contradicen.

Se expone en `POST /audit` y también se calcula dentro del pipeline de
`/evaluate` (`engine/src/service.rs`).

---

# Aegis Gate

A **deterministic action firewall** for autonomous agents. It intercepts the action an
agent is about to execute, evaluates it against a declarative policy, emits a verdict
`Allow / Review / Block`, and **attests that verdict on-chain** via the Solana
Attestation Service (SAS) on **devnet**.

The core property is **deterministic reproducibility**: for the same
`(action, policy)`, the verdict and its hashes are always identical, and any third
party can re-run the engine and get the same result. That reproducibility is the proof.

```
Action ──▶ Engine (pure, no LLM) ──▶ Verdict ──▶ Attestor ──▶ SAS (devnet) ──▶ tx
                     │                                                          │
        action_hash / policy_hash                                    explorer?cluster=devnet
```

Two action types are implemented: **Payment** and **CodeExec**.

## What it guarantees — and what it does not

**Guarantees**
- **Determinism.** The engine is a pure function: no wall clock (the timestamp is passed
  in as data), no network, no randomness, **no LLM** in the decision path. Same input →
  same verdict → same `action_hash` / `policy_hash`, byte-for-byte.
- **Auditable policy.** Policies are declarative JSON, hashed canonically.
- **Verifiable record.** Every verdict (Allow, Review **and** Block) is anchored on-chain
  with its hashes; anyone can re-run the engine and check the on-chain record matches.
- **Reproducible build surface.** `ruleset_hash` binds the engine version and the exact
  pinned grammar versions, so a third party knows which binary reproduces a result.

**Does NOT guarantee**
- It does **not** prove code is correct. The code validator only asserts that a code
  action does not violate the **declared static policies** (blocked calls/imports, secret
  literals, unbounded loops, dangerous SQL). It is not a general verifier.
- `UNBOUNDED_LOOP` uses a conservative reachability approximation (any `break` in the loop
  body counts as reachable) — it can only be *more* permissive, never wrongly Block.
- Everything runs on **devnet**. No mainnet.

## Layout

```
engine/     Rust — the deterministic gate (axum :8080). Pure function + validators.
attestor/   TypeScript — emits SAS attestations on devnet (hono :8090).
sdk/        TypeScript — thin client orchestrating engine → attestor.
ui/         Vite + React — test bench (Payment / Code tabs, Re-run reproducibility).
policies/   Default policy presets.
```

## Setup & run

### 1. Engine (Rust, port 8080)
```bash
cd engine
cargo test        # 38 tests: determinism, every rule, HTTP
cargo run         # serves POST /evaluate, GET /health
```

### 2. Attestor (TypeScript, port 8090, devnet)
```bash
cd attestor
npm install
npm run setup     # ONE TIME: generates a devnet issuer, airdrops SOL,
                  # creates the SAS credential + schema, writes attestor/.env
npm run dev       # serves POST /attest
```
`npm run setup` is idempotent and writes `attestor/.env` (gitignored — it holds the
devnet issuer secret). Verify any attestation later with:
```bash
npx tsx src/verify.ts <attestationPda>
```

### 3. UI (Vite + React)
```bash
cd ui
npm install
npm run dev       # open the printed localhost URL
```
Set the engine/attestor URLs at the top if you changed ports. Toggle **attest on devnet**
off to evaluate without touching the chain.

## The reproducibility demo

In the UI, evaluate any action, then press **Re-run**. It re-evaluates the *exact same
action* and shows the verdict and hashes are identical — the live argument for
deterministic reproducibility. `action_hash` deliberately excludes the action's transport
`id`, so the semantic action is what's hashed.

## Data model (canonical)

- **Amounts are integers in the token's minimal unit** (e.g. `500 USDC` → `500000000`).
  No floats anywhere in the decision path — floats would break byte-level reproducibility.
- `action_hash = sha256(canonical(action \ id))`, `policy_hash = sha256(canonical(policy))`.
  Canonical form is a JCS-aligned subset (sorted ASCII keys, integer numbers); the
  reference implementation in `engine/src/hashing.rs` *is* the definition.

## SAS schema (`governance_decision_v1`)

`action_hash:String, policy_hash:String, decision:String, reason_code:String,
agent_id:String, ts:u64` (layout `[12,12,12,12,12,3]`). The compact `reason_code` is the
sorted rule_ids joined by `,`; the full reasons stay off-chain and are re-derivable from
`(action, policy)`.

## Bounded SMT proof (optional, feature `smt`)

`engine/src/smt.rs` (off by default) proves one example property with Z3: over any
sequence of up to N individually-approvable payments,

- with only the `MAX_AMOUNT` rule, Z3 finds a **concrete counterexample** that drains the
  reserve below `min_reserve` (SAT) — a per-payment cap alone does not protect the reserve;
- adding the `RESERVE_INVARIANT` rule makes it **UNSAT** — proof that the per-action rule
  preserves the global invariant.

Z3 is vendored (`bundled`), so the binary needs no runtime `libz3`. Requires `cmake` at
build time.

```bash
cd engine
cargo test --features smt --test smt_tests    # 4 tests
cargo run  --features smt --example smt_demo   # prints the counterexample, then UNSAT
```

This is one honest example, not a general verifier. It verifies a property of the
action/state space — still zero LLM in the decision path.

**Payment integration.** When the engine runs with `--features smt`, every Payment verdict
also carries this proof (over the rate-limit horizon) as `verdict.smt`, shown in the UI as
positive assurance ("reserve invariant proven") plus the counterfactual that explains why
the rule exists. It is INFORMATIONAL — it never changes the decision, because the reserve
invariant is already enforced per-action. The engine's `/health` reports `smt: true/false`.

> Note: `cargo build`/`cargo test` (no features) overwrite the shared debug binary. To run
> the SMT engine after a plain build, force a relink: `rm target/debug/aegis_gate_engine &&
> cargo run --features smt`.

## Not implemented (by design)

- **Batching** attestations via state compression — extension point only.
