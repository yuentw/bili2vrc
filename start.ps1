#Requires -Version 5.1
$ErrorActionPreference = 'Stop'

Set-Location $PSScriptRoot
$Root = $PSScriptRoot

function Add-ToPath {
    param([string]$Dir)
    if ($env:PATH -notlike "*$Dir*") {
        $env:PATH = "$Dir;$env:PATH"
    }
}

function Test-UvAvailable {
    return [bool](Get-Command uv -ErrorAction SilentlyContinue)
}

function Ensure-Uv {
    if (Test-UvAvailable) {
        return
    }

    $localUv = Join-Path $Root '.uv\uv.exe'
    if (Test-Path $localUv) {
        Add-ToPath (Join-Path $Root '.uv')
        if (Test-UvAvailable) {
            return
        }
    }

    $userUv = Join-Path $env:USERPROFILE '.local\bin\uv.exe'
    if (Test-Path $userUv) {
        Add-ToPath (Join-Path $env:USERPROFILE '.local\bin')
        if (Test-UvAvailable) {
            return
        }
    }

    Write-Host '[bili2vrchat] 未找到 uv，正在安裝到 .uv ...'
    $env:UV_INSTALL_DIR = Join-Path $Root '.uv'
    $env:UV_NO_MODIFY_PATH = '1'
    iex (irm 'https://astral.sh/uv/install.ps1')

    Add-ToPath (Join-Path $Root '.uv')
    if (-not (Test-UvAvailable)) {
        Write-Error @'
[bili2vrchat] 安裝後仍找不到 uv。
  手動安裝：https://docs.astral.sh/uv/getting-started/installation/
'@
    }
    Write-Host '[bili2vrchat] uv 已安裝。'
}

function Update-Ytdlp {
    Write-Host '[bili2vrchat] 正在檢查 yt-dlp ...'
    & uv lock --upgrade-package yt-dlp
    if ($LASTEXITCODE -ne 0) {
        Write-Host '[bili2vrchat] yt-dlp 更新失敗，沿用現有版本。'
        return
    }

    & uv sync
    if ($LASTEXITCODE -ne 0) {
        Write-Host '[bili2vrchat] yt-dlp 更新失敗，沿用現有版本。'
        return
    }

    $version = & uv run --no-sync yt-dlp --version 2>$null
    if ($version) {
        Write-Host "[bili2vrchat] yt-dlp $version"
    }
}

function Test-BunAvailable {
    return [bool](Get-Command bun -ErrorAction SilentlyContinue)
}

function Ensure-Bun {
    if (Test-BunAvailable) {
        Add-ToPath (Join-Path $Root '.bun\bin')
        return
    }

    $localBun = Join-Path $Root '.bun\bin\bun.exe'
    if (Test-Path $localBun) {
        Add-ToPath (Join-Path $Root '.bun\bin')
        return
    }

    Write-Host '[bili2vrchat] 未找到 bun，正在安裝到 .bun ...'
    $env:BUN_INSTALL = Join-Path $Root '.bun'
    iex (irm 'https://bun.sh/install.ps1')

    Add-ToPath (Join-Path $Root '.bun\bin')
    if (-not (Test-Path $localBun) -and -not (Test-BunAvailable)) {
        Write-Error @'
[bili2vrchat] 安裝後仍找不到 bun。
  手動安裝：https://bun.sh
'@
    }
    Write-Host '[bili2vrchat] bun 已安裝。'
}

function Test-FrontendBuilt {
    $dist = Join-Path $Root 'frontend\.output\public'
    return (Test-Path (Join-Path $dist 'index.html')) -or (Test-Path (Join-Path $dist '200.html'))
}

function Ensure-Frontend {
    if (Test-FrontendBuilt) {
        return
    }

    Write-Host '[bili2vrchat] 前端尚未建置，正在建置 ...'
    Push-Location (Join-Path $Root 'frontend')
    try {
        & bun install
        if ($LASTEXITCODE -ne 0) {
            throw 'bun install failed'
        }
        & bun run generate
        if ($LASTEXITCODE -ne 0) {
            throw 'bun run generate failed'
        }
    }
    finally {
        Pop-Location
    }

    if (-not (Test-FrontendBuilt)) {
        Write-Error '[bili2vrchat] 建置完成但仍缺少 frontend/.output/public。'
    }
}

Write-Host '[bili2vrchat] 啟動中...'
Ensure-Uv
Update-Ytdlp
Ensure-Bun
Ensure-Frontend

Write-Host '[bili2vrchat] 啟動伺服器 ...'
& uv run app.py
exit $LASTEXITCODE
