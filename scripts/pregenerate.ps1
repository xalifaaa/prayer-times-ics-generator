# Regenerate prayer calendars and push to trigger deployment.
# Register monthly with Task Scheduler (run once):
#   schtasks /create /tn "PrayerCalendars" /tr "powershell -ExecutionPolicy Bypass -File C:\Users\xal\Documents\prayer-times-ics-generator\scripts\pregenerate.ps1" /sc monthly /d 1 /st 09:00
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)

python scripts/pregenerate.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

git add calendars locations_cache.json
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
    git commit -m "Update generated prayer calendars"
    git push
}
