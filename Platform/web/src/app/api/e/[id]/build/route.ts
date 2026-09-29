import { NextRequest } from "next/server";
import { load, payload, bad, actor } from "@/lib/server/api";
import { runBuild, statuses } from "@/lib/server/lib";

// Runs the generic, config-free build for a live engagement: transform, model and report, entirely in Python,
// no Power BI Desktop involved. The result is recorded on the engagement whether it passed or failed.
export async function POST(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const r = await load(params, req);
  if (!r) return bad("Engagement not found.", 404);
  const { e, role } = r;
  if (role !== "owner") return bad("Only the owner can run the build.", 403);
  if (e.mode === "demo") return bad("The sample engagement is read-only.", 403);
  if (statuses(e).build === "locked") return bad("This step is locked until the steps before it are done.", 403);
  const result = await runBuild(e, actor(req));
  // A preflight rejection never touched e.build, so any earlier build result on the engagement is stale for this
  // attempt and must not be returned as if it were current -- always surface the rejection instead.
  if (!result.ok && result.preflight) return bad(result.error || "The build could not run.");
  return Response.json(payload(e));
}
