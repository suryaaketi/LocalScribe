@echo off
setlocal
set "PYTHONUTF8=1"
py -3 "%~dp0localscribe.py" %*
if errorlevel 1 (
    echo.
    echo See the LocalScribe README for Windows setup.
    pause
    exit /b 1
)
