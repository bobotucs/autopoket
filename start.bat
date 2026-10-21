@echo off
rem Launch the AutoPocket web app (opens in your browser).
cd /d "%~dp0"
"%USERPROFILE%\.venvs\autopocket\Scripts\python.exe" run.py %*
