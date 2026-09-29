import { NextRequest } from "next/server";
import { listEngagements, createEngagement } from "@/lib/server/lib";
import { actor, bad } from "@/lib/server/api";
import { STEPS, roleOf } from "@/lib/steps";

export async function GET(req: NextRequest) {
  const who = actor(req);
  const list = listEngagements(who).map((e) => ({
    id: e.id, name: e.name, customer: e.customer, mode: e.mode, created: e.created,
    role: roleOf(e, who),
    doneCount: STEPS.filter((s) => e.done[s.key]).length, total: STEPS.length,
    next: STEPS.find((s) => !e.done[s.key])?.title ?? "Complete",
  }));
  return Response.json({ engagements: list });
}

export async function POST(req: NextRequest) {
  const b = await req.json().catch(() => ({}));
  const name = String(b.name || "").trim();
  const customer = String(b.customer || "").trim();
  if (name.length < 3) return bad("Give the engagement a name of at least 3 characters.");
  return Response.json({ ok: true, engagement: createEngagement(name, customer || name, actor(req)) });
}
