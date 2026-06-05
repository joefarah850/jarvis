@echo off
echo Stopping Jarvis...
taskkill /F /IM python.exe /FI "WINDOWTITLE eq main.py" >nul 2>&1
taskkill /F /IM electron.exe >nul 2>&1
taskkill /F /IM ollama.exe >nul 2>&1
echo Done.