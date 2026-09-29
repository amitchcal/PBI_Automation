# Opens a PBIP in a new Desktop instance and reports whether it opened, or the error dialog text (as an image). Stops only its own process.
param([string]$Pbip, [string]$ShotDir, [int]$WaitSeconds = 50)
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System; using System.Text; using System.Collections.Generic; using System.Runtime.InteropServices;
public class W5 {
 public delegate bool EnumProc(IntPtr h, IntPtr l);
 [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc p, IntPtr l);
 [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
 [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
 [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
 [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
 [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint f);
 public struct RECT { public int L,T,R,B; }
 public static List<IntPtr> ForPid(uint pid) { var l = new List<IntPtr>(); EnumWindows((h, x) => { uint p; GetWindowThreadProcessId(h, out p); if (p == pid && IsWindowVisible(h)) l.Add(h); return true; }, IntPtr.Zero); return l; }
 public static string Title(IntPtr h) { var s = new StringBuilder(256); GetWindowText(h, s, 256); return s.ToString(); }
}
"@
$name = [IO.Path]::GetFileName($Pbip)
Start-Process "C:\Program Files\Microsoft Power BI Desktop\bin\PBIDesktop.exe" -ArgumentList "`"$Pbip`""
$mine = $null; for ($i = 0; $i -lt 30 -and -not $mine; $i++) { Start-Sleep -Seconds 2; $mine = Get-CimInstance Win32_Process -Filter "Name='PBIDesktop.exe'" | Where-Object { $_.CommandLine -like "*$Pbip*" } | Select-Object -First 1 }
$verdict = "no window"
$deadline = (Get-Date).AddSeconds($WaitSeconds)
while ((Get-Date) -lt $deadline) {
  Start-Sleep -Seconds 4
  $titles = [W5]::ForPid([uint32]$mine.ProcessId) | ForEach-Object { [W5]::Title($_) } | Where-Object { $_ }
  if ($titles -contains "Unable to open document") {
    $h = [W5]::ForPid([uint32]$mine.ProcessId) | Where-Object { [W5]::Title($_) -eq "Unable to open document" } | Select-Object -First 1
    $r = New-Object W5+RECT; [W5]::GetWindowRect($h, [ref]$r) | Out-Null
    $bmp = New-Object System.Drawing.Bitmap ($r.R - $r.L), ($r.B - $r.T); $g = [System.Drawing.Graphics]::FromImage($bmp); $dc = $g.GetHdc(); [W5]::PrintWindow($h, $dc, 2) | Out-Null; $g.ReleaseHdc($dc); $g.Dispose()
    $bmp.Save((Join-Path $ShotDir "open_error.png")); $bmp.Dispose(); $verdict = "ERROR DIALOG (see open_error.png)"; break
  }
  if ($titles | Where-Object { $_ -like "$($name -replace '\.pbip$','')*" }) { $verdict = "OPENED: " + (($titles | Where-Object { $_ -like "*Power BI*" }) -join " | "); break }
}
Stop-Process -Id $mine.ProcessId -Force -ErrorAction SilentlyContinue
$verdict
