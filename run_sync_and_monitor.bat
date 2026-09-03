@echo off
REM ============================================================
REM  POS SALES SYNC - AUGUST 2026 FULL MONTH
REM  Run this script to start sync and monitor live progress
REM ============================================================
cd /d "%~dp0"

echo ============================================================
echo  POS SALES SYNC - AUGUST 2026
echo  Started: %date% %time%
echo ============================================================
echo.
echo  Log file: sync_aug_output.log
echo  Press Ctrl+C to stop monitoring, then run this again to resume.
echo.

REM Delete old log if exists
if exist sync_aug_output.log del sync_aug_output.log

REM Start sync in background, output to log file
start "POS Sync" cmd /c "python -u sync_aug_full_month.py >> sync_aug_output.log 2>&1"

REM Wait 3 seconds for sync to start writing
timeout /t 3 /nobreak >nul

REM Show live log + monitor combined
echo --- Starting live monitor ---
echo.
powershell -Command "Get-Content sync_aug_output.log -Wait -Tail 5"
