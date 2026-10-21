@echo off
rem One-time setup: creates a Python virtual environment and installs dependencies.
set VENV=%USERPROFILE%\.venvs\autopocket
if not exist "%VENV%\Scripts\python.exe" (
  py -3.12 -m venv "%VENV%" 2>nul || python -m venv "%VENV%"
)
"%VENV%\Scripts\python.exe" -m pip install --upgrade pip
"%VENV%\Scripts\python.exe" -m pip install -r "%~dp0requirements.txt"
echo.
echo Setup complete. Run start.bat to launch AutoPocket.
