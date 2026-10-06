@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
echo [INFO] Restarting backend...

powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%restart_backend.ps1" %*
if errorlevel 1 goto fail

echo [OK] Backend restart completed.
goto end

:fail
echo [ERROR] Backend restart failed.

:end
echo.
pause
