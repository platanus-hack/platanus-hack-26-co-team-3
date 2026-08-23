/**
 * Aegis Gate — SAS (Solana Attestation Service) plumbing, DEVNET ONLY.
 *
 * Shared helpers for setup.ts and server.ts:
 *   - RPC + subscriptions wired to devnet
 *   - issuer signer load/generate
 *   - a generic "sign, send, confirm" for a list of instructions
 *
 * Nothing here touches mainnet. Cluster is hard-pinned to devnet below.
 */

import {
  address,
  airdropFactory,
  appendTransactionMessageInstructions,
  createKeyPairSignerFromBytes,
  createSolanaRpc,
  createSolanaRpcSubscriptions,
  getSignatureFromTransaction,
  lamports,
  pipe,
  sendAndConfirmTransactionFactory,
  setTransactionMessageFeePayerSigner,
  setTransactionMessageLifetimeUsingBlockhash,
  createTransactionMessage,
  signTransactionMessageWithSigners,
  type Address,
  type IInstruction,
  type KeyPairSigner,
} from "@solana/kit";

export const DEVNET_HTTP = "https://api.devnet.solana.com";
export const DEVNET_WS = "wss://api.devnet.solana.com";
export const EXPLORER_CLUSTER = "?cluster=devnet";

export type Rpc = ReturnType<typeof createSolanaRpc>;
export type RpcSubs = ReturnType<typeof createSolanaRpcSubscriptions>;

export function makeRpc(): { rpc: Rpc; rpcSubscriptions: RpcSubs } {
  return {
    rpc: createSolanaRpc(DEVNET_HTTP),
    rpcSubscriptions: createSolanaRpcSubscriptions(DEVNET_WS),
  };
}

/** Load the issuer signer from a base64-encoded 64-byte secret key (env), or generate one. */
export async function loadIssuerFromEnv(): Promise<KeyPairSigner> {
  const b64 = process.env.ISSUER_SECRET_B64;
  if (!b64) {
    throw new Error("ISSUER_SECRET_B64 is not set — run `npm run setup` first.");
  }
  const bytes = Uint8Array.from(Buffer.from(b64, "base64"));
  return createKeyPairSignerFromBytes(bytes);
}

/**
 * Generate an issuer signer whose 64-byte secret (Solana format: 32-byte seed +
 * 32-byte pubkey) can be persisted. kit's own `generateKeyPairSigner` produces a
 * non-extractable key, so we mint the ed25519 material with Node's crypto and hand
 * the portable secret to kit. Devnet only — this key sponsors nothing on mainnet.
 */
export async function generateIssuer(): Promise<{ signer: KeyPairSigner; secretB64: string }> {
  const { generateKeyPairSync } = await import("node:crypto");
  const { privateKey } = generateKeyPairSync("ed25519");
  const jwk = privateKey.export({ format: "jwk" }) as { d: string; x: string };
  const seed = Buffer.from(jwk.d, "base64url"); // 32 bytes
  const pub = Buffer.from(jwk.x, "base64url"); // 32 bytes
  const secret64 = Buffer.concat([seed, pub]); // 64 bytes (Solana keypair format)
  const signer = await createKeyPairSignerFromBytes(new Uint8Array(secret64));
  return { signer, secretB64: secret64.toString("base64") };
}

/** Airdrop `sol` SOL to `to` on devnet and confirm. */
export async function airdrop(
  rpc: Rpc,
  rpcSubscriptions: RpcSubs,
  to: Address,
  sol: number,
): Promise<void> {
  const fn = airdropFactory({ rpc, rpcSubscriptions });
  await fn({
    recipientAddress: to,
    lamports: lamports(BigInt(Math.round(sol * 1_000_000_000))),
    commitment: "confirmed",
  });
}

/** Build, sign, send and confirm a transaction carrying `instructions`. Returns the signature. */
export async function sendInstructions(
  rpc: Rpc,
  rpcSubscriptions: RpcSubs,
  feePayer: KeyPairSigner,
  instructions: IInstruction[],
): Promise<string> {
  const { value: latestBlockhash } = await rpc.getLatestBlockhash().send();
  const message = pipe(
    createTransactionMessage({ version: 0 }),
    (m) => setTransactionMessageFeePayerSigner(feePayer, m),
    (m) => setTransactionMessageLifetimeUsingBlockhash(latestBlockhash, m),
    (m) => appendTransactionMessageInstructions(instructions, m),
  );
  const signed = await signTransactionMessageWithSigners(message);
  const send = sendAndConfirmTransactionFactory({ rpc, rpcSubscriptions });
  await send(signed, { commitment: "confirmed" });
  return getSignatureFromTransaction(signed);
}

export function txExplorer(signature: string): string {
  return `https://explorer.solana.com/tx/${signature}${EXPLORER_CLUSTER}`;
}

export function addressExplorer(addr: string): string {
  return `https://explorer.solana.com/address/${addr}${EXPLORER_CLUSTER}`;
}

export { address, type Address, type KeyPairSigner };
