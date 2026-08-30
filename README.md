# bili2vrc

> neko 🐱

**English** | [繁體中文](README_zh-TW.md)

Web UI to download **Bilibili / YouTube** videos and upload them to **your own Cloudflare R2 bucket** via the **R2 S3 API**. Produces a **direct URL for watching in VRChat**, with optional **playback speed**, **CBR / VBR encoding**, and hardware acceleration. No Cloudflare Worker required.

```
Browser → FastAPI (yt-dlp / ffmpeg) → R2 (S3 API) → VRChat direct URL
```

## Features

- Download from **Bilibili** and **YouTube** (yt-dlp)
- **Output modes**: **Keep original** (UI default) / **AV1** / **H.264** (VRChat-oriented re-encode)
- **Playback speed** (permanent change before upload; ≠ 1.0x forces re-encode and auto-switches off Keep original)
- **HDR → SDR** (when the selected format is HDR / HDR10 / HLG): optional tonemap before encode
- **Tonemap mapping** (advanced): **Mobius** (default) / **BT.2390** / **Hable** via ffmpeg `libplacebo` (Vulkan GPU; not NVENC)
- **Encode modes**: **VBR** (quality + bitrate ceiling) / **CBR** (fixed bitrate)
- **CRF / CQ** slider per output codec; quality presets for encoder tuning
- **Bitrate**: “original” or custom presets; only “original” auto-scales bitrate with speed
- Auto hardware encode (NVENC AV1/H.264, QSV, AMF, VideoToolbox, …) with software fallback (`libsvtav1` / `libx264`)
- Post-download **ffprobe integrity check**; **Keep original** at 1.0x without HDR→SDR uses **faststart** only (`-c copy`)
- Upload to **your R2 bucket**; result preview uses the **R2 public URL** (not local streaming)
- **TTL** in the UI (1 h / 1 d / 7 d / 30 d / forever) with background expiry cleanup
- Cookies stored in **browser localStorage** only
- **Paste** reads the clipboard then fetches formats; non-text clipboard (e.g. an image) is ignored so the button stays usable; Ctrl+V wait only if the browser blocks clipboard-read (typical on LAN HTTP)

---

## Prerequisites

| Tool | Required | Notes |
|------|----------|--------|
| Python 3.14+ | Yes | See `.python-version` / `pyproject.toml`. `uv run` can fetch this Python if needed |
| [uv](https://docs.astral.sh/uv/) | Yes | Python deps + `uv run app.py`; start scripts install into `.uv` if missing |
| [ffmpeg](https://ffmpeg.org/) | Yes | `ffmpeg` and `ffprobe`. Start scripts install if missing (Windows: winget `Gyan.FFmpeg`, else portable `.ffmpeg`; macOS: Homebrew; Linux: portable `.ffmpeg`). **HDR→SDR** needs **libplacebo** + **Vulkan** |
| JS runtime (YouTube) | Yes for YouTube | yt-dlp uses **node → bun → deno** (`YTDLP_JS_RUNTIME`). Start scripts already install **Bun**, which is enough for YouTube |
| [Bun](https://bun.sh/) | Yes (frontend) | Start scripts install into `.bun` and build the frontend if needed |
| Cloudflare R2 bucket | Yes | see [R2 setup](#cloudflare-r2-setup) below |
| [aria2](https://github.com/aria2/aria2) | Optional | faster Bilibili downloads; **not bundled** by start scripts; **not used for YouTube** |

### Python dependencies (`pyproject.toml` + `uv.lock`)

Managed with [uv](https://docs.astral.sh/uv/). Main packages:

| Package | Role |
|---------|------|
| fastapi / uvicorn | Web UI / API |
| requests | HTTP helpers |
| boto3 | Cloudflare R2 (S3-compatible) upload |
| yt-dlp | Bilibili / YouTube download |
| python-dotenv | Load `.env` at startup (`src/bili2vrc/config.py`) |

`requirements.txt` is kept for reference; use `uv sync` / `uv lock` for installs.

### Frontend (`frontend/`)

| Stack | Role |
|-------|------|
| Nuxt 4 / Vue 3 | SPA UI (`bun run generate` → `frontend/.output/public`, served by FastAPI) |

---

## Cloudflare R2 setup

You only need an **R2 bucket** and an **API token**. No Worker deployment.

### 1. Get Account ID

1. Log in to [Cloudflare Dashboard](https://dash.cloudflare.com/)
2. Open **Workers & R2** (or any zone overview)
3. Copy **Account ID** on the right → `CF_ACCOUNT_ID`

### 2. Create a bucket

1. **Storage & databases** → **R2 object storage**
2. **Create bucket** → pick a name (e.g. `my-vrchat-videos`) → `R2_BUCKET_NAME`

### 3. Create API token

1. On the R2 page, **Manage R2 API Tokens** → **Create API token**
2. Permissions: **Object Read & Write** (scope: your bucket or whole account)
3. After creation, copy:
   - **Access Key ID** → `R2_ACCESS_KEY_ID`
   - **Secret Access Key** → `R2_SECRET_ACCESS_KEY`

> The secret is shown **once**. Store it safely. If lost, create a new token.

### 4. Public access (for VRChat direct links)

R2 is private by default. To get an HTTP URL for VRChat:

1. Cloudflare Dashboard → **R2 Object Storage** → open your **bucket**
2. Open **Settings**
3. Under **Custom Domains**, click **Add** and connect a domain (e.g. `b2v.example.com`)
4. Wait until **Status** is **Active** and **Access** is **Enabled**
5. Set `R2_PUBLIC_BASE_URL` to that domain, e.g. `https://b2v.example.com`  
   (scheme optional — the app adds `https://` if missing)

Alternatively you can enable **Public Development URL** (`https://pub-xxxxxxxx.r2.dev`) on the same Settings page and use that as `R2_PUBLIC_BASE_URL`.

Without `R2_PUBLIC_BASE_URL`, uploads still work; the app returns `r2://bucket/key` instead of an HTTP link.

### 5. Streaming / seek

Public R2 URLs support **HTTP Range** requests. Combined with the app’s **faststart** step, VRChat can play progressively without downloading the full file first. This is progressive MP4 playback, not HLS/live streaming.

After upload, the in-page preview uses the **R2 public URL**. If the local server is stopped, an already-open result page can still play (while the R2 link is valid), but you cannot fetch formats or start new jobs.

---

## Configure bili2vrchat

Two ways (env vars override `src/bili2vrc/config.py`). You can also copy [.env.example](.env.example) to `.env` — `load_dotenv()` runs on import.

### Option A — Edit `src/bili2vrc/config.py` (simplest for local use)

Open `src/bili2vrc/config.py` and replace the `Fill in …` placeholders:

```python
CF_ACCOUNT_ID        = os.environ.get("CF_ACCOUNT_ID", "your-account-id")
R2_ACCESS_KEY_ID     = os.environ.get("R2_ACCESS_KEY_ID", "your-access-key-id")
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY", "your-secret-access-key")
R2_BUCKET_NAME       = os.environ.get("R2_BUCKET_NAME", "my-vrchat-videos")
R2_PUBLIC_BASE_URL   = os.environ.get("R2_PUBLIC_BASE_URL", "https://pub-xxxx.r2.dev").rstrip("/")
```

Values starting with `Fill in ` are treated as **not configured**.

> Do not commit real secrets to git. Use env vars or a local-only `src/bili2vrc/config.py` for production.

### Option B — Environment variables

**Windows (cmd), before `start.bat` / `start.ps1`:**

```bat
set CF_ACCOUNT_ID=your-account-id
set R2_ACCESS_KEY_ID=your-access-key-id
set R2_SECRET_ACCESS_KEY=your-secret-access-key
set R2_BUCKET_NAME=my-vrchat-videos
set R2_PUBLIC_BASE_URL=https://pub-xxxx.r2.dev
```

**Unix:**

```bash
export CF_ACCOUNT_ID=your-account-id
export R2_ACCESS_KEY_ID=your-access-key-id
export R2_SECRET_ACCESS_KEY=your-secret-access-key
export R2_BUCKET_NAME=my-vrchat-videos
export R2_PUBLIC_BASE_URL=https://pub-xxxx.r2.dev
```

---

## Install & run

### What start scripts do

`start.ps1` / `start.bat` / `start.sh` will:

- Install **uv** into project `.uv` if missing
- Install **ffmpeg** if `ffmpeg` / `ffprobe` are missing (see [Prerequisites](#prerequisites))
- Upgrade **yt-dlp** via `uv lock --upgrade-package yt-dlp` (keeps the existing version if that fails)
- Install **Bun** into project `.bun` if missing
- Build the frontend (`bun install` + `bun run generate`) if `frontend/.output/public` is missing
- Then run `uv run app.py`

### Windows

1. Configure R2 (see above); optional: copy `.env.example` to `.env`
2. Optional: for faster Bilibili downloads, download `aria2c.exe` from [aria2 releases](https://github.com/aria2/aria2/releases) and place it in the project root
3. Run:

```bat
start.ps1
```

or `start.bat`.

Or manually:

```bat
uv sync
cd frontend
bun install
bun run generate
cd ..
uv run app.py
```

4. Open [http://localhost:5000](http://localhost:5000) (use localhost / HTTPS for clipboard permission)

### Unix (macOS / Linux)

Start scripts can install uv, ffmpeg, and Bun. To install tools yourself:

```bash
# macOS
brew install ffmpeg node uv

# Debian / Ubuntu
sudo apt update
sudo apt install -y ffmpeg nodejs curl
# uv: https://docs.astral.sh/uv/getting-started/installation/
```

Optional aria2: `brew install aria2` or `sudo apt install -y aria2`.

**Start:**

```bash
chmod +x start.sh   # first time only
./start.sh
```

Or manually:

```bash
uv sync
cd frontend && bun install && bun run generate && cd ..
uv run app.py
```

Open [http://localhost:5000](http://localhost:5000). On LAN: `http://<host-ip>:5000` (LAN HTTP **cannot** request clipboard-read permission — paste into the URL field or use the Ctrl+V fallback).

An older **retro UI** still exists at [http://localhost:5000/retro](http://localhost:5000/retro) (not linked from the main page).

### Frontend dev (optional)

Run the API server and Nuxt dev server separately (API proxied to FastAPI):

```bash
uv run app.py          # :5000 — API + built UI if present
cd frontend && bun run dev   # :3000 — hot reload; /api/* → :5000
```

### Docker

Build:

```bash
./build-image.sh              # → mio9/bili2vrc:latest (see script for tags)
# or: docker build -t bili2vrchat .
```

Run:

```bash
docker run --rm -p 5000:5000 \
  -e CF_ACCOUNT_ID=your-account-id \
  -e R2_ACCESS_KEY_ID=your-access-key-id \
  -e R2_SECRET_ACCESS_KEY=your-secret-access-key \
  -e R2_BUCKET_NAME=my-vrchat-videos \
  -e R2_PUBLIC_BASE_URL=https://pub-xxxx.r2.dev \
  -v bili2vrchat-temp:/app/temp \
  bili2vrchat
```

Image: Bun builds Nuxt frontend; Python deps via `uv sync` from `uv.lock`; `CMD` is `uv run app.py`. Includes `ffmpeg`, `aria2`, `nodejs`. Pass R2 credentials via `-e` or `--env-file` (do not bake secrets into the image).

---

## Tampermonkey: Bilibili / YouTube → bili2vrc

Optional userscript: hover a video cover → **下載解析** → opens bili2vrc with `?url=` filled and **Fetch formats** started so you can pick a resolution.

**Bilibili:** cover hover (home / search / dynamics, etc.), **favorites**, **history**, and watch-page **related** cards.

**YouTube:** home, **watch history** (`/feed/history`), **subscriptions** (`/feed/subscriptions`), search, channel videos, watch-page **related** cards, **watch** page (**下載解析** to the left of Like), and **Shorts** (above Like in the right-hand action stack). The watch-page button is inline in the action bar so it does not overlay fullscreen playback.

**[Install bili2vrc Bridge](https://raw.githubusercontent.com/yuentw/bili2vrc/main/userscripts/bili2vrc-bridge.user.js)** — opens the Tampermonkey install page (requires [Tampermonkey](https://www.tampermonkey.net/) first).

1. Install [Tampermonkey](https://www.tampermonkey.net/)
2. Click **[Install bili2vrc Bridge](https://raw.githubusercontent.com/yuentw/bili2vrc/main/userscripts/bili2vrc-bridge.user.js)** and confirm install
3. Start bili2vrc (`start.ps1` / `start.bat` / `start.sh`)
4. On Bilibili or YouTube, hover a video card and click **下載解析**. On a YouTube watch page, use the button to the left of Like; on Shorts, use the button above Like.

Source: [userscripts/bili2vrc-bridge.user.js](userscripts/bili2vrc-bridge.user.js)

Default target: `http://localhost:5000`. Change via Tampermonkey menu → **設定 bili2vrc 網址**.

Deep link format: `http://localhost:5000/?url=<encoded video URL>`

---

## Usage

1. **Paste URL** — Bilibili or YouTube link → **Fetch formats**. **Paste** reads the clipboard then fetches; if the clipboard is not text (e.g. an image), it does nothing so you can copy a URL and click again
2. **Cookies (if needed)** — age-restricted / member videos: export `cookies.txt` and upload in the UI (stored in browser only). See [cookies/README.md](cookies/README.md)
3. **Pick a format** — choose resolution / codec / dynamic range (fills “original” bitrate). HDR rows show `HDR` / `HDR10` / `HLG`
4. **Upload options**
   - **Custom path** — optional object key; empty = random `f_xxxxxx`
   - **Retention** — 1 h / 1 d / 7 d / 30 d / forever (auto-delete when not forever)
   - **Playback speed** — permanent change before upload; ≠ 1.0x re-encodes (CFR, pitch preserved) and switches to **AV1**
   - **Output mode** — **Keep original** (default; faststart only) / **AV1** / **H.264** (VRChat-oriented Main Profile)
   - **HDR → SDR** — shown only when the selected format is HDR; downloads that stream then tonemaps to SDR (forces re-encode, switches off Keep original)
   - **Advanced encoding**
     - **Encode mode** — VBR (quality + ceiling) or CBR (fixed bitrate)
     - **CRF / CQ** — codec-specific quality slider
     - **Mapping (HDR→SDR)** — Mobius (default) / BT.2390 / Hable (`libplacebo`; enabled when HDR→SDR is on)
     - **Bitrate** — “original” or custom presets  
       - CBR custom: `2000 / 4000 / 5000 / 6000 / 8000 / 10000` kbps  
       - Only “original” auto-scales bitrate with speed; custom CBR / VBR do **not**
5. **Start** — download → verify → transcode (if needed) → upload to R2 → preview via R2 URL
6. **Copy URL** — paste into VRChat when upload completes

### When does it re-encode?

| Condition | Behavior |
|-----------|----------|
| **Keep original**, 1.0x, HDR→SDR off | **faststart** only (`-c copy`) |
| **AV1** or **H.264** | Re-encode to that codec (HW when available) |
| Playback speed ≠ 1.0x | Time stretch + re-encode (cannot keep original; UI switches to AV1) |
| **HDR → SDR** on | Tonemap (`libplacebo`) + re-encode (cannot keep original; UI switches to AV1) |

Example result: `https://pub-xxxx.r2.dev/f_abc123`

---

## TTL & auto-delete

| UI choice | Behavior |
|-----------|----------|
| 1 hour / 1 day / 7 days / 30 days | `expires` metadata set on the R2 object |
| Forever | `expires = 0` (no auto-delete; capped if `MAX_TTL` is set) |

A **background thread** in this app scans the bucket every `R2_CLEANUP_INTERVAL` seconds (default 3600) and deletes objects past `expires`. Cleanup runs **only while the app is running**.

---

## Configuration reference

| Variable | Default | Description |
|----------|---------|-------------|
| `CF_ACCOUNT_ID` | `Fill in …` in `src/bili2vrc/config.py` | Cloudflare account ID |
| `R2_ACCESS_KEY_ID` | `Fill in …` | R2 API access key ID |
| `R2_SECRET_ACCESS_KEY` | `Fill in …` | R2 API secret |
| `R2_BUCKET_NAME` | `Fill in …` | Bucket name (**required**) |
| `R2_PUBLIC_BASE_URL` | `Fill in … (optional)` | Public URL for VRChat links |
| `S3_ENDPOINT_URL` | empty | Optional S3-compatible endpoint (overrides R2 URL) |
| `S3_REGION` / `AWS_REGION` | empty | Optional S3 region |
| `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY` / `S3_BUCKET_NAME` / `S3_PUBLIC_BASE_URL` | R2 values | Optional S3 aliases; fall back to the R2 variables |
| `R2_CLEANUP_ENABLED` | on | `0` / `false` to disable expiry cleanup |
| `R2_CLEANUP_INTERVAL` | `3600` | Seconds between expiry scans |
| `MAX_TTL` | `2592000` | Max retention (seconds); `0` = no cap; forever is clamped |
| `DEFAULT_TTL` | `604800` | Default retention if UI omits TTL (7 days) |
| `DEFAULT_BITRATE_KBPS` | `3000` | Default re-encode bitrate (kbps) |
| `MIN_BITRATE_KBPS` | `500` | Minimum bitrate |
| `MAX_BITRATE_KBPS` | `50000` | Maximum bitrate; `0` = no cap |
| `SPEED_BITRATE_FACTOR` | `1.0` | Extra factor when “original” bitrate is scaled by speed |
| `DEFAULT_ENCODE_MODE` | `vbr` | `vbr` or `cbr` |
| `DEFAULT_ENCODE_QUALITY` | `balanced` | `high` / `balanced` / `medium` / `small` |
| `DEFAULT_OUTPUT_CODEC` | `av1` | API default codec when not keeping original (`av1` / `h264` / `h265`). The **UI** still defaults to Keep original |
| `YTDLP_JS_RUNTIME` | `auto` | `auto` (node → bun → deno) / `node` / `bun` / `deno` |
| `HOST` | `0.0.0.0` | Bind address |
| `PORT` | `5000` | HTTP port |
| `FRONTEND_DIST` | `frontend/.output/public` | Nuxt static output directory |
| `HW_ENCODER` | `auto` | `auto`, `av1_nvenc`, `libsvtav1`, `h264_nvenc`, `libx264`, `h264_qsv`, … |
| `DISABLE_HW_ACCEL` | off | `1` / `true` to force software encode/decode only |
| `LOG_LEVEL` | `INFO` | Python log level |
| `DISABLE_ARIA2C` | off | `1` / `true` to disable aria2c |
| `COOKIE_MAX_BYTES` | `65536` | Max cookie payload per request |

---

## Cookies

Login cookies for restricted videos are stored in **browser localStorage**, not on the server. Export steps: [cookies/README.md](cookies/README.md).

---

## Project layout

| Path | Role |
|------|------|
| `app.py` | Entry launcher → `uv run` → uvicorn + FastAPI |
| `src/bili2vrc/main.py` | FastAPI app factory, lifespan, static SPA |
| `src/bili2vrc/config.py` | Settings (R2, TTL, encode, paths); loads `.env` |
| `src/bili2vrc/api/` | REST + SSE routes (`/api/*`) |
| `src/bili2vrc/services/` | Format fetch, download/upload pipeline, job control |
| `src/bili2vrc/media/` | ffmpeg transcode, MP4 verify / faststart |
| `src/bili2vrc/download/` | yt-dlp helpers, cookies, aria2c |
| `src/bili2vrc/storage/r2.py` | R2 upload, public URL, expiry cleanup |
| `src/bili2vrc/encoding/hwaccel.py` | Hardware encoder detection and ffmpeg args |
| `frontend/` | Nuxt 4 SPA (`bun run generate` or `bun run dev`) |
| `frontend/.output/public` | Built static files served by FastAPI |
| `pyproject.toml` / `uv.lock` | Python project + locked deps (uv) |
| `requirements.txt` | Legacy pip list (mirror of main deps) |
| `start.ps1` / `start.bat` / `start.sh` | Auto-install uv / ffmpeg / Bun, refresh yt-dlp, build frontend, `uv run app.py` |
| `build-image.sh` | Docker image build helper |
| `Dockerfile` | Multi-stage: Bun frontend + `uv sync` + Python runtime |
| `userscripts/bili2vrc-bridge.user.js` | Optional Tampermonkey bridge (Bilibili / YouTube → bili2vrc) |
| `temp/` | Download/transcode scratch (gitignored) |

---

## Troubleshooting

| Issue | Check |
|-------|--------|
| `請設定 R2 環境變數` / R2 not configured | Fill `src/bili2vrc/config.py` or set env vars / `.env`; avoid `Fill in …` placeholders |
| Upload fails (403 / signature) | Rotate API token; verify bucket name and permissions |
| No HTTP URL after upload | Set `R2_PUBLIC_BASE_URL`; enable bucket **Settings → Custom Domains** (or Public Development URL) |
| YouTube fetch fails | Need a JS runtime: Node.js, Bun, or Deno (`node -version` / start scripts already install Bun) |
| `uv` / `bun` / `ffmpeg` not found | Run `start.ps1` / `start.bat` / `start.sh` (installs into `.uv` / `.bun` / `.ffmpeg`), or install manually |
| Frontend missing / blank UI | Run `cd frontend && bun install && bun run generate` |
| Bilibili slow | Add `aria2c.exe` to project root (Windows) or install aria2 to `PATH`. When fetching formats, choosing a non-H.264 source codec (e.g. AV1 / H.265 / VP9) can also speed up downloads |
| Expired files still in bucket | App must be running for cleanup; or wait until next scan interval |
| VRChat won’t play / can’t seek | Use output mode **H.264**; ensure `R2_PUBLIC_BASE_URL` is set |
| File balloons after speed change | Use **CBR** or a lower VBR ceiling / CRF; prefer custom bitrate presets |
| Paste does nothing | Clipboard may be an image / empty; copy the URL as text and click **Paste** again. On LAN HTTP the browser blocks clipboard-read — paste into the URL field or wait for the Ctrl+V prompt |
| Paste can’t read clipboard | Use `http://127.0.0.1:5000` or HTTPS; on LAN HTTP use Ctrl+V fallback or paste manually |
| HDR looks washed / crushed | Enable **HDR → SDR** on an HDR format; try another **Mapping** (Mobius / BT.2390 / Hable). Needs ffmpeg with **libplacebo** + Vulkan |
| Does 1.0x re-encode? | Only with **Keep original** and HDR→SDR off: no (faststart + verify). **AV1** / **H.264** / speed change / HDR→SDR always re-encode |
