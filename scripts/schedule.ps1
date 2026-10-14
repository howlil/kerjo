# scripts/schedule.ps1
# Script to register / unregister hourly kerjo scraping via Windows Task Scheduler (using schtasks.exe)

param(
    [Parameter(Position=0)]
    [ValidateSet("install", "uninstall", "status", "run-now")]
    [string]$Action = "status"
)

$TaskName = "KerjoHourlyScraper"
$ProjectDir = (Resolve-Path "$PSScriptRoot\..").Path
$RunScript = "$ProjectDir\scripts\run_worker.bat"

if ($Action -eq "install") {
    if (!(Test-Path $RunScript)) { throw "Worker script missing: $RunScript" }
    New-Item -ItemType Directory -Path (Join-Path $ProjectDir "data") -Force | Out-Null
    Write-Host "[*] Registering hourly task $TaskName..." -ForegroundColor Cyan
    $tr = 'cmd.exe /d /c ""' + $RunScript + '""'
    schtasks.exe /create /tn $TaskName /tr $tr /sc HOURLY /mo 1 /f
    if ($LASTEXITCODE -ne 0) { throw "schtasks.exe failed to register $TaskName (exit $LASTEXITCODE)" }
    Write-Host "[+] Task registered. Confirm via status." -ForegroundColor Green
}
elseif ($Action -eq "uninstall") {
    schtasks.exe /delete /tn $TaskName /f
    if ($LASTEXITCODE -ne 0) { throw "schtasks.exe failed to unregister $TaskName (exit $LASTEXITCODE)" }
    # Do not delete tracked scripts/run_worker.bat on uninstall.
    Write-Host "[-] Scheduled task unregistered." -ForegroundColor Green
}
elseif ($Action -eq "run-now") {
    schtasks.exe /run /tn $TaskName
    if ($LASTEXITCODE -ne 0) { throw "schtasks.exe failed to start $TaskName (exit $LASTEXITCODE)" }
    Write-Host "[+] Scheduled task started; see data/cron.log." -ForegroundColor Green
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
