# Build Plotweaver for Windows on your own PC (the GitHub workflow does the same thing).
#   powershell -ExecutionPolicy Bypass -File packaging\windows\build.ps1
# Needs Python 3.10+; the installer step also needs Inno Setup 6 (https://jrsoftware.org/isinfo.php).
# Results land in dist\:  Plotweaver-<v>-windows-portable.zip  and  Plotweaver-<v>-Setup.exe
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..\..")

python -m pip install -r requirements.txt pyinstaller
$v = (python packaging\windows\make_version_info.py).Trim()
pyinstaller --noconfirm plotweaver.spec
python make_sample.py "build\Sample Project" --replace

$portable = "dist\Plotweaver-$v-portable"
if (Test-Path $portable) { Remove-Item -Recurse -Force $portable }
Copy-Item -Recurse dist\Plotweaver $portable
Copy-Item packaging\windows\portable.txt $portable
Copy-Item -Recurse "build\Sample Project" "$portable\Sample Project"
$zip = "dist\Plotweaver-$v-windows-portable.zip"
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path $portable -DestinationPath $zip
Write-Host "Portable: $zip"

$iscc = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
          "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($iscc) {
    & $iscc "/DMyAppVersion=$v" packaging\windows\installer.iss
    Write-Host "Installer: dist\Plotweaver-$v-Setup.exe"
} else {
    Write-Host "Inno Setup not found, so no installer was built (the portable zip is ready)."
}
