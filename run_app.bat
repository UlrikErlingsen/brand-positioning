@echo off
rem PositionSignal - Windows launcher.
rem Double-click this file. The first start creates a private environment and
rem installs the app; later starts reuse it.
setlocal
cd /d "%~dp0"

set "PYTHON_CMD=py -3"
%PYTHON_CMD% -c "import sys" >nul 2>nul || set "PYTHON_CMD=python"
%PYTHON_CMD% -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul || (
  echo PositionSignal needs Python 3.10 or newer.
  echo Install it from https://www.python.org/downloads/
  echo IMPORTANT: tick "Add python.exe to PATH" during installation, then try again.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating PositionSignal's private Python environment...
  %PYTHON_CMD% -m venv .venv
)

for /f %%H in ('powershell -NoProfile -Command "(Get-FileHash requirements.txt -Algorithm SHA256).Hash.ToLower()"') do set "REQ_HASH=%%H"
if not exist ".venv\.positionsignal-requirements-%REQ_HASH%" (
  echo First launch: downloading PositionSignal's Python packages. This can take a few minutes.
  echo Later launches will be much faster.
  ".venv\Scripts\python.exe" -m pip --disable-pip-version-check install --prefer-binary -r requirements.txt || (
    echo Package installation failed. Check your internet connection and try again.
    pause
    exit /b 1
  )
  del /q .venv\.positionsignal-requirements-* .venv\.positionsignal-ready 2>nul
  type nul > ".venv\.positionsignal-requirements-%REQ_HASH%"
) else (
  echo Using the existing PositionSignal environment.
)

if not defined ARROW_DEFAULT_MEMORY_POOL set "ARROW_DEFAULT_MEMORY_POOL=system"
if not defined POSITIONSIGNAL_PORT set "POSITIONSIGNAL_PORT=8501"

echo Starting PositionSignal at http://127.0.0.1:%POSITIONSIGNAL_PORT% ...
".venv\Scripts\python.exe" -m streamlit run app.py ^
  --server.headless=false ^
  --server.address=127.0.0.1 ^
  --server.port=%POSITIONSIGNAL_PORT% ^
  --server.maxUploadSize=200 ^
  --server.fileWatcherType=none ^
  --browser.gatherUsageStats=false

if errorlevel 1 (
  echo PositionSignal stopped with an error. Review the message above.
  pause
  exit /b 1
)
