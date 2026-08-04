@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo [bili2vrchat] Starting...

call :ensure_uv
if errorlevel 1 goto :end_error

call :ensure_bun
if errorlevel 1 goto :end_error

call :ensure_frontend
if errorlevel 1 goto :end_error

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

:ensure_bun
where bun >nul 2>&1
if not errorlevel 1 (
  set "PATH=%~dp0.bun\bin;%PATH%"
  exit /b 0
)

if exist "%~dp0.bun\bin\bun.exe" (
  set "PATH=%~dp0.bun\bin;%PATH%"
  exit /b 0
)

echo [bili2vrchat] bun not found. Installing into .bun ...
set "BUN_INSTALL=%~dp0.bun"
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://bun.sh/install.ps1 | iex"
if errorlevel 1 (
  echo [bili2vrchat] Failed to install bun.
  echo   Manual install: https://bun.sh
  exit /b 1
)

if not exist "%~dp0.bun\bin\bun.exe" (
  echo [bili2vrchat] bun still not found after install ^(.bun\bin\bun.exe^).
  echo   Manual install: https://bun.sh
  exit /b 1
)

set "PATH=%~dp0.bun\bin;%PATH%"
echo [bili2vrchat] bun installed.
exit /b 0

:ensure_frontend
if exist "%~dp0frontend\.output\public\index.html" goto :frontend_ok
if exist "%~dp0frontend\.output\public\200.html" goto :frontend_ok

echo [bili2vrchat] Frontend not built. Building ...
pushd "%~dp0frontend" || exit /b 1
call bun install
if errorlevel 1 (
  popd
  echo [bili2vrchat] bun install failed.
  exit /b 1
)
call bun run generate
if errorlevel 1 (
  popd
  echo [bili2vrchat] bun run generate failed.
  exit /b 1
)
popd

if exist "%~dp0frontend\.output\public\index.html" goto :frontend_ok
if exist "%~dp0frontend\.output\public\200.html" goto :frontend_ok
echo [bili2vrchat] Frontend build finished but .output\public is still missing.
exit /b 1

:frontend_ok
exit /b 0

:end_error
echo.
pause
exit /b 1
