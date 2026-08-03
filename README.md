# bili2vrchat

> neko 🐱🐈

Web UI to download Bilibili / YouTube videos, optionally transcode for VRChat, and upload to Cloudflare R2 via a Worker presign endpoint.

```
Browser → Flask (yt-dlp / ffmpeg) → R2 → VRChat direct URL
```

## Prerequisites

| Tool | Required | Notes |
|------|----------|--------|
| Python 3.10+ | Yes | 3.14 tested |
| [ffmpeg](https://ffmpeg.org/) | Yes | Must include `ffprobe` on `PATH` |
| [Node.js](https://nodejs.org/) | Yes for YouTube | Used by yt-dlp (`--js-runtimes node`) |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | Yes | Installed via `requirements.txt` |
| aria2c | Optional | Speeds up Bilibili downloads; **not used for YouTube** |

---

## Windows

### 1. Install system tools

1. Install **Python 3** and ensure `python` is on `PATH`.
2. Install **ffmpeg** and add it to `PATH` (`ffmpeg -version` should work in a new terminal).
3. Install **Node.js** (`node -version` should work).

### 2. Optional: bundled aria2c

Place `aria2c.exe` in the project root for faster Bilibili downloads. The app checks the project folder before `PATH`.

### 3. Start

```bat
start.bat
```

`start.bat` installs Python dependencies and runs `python app.py`.

Or manually:

```bat
python -m pip install -r requirements.txt
python app.py
```

### 4. Open in browser

[http://localhost:5000](http://localhost:5000)

---

## Unix (macOS / Linux)

### 1. Install system tools

**macOS (Homebrew example):**

```bash
brew install ffmpeg node aria2
```

**Debian / Ubuntu:**

```bash
sudo apt update
sudo apt install -y ffmpeg nodejs aria2 python3 python3-pip python3-venv
```

### 2. Python environment (recommended)

```bash
cd /path/to/bili2vrchat
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

### 3. Start

```bash
chmod +x start.sh   # first time only
./start.sh
```

`start.sh` activates `.venv` if present, then runs `python3 app.py`.

Or manually:

```bash
source .venv/bin/activate   # if using venv
python3 app.py
```

### 4. Open in browser

[http://localhost:5000](http://localhost:5000)

On another machine in the same network, use `http://<host-ip>:5000` (default bind is `0.0.0.0`).

---

## Docker

```bash
docker build -t bili2vrchat .
docker run --rm -p 5000:5000 \
  -e WORKER_URL=https://your-worker.example \
  -e ADMIN_PASS=your-secret \
  -v bili2vrchat-temp:/app/temp \
  bili2vrchat
```

Image includes `ffmpeg`, `aria2`, and `nodejs`.

---

## Configuration

Set via environment variables (optional overrides in `config.py` defaults):

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Bind address |
| `PORT` | `5000` | HTTP port |
| `WORKER_URL` | (see `config.py`) | Cloudflare Worker base URL |
| `ADMIN_PASS` | (see `config.py`) | Worker admin password for presign |
| `DEFAULT_TTL` | `604800` | Default R2 object TTL (seconds) |
| `HW_ENCODER` | `auto` | Hardware encoder: `auto`, `libx264`, or e.g. `h264_videotoolbox` |
| `LOG_LEVEL` | `INFO` | Python log level |
| `DISABLE_ARIA2C` | off | Set `1` / `true` to disable aria2c globally |
| `COOKIE_MAX_BYTES` | `65536` | Max cookie payload size per request |

Example (Unix):

```bash
export PORT=8080
export LOG_LEVEL=DEBUG
export DISABLE_ARIA2C=1
./start.sh
```

Example (Windows cmd):

```bat
set PORT=8080
set LOG_LEVEL=DEBUG
python app.py
```

---

## Cookies

Login cookies for age-restricted or member-only videos are stored in **browser localStorage**, not on the server. See [cookies/README.md](cookies/README.md) for export and upload steps.

---

## Project layout

| Path | Role |
|------|------|
| `app.py` | Flask app, download/transcode/upload pipeline |
| `config.py` | Environment-based settings |
| `hwaccel.py` | Hardware encoder detection |
| `static/cookies.js` | Client-side cookie storage helpers |
| `templates/index.html` | Main UI |
| `start.sh` / `start.bat` | Local launch scripts |
| `temp/` | Download/transcode scratch (gitignored) |
