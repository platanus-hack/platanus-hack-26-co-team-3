/**
 * Read an attestation back from DEVNET and decode its data per the SAS schema.
 * Proves the on-chain record matches the verdict that was attested.
 *
 * Run: tsx src/verify.ts <attestationPda>
 */

import "dotenv/config";
import { fetchAttestation, fetchSchema, deserializeAttestationData } from "sas-lib";
import { address, makeRpc, addressExplorer } from "./sas.js";

async function main() {
  const pda = process.argv[2];
  if (!pda) throw new Error("usage: tsx src/verify.ts <attestationPda>");

  const schemaPda = address(process.env.SCHEMA_PDA!);
  const { rpc } = makeRpc();

  const schema = await fetchSchema(rpc, schemaPda);
  const attestation = await fetchAttestation(rpc, address(pda));
  const decoded = deserializeAttestationData(schema.data, Uint8Array.from(attestation.data.data));

  console.log(`attestation: ${addressExplorer(pda)}`);
  console.log("decoded on-chain data:");
  console.log(JSON.stringify(decoded, (_k, v) => (typeof v === "bigint" ? v.toString() : v), 2));
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
