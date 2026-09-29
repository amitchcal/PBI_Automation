import fs from "node:fs";
import path from "node:path";
import { NextRequest } from "next/server";
import { load, payload, bad, actor } from "@/lib/server/api";
import { engDir, PLATFORM, runPython, saveEngagement, audit, readJson, statuses } from "@/lib/server/lib";
import type { Issue } from "@/lib/steps";

export async function POST(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const r = await load(params, req);
  if (!r) return bad("Engagement not found.", 404);
  const { e, role } = r;
  if (role !== "owner") return bad("Only the owner can do this.", 403);
  if (e.mode === "demo") return bad("The sample engagement is read-only.", 403);
  if (statuses(e).data === "locked") return bad("This step is locked until the steps before it are done.", 403);
  if (!e.files.length) return bad("Upload at least one file first.");

  const work = path.join(engDir(e.id), "work");
  fs.mkdirSync(work, { recursive: true });
  const cfg = {
    engagement: { id: e.id, name: e.name },
    data_root: path.join(engDir(e.id), "uploads"),
    sources: e.files.map((f) => ({
      id: f.name.replace(/\.[^.]+$/, "").replace(/[^A-Za-z0-9_]/g, "_").toLowerCase(),
      path: f.name,
      type: f.name.toLowerCase().endsWith(".xlsx") ? "xlsx" : "csv",
    })),
    profiling: { max_top_values: 30 },
  };
  const cfgPath = path.join(work, "profile_config.json");
  fs.writeFileSync(cfgPath, JSON.stringify(cfg, null, 2));
  // Written under the kit's own outputs/<id>/profile, the same place every other agent (transform, model,
  // the config generator) expects to find it -- not under the web app's own data folder.
  const out = path.join(PLATFORM, "outputs", e.id, "profile");

  // The real profiling agent from the kit reads the files and writes profile.json and issues.json.
  const run = await runPython([path.join(PLATFORM, "kit", "profiling", "profile_agent.py"), cfgPath, out], PLATFORM);
  if (run.code !== 0) {
    e.profile = {
      ran: new Date().toISOString(), sources: [], issues: [],
      error: (run.stderr || run.stdout).split("\n").filter(Boolean).slice(-3).join(" ") || "The files could not be read.",
    };
    audit(e.id, actor(req), "file check failed", e.profile.error);
    saveEngagement(e);
    return Response.json(payload(e));
  }
  const prof = readJson<{ sources: Record<string, { rows: number; columns_count: number; duplicate_rows: number }> }>(path.join(out, "profile.json"));
  const issues = readJson<Issue[]>(path.join(out, "issues.json"));
  e.profile = {
    ran: new Date().toISOString(),
    sources: Object.entries(prof.sources).map(([id, s]) => ({ id, rows: s.rows, columns: s.columns_count, duplicate_rows: s.duplicate_rows })),
    issues,
  };
  e.decisions = {};
  audit(e.id, actor(req), "files checked", `${e.profile.sources.length} files, ${issues.length} findings, ${issues.filter((i) => i.needs_decision).length} need a decision`);
  saveEngagement(e);
  return Response.json(payload(e));
}
