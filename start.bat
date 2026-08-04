@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo [bili2vrchat] Starting...

where uv >nul 2>&1
if errorlevel 1 (
  echo [bili2vrchat] uv not found. Install from https://docs.astral.sh/uv/getting-started/installation/
  goto :end_error
)

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

:end_error
echo.
pause
exit /b 1
