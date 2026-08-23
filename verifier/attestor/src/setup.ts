/**
 * One-time SAS setup on DEVNET.
 *
 *   1. Load or generate the issuer (gate authority) keypair.
 *   2. Airdrop devnet SOL to it.
 *   3. Create the Credential (issuer authority).
 *   4. Create the Schema `governance_decision_v1`.
 *   5. Persist ISSUER_SECRET_B64 / CREDENTIAL_PDA / SCHEMA_PDA to attestor/.env.
 *
 * Idempotent: existing credential/schema accounts are detected and skipped, so this
 * can be re-run safely. Devnet only.
 *
 * Run: npm run setup
 */

import { writeFileSync, existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import "dotenv/config";
import {
  deriveCredentialPda,
  deriveSchemaPda,
  fetchMaybeCredential,
  fetchMaybeSchema,
  getCreateCredentialInstruction,
  getCreateSchemaInstruction,
} from "sas-lib";
import {
  addressExplorer,
  airdrop,
  generateIssuer,
  loadIssuerFromEnv,
  makeRpc,
  sendInstructions,
} from "./sas.js";

const CREDENTIAL_NAME = "aegis-gate-issuer";
const SCHEMA_NAME = "governance_decision_v1";
const SCHEMA_VERSION = 1;

// Schema fields (order matters — layout & fieldNames are index-aligned):
//   action_hash  String  -> 12
//   policy_hash  String  -> 12
//   decision     String  -> 12
//   reason_code  String  -> 12
//   agent_id     String  -> 12
//   ts           u64     -> 3
const SCHEMA_FIELD_NAMES = ["action_hash", "policy_hash", "decision", "reason_code", "agent_id", "ts"];
const SCHEMA_LAYOUT = new Uint8Array([12, 12, 12, 12, 12, 3]);

const __dirname = dirname(fileURLToPath(import.meta.url));
const ENV_PATH = join(__dirname, "..", ".env");

function persistEnv(entries: Record<string, string>) {
  const existing: Record<string, string> = {};
  if (existsSync(ENV_PATH)) {
    for (const line of readFileSync(ENV_PATH, "utf8").split("\n")) {
      const m = line.match(/^([A-Z0-9_]+)=(.*)$/);
      if (m) existing[m[1]] = m[2];
    }
  }
  const merged = { ...existing, ...entries };
  const body = Object.entries(merged).map(([k, v]) => `${k}=${v}`).join("\n") + "\n";
  writeFileSync(ENV_PATH, body);
  console.log(`  wrote ${ENV_PATH}`);
}

async function main() {
  const { rpc, rpcSubscriptions } = makeRpc();

  // 1. Issuer (reuse if already persisted).
  let issuer;
  let secretB64 = process.env.ISSUER_SECRET_B64;
  if (secretB64) {
    issuer = await loadIssuerFromEnv();
    console.log(`issuer (reused): ${issuer.address}`);
  } else {
    const gen = await generateIssuer();
    issuer = gen.signer;
    secretB64 = gen.secretB64;
    console.log(`issuer (new): ${issuer.address}`);
  }

  // 2. Airdrop if balance is low.
  const { value: balance } = await rpc.getBalance(issuer.address).send();
  console.log(`  balance: ${Number(balance) / 1e9} SOL`);
  if (Number(balance) < 0.5e9) {
    console.log("  requesting airdrop (2 SOL)...");
    await airdrop(rpc, rpcSubscriptions, issuer.address, 2);
  }

  // 3. Credential.
  const [credentialPda] = await deriveCredentialPda({ authority: issuer.address, name: CREDENTIAL_NAME });
  const maybeCred = await fetchMaybeCredential(rpc, credentialPda);
  if (maybeCred.exists) {
    console.log(`credential (exists): ${credentialPda}`);
  } else {
    const ix = getCreateCredentialInstruction({
      payer: issuer,
      credential: credentialPda,
      authority: issuer,
      name: CREDENTIAL_NAME,
      signers: [issuer.address],
    });
    const sig = await sendInstructions(rpc, rpcSubscriptions, issuer, [ix]);
    console.log(`credential (created): ${credentialPda}`);
    console.log(`  tx: ${sig}`);
  }

  // 4. Schema.
  const [schemaPda] = await deriveSchemaPda({
    credential: credentialPda,
    name: SCHEMA_NAME,
    version: SCHEMA_VERSION,
  });
  const maybeSchema = await fetchMaybeSchema(rpc, schemaPda);
  if (maybeSchema.exists) {
    console.log(`schema (exists): ${schemaPda}`);
  } else {
    const ix = getCreateSchemaInstruction({
      payer: issuer,
      authority: issuer,
      credential: credentialPda,
      schema: schemaPda,
      name: SCHEMA_NAME,
      description: "Aegis Gate deterministic action verdict (action_hash, policy_hash, decision, reason_code, agent_id, ts)",
      layout: SCHEMA_LAYOUT,
      fieldNames: SCHEMA_FIELD_NAMES,
    });
    const sig = await sendInstructions(rpc, rpcSubscriptions, issuer, [ix]);
    console.log(`schema (created): ${schemaPda}`);
    console.log(`  tx: ${sig}`);
  }

  // 5. Persist.
  persistEnv({
    ISSUER_SECRET_B64: secretB64!,
    CREDENTIAL_PDA: credentialPda,
    SCHEMA_PDA: schemaPda,
    CREDENTIAL_NAME,
    SCHEMA_NAME,
    SCHEMA_VERSION: String(SCHEMA_VERSION),
  });

  console.log("\nsetup complete (devnet).");
  console.log(`  credential: ${addressExplorer(credentialPda)}`);
  console.log(`  schema:     ${addressExplorer(schemaPda)}`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
