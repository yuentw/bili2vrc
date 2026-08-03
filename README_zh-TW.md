# bili2vrchat

> neko 🐱

[English](README.md) | **繁體中文**

用於下載 Bilibili / YouTube 影片、可選轉碼以適配 VRChat，並透過 **R2 S3 API** 上傳至**你自己的 Cloudflare R2 儲存桶**。**不需要**部署 Cloudflare Worker。

```
瀏覽器 → Flask (yt-dlp / ffmpeg) → R2 (S3 API) → VRChat 直連
```

## 功能

- 支援 **Bilibili**、**YouTube** 下載（yt-dlp）
- 可選 **VRChat 相容模式**（H.264 重編碼）、播放速度調整、faststart
- 上傳至**你的 R2 bucket**（boto3 / S3 相容 API）
- UI 可選**保存時間**（1 小時／1 天／7 天／30 天／永久），背景自動清理過期檔案
- Cookie 僅存於**瀏覽器 localStorage**，不會長期留在伺服器

---

## 前置依賴

| 工具 | 是否必需 | 說明 |
|------|----------|------|
| Python 3.10+ | 是 | 已在 3.14 上測試 |
| [ffmpeg](https://ffmpeg.org/) | 是 | `ffmpeg`、`ffprobe` 需在 `PATH` |
| [Node.js](https://nodejs.org/) | YouTube 必需 | 供 yt-dlp 使用 |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | 是 | 透過 `requirements.txt` 安裝 |
| Cloudflare R2 儲存桶 | 是 | 見下方 [R2 設定教學](#cloudflare-r2-設定教學) |
| [aria2](https://github.com/aria2/aria2) | 可選 | 加速 Bilibili 下載；**本專案不附帶**，需自行安裝（見下方）；**不用於 YouTube** |

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

1. R2 頁面點 **Manage R2 API Tokens** → **Create API token**
2. 權限選 **Object Read & Write**（範圍可限定你的 bucket）
3. 建立後複製：
   - **Access Key ID** → `R2_ACCESS_KEY_ID`
   - **Secret Access Key** → `R2_SECRET_ACCESS_KEY`

> Secret **只顯示一次**，請妥善保存；遺失需重新建立 Token。

### 4. 開啟公開存取（VRChat 直連用）

R2 預設為私有。若要產生 HTTP 連結給 VRChat：

1. 進入 bucket → **Settings**
2. 啟用 **Public access**／**R2.dev subdomain**（或綁定自訂網域）
3. 複製公開網址，例如 `https://pub-xxxxxxxx.r2.dev` → `R2_PUBLIC_BASE_URL`

若未設定 `R2_PUBLIC_BASE_URL`，上傳仍會成功，但完成後顯示的是 `r2://bucket/key`，不是可播放的 HTTP 網址。

### 5. 串流播放說明

公開 R2 網址支援 **HTTP Range** 請求。搭配本工具的 **faststart** 處理，VRChat 可邊下邊播、支援拖曳進度，無需等整支影片下載完。這是漸進式 MP4 播放，不是 HLS／直播串流。

---

## 設定 bili2vrchat

兩種方式（環境變數會覆寫 `config.py`）：

### 方式 A — 直接改 `config.py`（本機最簡單）

開啟 `config.py`，把 `Fill in … here` 改成你的實際值：

```python
CF_ACCOUNT_ID        = os.environ.get("CF_ACCOUNT_ID", "你的帳號ID")
R2_ACCESS_KEY_ID     = os.environ.get("R2_ACCESS_KEY_ID", "你的AccessKeyID")
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY", "你的SecretAccessKey")
R2_BUCKET_NAME       = os.environ.get("R2_BUCKET_NAME", "my-vrchat-videos")
R2_PUBLIC_BASE_URL   = os.environ.get("R2_PUBLIC_BASE_URL", "https://pub-xxxx.r2.dev").rstrip("/")
```

以 `Fill in ` 開頭的值會被視為**尚未設定**。

> 請勿把真實金鑰 commit 到 git；正式環境建議用環境變數。

### 方式 B — 環境變數

**Windows（cmd），可在 `start.bat` 的 `python app.py` 前加入：**

```bat
set CF_ACCOUNT_ID=你的帳號ID
set R2_ACCESS_KEY_ID=你的AccessKeyID
set R2_SECRET_ACCESS_KEY=你的SecretAccessKey
set R2_BUCKET_NAME=my-vrchat-videos
set R2_PUBLIC_BASE_URL=https://pub-xxxx.r2.dev
```

**Unix：**

```bash
export CF_ACCOUNT_ID=你的帳號ID
export R2_ACCESS_KEY_ID=你的AccessKeyID
export R2_SECRET_ACCESS_KEY=你的SecretAccessKey
export R2_BUCKET_NAME=my-vrchat-videos
export R2_PUBLIC_BASE_URL=https://pub-xxxx.r2.dev
```

---

## 安裝與啟動

### Windows

1. 安裝 **Python 3**、**ffmpeg**（`ffmpeg -version`）、**Node.js**（`node -version`）
2. 可選：若要加速 Bilibili，請自行安裝 aria2 — Windows 可從 [aria2 releases](https://github.com/aria2/aria2/releases) 下載 `aria2c.exe` 放在專案根目錄；Unix 請用套件管理器安裝（見下方）。本專案不附帶 aria2。
3. 完成上方 R2 設定
4. 執行：

```bat
start.bat
```

或手動：

```bat
python -m pip install -r requirements.txt
python app.py
```

5. 開啟 [http://localhost:5000](http://localhost:5000)

### Unix（macOS / Linux）

**安裝工具：**

```bash
# macOS
brew install ffmpeg node aria2

# Debian / Ubuntu
sudo apt update
sudo apt install -y ffmpeg nodejs aria2 python3 python3-pip python3-venv
```

**建議使用 venv：**

```bash
cd /path/to/bili2vrchat
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

**啟動：**

```bash
chmod +x start.sh   # 僅首次
./start.sh
```

瀏覽器開啟 [http://localhost:5000](http://localhost:5000)。同一區域網路可用 `http://<主機IP>:5000`。

**復古介面：** [http://localhost:5000/retro](http://localhost:5000/retro)

### Docker

```bash
docker build -t bili2vrchat .
docker run --rm -p 5000:5000 \
  -e CF_ACCOUNT_ID=你的帳號ID \
  -e R2_ACCESS_KEY_ID=你的AccessKeyID \
  -e R2_SECRET_ACCESS_KEY=你的SecretAccessKey \
  -e R2_BUCKET_NAME=my-vrchat-videos \
  -e R2_PUBLIC_BASE_URL=https://pub-xxxx.r2.dev \
  -v bili2vrchat-temp:/app/temp \
  bili2vrchat
```

映像檔已含 `ffmpeg`、`aria2`、`nodejs`。R2 憑證請用 `-e` 傳入，不要寫進映像檔。

---

## 使用教學

1. **貼上網址** — Bilibili 或 YouTube 連結 → 點 **獲取格式**
2. **Cookie（若需要）** — 會員／年齡限制影片：匯出 `cookies.txt` 並在頁面上傳（僅存瀏覽器）。詳見 [cookies/README.md](cookies/README.md)
3. **選擇格式** — 在表格中選解析度／編碼
4. **上傳選項**
   - **自訂路徑** — 可選 object key；留空則隨機 `f_xxxxxx`
   - **保存時間** — 1 小時／1 天／7 天／30 天／永久（非永久會自動刪除）
   - **播放速度** — 上傳前永久變更速度
   - **VRChat 相容模式** — 重編碼為 H.264（修復部分撕裂問題，較慢）
5. **開始處理** — 下載 → 轉碼（若需要）→ 上傳 R2
6. **複製連結** — 完成後貼到 VRChat

完成範例：`https://pub-xxxx.r2.dev/f_abc123`

---

## 保存時間與自動刪除

| UI 選項 | 行為 |
|---------|------|
| 1 小時／1 天／7 天／30 天 | 寫入 R2 物件 metadata `expires` |
| 永久保存 | `expires = 0`（不自動刪除） |

本程式會以背景執行緒每 `R2_CLEANUP_INTERVAL` 秒（預設 3600）掃描 bucket，刪除已過期物件。**僅在程式運行時**才會執行清理。

---

## 設定參考

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `CF_ACCOUNT_ID` | `config.py` 內 `Fill in …` | Cloudflare 帳號 ID |
| `R2_ACCESS_KEY_ID` | `Fill in …` | R2 Access Key ID |
| `R2_SECRET_ACCESS_KEY` | `Fill in …` | R2 Secret Access Key |
| `R2_BUCKET_NAME` | `Fill in …` | 儲存桶名稱（**必填**） |
| `R2_PUBLIC_BASE_URL` | `Fill in … (optional)` | 公開網址（VRChat 直連） |
| `R2_CLEANUP_ENABLED` | 開啟 | `0` / `false` 停用過期清理 |
| `R2_CLEANUP_INTERVAL` | `3600` | 過期掃描間隔（秒） |
| `DEFAULT_TTL` | `604800` | UI 未指定時預設 7 天 |
| `HOST` | `0.0.0.0` | 綁定位址 |
| `PORT` | `5000` | HTTP 連接埠 |
| `HW_ENCODER` | `auto` | `auto`、`libx264`、`h264_videotoolbox` 等 |
| `LOG_LEVEL` | `INFO` | 日誌級別 |
| `DISABLE_ARIA2C` | 關閉 | `1` / `true` 停用 aria2c |
| `COOKIE_MAX_BYTES` | `65536` | 單次 Cookie 上限 |

---

## Cookie

年齡限制或會員影片的登入 Cookie 存於**瀏覽器 localStorage**。匯出步驟：[cookies/README.md](cookies/README.md)。

---

## 專案結構

| 路徑 | 用途 |
|------|------|
| `app.py` | Flask：下載／轉碼／上傳流程 |
| `config.py` | 設定（R2 憑證、TTL、伺服器） |
| `r2.py` | R2 上傳、公開網址、過期清理 |
| `hwaccel.py` | 硬體編碼器偵測 |
| `static/cookies.js` | 客戶端 Cookie 輔助 |
| `templates/index.html` | 主介面 |
| `templates/index_pixel.html` | 復古介面（`/retro`） |
| `start.sh` / `start.bat` | 啟動腳本 |
| `temp/` | 下載／轉碼暫存（gitignore） |

---

## 常見問題

| 狀況 | 檢查 |
|------|------|
| 提示 `請設定 R2 環境變數` | 填好 `config.py` 或環境變數，勿保留 `Fill in …` |
| 上傳失敗（403／簽章錯誤） | 重建 API Token；確認 bucket 名稱與權限 |
| 完成後沒有 HTTP 網址 | 設定 `R2_PUBLIC_BASE_URL` 並開啟 bucket 公開存取 |
| YouTube 獲取格式失敗 | 安裝 Node.js，確認 `node -version` |
| Bilibili 很慢 | Windows：將 `aria2c.exe` 放在專案根目錄；或安裝 aria2 至 `PATH` |
| 過期檔案仍在 bucket | 程式需持續運行才會清理；或等下一個掃描週期 |
| VRChat 無法播放／不能 seek | 開啟 **VRChat 相容模式**；確認已設 `R2_PUBLIC_BASE_URL` |
