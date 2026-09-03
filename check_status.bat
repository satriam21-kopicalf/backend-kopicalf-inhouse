@echo off
REM ============================================================
REM  POS SALES STATUS - Quick DB Count Check
REM  Shows current record counts for August 2026
REM ============================================================
cd /d "%~dp0"
python -u pos_monitor.py --counts
pause
