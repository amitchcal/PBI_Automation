# Opens a generated PBIP in a NEW Power BI Desktop instance, refreshes it, runs the expected checks, writes results, and stops only the instance it started.
# Usage: powershell -File desktop_verify.ps1 -Pbip <path to .pbip> -Checks <expected_checks.json> -Out <desktop_check.json> [-ProbeTable <table name>]
param([string]$Pbip, [string]$Checks, [string]$Out, [int]$RefreshTimeoutSeconds = 1800, [string]$Screenshot = "", [string]$ProbeTable = "FactEvents")   # -Screenshot <png> also saves an image of the report window after the refresh; -ProbeTable is any real data table in the model, used only to detect that the refresh actually loaded rows
$ErrorActionPreference = "Stop"
$exe = "C:\Program Files\Microsoft Power BI Desktop\bin\PBIDesktop.exe"
$dll = "C:\Program Files\Microsoft Office\root\vfs\ProgramFilesX64\Microsoft.NET\ADOMD.NET\130\Microsoft.AnalysisServices.AdomdClient.dll"
Add-Type -Path $dll
$result = [ordered]@{ pbip = $Pbip; started = (Get-Date).ToString("s") }
$mine = $null
try {
  $before = @(Get-Process PBIDesktop -ErrorAction SilentlyContinue | ForEach-Object { $_.Id })
  $result.other_desktop_pids_untouched = $before
  Start-Process -FilePath $exe -ArgumentList "`"$Pbip`""
  # find the instance we started: a new PBIDesktop process whose command line names our file
  $deadline = (Get-Date).AddSeconds(180)
  while (-not $mine -and (Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 3
    $mine = Get-CimInstance Win32_Process -Filter "Name='PBIDesktop.exe'" | Where-Object { $before -notcontains $_.ProcessId -and $_.CommandLine -like "*$([IO.Path]::GetFileName($Pbip))*" } | Select-Object -First 1
  }
  if (-not $mine) { throw "Desktop did not start for this project" }
  $result.desktop_pid = $mine.ProcessId
  # wait for its local model server and port
  $port = $null; $deadline = (Get-Date).AddSeconds(180)
  while (-not $port -and (Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 3
    $srv = Get-CimInstance Win32_Process -Filter "Name='msmdsrv.exe'" | Where-Object { $_.ParentProcessId -eq $mine.ProcessId } | Select-Object -First 1
    if ($srv) {
      $ws = ($srv.CommandLine -split ' ' | Where-Object { $_ -like 'AnalysisServicesWorkspace_*' } | Select-Object -First 1)
      $pf = "$env:LOCALAPPDATA\Microsoft\Power BI Desktop\AnalysisServicesWorkspaces\$ws\Data\msmdsrv.port.txt"
      if (Test-Path $pf) { $port = (Get-Content $pf -Encoding Unicode).Trim() }
    }
  }
  if (-not $port) { throw "local model server not found" }
  $result.port = $port
  $conn = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection("Data Source=localhost:$port")
  $conn.Open(); $cmd = $conn.CreateCommand()
  try { $cmd.CommandTimeout = $RefreshTimeoutSeconds } catch { }
  $cmd.CommandText = 'SELECT [CATALOG_NAME] FROM $SYSTEM.DBSCHEMA_CATALOGS'
  $db = $null; $deadline = (Get-Date).AddSeconds(240)
  while (-not $db -and (Get-Date) -lt $deadline) {   # the model is loaded a little after the server starts
    $r = $cmd.ExecuteReader(); while ($r.Read()) { $db = $r.GetValue(0) }; $r.Close()
    if (-not $db) { Start-Sleep -Seconds 5 }
  }
  if (-not $db) { throw "model did not load in Desktop" }
  $result.database = $db
  # full refresh, timed
  # A refresh can return at once without loading data if Desktop is still starting up, so confirm rows exist and retry.
  Start-Sleep -Seconds 10
  $attempt = 0; $loaded = $false
  while (-not $loaded -and $attempt -lt 4) {
    $attempt++
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $cmd.CommandText = '{"refresh":{"type":"full","objects":[{"database":"' + $db + '"}]}}'
    try { $null = $cmd.ExecuteNonQuery(); $result.refresh = [ordered]@{ ok = $true; seconds = [math]::Round($sw.Elapsed.TotalSeconds, 1); attempts = $attempt } }
    catch { $result.refresh = [ordered]@{ ok = $false; seconds = [math]::Round($sw.Elapsed.TotalSeconds, 1); attempts = $attempt; error = $_.Exception.Message }; break }
    try { $cmd.CommandText = 'EVALUATE ROW("n", COUNTROWS(''' + $ProbeTable + '''))'; $r = $cmd.ExecuteReader(); $n = $null; while ($r.Read()) { $n = $r.GetValue(0) }; $r.Close(); if ($n -gt 0) { $loaded = $true } } catch { }
    if (-not $loaded) { Start-Sleep -Seconds 15 }
  }
  if ($result.refresh.ok -and -not $loaded) { $result.refresh.ok = $false; $result.refresh.error = "refresh returned but no data was loaded after $attempt attempts" }
  # checks
  $results = @()
  if ($result.refresh.ok) {
    if ($Checks) { $spec = Get-Content $Checks -Raw | ConvertFrom-Json } else { $spec = [pscustomobject]@{ scalar = @(); table = @(); dmv = @() } }
    if ($spec -is [array]) { $scalar = $spec; $tables = @(); $dmvs = @() } else { $scalar = @($spec.scalar); $tables = @($spec.table); $dmvs = @($spec.dmv) }
    foreach ($c in $scalar) {
      $tol = 0.011; if ($null -ne $c.tol) { $tol = [double]$c.tol }
      $cmd.CommandText = 'EVALUATE ROW("v", ' + $c.dax + ')'
      try {
        $r = $cmd.ExecuteReader(); $v = $null; while ($r.Read()) { $v = $r.GetValue(0) }; $r.Close()
        $ok = ($null -ne $v) -and ([math]::Abs([double]$v - [double]$c.expected) -lt $tol)
        $results += [ordered]@{ check = $c.name; expected = $c.expected; actual = $v; pass = $ok }
      } catch { $results += [ordered]@{ check = $c.name; expected = $c.expected; actual = $null; pass = $false; error = $_.Exception.Message } }
    }
    foreach ($t in $tables) {   # per-row comparison, e.g. a sample of customers; blank counts as 0
      try {
        $kc = 1; if ($null -ne $t.key_cols) { $kc = [int]$t.key_cols }      # how many leading columns form the row key
        $ttol = 0.011; if ($null -ne $t.tol) { $ttol = [double]$t.tol }
        $cmd.CommandText = $t.dax; $r = $cmd.ExecuteReader(); $got = @{}
        while ($r.Read()) {
          $kp = @(); for ($i = 0; $i -lt $kc; $i++) { $kp += [string]$r.GetValue($i) }
          $vals = @(); for ($i = $kc; $i -lt $r.FieldCount; $i++) { $x = $r.GetValue($i); if ($null -eq $x) { $x = 0 }; $vals += [double]$x }; $got[($kp -join "|")] = $vals }
        $r.Close(); $bad = @(); $n = 0
        foreach ($p in $t.expected.PSObject.Properties) {
          $n++; $e = @($p.Value | ForEach-Object { [double]$_ }); $g = $got[$p.Name]; if ($null -eq $g) { $g = @(0) * $e.Count }
          for ($i = 0; $i -lt $e.Count; $i++) { if ([math]::Abs($g[$i] - $e[$i]) -ge $ttol) { $bad += "$($p.Name) col $($t.columns[$i]): expected $($e[$i]) got $($g[$i])"; break } }
        }
        $results += [ordered]@{ check = $t.name; expected = "$n rows"; actual = "$($n - $bad.Count) of $n rows match"; pass = ($bad.Count -eq 0); mismatches = ($bad | Select-Object -First 5) }
      } catch { $results += [ordered]@{ check = $t.name; expected = "rows"; actual = $null; pass = $false; error = $_.Exception.Message } }
    }
    foreach ($d in $dmvs) {
      try {
        $cmd.CommandText = $d.query; $r = $cmd.ExecuteReader(); $n = 0
        while ($r.Read()) {   # optional row filters, applied here because the DMV query dialect is limited
          $keep = $true
          if ($d.filter) { foreach ($p in $d.filter.PSObject.Properties) { if ([string]$r.GetValue($r.GetOrdinal($p.Name)) -ne [string]$p.Value) { $keep = $false } } }
          if ($d.not_equal) { foreach ($p in $d.not_equal.PSObject.Properties) { if ([string]$r.GetValue($r.GetOrdinal($p.Name)) -eq [string]$p.Value) { $keep = $false } } }
          if ($keep) { $n++ }
        }
        $r.Close()
        $results += [ordered]@{ check = $d.name; expected = $d.expected_rows; actual = $n; pass = ($n -eq $d.expected_rows) }
      } catch { $results += [ordered]@{ check = $d.name; expected = $d.expected_rows; actual = $null; pass = $false; error = $_.Exception.Message } }
    }
  }
  $result.checks = $results
  $result.all_passed = ($results.Count -gt 0) -and (@($results | Where-Object { -not $_.pass }).Count -eq 0)
  $conn.Close()
  if ($Screenshot) {
    Add-Type -AssemblyName System.Drawing
    Add-Type @"
using System; using System.Runtime.InteropServices;
public class WS { [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
 [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint f);
 [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
 public struct RECT { public int L,T,R,B; } }
"@
    Start-Sleep -Seconds 12                       # let visuals finish rendering after the refresh
    $h = (Get-Process -Id $mine.ProcessId).MainWindowHandle; [WS]::ShowWindow($h, 3) | Out-Null; Start-Sleep -Seconds 6
    $rc = New-Object WS+RECT; [WS]::GetWindowRect($h, [ref]$rc) | Out-Null
    $bmp = New-Object System.Drawing.Bitmap ($rc.R - $rc.L), ($rc.B - $rc.T); $gr = [System.Drawing.Graphics]::FromImage($bmp); $dc = $gr.GetHdc()
    [WS]::PrintWindow($h, $dc, 2) | Out-Null; $gr.ReleaseHdc($dc); $gr.Dispose(); $bmp.Save($Screenshot); $bmp.Dispose(); $result.screenshot = $Screenshot
  }
}
catch { $result.error = $_.Exception.Message }
finally {
  if ($mine) { Stop-Process -Id $mine.ProcessId -Force -ErrorAction SilentlyContinue; $result.stopped_own_pid = $mine.ProcessId }
  $result.finished = (Get-Date).ToString("s")
  $result | ConvertTo-Json -Depth 6 | Set-Content -Path $Out -Encoding UTF8
}
