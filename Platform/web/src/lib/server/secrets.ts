// Story I-06: "credentials stored securely" -- a data source's password or token is encrypted at rest (AES-256-GCM)
// with a key generated on this machine the first time it's needed, so reading state.json off disk does not hand
// over a plain-text password. This is proportionate to a local prototype, not a hardened secrets vault: the key
// itself lives on the same disk (there is no separate vault or KMS to hold it in this deployment), so it protects
// against a stray read of the data folder, a backup copied elsewhere, or a screen-share -- not against someone
// with full access to this machine's filesystem. Real deployment should move the key to the platform's own secret
// store (environment variable, cloud KMS, etc.); that swap only touches this one file.
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { WEB } from "@/lib/server/lib";

const KEY_PATH = path.join(WEB, "data", ".secret.key");

function key(): Buffer {
  fs.mkdirSync(path.dirname(KEY_PATH), { recursive: true });
  if (!fs.existsSync(KEY_PATH)) fs.writeFileSync(KEY_PATH, crypto.randomBytes(32));
  return fs.readFileSync(KEY_PATH);
}

const PREFIX = "enc:v1:";

export function encrypt(plain: string): string {
  const iv = crypto.randomBytes(12);
  const cipher = crypto.createCipheriv("aes-256-gcm", key(), iv);
  const ct = Buffer.concat([cipher.update(plain, "utf8"), cipher.final()]);
  const tag = cipher.getAuthTag();
  return PREFIX + Buffer.concat([iv, tag, ct]).toString("base64");
}

export function decrypt(stored: string): string {
  if (!stored.startsWith(PREFIX)) throw new Error("Not an encrypted value.");
  const buf = Buffer.from(stored.slice(PREFIX.length), "base64");
  const iv = buf.subarray(0, 12), tag = buf.subarray(12, 28), ct = buf.subarray(28);
  const decipher = crypto.createDecipheriv("aes-256-gcm", key(), iv);
  decipher.setAuthTag(tag);
  return Buffer.concat([decipher.update(ct), decipher.final()]).toString("utf8");
}

export const isEncrypted = (v: unknown): v is string => typeof v === "string" && v.startsWith(PREFIX);

// Fields that hold a secret, per source kind -- encrypted on save, decrypted only in memory right before the
// Python connector runs, and never sent back to the browser (see connect/route.ts, which strips them from every
// response).
export const SECRET_FIELDS: Record<string, string[]> = { sqlite: [], http: ["password", "bearer"] };

export function encryptConfig(kind: string, config: Record<string, unknown>): Record<string, unknown> {
  const out = { ...config };
  for (const f of SECRET_FIELDS[kind] || []) {
    const v = out[f];
    if (typeof v === "string" && v && !isEncrypted(v)) out[f] = encrypt(v);
  }
  return out;
}

export function decryptConfig(kind: string, config: Record<string, unknown>): Record<string, unknown> {
  const out = { ...config };
  for (const f of SECRET_FIELDS[kind] || []) {
    const v = out[f];
    if (isEncrypted(v)) out[f] = decrypt(v);
  }
  return out;
}

export function redactConfig(kind: string, config: Record<string, unknown>): Record<string, unknown> {
  const out = { ...config };
  for (const f of SECRET_FIELDS[kind] || []) if (out[f]) out[f] = "••••••••";
  return out;
}
