Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$sig = @"
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
[DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
[DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
[StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
"@
Add-Type -MemberDefinition $sig -Name Win32U -Namespace Native -UsingNamespace System.Runtime.InteropServices

$p = Get-Process Capture | Where-Object { $_.MainWindowHandle -ne [IntPtr]::Zero } | Select-Object -First 1
if (-not $p) { throw "Capture window not found" }
$hwnd = $p.MainWindowHandle
[void][Native.Win32U]::ShowWindow($hwnd, 9)
[void][Native.Win32U]::SetForegroundWindow($hwnd)
Start-Sleep -Milliseconds 1200

$rect = New-Object Native.Win32U+RECT
[void][Native.Win32U]::GetWindowRect($hwnd, [ref]$rect)
$w = $rect.Right - $rect.Left
$h = $rect.Bottom - $rect.Top
Write-Host "rect $w x $h at $($rect.Left),$($rect.Top)"

$bmp = New-Object System.Drawing.Bitmap $w, $h
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($rect.Left, $rect.Top, 0, 0, (New-Object System.Drawing.Size $w, $h))
$g.Dispose()
$path = "C:\Users\lance\tcl-mcp-server\lab3_results\S_schematics_PAGE1.png"
$bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()
Get-Item $path | Format-List FullName, Length, LastWriteTime
