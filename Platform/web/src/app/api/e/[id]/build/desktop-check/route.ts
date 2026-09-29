import { NextRequest } from "next/server";
import { load, payload, bad, actor } from "@/lib/server/api";
import { runDesktopCheck, statuses } from "@/lib/server/lib";

// Explicit, separate from the automated build: this opens Power BI Desktop on the machine running the server
// and takes a few minutes, so it only runs when the person clicks a clearly-labelled button for it.
export async function POST(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const r = await load(params, req);
  if (!r) return bad("Engagement not found.", 404);
  const { e, role } = r;
  if (role !== "owner") return bad("Only the owner can run this (it opens Power BI Desktop on the builder's machine).", 403);
  if (e.mode === "demo") return bad("The sample engagement is read-only.", 403);
  if (statuses(e).build === "locked") return bad("This step is locked until the steps before it are done.", 403);
  const result = await runDesktopCheck(e, actor(req));
  if (!result.ok && result.preflight) return bad(result.error || "The Desktop check could not run.");
  return Response.json(payload(e));
}
