# bili2vrc

> neko 🐱

[English](README.md) | **繁體中文**

用於下載 **Bilibili / YouTube** 影片，並透過 **R2 S3 API** 上傳至**你自己的 Cloudflare R2 儲存桶**。產生**直連網址**，可在 **VRChat** 觀看，並支援**影片倍速**、**CBR／VBR 編碼**與硬體加速。**不需要**部署 Cloudflare Worker。

```
瀏覽器 → FastAPI (yt-dlp / ffmpeg) → R2 (S3 API) → VRChat 直連
```

## 功能

- 支援 **Bilibili**、**YouTube** 下載（yt-dlp）
- **輸出模式**：**保留原始**（UI 預設）／**AV1**／**H.264**（偏 VRChat 相容重編碼）
- **播放速度**（上傳前永久變更；≠ 1.0x 會強制重編碼，並自動取消保留原始）
- **HDR → SDR**（所選格式為 HDR／HDR10／HLG 時）：可選 tonemap 後再編碼
- **Mapping**（進階）：**Mobius**（預設）／**BT.2390**／**Hable**，經 ffmpeg `libplacebo`（Vulkan GPU；非 NVENC）
- **編碼模式**：**VBR**（品質 + 碼率上限）／**CBR**（固定碼率）
- **CRF／CQ** 依輸出編碼調整；另有編碼器品質預設
- **碼率**：可選「原始」或自訂預設；僅「原始」會在倍速時自動 × 倍速調整碼率
- 硬體編碼自動偵測（NVENC AV1／H.264、QSV、AMF、VideoToolbox 等），失敗回退軟體（`libsvtav1`／`libx264`）
- 下載後 **ffprobe 完整性驗證**；**保留原始**＋原速＋未開 HDR→SDR 時僅做 **faststart**（`-c copy`）
- 上傳至**你的 R2 bucket**；完成後以 **R2 公開網址**預覽（不經本機串流）
- UI 可選**保存時間**（1 小時／1 天／7 天／30 天／永久），背景自動清理過期檔案
- Cookie 僅存於**瀏覽器 localStorage**
- **貼上**會讀取剪貼簿再獲取格式；非文字內容（例如圖片）會忽略，按鈕仍可再按；僅在瀏覽器禁止讀取剪貼簿時才進入 Ctrl+V 等待（常見於區網 HTTP）

---

## 前置依賴

| 工具 | 是否必需 | 說明 |
|------|----------|------|
| Python 3.14+ | 是 | 見 `.python-version`、`pyproject.toml`。`uv run` 必要時可代為下載此版本 Python |
| [uv](https://docs.astral.sh/uv/) | 是 | Python 依賴與 `uv run app.py`；啟動腳本找不到時會裝到專案 `.uv` |
| [ffmpeg](https://ffmpeg.org/) | 是 | 需要 `ffmpeg`、`ffprobe`。啟動腳本找不到時會自動安裝（Windows：winget `Gyan.FFmpeg`，否則便攜版 `.ffmpeg`；macOS：Homebrew；Linux：便攜版 `.ffmpeg`）。**HDR→SDR** 需建置含 **libplacebo** + **Vulkan** |
| JS runtime（YouTube） | YouTube 必需 | yt-dlp 使用 **node → bun → deno**（`YTDLP_JS_RUNTIME`）。啟動腳本已會安裝 **Bun**，足以跑 YouTube |
| [Bun](https://bun.sh/) | 是（前端） | 啟動腳本可裝到專案 `.bun`，並在需要時建置前端 |
| Cloudflare R2 儲存桶 | 是 | 見下方 [R2 設定教學](#cloudflare-r2-設定教學) |
| [aria2](https://github.com/aria2/aria2) | 可選 | 加速 Bilibili 下載；**啟動腳本不附帶**；**不用於 YouTube** |

### Python 依賴（`pyproject.toml` + `uv.lock`）

以 [uv](https://docs.astral.sh/uv/) 管理。主要套件：

| 套件 | 用途 |
|------|------|
| fastapi / uvicorn | Web UI／API |
| requests | HTTP |
| boto3 | Cloudflare R2（S3 相容）上傳 |
| yt-dlp | Bilibili／YouTube 下載 |
| python-dotenv | 啟動時載入 `.env`（`src/bili2vrc/config.py`） |

`requirements.txt` 僅供參考；安裝請用 `uv sync`／`uv lock`。

### 前端（`frontend/`）

| 技術 | 用途 |
|------|------|
| Nuxt 4／Vue 3 | SPA UI（`bun run generate` → `frontend/.output/public`，由 FastAPI 提供） |

---

## Cloudflare R2 設定教學

只需要 **R2 儲存桶**與 **API Token**，無需 Worker。

### 1. 取得 Account ID

1. 登入 [Cloudflare 儀表板](https://dash.cloudflare.com/)
2. 進入 **Workers & R2**（或任一網域總覽）
3. 右側複製 **Account ID** → 對應 `CF_ACCOUNT_ID`

### 2. 建立儲存桶（Bucket）

1. **Storage & databases** → **R2 object storage**
2. **Create bucket** → 輸入名稱（例如 `my-vrchat-videos`）→ 對應 `R2_BUCKET_NAME`

### 3. 建立 API Token

1. 在 R2 頁面點 **Manage R2 API Tokens** → **Create API token**
2. 權限選 **Object Read & Write**（範圍可限單一 bucket 或整個帳號）
3. 建立後複製：
   - **Access Key ID** → `R2_ACCESS_KEY_ID`
   - **Secret Access Key** → `R2_SECRET_ACCESS_KEY`

> Secret 只顯示**一次**，請妥善保存。遺失請重新建立 Token。

### 4. 公開存取（給 VRChat 直連）

R2 預設為私有。要讓 VRChat 用 HTTP 網址播放：

1. Cloudflare 儀表板 → **R2 Object Storage** → 開啟你的 **bucket**
2. 進入 **Settings**
3. 在 **Custom Domains** 點 **Add**，綁定網域（例如 `b2v.example.com`）
4. 等到 **Status** 為 **Active**、**Access** 為 **Enabled**
5. 將 `R2_PUBLIC_BASE_URL` 設成該網域，例如 `https://b2v.example.com`  
   （可省略 `https://`，程式會自動補上）

也可在同一 Settings 頁啟用 **Public Development URL**（`https://pub-xxxxxxxx.r2.dev`）作為 `R2_PUBLIC_BASE_URL`。

未設定 `R2_PUBLIC_BASE_URL` 時仍可上傳，但回傳的是 `r2://bucket/key` 而非 HTTP 連結。

### 5. 串流／跳轉

公開 R2 網址支援 **HTTP Range**。搭配程式的 **faststart**，VRChat 可漸進播放、不必先下載整檔。這是漸進式 MP4，不是 HLS／直播。

上傳完成後，頁面預覽使用 **R2 公開網址**。本機伺服器關掉後，已開啟的結果頁在連結仍有效時可繼續播，但無法再獲取格式或開新任務。

---

## 設定 bili2vrchat

兩種方式（環境變數會覆蓋 `src/bili2vrc/config.py`）。也可把 [.env.example](.env.example) 複製成 `.env`——匯入時會執行 `load_dotenv()`。

### 方式 A — 改 `src/bili2vrc/config.py`（本機最簡單）

開啟 `src/bili2vrc/config.py`，把 `Fill in …` 佔位符換成實際值：

```python
CF_ACCOUNT_ID        = os.environ.get("CF_ACCOUNT_ID", "your-account-id")
R2_ACCESS_KEY_ID     = os.environ.get("R2_ACCESS_KEY_ID", "your-access-key-id")
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY", "your-secret-access-key")
R2_BUCKET_NAME       = os.environ.get("R2_BUCKET_NAME", "my-vrchat-videos")
R2_PUBLIC_BASE_URL   = os.environ.get("R2_PUBLIC_BASE_URL", "https://pub-xxxx.r2.dev").rstrip("/")
```

以 `Fill in ` 開頭的值會被視為**尚未設定**。

> 不要把真實密鑰提交進 git。正式環境請用環境變數，或僅本機使用的 `src/bili2vrc/config.py`。

### 方式 B — 環境變數

**Windows（cmd），在執行 `start.bat`／`start.ps1` 之前：**

```bat
set CF_ACCOUNT_ID=your-account-id
set R2_ACCESS_KEY_ID=your-access-key-id
set R2_SECRET_ACCESS_KEY=your-secret-access-key
set R2_BUCKET_NAME=my-vrchat-videos
set R2_PUBLIC_BASE_URL=https://pub-xxxx.r2.dev
```

**Unix：**

```bash
export CF_ACCOUNT_ID=your-account-id
export R2_ACCESS_KEY_ID=your-access-key-id
export R2_SECRET_ACCESS_KEY=your-secret-access-key
export R2_BUCKET_NAME=my-vrchat-videos
export R2_PUBLIC_BASE_URL=https://pub-xxxx.r2.dev
```

---

## 安裝與執行

### 啟動腳本會做什麼

`start.ps1`／`start.bat`／`start.sh` 會：

- 找不到 **uv** 時安裝到專案 `.uv`
- 找不到 `ffmpeg`／`ffprobe` 時安裝 ffmpeg（見 [前置依賴](#前置依賴)）
- 用 `uv lock --upgrade-package yt-dlp` 更新 **yt-dlp**（失敗則沿用現有版本）
- 找不到 **Bun** 時安裝到專案 `.bun`
- 缺少 `frontend/.output/public` 時建置前端（`bun install` + `bun run generate`）
- 然後執行 `uv run app.py`

### Windows

1. 設定 R2（見上方）；可選：把 `.env.example` 複製成 `.env`
2. 可選：若要加速 Bilibili，從 [aria2 releases](https://github.com/aria2/aria2/releases) 下載 `aria2c.exe` 放在專案根目錄
3. 執行：

```bat
start.ps1
```

或 `start.bat`。

或手動：

```bat
uv sync
cd frontend
bun install
bun run generate
cd ..
uv run app.py
```

4. 開啟 [http://localhost:5000](http://localhost:5000)（剪貼簿權限請用 localhost／HTTPS）

### Unix（macOS / Linux）

啟動腳本可安裝 uv、ffmpeg、Bun。若要自行安裝工具：

```bash
# macOS
brew install ffmpeg node uv

# Debian / Ubuntu
sudo apt update
sudo apt install -y ffmpeg nodejs curl
# uv：https://docs.astral.sh/uv/getting-started/installation/
```

可選 aria2：`brew install aria2` 或 `sudo apt install -y aria2`。

**啟動：**

```bash
chmod +x start.sh   # 僅首次
./start.sh
```

或手動：

```bash
uv sync
cd frontend && bun install && bun run generate && cd ..
uv run app.py
```

開啟 [http://localhost:5000](http://localhost:5000)。區網請用 `http://<主機IP>:5000`（區網 HTTP **無法**申請 clipboard-read 權限——請貼到網址欄，或使用 Ctrl+V 後備）。

舊版 **retro UI** 仍在 [http://localhost:5000/retro](http://localhost:5000/retro)（主畫面沒有連結）。

### 前端開發（可選）

API 與 Nuxt 開發伺服器分開跑（API 會代理到 FastAPI）：

```bash
uv run app.py          # :5000 — API + 若已建置則含 UI
cd frontend && bun run dev   # :3000 — 熱更新；/api/* → :5000
```

### Docker

建置：

```bash
./build-image.sh              # → mio9/bili2vrc:latest（標籤見腳本）
# 或：docker build -t bili2vrchat .
```

執行：

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

映像檔以 Bun 建置 Nuxt 前端；Python 依賴由 `uv sync`（`uv.lock`）安裝；`CMD` 為 `uv run app.py`。含 `ffmpeg`、`aria2`、`nodejs`。R2 憑證請用 `-e` 或 `--env-file` 傳入，勿寫進映像檔。

---

## Tampermonkey：Bilibili／YouTube → bili2vrc

可選 userscript：滑鼠停在影片封面上 → **下載解析** → 開啟 bili2vrc，帶入 `?url=` 並開始**獲取格式**，方便選畫質。

**Bilibili：** 封面懸浮（首頁／搜尋／動態等）、**收藏**、**歷史記錄**、播放頁**相關推薦**卡片。

**YouTube：** 首頁、**觀看紀錄**（`/feed/history`）、**訂閱／新影片**（`/feed/subscriptions`）、搜尋、頻道影片、觀看頁**右側推薦**、**觀看頁**（**下載解析** 在按讚鈕左邊），以及 **Shorts**（右側互動欄、按讚鈕上方）。觀看頁鈕在動作列內，全螢幕時不會蓋住畫面。

**[安裝 bili2vrc Bridge](https://raw.githubusercontent.com/yuentw/bili2vrc/main/userscripts/bili2vrc-bridge.user.js)** — 開啟 Tampermonkey 安裝頁（需先裝 [Tampermonkey](https://www.tampermonkey.net/)）。

1. 安裝 [Tampermonkey](https://www.tampermonkey.net/)
2. 點 **[安裝 bili2vrc Bridge](https://raw.githubusercontent.com/yuentw/bili2vrc/main/userscripts/bili2vrc-bridge.user.js)** 並確認安裝
3. 啟動 bili2vrc（`start.ps1`／`start.bat`／`start.sh`）
4. 在 Bilibili 或 YouTube 將游標停在影片卡片上，點 **下載解析**。YouTube 觀看頁請用按讚鈕左邊的鈕；Shorts 請用右側按讚上方的鈕。

原始碼：[userscripts/bili2vrc-bridge.user.js](userscripts/bili2vrc-bridge.user.js)

預設目標：`http://localhost:5000`。可在 Tampermonkey 選單 → **設定 bili2vrc 網址** 變更。

深連結格式：`http://localhost:5000/?url=<編碼後的影片網址>`

---

## 使用方式

1. **貼上網址** — Bilibili 或 YouTube 連結 → **獲取格式**。**貼上**會讀取剪貼簿再獲取；若剪貼簿不是文字（例如圖片）則不做任何事，可再複製網址後重按
2. **Cookie（若需要）** — 年齡限制／會員影片：匯出 `cookies.txt` 並在 UI 上傳（僅存瀏覽器）。見 [cookies/README.md](cookies/README.md)
3. **選格式** — 選解析度／編碼／動態範圍（會填入「原始」碼率）。HDR 列會顯示 `HDR`／`HDR10`／`HLG`
4. **上傳選項**
   - **自訂路徑** — 可選物件 key；空白則隨機 `f_xxxxxx`
   - **保存時間** — 1 小時／1 天／7 天／30 天／永久（非永久會自動刪除）
   - **播放速度** — 上傳前永久變更；≠ 1.0x 會重編碼（CFR、音高保留）並切到 **AV1**
   - **輸出模式** — **保留原始**（預設；僅 faststart）／**AV1**／**H.264**（偏 VRChat 的 Main Profile）
   - **HDR → SDR** — 僅在所選格式為 HDR 時顯示；下載該串流後 tonemap 成 SDR（強制重編碼，取消保留原始）
   - **進階編碼**
     - **編碼模式** — VBR（品質 + 上限）或 CBR（固定碼率）
     - **CRF／CQ** — 依編碼的品質滑桿
     - **Mapping（HDR→SDR）** — Mobius（預設）／BT.2390／Hable（`libplacebo`；開啟 HDR→SDR 時可用）
     - **碼率** — 「原始」或自訂預設  
       - CBR 自訂：`2000 / 4000 / 5000 / 6000 / 8000 / 10000` kbps  
       - 僅「原始」會隨倍速自動調整碼率；自訂 CBR／VBR **不會**
5. **開始** — 下載 → 驗證 → 轉碼（若需要）→ 上傳 R2 → 以 R2 網址預覽
6. **複製網址** — 上傳完成後貼到 VRChat

### 什麼時候會重編碼？

| 條件 | 行為 |
|------|------|
| **保留原始**、1.0x、未開 HDR→SDR | 僅 **faststart**（`-c copy`） |
| **AV1** 或 **H.264** | 重編碼為該編碼（有硬體則用硬體） |
| 播放速度 ≠ 1.0x | 時間伸縮 + 重編碼（無法保留原始；UI 切到 AV1） |
| 開啟 **HDR → SDR** | Tonemap（`libplacebo`）+ 重編碼（無法保留原始；UI 切到 AV1） |

結果範例：`https://pub-xxxx.r2.dev/f_abc123`

---

## TTL 與自動刪除

| UI 選項 | 行為 |
|---------|------|
| 1 小時／1 天／7 天／30 天 | 在 R2 物件寫入 `expires` metadata |
| 永久 | `expires = 0`（不自動刪；若設了 `MAX_TTL` 會被上限夾住） |

本程式有一條**背景執行緒**，每隔 `R2_CLEANUP_INTERVAL` 秒（預設 3600）掃描 bucket，刪除已過 `expires` 的物件。清理**只在應用程式運行時**進行。

---

## 設定變數一覽

| 變數 | 預設 | 說明 |
|------|------|------|
| `CF_ACCOUNT_ID` | `src/bili2vrc/config.py` 的 `Fill in …` | Cloudflare 帳號 ID |
| `R2_ACCESS_KEY_ID` | `Fill in …` | R2 API access key ID |
| `R2_SECRET_ACCESS_KEY` | `Fill in …` | R2 API secret |
| `R2_BUCKET_NAME` | `Fill in …` | Bucket 名稱（**必填**） |
| `R2_PUBLIC_BASE_URL` | `Fill in … (optional)` | 給 VRChat 的公開網址 |
| `S3_ENDPOINT_URL` | 空 | 可選 S3 相容端點（覆蓋 R2 URL） |
| `S3_REGION`／`AWS_REGION` | 空 | 可選 S3 region |
| `S3_ACCESS_KEY_ID`／`S3_SECRET_ACCESS_KEY`／`S3_BUCKET_NAME`／`S3_PUBLIC_BASE_URL` | R2 值 | 可選 S3 別名；未設則沿用 R2 變數 |
| `R2_CLEANUP_ENABLED` | 開 | `0`／`false` 關閉過期清理 |
| `R2_CLEANUP_INTERVAL` | `3600` | 過期掃描間隔（秒） |
| `MAX_TTL` | `2592000` | 最長保存（秒）；`0` = 無上限；永久會被夾住 |
| `DEFAULT_TTL` | `604800` | UI 未指定 TTL 時的預設保存（7 天） |
| `DEFAULT_BITRATE_KBPS` | `3000` | 預設重編碼碼率（kbps） |
| `MIN_BITRATE_KBPS` | `500` | 最低碼率 |
| `MAX_BITRATE_KBPS` | `50000` | 最高碼率；`0` = 無上限 |
| `SPEED_BITRATE_FACTOR` | `1.0` | 「原始」碼率依倍速縮放時的額外係數 |
| `DEFAULT_ENCODE_MODE` | `vbr` | `vbr` 或 `cbr` |
| `DEFAULT_ENCODE_QUALITY` | `balanced` | `high`／`balanced`／`medium`／`small` |
| `DEFAULT_OUTPUT_CODEC` | `av1` | 非保留原始時的 API 預設編碼（`av1`／`h264`／`h265`）。**UI** 仍預設保留原始 |
| `YTDLP_JS_RUNTIME` | `auto` | `auto`（node → bun → deno）／`node`／`bun`／`deno` |
| `HOST` | `0.0.0.0` | 綁定位址 |
| `PORT` | `5000` | HTTP 連接埠 |
| `FRONTEND_DIST` | `frontend/.output/public` | Nuxt 靜態輸出目錄 |
| `HW_ENCODER` | `auto` | `auto`、`av1_nvenc`、`libsvtav1`、`h264_nvenc`、`libx264`、`h264_qsv`、… |
| `DISABLE_HW_ACCEL` | 關 | `1`／`true` 強制只用軟體編解碼 |
| `LOG_LEVEL` | `INFO` | Python 日誌等級 |
| `DISABLE_ARIA2C` | 關 | `1`／`true` 停用 aria2c |
| `COOKIE_MAX_BYTES` | `65536` | 每次請求 Cookie 大小上限 |

---

## Cookie

受限影片的登入 Cookie 存在**瀏覽器 localStorage**，不在伺服器。匯出步驟見 [cookies/README.md](cookies/README.md)。

---

## 專案結構

| 路徑 | 用途 |
|------|------|
| `app.py` | 進入點 → `uv run` → uvicorn + FastAPI |
| `src/bili2vrc/main.py` | FastAPI app factory、lifespan、靜態 SPA |
| `src/bili2vrc/config.py` | 設定（R2、TTL、編碼、路徑）；載入 `.env` |
| `src/bili2vrc/api/` | REST + SSE 路由（`/api/*`） |
| `src/bili2vrc/services/` | 獲取格式、下載／上傳流程、任務控制 |
| `src/bili2vrc/media/` | ffmpeg 轉碼、MP4 驗證／faststart |
| `src/bili2vrc/download/` | yt-dlp、Cookie、aria2c |
| `src/bili2vrc/storage/r2.py` | R2 上傳、公開網址、過期清理 |
| `src/bili2vrc/encoding/hwaccel.py` | 硬體編碼器偵測與 ffmpeg 參數 |
| `frontend/` | Nuxt 4 SPA（`bun run generate` 或 `bun run dev`） |
| `frontend/.output/public` | 建置後由 FastAPI 提供的靜態檔 |
| `pyproject.toml`／`uv.lock` | Python 專案與鎖定依賴（uv） |
| `requirements.txt` | 舊版 pip 清單（對應主要依賴） |
| `start.ps1`／`start.bat`／`start.sh` | 自動安裝 uv／ffmpeg／Bun、更新 yt-dlp、建置前端、`uv run app.py` |
| `build-image.sh` | Docker 映像建置輔助 |
| `Dockerfile` | 多階段：Bun 前端 + `uv sync` + Python 執行環境 |
| `userscripts/bili2vrc-bridge.user.js` | 可選 Tampermonkey 橋接（Bilibili／YouTube → bili2vrc） |
| `temp/` | 下載／轉碼暫存（已 gitignore） |

---

## 疑難排解

| 狀況 | 檢查 |
|------|------|
| `請設定 R2 環境變數`／R2 未設定 | 填寫 `src/bili2vrc/config.py` 或設環境變數／`.env`；不要留著 `Fill in …` |
| 上傳失敗（403／簽名） | 換新 API token；核對 bucket 名稱與權限 |
| 上傳後沒有 HTTP 網址 | 設定 `R2_PUBLIC_BASE_URL`；在 bucket **Settings → Custom Domains**（或 Public Development URL）啟用公開存取 |
| YouTube 獲取失敗 | 需要 JS runtime：Node.js、Bun 或 Deno（`node -version`／啟動腳本已會裝 Bun） |
| 找不到 `uv`／`bun`／`ffmpeg` | 跑 `start.ps1`／`start.bat`／`start.sh`（會裝到 `.uv`／`.bun`／`.ffmpeg`），或自行安裝 |
| 前端空白／找不到頁面 | 執行 `cd frontend && bun install && bun run generate` |
| Bilibili 很慢 | Windows：將 `aria2c.exe` 放在專案根目錄；或安裝 aria2 至 `PATH`。獲取格式時選擇非 H.264 來源編碼（如 AV1／H.265／VP9）也可加快下載 |
| 過期檔還在 bucket | 應用程式必須在跑才會清理；或等到下次掃描間隔 |
| VRChat 播不了／不能跳轉 | 輸出模式改用 **H.264**；確認已設 `R2_PUBLIC_BASE_URL` |
| 改倍速後檔案暴肥 | 改用 **CBR**，或降低 VBR 上限／CRF；優先自訂碼率預設 |
| 按貼上沒反應 | 剪貼簿可能是圖片／空白；把網址複製成文字再按一次**貼上**。區網 HTTP 瀏覽器會擋 clipboard-read——請貼到網址欄，或等 Ctrl+V 提示 |
| 貼上讀不到剪貼簿 | 用 `http://127.0.0.1:5000` 或 HTTPS；區網 HTTP 請用 Ctrl+V 後備或手動貼上 |
| HDR 過曝／灰階怪異 | 對 HDR 格式開啟 **HDR → SDR**，或換 **Mapping**（Mobius／BT.2390／Hable）。需 ffmpeg 含 **libplacebo** + Vulkan |
| 1.0x 會重編碼嗎？ | 僅在**保留原始**且未開 HDR→SDR：不會（faststart + 驗證）。**AV1**／**H.264**／改倍速／HDR→SDR 一定重編碼 |
