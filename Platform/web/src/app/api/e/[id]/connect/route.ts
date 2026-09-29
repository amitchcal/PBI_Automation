import fs from "node:fs";
import path from "node:path";
import { NextRequest } from "next/server";
import { load, payload, bad, actor } from "@/lib/server/api";
import { engDir, PLATFORM, runPython, saveEngagement, audit, statuses } from "@/lib/server/lib";
import { encryptConfig, decryptConfig } from "@/lib/server/secrets";
import type { SourceKind } from "@/lib/steps";

// Story I-06: connect to a database or a network data source instead of uploading a file. This one route covers
// all three actions on a connection: try it without saving anything ("test"), save it and pull one file from it
// ("pull"), and forget it ("remove"). The kit's own db_connect.py does the actual connecting -- see that file for
// why SQLite and HTTP were the two kinds chosen, and how read-only access is enforced, not just asked for.
const CONNECT_DIR = path.join(PLATFORM, "kit", "connect");
const SCRIPT = path.join(CONNECT_DIR, "db_connect.py");

function slug(s: string) {
  return (s || "source").toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "").slice(0, 40) || "source";
}

async function runConnector(action: "test" | "pull", kind: SourceKind, config: Record<string, unknown>, outPath?: string) {
  const args = [SCRIPT, action, ...(outPath ? [outPath] : [])];
  const r = await runPython(args, CONNECT_DIR, JSON.stringify({ kind, ...config }));
  try { return JSON.parse(r.stdout.trim().split("\n").pop() || "{}"); }
  catch { return { ok: false, error: (r.stderr || r.stdout).split("\n").filter(Boolean).slice(-3).join(" ") || "The connector did not return a result." }; }
}

export async function POST(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const r = await load(params, req);
  if (!r) return bad("Engagement not found.", 404);
  const { e, role } = r;
  if (role !== "owner") return bad("Only the owner can manage data connections.", 403);
  if (e.mode === "demo") return bad("The sample engagement is read-only.", 403);
  if (statuses(e).data === "locked") return bad("This step is locked until the steps before it are done.", 403);

  const body = (await req.json().catch(() => null)) as Record<string, unknown> | null;
  if (!body || typeof body.op !== "string") return bad("Missing action.");
  const who = actor(req);

  if (body.op === "test") {
    const kind = body.kind as SourceKind; const config = (body.config || {}) as Record<string, unknown>;
    if (kind !== "sqlite" && kind !== "http") return bad("Unknown source kind.");
    const result = await runConnector("test", kind, config);
    audit(e.id, who, "data connection tested", `${kind}: ${result.ok ? "ok" : result.error}`);
    return Response.json(result);
  }

  if (body.op === "pull") {
    const kind = body.kind as SourceKind; const config = (body.config || {}) as Record<string, unknown>;
    const label = String(body.label || kind).trim() || kind;
    if (kind !== "sqlite" && kind !== "http") return bad("Unknown source kind.");
    const uploads = path.join(engDir(e.id), "uploads");
    fs.mkdirSync(uploads, { recursive: true });
    let name = `${slug(label)}.csv`; let n = 2;
    while (fs.existsSync(path.join(uploads, name))) name = `${slug(label)}_${n++}.csv`;
    const outPath = path.join(uploads, name);
    const result = await runConnector("pull", kind, config, outPath);
    if (!result.ok) { audit(e.id, who, "data connection pull failed", `${kind}: ${result.error}`); return bad(result.error || "The pull failed."); }
    // an .xlsx source is written next to the suggested .csv path with its own extension (see db_connect.py); if
    // that happened, point the file record at the file that actually exists
    const realName = fs.existsSync(outPath) ? name : name.replace(/\.csv$/, ".xlsx");
    const stat = fs.statSync(path.join(uploads, realName));
    e.files = e.files.filter((f) => f.name !== realName);
    e.files.push({ name: realName, size: stat.size, uploaded: new Date().toISOString() });
    delete e.profile;
    const conn = { id: `c${Date.now()}`, kind, label, config: encryptConfig(kind, config), lastTest: { at: new Date().toISOString(), ok: true }, pulledAs: realName, pulledAt: new Date().toISOString() };
    e.connections = [...(e.connections || []), conn];
    audit(e.id, who, "data pulled from a connection", `${kind} → ${realName}${result.rows != null ? ` (${result.rows} rows)` : ""}`);
    saveEngagement(e);
    return Response.json(payload(e));
  }

  if (body.op === "repull") {
    const id = String(body.connectionId || "");
    const conn = (e.connections || []).find((c) => c.id === id);
    if (!conn) return bad("That connection was not found.");
    const config = decryptConfig(conn.kind, conn.config);
    const uploads = path.join(engDir(e.id), "uploads");
    const outPath = path.join(uploads, conn.pulledAs || `${slug(conn.label)}.csv`);
    const result = await runConnector("pull", conn.kind, config, outPath);
    if (!result.ok) { conn.lastTest = { at: new Date().toISOString(), ok: false, error: result.error }; saveEngagement(e); audit(e.id, who, "data re-pull failed", `${conn.kind}: ${result.error}`); return bad(result.error || "The pull failed."); }
    const stat = fs.statSync(path.join(uploads, conn.pulledAs!));
    e.files = e.files.filter((f) => f.name !== conn.pulledAs);
    e.files.push({ name: conn.pulledAs!, size: stat.size, uploaded: new Date().toISOString() });
    delete e.profile;
    conn.lastTest = { at: new Date().toISOString(), ok: true }; conn.pulledAt = new Date().toISOString();
    audit(e.id, who, "data re-pulled from a connection", `${conn.kind} → ${conn.pulledAs}${result.rows != null ? ` (${result.rows} rows)` : ""}`);
    saveEngagement(e);
    return Response.json(payload(e));
  }

  if (body.op === "remove") {
    const id = String(body.connectionId || "");
    const conn = (e.connections || []).find((c) => c.id === id);
    if (!conn) return bad("That connection was not found.");
    if (conn.pulledAs) {
      e.files = e.files.filter((f) => f.name !== conn.pulledAs);
      const p = path.join(engDir(e.id), "uploads", conn.pulledAs);
      if (fs.existsSync(p)) fs.rmSync(p);
      delete e.profile;
    }
    e.connections = e.connections.filter((c) => c.id !== id);
    audit(e.id, who, "data connection removed", `${conn.kind}: ${conn.label}`);
    saveEngagement(e);
    return Response.json(payload(e));
  }

  return bad("Unknown action.");
}
