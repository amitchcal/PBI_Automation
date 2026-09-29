# Starts a NEW Desktop instance on a PBIP, refreshes it, maximises it and leaves it running (for interaction tests). Prints the pid.
# Stop it afterwards with: Stop-Process -Id <pid>. Never touches other Desktop instances.
param([string]$Pbip, [string]$Out)
$ErrorActionPreference = "Stop"
$dll = "C:\Program Files\Microsoft Office\root\vfs\ProgramFilesX64\Microsoft.NET\ADOMD.NET\130\Microsoft.AnalysisServices.AdomdClient.dll"; Add-Type -Path $dll
$before = @(Get-Process PBIDesktop -ErrorAction SilentlyContinue | ForEach-Object { $_.Id })
Start-Process "C:\Program Files\Microsoft Power BI Desktop\bin\PBIDesktop.exe" -ArgumentList "`"$Pbip`""
$mine = $null; $deadline = (Get-Date).AddSeconds(180)
while (-not $mine -and (Get-Date) -lt $deadline) { Start-Sleep -Seconds 3; $mine = Get-CimInstance Win32_Process -Filter "Name='PBIDesktop.exe'" | Where-Object { $before -notcontains $_.ProcessId -and $_.CommandLine -like "*$([IO.Path]::GetFileName($Pbip))*" } | Select-Object -First 1 }
$port = $null
while (-not $port -and (Get-Date) -lt $deadline) { Start-Sleep -Seconds 3
  $srv = Get-CimInstance Win32_Process -Filter "Name='msmdsrv.exe'" | Where-Object { $_.ParentProcessId -eq $mine.ProcessId } | Select-Object -First 1
  if ($srv) { $ws = ($srv.CommandLine -split ' ' | Where-Object { $_ -like 'AnalysisServicesWorkspace_*' } | Select-Object -First 1); $pf = "$env:LOCALAPPDATA\Microsoft\Power BI Desktop\AnalysisServicesWorkspaces\$ws\Data\msmdsrv.port.txt"; if (Test-Path $pf) { $port = (Get-Content $pf -Encoding Unicode).Trim() } } }
$conn = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection("Data Source=localhost:$port"); $conn.Open(); $cmd = $conn.CreateCommand()
$cmd.CommandText = 'SELECT [CATALOG_NAME] FROM $SYSTEM.DBSCHEMA_CATALOGS'; $db = $null
while (-not $db) { $r = $cmd.ExecuteReader(); while ($r.Read()) { $db = $r.GetValue(0) }; $r.Close(); if (-not $db) { Start-Sleep -Seconds 5 } }
Start-Sleep -Seconds 10
for ($a = 1; $a -le 4; $a++) {
  $cmd.CommandText = '{"refresh":{"type":"full","objects":[{"database":"' + $db + '"}]}}'; $null = $cmd.ExecuteNonQuery()
  $cmd.CommandText = 'EVALUATE ROW("n", COUNTROWS(FactEvents))'; $r = $cmd.ExecuteReader(); $n = 0; while ($r.Read()) { $n = $r.GetValue(0) }; $r.Close(); if ($n -gt 0) { break }; Start-Sleep -Seconds 15 }
$conn.Close()
Add-Type @"
using System; using System.Runtime.InteropServices;
public class WSS { [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c); [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h); }
"@
$h = (Get-Process -Id $mine.ProcessId).MainWindowHandle; [WSS]::ShowWindow($h, 3) | Out-Null; [WSS]::SetForegroundWindow($h) | Out-Null; Start-Sleep -Seconds 12
@{ pid = $mine.ProcessId; rows = $n } | ConvertTo-Json | Set-Content $Out
