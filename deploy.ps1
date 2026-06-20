$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $dir

Write-Host "================================================"
Write-Host " Poster Viewers - Deploy to GitHub Pages"
Write-Host "================================================"
Write-Host ""

Write-Host "Step 1: Rebuilding slides.json..."
wsl -e python3 update_slides.py
Write-Host ""

Write-Host "Step 2: Committing changes..."
$ts = Get-Date -Format "yyyy-MM-dd HH:mm"
wsl -e git -c core.logAllRefUpdates=false add -A
wsl -e git -c core.logAllRefUpdates=false commit -m "update media $ts"
Write-Host ""

Write-Host "Step 3: Pushing to GitHub Pages..."
wsl -e git -c core.logAllRefUpdates=false push origin main
Write-Host ""

Write-Host "Done! TVs update within ~1 minute."
Read-Host "Press Enter to exit"
