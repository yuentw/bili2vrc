@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

echo [bili2vrchat] Starting...

call :ensure_uv
if errorlevel 1 goto :end_error

call :ensure_ffmpeg
if errorlevel 1 goto :end_error

call :update_ytdlp

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

echo [bili2vrchat] uv not found. Install into .uv?
call :confirm_install
if errorlevel 1 exit /b 1
echo [bili2vrchat] Installing uv into .uv ...
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

:ensure_ffmpeg
where ffmpeg >nul 2>&1
if not errorlevel 1 (
  where ffprobe >nul 2>&1
  if not errorlevel 1 exit /b 0
)

if exist "%~dp0.ffmpeg\bin\ffmpeg.exe" (
  set "PATH=%~dp0.ffmpeg\bin;%PATH%"
  where ffmpeg >nul 2>&1
  if not errorlevel 1 (
    where ffprobe >nul 2>&1
    if not errorlevel 1 exit /b 0
  )
)

where winget >nul 2>&1
if not errorlevel 1 (
  echo [bili2vrchat] ffmpeg not found. Install with winget?
  call :confirm_install
  if errorlevel 1 exit /b 1
  echo [bili2vrchat] Installing ffmpeg with winget ...
  winget install --id Gyan.FFmpeg --exact --scope user --accept-package-agreements --accept-source-agreements --disable-interactivity
  if exist "%LOCALAPPDATA%\Microsoft\WinGet\Links\ffmpeg.exe" (
    set "PATH=%LOCALAPPDATA%\Microsoft\WinGet\Links;%PATH%"
  )
  for /d %%i in ("%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*") do (
    for /d %%j in ("%%i\ffmpeg-*") do (
      if exist "%%j\bin\ffmpeg.exe" set "PATH=%%j\bin;%PATH%"
    )
  )
  where ffmpeg >nul 2>&1
  if not errorlevel 1 (
    where ffprobe >nul 2>&1
    if not errorlevel 1 (
      echo [bili2vrchat] ffmpeg installed.
      exit /b 0
    )
  )
)

echo [bili2vrchat] ffmpeg not found. Install into .ffmpeg?
call :confirm_install
if errorlevel 1 exit /b 1
echo [bili2vrchat] Installing ffmpeg into .ffmpeg ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $root=(Get-Location).Path; $asset=if($env:PROCESSOR_ARCHITECTURE -eq 'ARM64'){'ffmpeg-master-latest-winarm64-gpl.zip'}else{'ffmpeg-master-latest-win64-gpl.zip'}; $zip=Join-Path $root '.ffmpeg-download.zip'; $ex=Join-Path $root '.ffmpeg-extract'; $bin=Join-Path $root '.ffmpeg\bin'; curl.exe -fL --retry 3 -o $zip ('https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/' + $asset); if($LASTEXITCODE -ne 0){throw 'download failed'}; if(Test-Path $ex){Remove-Item $ex -Recurse -Force}; New-Item -ItemType Directory -Path $ex -Force | Out-Null; tar.exe -xf $zip -C $ex; if($LASTEXITCODE -ne 0){throw 'extract failed'}; $ff=(Get-ChildItem $ex -Recurse -Filter ffmpeg.exe | Select-Object -First 1); if(-not $ff){throw 'ffmpeg.exe missing'}; if(Test-Path (Join-Path $root '.ffmpeg')){Remove-Item (Join-Path $root '.ffmpeg') -Recurse -Force}; New-Item -ItemType Directory -Path $bin -Force | Out-Null; Copy-Item (Join-Path $ff.DirectoryName '*') $bin -Force; Remove-Item $zip -Force; Remove-Item $ex -Recurse -Force"
if errorlevel 1 (
  echo [bili2vrchat] Failed to install ffmpeg.
  echo   Manual install: winget install --id Gyan.FFmpeg --exact
  echo   Or: https://ffmpeg.org/download.html
  exit /b 1
)

if not exist "%~dp0.ffmpeg\bin\ffmpeg.exe" (
  echo [bili2vrchat] ffmpeg still not found after install.
  echo   Manual install: winget install --id Gyan.FFmpeg --exact
  echo   Or: https://ffmpeg.org/download.html
  exit /b 1
)

set "PATH=%~dp0.ffmpeg\bin;%PATH%"
echo [bili2vrchat] ffmpeg installed.
exit /b 0

:update_ytdlp
echo [bili2vrchat] Checking yt-dlp ...
uv lock --upgrade-package yt-dlp
if errorlevel 1 (
  echo [bili2vrchat] yt-dlp update skipped. Using existing version.
  exit /b 0
)
uv sync
if errorlevel 1 (
  echo [bili2vrchat] yt-dlp sync skipped. Using existing version.
  exit /b 0
)
for /f "delims=" %%v in ('uv run --no-sync yt-dlp --version 2^>nul') do echo [bili2vrchat] yt-dlp %%v
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

echo [bili2vrchat] bun not found. Install into .bun?
call :confirm_install
if errorlevel 1 exit /b 1
echo [bili2vrchat] Installing bun into .bun ...
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
set "APP_VERSION="
for /f "usebackq tokens=3 delims= " %%a in (`findstr /b /c:"version = " "%~dp0pyproject.toml"`) do set "APP_VERSION=%%~a"
if not defined APP_VERSION (
  echo [bili2vrchat] Could not read version from pyproject.toml.
  exit /b 1
)

set "DIST=%~dp0frontend\.output\public"
set "STAMP_FILE=%DIST%\.bili2vrc-version"
set "STAMP="
if exist "%STAMP_FILE%" set /p STAMP=<"%STAMP_FILE%"

set "DIST_OK=0"
if exist "%DIST%\index.html" set "DIST_OK=1"
if exist "%DIST%\200.html" set "DIST_OK=1"

if "!DIST_OK!"=="1" if "!STAMP!"=="!APP_VERSION!" (
  echo [bili2vrchat] Frontend already !APP_VERSION!, skipping build.
  exit /b 0
)

if "!DIST_OK!"=="1" (
  echo [bili2vrchat] Frontend version mismatch (built: !STAMP!, current: !APP_VERSION!). Run bun install and bun run generate?
) else (
  echo [bili2vrchat] Frontend not built. Run bun install and bun run generate?
)
call :confirm_install
if errorlevel 1 exit /b 1
echo [bili2vrchat] Building frontend ...
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

if exist "%DIST%\index.html" goto :frontend_stamp
if exist "%DIST%\200.html" goto :frontend_stamp
echo [bili2vrchat] Frontend build finished but .output\public is still missing.
exit /b 1

:frontend_stamp
<nul set /p="!APP_VERSION!">"%STAMP_FILE%"
exit /b 0

:confirm_install
set /p "CONFIRM_REPLY=[y/N] "
if /i "%CONFIRM_REPLY%"=="y" exit /b 0
if /i "%CONFIRM_REPLY%"=="yes" exit /b 0
echo [bili2vrchat] Cancelled.
exit /b 1

:end_error
echo.
pause
exit /b 1
