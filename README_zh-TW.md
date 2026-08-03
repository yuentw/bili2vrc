# bili2vrchat

> neko 🐱

[English](README.md) | **繁體中文**

用於下載 Bilibili / YouTube 影片、可選轉碼以適配 VRChat，並透過 Worker 預簽名介面上傳至 Cloudflare R2 的 Web 介面。

```
瀏覽器 → Flask (yt-dlp / ffmpeg) → R2 → VRChat 直連
```

## 前置依賴

| 工具 | 是否必需 | 說明 |
|------|----------|------|
| Python 3.10+ | 是 | 已在 3.14 上測試 |
| [ffmpeg](https://ffmpeg.org/) | 是 | 需將 `ffprobe` 加入 `PATH` |
| [Node.js](https://nodejs.org/) | YouTube 必需 | 供 yt-dlp 使用（`--js-runtimes node`） |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | 是 | 透過 `requirements.txt` 安裝 |
| aria2c | 可選 | 加速 Bilibili 下載；**不用於 YouTube** |

---

## Windows

### 1. 安裝系統工具

1. 安裝 **Python 3**，並確保 `python` 在 `PATH` 中。
2. 安裝 **ffmpeg** 並加入 `PATH`（在新終端機中執行 `ffmpeg -version` 應能正常運作）。
3. 安裝 **Node.js**（執行 `node -version` 應能正常運作）。

### 2. 可選：內建 aria2c

將 `aria2c.exe` 放在專案根目錄，可加速 Bilibili 下載。程式會優先檢查專案目錄，再查找 `PATH`。

### 3. 啟動

```bat
start.bat
```

`start.bat` 會安裝 Python 依賴並執行 `python app.py`。

也可手動執行：

```bat
python -m pip install -r requirements.txt
python app.py
```

### 4. 在瀏覽器中開啟

[http://localhost:5000](http://localhost:5000)

---

## Unix（macOS / Linux）

### 1. 安裝系統工具

**macOS（Homebrew 範例）：**

```bash
brew install ffmpeg node aria2
```

**Debian / Ubuntu：**

```bash
sudo apt update
sudo apt install -y ffmpeg nodejs aria2 python3 python3-pip python3-venv
```

### 2. Python 環境（建議）

```bash
cd /path/to/bili2vrchat
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

### 3. 啟動

```bash
chmod +x start.sh   # 僅首次需要
./start.sh
```

`start.sh` 若存在 `.venv` 會先啟用，再執行 `python3 app.py`。

也可手動執行：

```bash
source .venv/bin/activate   # 若使用 venv
python3 app.py
```

### 4. 在瀏覽器中開啟

[http://localhost:5000](http://localhost:5000)

同一區域網路內的其他裝置可存取 `http://<主機IP>:5000`（預設綁定 `0.0.0.0`）。

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

映像檔已包含 `ffmpeg`、`aria2` 和 `nodejs`。

---

## 設定

透過環境變數設定（可選，預設值見 `config.py`）：

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `HOST` | `0.0.0.0` | 綁定位址 |
| `PORT` | `5000` | HTTP 連接埠 |
| `WORKER_URL` | （見 `config.py`） | Cloudflare Worker 基礎 URL |
| `ADMIN_PASS` | （見 `config.py`） | Worker 管理員密碼，用於預簽名 |
| `DEFAULT_TTL` | `604800` | R2 物件預設 TTL（秒） |
| `HW_ENCODER` | `auto` | 硬體編碼器：`auto`、`libx264`，或如 `h264_videotoolbox` |
| `LOG_LEVEL` | `INFO` | Python 日誌級別 |
| `DISABLE_ARIA2C` | 關閉 | 設為 `1` / `true` 可全域停用 aria2c |
| `COOKIE_MAX_BYTES` | `65536` | 單次請求允許的 Cookie 最大體積 |

範例（Unix）：

```bash
export PORT=8080
export LOG_LEVEL=DEBUG
export DISABLE_ARIA2C=1
./start.sh
```

範例（Windows cmd）：

```bat
set PORT=8080
set LOG_LEVEL=DEBUG
python app.py
```

---

## Cookie

年齡限制或會員專享影片的登入 Cookie 儲存在**瀏覽器 localStorage** 中，不會儲存在伺服器上。匯出與上傳步驟見 [cookies/README.md](cookies/README.md)。

---

## 專案結構

| 路徑 | 用途 |
|------|------|
| `app.py` | Flask 應用程式，下載 / 轉碼 / 上傳流程 |
| `config.py` | 基於環境變數的設定 |
| `hwaccel.py` | 硬體編碼器偵測 |
| `static/cookies.js` | 客戶端 Cookie 儲存輔助 |
| `templates/index.html` | 主介面 |
| `start.sh` / `start.bat` | 本地啟動指令碼 |
| `temp/` | 下載與轉碼暫存目錄（已 gitignore） |
