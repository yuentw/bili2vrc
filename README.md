# bili2vrchat

> neko 🐱

**English** | [繁體中文](README_zh-TW.md)

Web UI to download Bilibili / YouTube videos, optionally transcode for VRChat, and upload to **your own Cloudflare R2 bucket** via the S3 API. No Cloudflare Worker required.

```
Browser → Flask (yt-dlp / ffmpeg) → R2 (S3 API) → VRChat direct URL
```

## Features

- Download from **Bilibili** and **YouTube** (yt-dlp)
- Optional **H.264 VRChat compat** transcode, playback speed change, faststart
- Upload to **your R2 bucket** (boto3 / S3-compatible API)
- **TTL** in the UI (1 h / 1 d / 7 d / 30 d / forever) with background expiry cleanup
- Cookies stored in **browser localStorage** only (not on server disk)

---

## Prerequisites

| Tool | Required | Notes |
|------|----------|--------|
| Python 3.10+ | Yes | 3.14 tested |
| [ffmpeg](https://ffmpeg.org/) | Yes | `ffmpeg` and `ffprobe` on `PATH` |
| [Node.js](https://nodejs.org/) | Yes for YouTube | yt-dlp (`--js-runtimes node`) |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | Yes | via `requirements.txt` |
| Cloudflare R2 bucket | Yes | see [R2 setup](#cloudflare-r2-setup) below |
| aria2c | Optional | faster Bilibili downloads; **not used for YouTube** |

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

1. Open your bucket → **Settings**
2. Enable **Public access** / **R2.dev subdomain** (or connect a custom domain)
3. Copy the public base URL, e.g. `https://pub-xxxxxxxx.r2.dev` → `R2_PUBLIC_BASE_URL`

Without `R2_PUBLIC_BASE_URL`, uploads still work; the app returns `r2://bucket/key` instead of an HTTP link.

### 5. Streaming / seek

Public R2 URLs support **HTTP Range** requests. Combined with the app’s **faststart** step, VRChat can play progressively without downloading the full file first. This is progressive MP4 playback, not HLS/live streaming.

---

## Configure bili2vrchat

Two ways (env vars override `config.py`):

### Option A — Edit `config.py` (simplest for local use)

Open `config.py` and replace the `Fill in … here` placeholders:

```python
CF_ACCOUNT_ID        = os.environ.get("CF_ACCOUNT_ID", "your-account-id")
R2_ACCESS_KEY_ID     = os.environ.get("R2_ACCESS_KEY_ID", "your-access-key-id")
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY", "your-secret-access-key")
R2_BUCKET_NAME       = os.environ.get("R2_BUCKET_NAME", "my-vrchat-videos")
R2_PUBLIC_BASE_URL   = os.environ.get("R2_PUBLIC_BASE_URL", "https://pub-xxxx.r2.dev").rstrip("/")
```

Values starting with `Fill in ` are treated as **not configured**.

> Do not commit real secrets to git. Use env vars or a local-only `config.py` for production.

### Option B — Environment variables

**Windows (cmd), before `start.bat` or in `start.bat`:**

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

### Windows

1. Install **Python 3**, **ffmpeg** (`ffmpeg -version`), **Node.js** (`node -version`)
2. Optional: place `aria2c.exe` in the project root for faster Bilibili downloads
3. Configure R2 (see above)
4. Run:

```bat
start.bat
```

Or manually:

```bat
python -m pip install -r requirements.txt
python app.py
```

5. Open [http://localhost:5000](http://localhost:5000)

### Unix (macOS / Linux)

**Install tools:**

```bash
# macOS
brew install ffmpeg node aria2

# Debian / Ubuntu
sudo apt update
sudo apt install -y ffmpeg nodejs aria2 python3 python3-pip python3-venv
```

**venv (recommended):**

```bash
cd /path/to/bili2vrchat
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

**Start:**

```bash
chmod +x start.sh   # first time only
./start.sh
```

Open [http://localhost:5000](http://localhost:5000). On LAN: `http://<host-ip>:5000` (bind `0.0.0.0` by default).

**Retro UI:** [http://localhost:5000/retro](http://localhost:5000/retro)

### Docker

```bash
docker build -t bili2vrchat .
docker run --rm -p 5000:5000 \
  -e CF_ACCOUNT_ID=your-account-id \
  -e R2_ACCESS_KEY_ID=your-access-key-id \
  -e R2_SECRET_ACCESS_KEY=your-secret-access-key \
  -e R2_BUCKET_NAME=my-vrchat-videos \
  -e R2_PUBLIC_BASE_URL=https://pub-xxxx.r2.dev \
  -v bili2vrchat-temp:/app/temp \
  bili2vrchat
```

Image includes `ffmpeg`, `aria2`, and `nodejs`. Pass R2 credentials via `-e` (do not bake secrets into the image).

---

## Usage

1. **Paste URL** — Bilibili or YouTube link → **Fetch formats**
2. **Cookies (if needed)** — age-restricted / member videos: export `cookies.txt` and upload in the UI (stored in browser only). See [cookies/README.md](cookies/README.md)
3. **Pick a format** — choose resolution / codec from the table
4. **Upload options**
   - **Custom path** — optional object key; empty = random `f_xxxxxx`
   - **Retention** — 1 h / 1 d / 7 d / 30 d / forever (auto-delete when not forever)
   - **Playback speed** — permanent speed change before upload
   - **VRChat compat mode** — re-encode to H.264 (fixes some sync/tear issues; slower)
5. **Start** — download → transcode (if needed) → upload to R2
6. **Copy URL** — paste into VRChat when upload completes

Example result: `https://pub-xxxx.r2.dev/f_abc123`

---

## TTL & auto-delete

| UI choice | Behavior |
|-----------|----------|
| 1 hour / 1 day / 7 days / 30 days | `expires` metadata set on the R2 object |
| Forever | `expires = 0` (no auto-delete) |

A **background thread** in this app scans the bucket every `R2_CLEANUP_INTERVAL` seconds (default 3600) and deletes objects past `expires`. Cleanup runs **only while the app is running**.

---

## Configuration reference

| Variable | Default | Description |
|----------|---------|-------------|
| `CF_ACCOUNT_ID` | `Fill in …` in `config.py` | Cloudflare account ID |
| `R2_ACCESS_KEY_ID` | `Fill in …` | R2 API access key ID |
| `R2_SECRET_ACCESS_KEY` | `Fill in …` | R2 API secret |
| `R2_BUCKET_NAME` | `Fill in …` | Bucket name (**required**) |
| `R2_PUBLIC_BASE_URL` | `Fill in … (optional)` | Public URL for VRChat links |
| `R2_CLEANUP_ENABLED` | on | `0` / `false` to disable expiry cleanup |
| `R2_CLEANUP_INTERVAL` | `3600` | Seconds between expiry scans |
| `DEFAULT_TTL` | `604800` | Default retention if UI omits TTL (7 days) |
| `HOST` | `0.0.0.0` | Bind address |
| `PORT` | `5000` | HTTP port |
| `HW_ENCODER` | `auto` | `auto`, `libx264`, `h264_videotoolbox`, etc. |
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
| `app.py` | Flask app: download / transcode / upload pipeline |
| `config.py` | Settings (R2 credentials, TTL, server) |
| `r2.py` | R2 upload, public URL builder, expiry cleanup |
| `hwaccel.py` | Hardware encoder detection |
| `static/cookies.js` | Client-side cookie helpers |
| `templates/index.html` | Main UI |
| `templates/index_pixel.html` | Retro UI (`/retro`) |
| `start.sh` / `start.bat` | Launch scripts |
| `temp/` | Download/transcode scratch (gitignored) |

---

## Troubleshooting

| Issue | Check |
|-------|--------|
| `請設定 R2 環境變數` / R2 not configured | Fill `config.py` or set env vars; avoid leaving `Fill in …` placeholders |
| Upload fails (403 / signature) | Rotate API token; verify bucket name and permissions |
| No HTTP URL after upload | Set `R2_PUBLIC_BASE_URL` and enable bucket public access |
| YouTube fetch fails | Install Node.js; run `node -version` |
| Bilibili slow | Add `aria2c` to project root or `PATH` |
| Expired files still in bucket | App must be running for cleanup; or wait until next scan interval |
| VRChat won’t play / can’t seek | Enable **VRChat compat mode**; ensure `R2_PUBLIC_BASE_URL` is set |
