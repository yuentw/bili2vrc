@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

echo [bili2vrchat] 啟動中...

:: ── bun：優先 PATH，其次專案 .bun；皆無則安裝到 .bun ──
set "BUN_CMD="
where bun >nul 2>&1 && set "BUN_CMD=bun"
if not defined BUN_CMD if exist "%~dp0.bun\bin\bun.exe" set "BUN_CMD=%~dp0.bun\bin\bun.exe"

if not defined BUN_CMD (
  echo [bili2vrchat] 未偵測到 bun，安裝至 .bun ...
  set "BUN_INSTALL=%~dp0.bun"
  powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://bun.sh/install.ps1 | iex"
  if errorlevel 1 (
    echo [bili2vrchat] bun 安裝失敗
    pause
    exit /b 1
  )
  if not exist "%~dp0.bun\bin\bun.exe" (
    echo [bili2vrchat] bun 安裝後找不到 .bun\bin\bun.exe
    pause
    exit /b 1
  )
  set "BUN_CMD=%~dp0.bun\bin\bun.exe"
)

set "PATH=%~dp0.bun\bin;%PATH%"

:: ── frontend：bun install + generate ──
echo [bili2vrchat] 建置 frontend ...
pushd frontend
"%BUN_CMD%" install
if errorlevel 1 (
  echo [bili2vrchat] bun install 失敗
  popd
  pause
  exit /b 1
)
"%BUN_CMD%" run generate
if errorlevel 1 (
  echo [bili2vrchat] bun run generate 失敗
  popd
  pause
  exit /b 1
)
popd

:: ── Python 依賴與啟動 ──
python -m pip install -r requirements.txt -q
python app.py

pause
