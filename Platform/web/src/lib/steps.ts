// The fixed order of an engagement. Every step is mandatory and a step opens only when the one before it is done.
export type StepKey =
  | "consent" | "questionnaire" | "brand" | "data" | "summary" | "issues"
  | "kpis" | "segments" | "build" | "review" | "accept" | "publish";

export interface StepMeta {
  key: StepKey;
  n: number;
  title: string;
  blurb: string;      // one line, plain language
  who: "You" | "Automatic" | "Both";
  minutes: string;
}

export const STEPS: StepMeta[] = [
  { key: "consent", n: 1, title: "Agreement", who: "You", minutes: "2 min", blurb: "Confirm confidentiality, AI use and data handling before anything is uploaded." },
  { key: "questionnaire", n: 2, title: "Your needs", who: "You", minutes: "15 min", blurb: "Tell us the problem, the audience, the numbers you care about and any security needs." },
  { key: "brand", n: 3, title: "Look and feel", who: "You", minutes: "5 min", blurb: "Set your logo, colours and layout. We check the colours are readable." },
  { key: "data", n: 4, title: "Your data", who: "Both", minutes: "5 min", blurb: "Upload your files. We read them and check them straight away." },
  { key: "summary", n: 5, title: "Confirm the plan", who: "You", minutes: "5 min", blurb: "Review what will be built, and anything missing or contradictory." },
  { key: "issues", n: 6, title: "Data decisions", who: "You", minutes: "10 min", blurb: "Decide how to handle each problem found in your data. A recommended answer is pre-selected." },
  { key: "kpis", n: 7, title: "KPI definitions", who: "You", minutes: "10 min", blurb: "Approve the plain-words meaning of every number that will appear." },
  { key: "segments", n: 8, title: "Customer groups", who: "You", minutes: "5 min", blurb: "Approve the groups (for example age bands) and see how big each is." },
  { key: "build", n: 9, title: "Build", who: "Automatic", minutes: "about 30 min", blurb: "The model, measures, report and documents are built and checked against independent numbers." },
  { key: "review", n: 10, title: "Draft review", who: "You", minutes: "30 min", blurb: "Look at the first draft, the checks and the open questions, and send feedback." },
  { key: "accept", n: 11, title: "Acceptance", who: "You", minutes: "15 min", blurb: "Confirm key numbers against a source you trust, and sign off." },
  { key: "publish", n: 12, title: "Publish and hand over", who: "Both", minutes: "20 min", blurb: "Publish, test as a viewer, receive the pack, and record that working copies are removed." },
];

export const stepIndex = (k: StepKey) => STEPS.findIndex((s) => s.key === k);

// Story W-03: pure function (no server-only imports) so both the API routes and the client UI can compute the
// same answer -- the sample is a shared read-only reference open to anyone signed in.
export function roleOf(e: Pick<Engagement, "mode" | "owner" | "reviewers">, who: string): Role | null {
  if (e.mode === "demo") return "reviewer";
  if (e.owner === who) return "owner";
  if ((e.reviewers || []).includes(who)) return "reviewer";
  return null;
}

export interface Done { at: string; by: string; note?: string }

export type Role = "owner" | "reviewer";

export interface Engagement {
  id: string;
  name: string;
  customer: string;
  mode: "demo" | "live";
  created: string;
  owner: string;          // story W-03: the name that created it -- full access
  reviewers: string[];    // story W-03: names given read access plus draft-review feedback, nothing else
  done: Partial<Record<StepKey, Done>>;
  consent?: { ticks: boolean[]; name: string };
  questionnaire: Record<string, string>;
  brand?: { name: string; tagline: string; primary: string; secondary: string; accent: string; heading: string; body: string; template: string; logoFile?: string; approved?: boolean; customTemplateFile?: string };
  brandResult?: { ok: boolean; name?: string; checks?: { name: string; foreground: string; background: string; ratio: number; needed: number; pass: boolean; mandatory: boolean }[]; mandatory_failed?: string[]; errors?: string[]; theme_errors?: string[] };
  files: { name: string; size: number; uploaded: string }[];
  connections: DataConnection[];
  profile?: { ran: string; sources: { id: string; rows: number; columns: number; duplicate_rows: number }[]; issues: Issue[]; error?: string };
  decisions: Record<string, { decision: string; by: string; at: string }>;
  kpiApprovals: Record<string, { at: string; by: string }>;
  segmentsApproved?: { at: string; by: string };
  summaryConfirmed?: { at: string; by: string };
  feedback: { id: string; text: string; page: string; at: string; by: string; status: string }[];
  acceptance?: { ticks: boolean[]; name: string };
  handover?: { ticks: boolean[]; name: string };
  build?: BuildResult;
}

export interface BuildResult {
  ranAt: string;
  ok: boolean;
  stages: { name: string; ok: boolean; error?: string }[];
  tables: number;
  relationships: number;
  measures: number;
  pages: number;
  reviewItems: string[];
  modelPbip?: string;
  reportPbip?: string;
  desktopCheck?: DesktopCheckResult;
}

export interface DesktopCheckResult {
  ranAt: string;
  ok: boolean;
  modelChecks: { total: number; passed: number };
  reportOpened: boolean;
  refreshSeconds?: number;
  error?: string;
  mismatches: string[];
}

export interface Issue {
  id: string; kind: string; source: string; columns: string[]; severity: string; title: string; evidence: string;
  proposed_rule: string; options: string[]; needs_decision: boolean; examples: Record<string, unknown>[];
}

// Story I-06: connect to a database or network source instead of uploading a file. `config` holds whatever that
// kind needs (a SQLite path and query, or a URL and optional credentials); any secret field within it is
// encrypted at rest -- see lib/server/secrets.ts, the only place that reads or writes the real value.
export type SourceKind = "sqlite" | "http";
export interface DataConnection {
  id: string; kind: SourceKind; label: string; config: Record<string, unknown>;
  lastTest?: { at: string; ok: boolean; error?: string; preview?: unknown };
  pulledAs?: string; pulledAt?: string;
}

export const CONSENT_STATEMENTS = [
  "We have signed a confidentiality agreement covering our data, systems and the deliverables.",
  "We approve the use of an AI service to build this report, and we understand what data it can see.",
  "We understand that our data stays in the environment we choose, and that any sample we upload is ours to remove.",
  "We agree that our reusable materials stay ours, and that the builder's reusable tools stay theirs.",
];

export const ACCEPTANCE_ITEMS = [
  "I compared the headline numbers on the Overview page with a source I trust, and they agree.",
  "I checked a sample of customers or records by hand against the report.",
  "I read the list of assumptions and limitations and accept them.",
  "The report answers the questions in my needs form.",
];

export const HANDOVER_ITEMS = [
  "The report is published in our workspace and opens for a viewer.",
  "Slicers, drill-through and tooltips work in the published report.",
  "Scheduled refresh is set and one refresh has succeeded.",
  "We received the user guide, technical document and findings deck.",
  "The builder's working copies of our data have been deleted, and we have the deletion record.",
];

export interface QField { key: string; label: string; help: string; type: "text" | "textarea" | "select"; options?: string[]; required?: boolean; placeholder?: string }
export interface QSection { id: string; title: string; intro: string; fields: QField[] }

export const QUESTIONNAIRE: QSection[] = [
  { id: "need", title: "The problem", intro: "What are you trying to understand or decide?", fields: [
    { key: "problem", label: "What business problem should this dashboard help with?", help: "Write it as you would explain it to a colleague.", type: "textarea", required: true, placeholder: "For example: we send offers to customers and want to know which ones work and for whom." },
    { key: "decisions", label: "Which decisions will people make with it?", help: "For example: which offers to repeat, who to target next.", type: "textarea" },
    { key: "audience", label: "Who will use it most?", help: "Pick the closest.", type: "select", options: ["Executives", "Marketing team", "Operations", "Analysts", "A mix"], required: true },
    { key: "frequency", label: "How often will it be looked at?", help: "", type: "select", options: ["Daily", "Weekly", "Monthly", "Ad hoc"] },
  ] },
  { id: "kpis", title: "Numbers and insights", intro: "The numbers that matter to you, in your own definition.", fields: [
    { key: "kpis", label: "Your key numbers, one per line, with how you calculate each", help: "Format: name, then a dash, then the definition. We will show each back to you to approve.", type: "textarea", required: true, placeholder: "Redemption rate - offers completed divided by offers sent\nAverage order value - total spend divided by number of orders" },
    { key: "insights", label: "Which insights would you like the report to show?", help: "Comparisons, trends, best and worst performers, anything you are curious about.", type: "textarea" },
    { key: "targets", label: "Do you have targets or benchmarks?", help: "Optional.", type: "text" },
  ] },
  { id: "data", title: "Your data", intro: "Where the numbers come from.", fields: [
    { key: "sources", label: "Where does your data live?", help: "For example spreadsheets, a database, exported files, a system name.", type: "textarea", required: true },
    { key: "refresh", label: "How often does it change?", help: "", type: "select", options: ["Daily", "Weekly", "Monthly", "One-off"], required: true },
    { key: "data_owner", label: "Who owns the data?", help: "The person we ask if something looks wrong.", type: "text", required: true },
  ] },
  { id: "security", title: "Security and privacy", intro: "Who may see what.", fields: [
    { key: "who_sees", label: "Who should be allowed to see the report, and does anyone need a restricted view?", help: "For example: regional managers see only their region.", type: "textarea", required: true },
    { key: "rls", label: "Do different people need to see different rows of data?", help: "Also called row-level security.", type: "select", options: ["Yes", "No", "Not sure"], required: true },
    { key: "sensitive", label: "Is any field personal or sensitive?", help: "Names, phone numbers, health or financial details.", type: "text" },
  ] },
  { id: "publish", title: "Publishing", intro: "Where the finished report will live.", fields: [
    { key: "workspace", label: "Where will it be published?", help: "The Power BI workspace or team space.", type: "text", required: true },
    { key: "licences", label: "Which Power BI licence do viewers have?", help: "", type: "select", options: ["Pro", "Premium per user", "Fabric or Premium capacity", "Not sure"], required: true },
    { key: "restrictions", label: "Are any features blocked in your organisation?", help: "For example map visuals or sharing.", type: "text" },
    { key: "future", label: "Anything you would like to do next, after this first version?", help: "We keep this separate from the first delivery.", type: "textarea" },
  ] },
];

export const REQUIRED_Q = QUESTIONNAIRE.flatMap((s) => s.fields.filter((f) => f.required).map((f) => f.key));
