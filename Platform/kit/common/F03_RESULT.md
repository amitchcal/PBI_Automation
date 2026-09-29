# F-03 result: reading a measure value back from the model

**Date:** 29 Sep 2026. **Desktop:** Power BI Desktop 2.156 (26.07).

## What was built
- `kit/common/read_measure.ps1` — the single-purpose tool the acceptance criteria asks for: given a `.pbip` path
  and a DAX expression, opens (or attaches to) a Desktop instance, refreshes, and prints the value.
- `kit/common/desktop_verify.ps1`, `desktop_session.ps1`, `desktop_open_test.ps1` — moved here from
  `kit/transform/`, where they had lived since the F-02/T-05 spikes even though nothing about them is
  transform-specific. These are the batch versions (many scalar/table/DMV checks in one run) used throughout the
  RewardsNext build; `read_measure.ps1` is the same connect logic trimmed to one ad hoc value.

## Proven: the local-model route
This route has been exercised well beyond a single test — it is the mechanism behind every Desktop check run in
this project (transform, model, report, the D4a change, the two layout fixes): open a fresh Desktop instance on
a `.pbip`, find its local Analysis Services server via
`%LOCALAPPDATA%\Microsoft\Power BI Desktop\AnalysisServicesWorkspaces\...\msmdsrv.port.txt`, connect with
ADOMD.NET, refresh, and run `EVALUATE ROW("v", <dax>)`. Tested again just now with `read_measure.ps1` directly:
`[Total Customers]` on the RewardsNext report returned `17000`, and a bad file path failed cleanly with a
labelled error rather than hanging.

## Documented fallback, per failure point (acceptance criteria: "documented fallback where the query route is blocked")
| Where it can fail | Fallback |
|---|---|
| `Microsoft.AnalysisServices.AdomdClient.dll` not found (ADOMD.NET not installed with this Office/Desktop build) | Read the value from a visual on screen, or use Power BI Desktop's own "Export data" on a visual bound to that measure. |
| Desktop never opens a new instance for the file | Usually antivirus or a slow disk delaying startup; raise the timeout, or check Desktop opened with no visible error window. |
| Local AS server (`msmdsrv.exe`) never starts, or its port file never appears | Check `%LOCALAPPDATA%\Microsoft\Power BI Desktop\AnalysisServicesWorkspaces` for an error; a firewall or AV product can block `msmdsrv.exe`. Fall back to reading the visual, or to the Power BI REST API against a *published* dataset (needs tenant permissions — see F-04, not yet available). |
| Model catalog never appears after the server starts | The model just hasn't finished loading; retry or raise the timeout (this project's own model typically takes 10-50s after the server port appears). |
| The DAX itself errors | Often a measure needs `CALCULATE`/`EVALUATE` context it doesn't have standalone, or a table/column name is wrong; check the expression in Desktop's own DAX query view first. |

## Not proven: the service-model route
Reading a measure from a *published* dataset (Power BI Service, via the XMLA endpoint or the REST API's
`executeQueries`) has not been attempted. Both routes need things only the customer or Amit's own tenant can
supply: XMLA read requires a Premium/Fabric or Premium-Per-User capacity workspace with the XMLA endpoint set to
Read or Read/Write; the REST API route needs an Azure AD app registration (a client ID and secret, or a signed-in
user token) with access to the workspace. Neither should be attempted with fabricated credentials — this is
exactly the tenant/permission information F-04 also needs, and the two stories should be resolved together once
that's available.

## Honest notes
- This is a spike result, not a hardened tool: `read_measure.ps1` has been run twice (one success, one deliberate
  failure case) plus the many `desktop_verify.ps1` runs it's built from. It has not been tried against a
  Desktop version other than 2.156, or a machine without this exact ADOMD.NET path.
- Human gate: this story is marked "In Progress," not "Done" — F-03 needs the customer's tenant and Desktop
  settings input per the backlog, and confirming the service-model gap above is acceptable to leave open for now
  is a call for Amit, not the assistant.
