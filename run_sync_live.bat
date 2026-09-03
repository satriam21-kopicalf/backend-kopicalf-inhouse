@echo off
REM ============================================================
REM  POS SALES SYNC - AUGUST 2026 (LIVE MODE)
REM  Runs sync and shows real-time output in THIS terminal
REM ============================================================
cd /d "%~dp0"
python -u sync_aug_full_month.py
pause
