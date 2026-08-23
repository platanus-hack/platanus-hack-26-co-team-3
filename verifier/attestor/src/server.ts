/**
 * Attestor HTTP server (hono) — POST /attest on :8090, DEVNET ONLY.
 *
 * Receives a Verdict (+ agent_id, ts), serializes it per the SAS schema, derives the
 * attestation PDA, builds the create-attestation instruction, and sends it to devnet.
 * Returns { attestationPda, txSignature, explorerUrl }.
 *
 * We attest EVERY decision — Allow, Review AND Block. Proving a dangerous action was
 * stopped is the whole point, so a Block is worth anchoring on-chain too.
 *
 * Run: npm run dev
 */

import "dotenv/config";
import { serve } from "@hono/node-server";
import { Hono } from "hono";
import { cors } from "hono/cors";
import {
  deriveAttestationPda,
  fetchSchema,
  getCreateAttestationInstruction,
  serializeAttestationData,
} from "sas-lib";
import {
  address,
  loadIssuerFromEnv,
  makeRpc,
  sendInstructions,
  txExplorer,
  type Address,
  type KeyPairSigner,
} from "./sas.js";
import { getBase58Decoder } from "@solana/kit";

type Verdict = {
  decision: "Allow" | "Review" | "Block";
  reasons: { rule_id: string; detail: string }[];
  action_hash: string;
  policy_hash: string;
  engine_version: string;
  ruleset_hash: string;
};

type AttestRequest = { verdict: Verdict; agent_id: string; ts: number };

// Derive a compact on-chain reason_code from the verdict's reasons (deterministic):
// the sorted rule_ids joined by ",". The full reasons stay off-chain, re-derivable
// from (action, policy) via the engine. Capped so it never blows the field.
function reasonCode(v: Verdict): string {
  const code = v.reasons.map((r) => r.rule_id).join(",");
  return code.length > 200 ? code.slice(0, 200) : code;
}

// A random 32-byte nonce so each attestation gets a unique PDA (MVP = one attestation
// per decision; avoids "account already exists" on repeated demo clicks).
function randomNonce(): Address {
  const bytes = new Uint8Array(32);
  globalThis.crypto.getRandomValues(bytes);
  return address(getBase58Decoder().decode(bytes));
}

async function main() {
  const credentialPda = address(requireEnv("CREDENTIAL_PDA"));
  const schemaPda = address(requireEnv("SCHEMA_PDA"));
  const { rpc, rpcSubscriptions } = makeRpc();
  const issuer: KeyPairSigner = await loadIssuerFromEnv();

  // Fetch the schema once — its layout drives attestation-data serialization.
  const schema = await fetchSchema(rpc, schemaPda);

  const app = new Hono();
  app.use("*", cors());

  app.get("/health", (c) =>
    c.json({ status: "ok", issuer: issuer.address, credentialPda, schemaPda, cluster: "devnet" }),
  );

  app.post("/attest", async (c) => {
    let body: AttestRequest;
    try {
      body = await c.req.json();
    } catch {
      return c.json({ error: "invalid JSON body" }, 400);
    }
    const { verdict, agent_id, ts } = body ?? ({} as AttestRequest);
    if (!verdict || !agent_id || typeof ts !== "number") {
      return c.json({ error: "body must be { verdict, agent_id, ts:number }" }, 400);
    }

    try {
      const data = serializeAttestationData(schema.data, {
        action_hash: verdict.action_hash,
        policy_hash: verdict.policy_hash,
        decision: verdict.decision,
        reason_code: reasonCode(verdict),
        agent_id,
        ts: BigInt(ts),
      });

      const nonce = randomNonce();
      const [attestationPda] = await deriveAttestationPda({
        credential: credentialPda,
        schema: schemaPda,
        nonce,
      });

      const ix = getCreateAttestationInstruction({
        payer: issuer,
        authority: issuer, // authorized signer on the credential
        credential: credentialPda,
        schema: schemaPda,
        attestation: attestationPda,
        nonce,
        data,
        expiry: 0n, // no expiry
      });

      const txSignature = await sendInstructions(rpc, rpcSubscriptions, issuer, [ix]);

      return c.json({
        attestationPda,
        txSignature,
        explorerUrl: txExplorer(txSignature),
        decision: verdict.decision,
        cluster: "devnet",
      });
    } catch (e) {
      console.error("attest failed:", e);
      return c.json({ error: String(e) }, 500);
    }
  });

  const port = Number(process.env.ATTESTOR_PORT ?? 8090);
  serve({ fetch: app.fetch, port });
  console.log(`aegis-gate attestor on http://127.0.0.1:${port} (devnet)`);
  console.log(`  issuer:     ${issuer.address}`);
  console.log(`  credential: ${credentialPda}`);
  console.log(`  schema:     ${schemaPda}`);
}

function requireEnv(k: string): string {
  const v = process.env[k];
  if (!v) throw new Error(`${k} is not set — run \`npm run setup\` first.`);
  return v;
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
