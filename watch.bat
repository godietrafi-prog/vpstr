@echo off
echo ================================================
echo  Poster Viewers - Auto Watcher
echo ================================================
echo.
echo Running via WSL Python...
echo Watching media\ for changes...
echo Close this window to stop.
echo.

wsl --cd "%~dp0" python3 update_slides.py --watch

pause
