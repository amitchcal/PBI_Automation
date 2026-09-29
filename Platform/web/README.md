# Engagement Console (web interface prototype)

A guided, 12-step web interface that walks a non-technical user through a Power BI delivery engagement:
consent, questionnaire, brand kit, data upload, profiling, KPIs, segments, build, review, acceptance, publish.
Colours, logo and name come from the brand kit (`kit/brand`), so the same app is re-skinned per client.
A dummy "Meridian" kit is in use until a client supplies theirs.

## Run

```
cd Platform/web
npm install
npm run sync-brand      # regenerates src/app/brand.css and public/brand/* from the brand kit
npx next dev -p 3210    # http://localhost:3210
# or: npm run build && npx next start -p 3210
```

Requires Python on PATH (the console runs the profiling and brand agents from `Platform/kit`).

## What is real

| Area | Status |
|---|---|
| Step order enforcement, consent gate (uploads blocked until consent), validations per step | Real, enforced on the server |
| Append-only activity log (who, what, when) | Real (file-based) |
| File upload with type and size checks | Real |
| Data profiling on uploaded files | Real: runs `kit/profiling/profile_agent.py` |
| Brand kit build with contrast checks and Power BI theme validation | Real: runs `kit/brand/build_brand.py` |
| **Automated first-draft build for a new engagement** | Real: `POST /api/e/[id]/build` runs `kit/runner/generate_configs.py` then `kit/runner/run_build.py`, which chain `generic_transform.py` → `generic_model.py` → `report_agent.py` and produce a checked PBIP project (see below) |
| **Power BI Desktop check, from the web app** | Real: `POST /api/e/[id]/build/desktop-check` opens the generated project in Power BI Desktop, refreshes it and re-runs the same checks live in Power BI, not just in pandas |
| Sample engagement (RewardsNext, steps 1-9 done) | Real outputs: profile, decisions, checks, documents from the verified build |
| Review page checks table | Real: from the Desktop-verified 251 checks |

### What the automated first-draft build actually does

Tested end to end on an unrelated synthetic dataset (not RewardsNext) through the real web routes, not just the scripts directly:
- Passes every uploaded file through as one table, applying your data decisions where they map to a generic rule (an "unknown" sentinel value becomes a blank column; duplicate rows are kept-and-flagged or removed, as you chose).
- Detects relationships between files from the profiler's own orphan-free key matching -- no schema is assumed.
- Adds a row-count measure per table and a sum/average measure per numeric column, each checked against an independent pandas value (the same style of check as the RewardsNext build, just generic instead of hand-authored).
- Builds a report: one overview page of row-count cards, one table page per source, in your brand.
- Lists what it could *not* do automatically -- your own KPI formulas (it only lists them, it does not guess DAX for free-text definitions), structured/JSON-like columns, and anything else outside its generic rules -- as a review checklist on the Build page.

A separate, explicit button on the Build page ("Run Power BI Desktop check") then opens the actual generated project in Power BI Desktop on this computer, refreshes it and re-runs the same checks live in Power BI, not just in pandas. It's deliberately not automatic -- it takes over a Desktop window for a few minutes, so it only runs when someone clicks it and confirms. Verified end to end on the same synthetic dataset: 6 of 6 measures passed inside a real Desktop refresh, and the finished report project also opened cleanly.

While building this I found and fixed a real generality bug in `desktop_verify.ps1`: its post-refresh "did any rows actually load" probe was hardcoded to a RewardsNext-specific table name (`FactEvents`), so the script silently reported "no data was loaded" for any other engagement's schema even when the refresh had fully succeeded (confirmed directly against the live model in Desktop). Fixed with a `-ProbeTable` parameter (default unchanged, so RewardsNext's own behaviour is untouched).

The automated build does **not** build customer segments/groups (the Customer groups step lets you continue without them) or the documents/deck (`kit/docs/*.py` is still RewardsNext-specific).

## What is placeholder or not built

- **Sign-in** is a name typed into the browser. No passwords, roles or tenant isolation (backlog W-03). Do not expose beyond a trusted machine.
- **No install guide or clean-machine deploy** for the platform itself (backlog W-07); it has only been run on this development machine.
- **No real publishing** to Power BI Service. Publish records the handover, it does not deploy.
- **Documents and the findings deck** are not generated for a new engagement; `kit/docs/*.py` is still RewardsNext-specific.
- **Configuration summary is rule-based**, not LLM-extracted, so it only reflects what the questionnaire and profile contain.
- Storage is JSON files under `data/engagements/` (fine for a pilot, not for multiple users).
- Slicer, drill-through and tooltip behaviour in the *published* report is untested.
- `next build` shows two tracing warnings because the app reads files at runtime; harmless for a local runner.

## Layout

- `src/lib/steps.ts` steps, questionnaire, consent/acceptance text
- `src/lib/server/lib.ts` engagement state, `act()` reducer, agent runners, sample seeding
- `src/app/api/**` route handlers; `src/components/steps-*.tsx` one component per step
- `data/engagements/` runtime state (the sample is re-seeded if missing)
