# Story F-03: read one value back from a Power BI project's local model.
# Opens the PBIP in a NEW Desktop instance (or attaches to one already open on that exact file if -AttachExisting
# is passed), waits for the local Analysis Services model to come up, and evaluates one DAX expression.
# Prints the value to stdout and exits 0; on any failure prints "ERROR: <message>" to stderr and exits 1.
# Only ever stops the Desktop process THIS script started (never an instance that was already running).
#
# Usage:
#   powershell -File read_measure.ps1 -Pbip "C:\...\Project.pbip" -Dax "[Total Customers]"
#   powershell -File read_measure.ps1 -Pbip "C:\...\Project.pbip" -Dax "COUNTROWS(FactEvents)" -NoRefresh
#   powershell -File read_measure.ps1 -AttachExisting -Dax "[Total Customers]"   # use whichever Desktop is already open
#
# This is the general-purpose version of the query logic proven throughout the RewardsNext build (desktop_verify.ps1
# runs the same connect/refresh sequence for a whole batch of checks); this script is for a single ad hoc value.
param(
  [string]$Pbip,
  [Parameter(Mandatory=$true)][string]$Dax,
  [switch]$NoRefresh,       # skip the full refresh; use when the model is already loaded and you just want a fresh read
  [switch]$AttachExisting,  # query whatever Desktop instance is already open, instead of starting a new one (no -Pbip needed)
  [int]$TimeoutSeconds = 180
)
$ErrorActionPreference = "Stop"
function Fail($msg) { Write-Error "ERROR: $msg"; exit 1 }

$dll = "C:\Program Files\Microsoft Office\root\vfs\ProgramFilesX64\Microsoft.NET\ADOMD.NET\130\Microsoft.AnalysisServices.AdomdClient.dll"
if (-not (Test-Path $dll)) { Fail "ADOMD.NET client not found at $dll -- fallback: read the value from a visual on screen, or use Power BI's own 'Export data' on a visual bound to that measure." }
try { Add-Type -Path $dll } catch { Fail "could not load ADOMD.NET client: $($_.Exception.Message)" }

$mine = $null
if ($AttachExisting) {
  $mine = Get-CimInstance Win32_Process -Filter "Name='PBIDesktop.exe'" | Select-Object -First 1
  if (-not $mine) { Fail "no Power BI Desktop instance is open -- pass -Pbip to start one" }
} else {
  if (-not $Pbip) { Fail "-Pbip is required unless -AttachExisting is passed" }
  if (-not (Test-Path $Pbip)) { Fail "file not found: $Pbip" }
  $before = @(Get-Process PBIDesktop -ErrorAction SilentlyContinue | ForEach-Object { $_.Id })
  Start-Process "C:\Program Files\Microsoft Power BI Desktop\bin\PBIDesktop.exe" -ArgumentList "`"$Pbip`""
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while (-not $mine -and (Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 3
    $mine = Get-CimInstance Win32_Process -Filter "Name='PBIDesktop.exe'" | Where-Object { $before -notcontains $_.ProcessId -and $_.CommandLine -like "*$([IO.Path]::GetFileName($Pbip))*" } | Select-Object -First 1
  }
  if (-not $mine) { Fail "Desktop did not open a new instance for this file within $TimeoutSeconds s -- fallback: check whether antivirus or a slow disk is delaying startup, or raise -TimeoutSeconds" }
}

$port = $null; $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
while (-not $port -and (Get-Date) -lt $deadline) {
  Start-Sleep -Seconds 3
  $srv = Get-CimInstance Win32_Process -Filter "Name='msmdsrv.exe'" | Where-Object { $_.ParentProcessId -eq $mine.ProcessId } | Select-Object -First 1
  if ($srv) {
    $ws = ($srv.CommandLine -split ' ' | Where-Object { $_ -like 'AnalysisServicesWorkspace_*' } | Select-Object -First 1)
    $pf = "$env:LOCALAPPDATA\Microsoft\Power BI Desktop\AnalysisServicesWorkspaces\$ws\Data\msmdsrv.port.txt"
    if (Test-Path $pf) { $port = (Get-Content $pf -Encoding Unicode).Trim() }
  }
}
if (-not $port) {
  $r = "local model server did not start within $TimeoutSeconds s -- fallback: this can mean the local AS engine failed to launch (check %LOCALAPPDATA%\Microsoft\Power BI Desktop\AnalysisServicesWorkspaces for an error, or that a firewall/AV product blocked msmdsrv.exe); read the value from the visual instead, or use the Power BI REST API against a published dataset if one exists (needs tenant permissions -- see F-04)."
  if (-not $AttachExisting) { Stop-Process -Id $mine.ProcessId -Force -ErrorAction SilentlyContinue }
  Fail $r
}

try {
  $conn = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection("Data Source=localhost:$port")
  $conn.Open(); $cmd = $conn.CreateCommand()
  $cmd.CommandText = 'SELECT [CATALOG_NAME] FROM $SYSTEM.DBSCHEMA_CATALOGS'
  $db = $null; $deadline = (Get-Date).AddSeconds(240)
  while (-not $db -and (Get-Date) -lt $deadline) { $r = $cmd.ExecuteReader(); while ($r.Read()) { $db = $r.GetValue(0) }; $r.Close(); if (-not $db) { Start-Sleep -Seconds 5 } }
  if (-not $db) { Fail "model catalog did not appear -- the local server started but the model has not loaded yet; try again or raise -TimeoutSeconds" }
  if (-not $NoRefresh) {
    Start-Sleep -Seconds 5
    $cmd.CommandText = '{"refresh":{"type":"full","objects":[{"database":"' + $db + '"}]}}'
    $cmd.ExecuteNonQuery() | Out-Null
  }
  $cmd.CommandText = 'EVALUATE ROW("v", ' + $Dax + ')'
  $val = $null; $r = $cmd.ExecuteReader(); while ($r.Read()) { $val = $r.GetValue(0) }; $r.Close()
  $conn.Close()
  if ($null -eq $val) { Write-Output "(blank)" } else { Write-Output $val }
} catch {
  Fail "$($_.Exception.Message) -- fallback: the DAX may not evaluate outside a full CALCULATE/EVALUATE context, or a table/relationship name may be wrong; check the expression in Desktop's own DAX query view first."
} finally {
  if ($mine -and -not $AttachExisting) { Stop-Process -Id $mine.ProcessId -Force -ErrorAction SilentlyContinue }
}
