@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo [bili2vrchat] Starting...

rem bun: prefer PATH, then project .bun; install into .bun if missing
set "BUN_CMD="
where bun >nul 2>&1
if not errorlevel 1 set "BUN_CMD=bun"
if not defined BUN_CMD if exist "%~dp0.bun\bin\bun.exe" set "BUN_CMD=%~dp0.bun\bin\bun.exe"

if defined BUN_CMD goto :have_bun

echo [bili2vrchat] bun not found; installing into .bun ...
set "BUN_INSTALL=%~dp0.bun"
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://bun.sh/install.ps1 | iex"
if errorlevel 1 goto :fail_bun_install
if not exist "%~dp0.bun\bin\bun.exe" goto :fail_bun_missing
set "BUN_CMD=%~dp0.bun\bin\bun.exe"

:have_bun
set "PATH=%~dp0.bun\bin;%PATH%"

echo [bili2vrchat] Building frontend ...
pushd "%~dp0frontend" || goto :fail_frontend_dir
call "%BUN_CMD%" install
if errorlevel 1 goto :fail_bun_install_deps
call "%BUN_CMD%" run generate
if errorlevel 1 goto :fail_bun_generate
popd

echo [bili2vrchat] Installing Python deps ...
python -m pip install -r src/requirements.txt -q
if errorlevel 1 goto :fail_pip

echo [bili2vrchat] Starting server ...
python app.py
echo.
pause
exit /b 0

:fail_bun_install
echo [bili2vrchat] bun install failed.
goto :end_error

:fail_bun_missing
echo [bili2vrchat] bun.exe not found after install: .bun\bin\bun.exe
goto :end_error

:fail_frontend_dir
echo [bili2vrchat] frontend folder not found.
goto :end_error

:fail_bun_install_deps
popd
echo [bili2vrchat] bun install (frontend deps) failed.
goto :end_error

:fail_bun_generate
popd
echo [bili2vrchat] bun run generate failed.
goto :end_error

:fail_pip
echo [bili2vrchat] pip install failed. Is Python on PATH?
goto :end_error

:end_error
echo.
pause
exit /b 1
