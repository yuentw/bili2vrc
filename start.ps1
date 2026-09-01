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

function Confirm-Install {
    param([string]$Prompt)
    $reply = Read-Host "$Prompt [y/N]"
    if ($reply -match '^(y|yes)$') {
        return
    }
    throw '[bili2vrchat] 已取消。'
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

    Confirm-Install '[bili2vrchat] 未找到 uv。是否安裝到 .uv？'
    Write-Host '[bili2vrchat] 正在安裝 uv 到 .uv ...'
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

function Test-FfmpegAvailable {
    return [bool](Get-Command ffmpeg -ErrorAction SilentlyContinue) -and
        [bool](Get-Command ffprobe -ErrorAction SilentlyContinue)
}

function Add-WingetFfmpegToPath {
    $links = Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Links'
    if (Test-Path (Join-Path $links 'ffmpeg.exe')) {
        Add-ToPath $links
    }

    $packages = Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Packages'
    if (Test-Path $packages) {
        $ffmpegExe = Get-ChildItem -Path $packages -Directory -Filter 'Gyan.FFmpeg*' -ErrorAction SilentlyContinue |
            ForEach-Object { Get-ChildItem $_.FullName -Filter ffmpeg.exe -Recurse -ErrorAction SilentlyContinue } |
            Select-Object -First 1
        if ($ffmpegExe) {
            Add-ToPath $ffmpegExe.DirectoryName
        }
    }
}

function Ensure-Ffmpeg {
    if (Test-FfmpegAvailable) {
        return
    }

    $localBin = Join-Path $Root '.ffmpeg\bin'
    if (Test-Path (Join-Path $localBin 'ffmpeg.exe')) {
        Add-ToPath $localBin
        if (Test-FfmpegAvailable) {
            return
        }
    }

    Add-WingetFfmpegToPath
    if (Test-FfmpegAvailable) {
        return
    }

    $wingetOk = $false
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Confirm-Install '[bili2vrchat] 未找到 ffmpeg。是否用 winget 安裝？'
        Write-Host '[bili2vrchat] 正在用 winget 安裝 ffmpeg ...'
        & winget install --id Gyan.FFmpeg --exact --scope user --accept-package-agreements --accept-source-agreements --disable-interactivity
        $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
        $machinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
        if ($userPath) { $env:PATH = "$userPath;$env:PATH" }
        if ($machinePath) { $env:PATH = "$env:PATH;$machinePath" }
        Add-WingetFfmpegToPath
        $wingetOk = Test-FfmpegAvailable
    }

    if (-not $wingetOk) {
        Confirm-Install '[bili2vrchat] 未找到 ffmpeg。是否下載安裝到 .ffmpeg？'
        Write-Host '[bili2vrchat] 正在安裝 ffmpeg 到 .ffmpeg ...'
        $asset = if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') {
            'ffmpeg-master-latest-winarm64-gpl.zip'
        } else {
            'ffmpeg-master-latest-win64-gpl.zip'
        }
        $zipUrl = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/$asset"
        $zipPath = Join-Path $Root '.ffmpeg-download.zip'
        $extractDir = Join-Path $Root '.ffmpeg-extract'
        $localRoot = Join-Path $Root '.ffmpeg'

        try {
            if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
            if (Test-Path $extractDir) { Remove-Item $extractDir -Recurse -Force }

            if (Get-Command curl.exe -ErrorAction SilentlyContinue) {
                & curl.exe -fL --retry 3 -o $zipPath $zipUrl
                if ($LASTEXITCODE -ne 0) {
                    Write-Error "[bili2vrchat] 下載 ffmpeg 失敗。`n  手動安裝：winget install --id Gyan.FFmpeg --exact"
                }
            } else {
                Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath -UseBasicParsing
            }

            New-Item -ItemType Directory -Path $extractDir -Force | Out-Null
            if (Get-Command tar.exe -ErrorAction SilentlyContinue) {
                & tar.exe -xf $zipPath -C $extractDir
                if ($LASTEXITCODE -ne 0) {
                    Write-Error '[bili2vrchat] 解壓 ffmpeg 失敗。'
                }
            } else {
                Expand-Archive -Path $zipPath -DestinationPath $extractDir -Force
            }

            $ffmpegExe = Get-ChildItem -Path $extractDir -Recurse -Filter ffmpeg.exe | Select-Object -First 1
            if (-not $ffmpegExe) {
                Write-Error '[bili2vrchat] 下載的壓縮檔中找不到 ffmpeg.exe。'
            }

            $sourceBin = $ffmpegExe.DirectoryName
            if (Test-Path $localRoot) { Remove-Item $localRoot -Recurse -Force }
            New-Item -ItemType Directory -Path $localBin -Force | Out-Null
            Copy-Item -Path (Join-Path $sourceBin '*') -Destination $localBin -Force
            Add-ToPath $localBin
        }
        finally {
            if (Test-Path $zipPath) { Remove-Item $zipPath -Force -ErrorAction SilentlyContinue }
            if (Test-Path $extractDir) { Remove-Item $extractDir -Recurse -Force -ErrorAction SilentlyContinue }
        }
    }

    if (-not (Test-FfmpegAvailable)) {
        Write-Error @'
[bili2vrchat] 安裝後仍找不到 ffmpeg。
  手動安裝：winget install --id Gyan.FFmpeg --exact
  或：https://ffmpeg.org/download.html
'@
    }
    Write-Host '[bili2vrchat] ffmpeg 已安裝。'
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

    Confirm-Install '[bili2vrchat] 未找到 bun。是否安裝到 .bun？'
    Write-Host '[bili2vrchat] 正在安裝 bun 到 .bun ...'
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

function Get-AppVersion {
    $pyproject = Join-Path $Root 'pyproject.toml'
    $match = Select-String -Path $pyproject -Pattern '^version\s*=\s*"([^"]+)"' | Select-Object -First 1
    if (-not $match) {
        Write-Error '[bili2vrchat] 無法從 pyproject.toml 讀取 version。'
    }
    return $match.Matches[0].Groups[1].Value
}

function Get-FrontendStamp {
    $stampPath = Join-Path $Root 'frontend\.output\public\.bili2vrc-version'
    if (-not (Test-Path $stampPath)) {
        return ''
    }
    return (Get-Content -Path $stampPath -Raw).Trim()
}

function Write-FrontendStamp {
    param([string]$Version)
    $stampPath = Join-Path $Root 'frontend\.output\public\.bili2vrc-version'
    Set-Content -Path $stampPath -Value $Version -NoNewline -Encoding ascii
}

function Ensure-Frontend {
    $appVersion = Get-AppVersion
    $stamp = Get-FrontendStamp
    if ((Test-FrontendBuilt) -and ($stamp -eq $appVersion)) {
        Write-Host "[bili2vrchat] 前端已是 $appVersion，略過建置。"
        return
    }

    $reason = if (-not (Test-FrontendBuilt)) {
        '前端尚未建置'
    } else {
        "前端版本不符（建置：$stamp，目前：$appVersion）"
    }
    Confirm-Install "[bili2vrchat] $reason。是否執行 bun install 與 bun run generate？"
    Write-Host '[bili2vrchat] 正在建置前端 ...'
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
    Write-FrontendStamp $appVersion
}

Write-Host '[bili2vrchat] 啟動中...'
Ensure-Uv
Ensure-Ffmpeg
Update-Ytdlp
Ensure-Bun
Ensure-Frontend

Write-Host '[bili2vrchat] 啟動伺服器 ...'
& uv run app.py
exit $LASTEXITCODE
