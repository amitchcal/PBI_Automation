import { NextRequest } from "next/server";
import { getEngagement, statuses, currentStep } from "@/lib/server/lib";
import { roleOf, type Role, type Engagement } from "@/lib/steps";
import { redactConfig } from "@/lib/server/secrets";

export const actor = (req: NextRequest) => req.headers.get("x-actor")?.slice(0, 60) || "Amit Chakraborty";
export const bad = (error: string, status = 400) => Response.json({ ok: false, error }, { status });

// Story W-03: every route that loads an engagement goes through here, so access is checked in one place rather
// than trusted to be repeated correctly in nine separate route files. Not found and not-yours both come back as
// a plain 404 -- an engagement that isn't yours to see should not even confirm it exists.
export async function load(params: Promise<{ id: string }>, req: NextRequest) {
  const { id } = await params;
  const e = getEngagement(id);
  if (!e) return null;
  const role: Role | null = roleOf(e, actor(req));
  if (!role) return null;
  return { e, id, role };
}

// Every route sends the engagement back to the browser through this one function -- redacting each data
// connection's secret fields here, rather than in every route that might touch one, is what makes it safe to
// assume a stored password or token never actually reaches the client (story I-06). The encrypted value on disk
// is replaced with dots, not sent even in its encrypted form, and the original object is never mutated (routes
// may still save it after calling this).
export const payload = (e: Engagement) => ({
  ok: true,
  engagement: { ...e, connections: (e.connections || []).map((c) => ({ ...c, config: redactConfig(c.kind, c.config) })) },
  statuses: statuses(e), current: currentStep(e),
});
