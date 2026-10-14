# scripts/schedule.ps1
# Script to register / unregister hourly jobhunt scraping via Windows Task Scheduler (using schtasks.exe)

param(
    [Parameter(Position=0)]
    [ValidateSet("install", "uninstall", "status", "run-now")]
    [string]$Action = "status"
)

$TaskName = "JobhuntHourlyScraper"
$PythonExe = (Get-Command python).Source
$ProjectDir = (Resolve-Path "$PSScriptRoot\..").Path
$RunScript = "$ProjectDir\scripts\run_worker.bat"

if ($Action -eq "install") {
    # Generate run_worker.bat helper
    $BatContent = @"
@echo off
cd /d "$ProjectDir"
set PYTHONPATH=apps\api
"$PythonExe" -m jobhunt run >> "$ProjectDir\data\cron.log" 2>&1
"@
    Set-Content -Path $RunScript -Value $BatContent -Encoding ASCII

    Write-Host "[*] Creating scheduled task '$TaskName' to run every 1 hour..." -ForegroundColor Cyan

    $tr = "`"$RunScript`""
    $res = schtasks /create /tn "$TaskName" /tr $tr /sc HOURLY /mo 1 /f
    Write-Host $res

    Write-Host "[+] Task '$TaskName' successfully registered! It will run automatically every hour." -ForegroundColor Green
    Write-Host "    Log file: $ProjectDir\data\cron.log" -ForegroundColor Yellow
}
elseif ($Action -eq "uninstall") {
    Write-Host "[*] Unregistering scheduled task '$TaskName'..." -ForegroundColor Cyan
    $res = schtasks /delete /tn "$TaskName" /f
    Write-Host $res
    if (Test-Path $RunScript) {
        Remove-Item $RunScript -Force
    }
    Write-Host "[-] Task '$TaskName' unregistered." -ForegroundColor Green
}
elseif ($Action -eq "run-now") {
    Write-Host "[*] Triggering task '$TaskName' now..." -ForegroundColor Cyan
    $res = schtasks /run /tn "$TaskName"
    Write-Host $res
    Write-Host "[+] Task triggered. Check $ProjectDir\data\cron.log for progress." -ForegroundColor Green
}
elseif ($Action -eq "status") {
    $res = schtasks /query /tn "$TaskName" /fo LIST 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "=== $TaskName Status ===" -ForegroundColor Green
        $res | ForEach-Object { Write-Host $_ }
    } else {
        Write-Host "[-] Task '$TaskName' is NOT installed." -ForegroundColor Yellow
        Write-Host "    Run 'powershell scripts/schedule.ps1 install' to register it."
    }
}
