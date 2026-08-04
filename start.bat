@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo [bili2vrchat] Starting...

call :ensure_uv
if errorlevel 1 goto :end_error

if not exist "%~dp0frontend\.output\public\index.html" (
  if not exist "%~dp0frontend\.output\public\200.html" (
    echo [bili2vrchat] Warning: frontend not built ^(missing frontend\.output\public^)
    echo   Run: cd frontend ^& bun install ^& bun run generate
    echo   ^(requires bun: https://bun.sh^)
  )
)

echo [bili2vrchat] Starting server ...
uv run app.py
echo.
pause
exit /b 0

:ensure_uv
where uv >nul 2>&1
if not errorlevel 1 exit /b 0

if exist "%~dp0.uv\uv.exe" (
  set "PATH=%~dp0.uv;%PATH%"
  where uv >nul 2>&1
  if not errorlevel 1 exit /b 0
)

if exist "%USERPROFILE%\.local\bin\uv.exe" (
  set "PATH=%USERPROFILE%\.local\bin;%PATH%"
  where uv >nul 2>&1
  if not errorlevel 1 exit /b 0
)

echo [bili2vrchat] uv not found. Installing into .uv ...
set "UV_INSTALL_DIR=%~dp0.uv"
set "UV_NO_MODIFY_PATH=1"
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
if errorlevel 1 (
  echo [bili2vrchat] Failed to install uv.
  echo   Manual install: https://docs.astral.sh/uv/getting-started/installation/
  exit /b 1
)

set "PATH=%~dp0.uv;%PATH%"
where uv >nul 2>&1
if errorlevel 1 (
  echo [bili2vrchat] uv still not found after install.
  echo   Manual install: https://docs.astral.sh/uv/getting-started/installation/
  exit /b 1
)
echo [bili2vrchat] uv installed.
exit /b 0

:end_error
echo.
pause
exit /b 1
