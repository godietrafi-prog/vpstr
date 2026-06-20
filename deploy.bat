@echo off
echo ================================================
echo  Poster Viewers - Deploy to GitHub Pages
echo ================================================
echo.

cd /d "%~dp0"

echo Step 1: Rebuilding slides.json...
wsl -e python3 update_slides.py
echo.

echo Step 2: Committing changes...
wsl -e git -c core.logAllRefUpdates=false add -A
wsl -e git -c core.logAllRefUpdates=false commit -m "update media %date% %time:~0,5%"
echo.

echo Step 3: Pushing to GitHub Pages...
wsl -e git -c core.logAllRefUpdates=false push origin main
echo.

echo Done! The TVs will update within ~1 minute.
echo.
pause
