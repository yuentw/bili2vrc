# bili2vrc

> neko 🐱

[English](README.md) | **繁體中文**

用於下載 **Bilibili / YouTube** 影片，並透過 **R2 S3 API** 上傳至**你自己的 Cloudflare R2 儲存桶**。產生**直連網址**，可在 **VRChat** 觀看，並支援**影片倍速**、**CBR／VBR 編碼**與硬體加速。**不需要**部署 Cloudflare Worker。

```
瀏覽器 → FastAPI (yt-dlp / ffmpeg) → R2 (S3 API) → VRChat 直連
```

## 功能

- 支援 **Bilibili**、**YouTube** 下載（yt-dlp）
- **輸出模式**：**保留原始**／**AV1**（預設）／**H.264**（偏 VRChat 相容重編碼）
- **播放速度**（上傳前永久變更；≠ 1.0x 會強制重編碼，無法保留原始）
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
- 現代版 UI：**貼上**按鈕（申請剪貼簿權限；HTTP 環境可改 Ctrl+V）

---

## 前置依賴

| 工具 | 是否必需 | 說明 |
|------|----------|------|
| Python 3.14+ | 是 | 見 `.python-version`、`pyproject.toml` |
| [uv](https://docs.astral.sh/uv/) | 是 | Python 依賴與 `uv run app.py`；啟動腳本可裝到專案 `.uv` |
| [ffmpeg](https://ffmpeg.org/) | 是 | `ffmpeg`、`ffprobe` 需在 `PATH`。**HDR→SDR** 需建置含 **libplacebo** + **Vulkan** |
| [Node.js](https://nodejs.org/) | YouTube 必需 | 供 yt-dlp 使用（`--js-runtimes node`） |
| [Bun](https://bun.sh/) | 是（前端建置） | 啟動腳本可裝到專案 `.bun` 並建置前端 |
| Cloudflare R2 儲存桶 | 是 | 見下方 [R2 設定教學](#cloudflare-r2-設定教學) |
| [aria2](https://github.com/aria2/aria2) | 可選 | 加速 Bilibili 下載；**本專案不附帶**；**不用於 YouTube** |

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

1. R2 頁面點 **Manage R2 API Tokens** → **Create API token**
2. 權限選 **Object Read & Write**（範圍可限定你的 bucket）
3. 建立後複製：
   - **Access Key ID** → `R2_ACCESS_KEY_ID`
   - **Secret Access Key** → `R2_SECRET_ACCESS_KEY`

> Secret **只顯示一次**，請妥善保存；遺失需重新建立 Token。

### 4. 開啟公開存取（VRChat 直連用）

R2 預設為私有。若要產生 HTTP 連結給 VRChat：

1. Cloudflare 儀表板 → **R2 Object Storage** → 進入你的 **bucket**
2. 開啟 **Settings**
3. 在 **Custom Domains** 點 **Add**，綁定自訂網域（例如 `b2v.example.com`）
4. 等到 **Status** 為 **Active**、**Access** 為 **Enabled**
5. 將該網域設為 `R2_PUBLIC_BASE_URL`，例如 `https://b2v.example.com`  
   （可省略 `https://`，程式會自動補上）

同一頁也可改開 **Public Development URL**（`https://pub-xxxxxxxx.r2.dev`）作為 `R2_PUBLIC_BASE_URL`。

若未設定 `R2_PUBLIC_BASE_URL`，上傳仍會成功，但完成後顯示的是 `r2://bucket/key`，不是可播放的 HTTP 網址。

### 5. 串流播放說明

公開 R2 網址支援 **HTTP Range** 請求。搭配本工具的 **faststart** 處理，VRChat 可邊下邊播、支援拖曳進度，無需等整支影片下載完。這是漸進式 MP4 播放，不是 HLS／直播串流。

上傳完成後，網頁預覽直接使用 **R2 公開網址**；本機伺服器關機後，已開著的結果頁仍可播放（R2 連結有效即可），但無法再獲取格式或新上傳。

---

## 設定 bili2vrchat

兩種方式（環境變數會覆寫 `src/bili2vrc/config.py`）。亦可複製 [.env.example](.env.example) 為 `.env` — 匯入時會執行 `load_dotenv()`。

### 方式 A — 直接改 `src/bili2vrc/config.py`（本機最簡單）

開啟 `src/bili2vrc/config.py`，把 `Fill in … here` 改成你的實際值：

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

**Windows（cmd），可在 `start.bat` 前設定，或使用 `.env`：**

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

### 首次設定

1. 安裝 **ffmpeg**、**Node.js**（YouTube）；見 [前置依賴](#前置依賴)
2. 設定 R2（見上方）；可選：`cp .env.example .env`
3. 執行 `start.bat`／`start.sh`（會自動處理 uv／Bun／前端建置）

`start.bat`／`start.sh` 會：

- 若無 **uv**，安裝到專案 `.uv`
- 若無 **Bun**，安裝到專案 `.bun`
- 若缺少 `frontend/.output/public`，自動 `bun install` + `bun run generate`
- 然後 `uv run app.py`

### Windows

1. 安裝 **Python 3.14+**、**ffmpeg**（`ffmpeg -version`）、**Node.js**（`node -version`）
2. 可選：若要加速 Bilibili，從 [aria2 releases](https://github.com/aria2/aria2/releases) 下載 `aria2c.exe` 放在專案根目錄
3. 完成上方 R2 設定
4. 執行：

```bat
start.bat
```

或手動：

```bat
uv sync
cd frontend
bun install
bun run generate
cd ..
uv run app.py
```

5. 開啟 [http://localhost:5000](http://localhost:5000)（剪貼簿權限請用 localhost／HTTPS）

### Unix（macOS / Linux）

**安裝工具：**

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

瀏覽器開啟 [http://localhost:5000](http://localhost:5000)。同一區域網路可用 `http://<主機IP>:5000`（區網 HTTP **無法**申請剪貼簿讀取權限，請改手動貼上或用 Ctrl+V 備援）。

**復古介面：** [http://localhost:5000/retro](http://localhost:5000/retro)

### 前端開發（可選）

API 伺服器與 Nuxt 開發伺服器分開跑（API 代理至 FastAPI）：

```bash
uv run app.py              # :5000 — API + 已建置的 UI（若有）
cd frontend && bun run dev # :3000 — 熱更新；/api/* → :5000
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
  -e CF_ACCOUNT_ID=你的帳號ID \
  -e R2_ACCESS_KEY_ID=你的AccessKeyID \
  -e R2_SECRET_ACCESS_KEY=你的SecretAccessKey \
  -e R2_BUCKET_NAME=my-vrchat-videos \
  -e R2_PUBLIC_BASE_URL=https://pub-xxxx.r2.dev \
  -v bili2vrchat-temp:/app/temp \
  bili2vrchat
```

映像檔以 Bun 建置 Nuxt 前端；Python 依賴由 `uv sync`（`uv.lock`）安裝；`CMD` 為 `uv run app.py`。含 `ffmpeg`、`aria2`、`nodejs`。R2 憑證請用 `-e` 或 `--env-file` 傳入，勿寫進映像檔。

---

## Tampermonkey：B 站 → bili2vrc

可選油猴腳本：滑鼠移到 B 站影片封面上出現 **下載解析** → 開啟 bili2vrc，自動填入 `?url=` 並執行 **獲取格式**，再手動選解析度。

支援封面懸浮（首頁／搜尋／動態等）、**收藏夾**、**歷史記錄**、觀看頁**右側推薦**等。

**[一鍵安裝 bili2vrc Bridge](https://raw.githubusercontent.com/yuentw/bili2vrc/main/userscripts/bili2vrc-bridge.user.js)** — 會開啟 Tampermonkey 安裝頁（需先安裝 [Tampermonkey](https://www.tampermonkey.net/)）。

1. 安裝 [Tampermonkey](https://www.tampermonkey.net/)
2. 點 **[一鍵安裝 bili2vrc Bridge](https://raw.githubusercontent.com/yuentw/bili2vrc/main/userscripts/bili2vrc-bridge.user.js)**，確認安裝
3. 先啟動 bili2vrc（`start.bat`／`start.sh`）
4. 在 B 站將滑鼠移到影片封面，點 **下載解析**

原始檔：[userscripts/bili2vrc-bridge.user.js](userscripts/bili2vrc-bridge.user.js)

預設跳轉：`http://localhost:5000`。可在油猴選單 → **設定 bili2vrc 網址** 修改。

深連結格式：`http://localhost:5000/?url=<編碼後的 B 站影片網址>`

---

## 使用教學

1. **貼上網址** — Bilibili 或 YouTube 連結 → 點 **獲取格式**（現代版亦可點 **貼上**，讀取剪貼簿後自動獲取）
2. **Cookie（若需要）** — 會員／年齡限制影片：匯出 `cookies.txt` 並在頁面上傳（僅存瀏覽器）。詳見 [cookies/README.md](cookies/README.md)
3. **選擇格式** — 在表格中選解析度／編碼／動態範圍（會帶入「原始」碼率）。HDR 列會顯示 `HDR`／`HDR10`／`HLG`
4. **上傳選項**
   - **自訂路徑** — 可選 object key；留空則隨機 `f_xxxxxx`
   - **保存時間** — 1 小時／1 天／7 天／30 天／永久（非永久會自動刪除）
   - **播放速度** — 上傳前永久變更；≠ 1.0x 會重編碼（CFR + 保留音高），並禁用**保留原始**
   - **輸出模式** — **保留原始**（僅 faststart）／**AV1**（預設重編碼）／**H.264**（偏 VRChat Main Profile）
   - **HDR → SDR** — 僅在所選格式為 HDR 時顯示；下載該串流後 tonemap 為 SDR（強制重編碼）
   - **進階編碼**
     - **編碼模式** — VBR（品質 + 上限）或 CBR（固定碼率）
     - **CRF／CQ** — 依輸出編碼的品質滑桿
     - **Mapping（HDR→SDR）** — Mobius（預設）／BT.2390／Hable（`libplacebo`；需開啟 HDR→SDR）
     - **碼率** — 「原始」或自訂預設  
       - CBR 自訂：`2000 / 4000 / 5000 / 6000 / 8000 / 10000` kbps  
       - 僅選「原始」時，倍速會自動 × 倍速調整碼率；自訂 CBR／VBR **不**隨倍速相乘
5. **開始處理** — 下載 → 驗證 → 轉碼（若需要）→ 上傳 R2 → 以 R2 網址預覽
6. **複製連結** — 完成後貼到 VRChat

### 何時會重編碼？

| 條件 | 行為 |
|------|------|
| **保留原始**、原速、未開 HDR→SDR | 僅 **faststart**（`-c copy`） |
| **AV1**（預設）或 **H.264** | 重編碼為該編碼（有硬體則優先） |
| 播放速度 ≠ 1.0x | 時間拉伸 + 重編碼（無法保留原始） |
| 開啟 **HDR → SDR** | tonemap（`libplacebo`）+ 重編碼 |

完成範例：`https://pub-xxxx.r2.dev/f_abc123`

---

## 保存時間與自動刪除

| UI 選項 | 行為 |
|---------|------|
| 1 小時／1 天／7 天／30 天 | 寫入 R2 物件 metadata `expires` |
| 永久保存 | `expires = 0`（不自動刪除；若設了 `MAX_TTL` 會被上限截斷） |

本程式會以背景執行緒每 `R2_CLEANUP_INTERVAL` 秒（預設 3600）掃描 bucket，刪除已過期物件。**僅在程式運行時**才會執行清理。

---

## 設定參考

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `CF_ACCOUNT_ID` | `src/bili2vrc/config.py` 內 `Fill in …` | Cloudflare 帳號 ID |
| `R2_ACCESS_KEY_ID` | `Fill in …` | R2 Access Key ID |
| `R2_SECRET_ACCESS_KEY` | `Fill in …` | R2 Secret Access Key |
| `R2_BUCKET_NAME` | `Fill in …` | 儲存桶名稱（**必填**） |
| `R2_PUBLIC_BASE_URL` | `Fill in … (optional)` | 公開網址（VRChat 直連） |
| `R2_CLEANUP_ENABLED` | 開啟 | `0` / `false` 停用過期清理 |
| `R2_CLEANUP_INTERVAL` | `3600` | 過期掃描間隔（秒） |
| `MAX_TTL` | `2592000` | 最長保存（秒）；`0` = 不限制；永久選項會被截斷 |
| `DEFAULT_TTL` | `604800` | UI 未指定時預設 7 天 |
| `DEFAULT_BITRATE_KBPS` | `3000` | 重編碼預設碼率（kbps） |
| `MIN_BITRATE_KBPS` | `500` | 碼率下限 |
| `MAX_BITRATE_KBPS` | `50000` | 碼率上限；`0` = 不限制 |
| `SPEED_BITRATE_FACTOR` | `1.0` | 「原始」碼率 × 倍速時的額外倍率 |
| `DEFAULT_ENCODE_MODE` | `vbr` | `vbr` 或 `cbr` |
| `DEFAULT_ENCODE_QUALITY` | `balanced` | `high`／`balanced`／`medium`／`small` |
| `DEFAULT_OUTPUT_CODEC` | `av1` | `av1`／`h264`／`h265`（非「保留原始」時的 API 預設） |
| `HOST` | `0.0.0.0` | 綁定位址 |
| `PORT` | `5000` | HTTP 連接埠 |
| `FRONTEND_DIST` | `frontend/.output/public` | Nuxt 靜態輸出目錄 |
| `HW_ENCODER` | `auto` | `auto`、`av1_nvenc`、`libsvtav1`、`h264_nvenc`、`libx264`、`h264_qsv` 等 |
| `DISABLE_HW_ACCEL` | 關閉 | `1` / `true` 強制僅用軟體編碼/解碼 |
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
| `app.py` | 入口啟動器 → `uv run` → uvicorn + FastAPI |
| `src/bili2vrc/main.py` | FastAPI 應用、lifespan、靜態 SPA |
| `src/bili2vrc/config.py` | 設定（R2、TTL、編碼、路徑）；載入 `.env` |
| `src/bili2vrc/api/` | REST + SSE 路由（`/api/*`） |
| `src/bili2vrc/services/` | 格式取得、下載上傳流程、任務控制 |
| `src/bili2vrc/media/` | ffmpeg 轉碼、MP4 驗證／faststart |
| `src/bili2vrc/download/` | yt-dlp、Cookie、aria2c |
| `src/bili2vrc/storage/r2.py` | R2 上傳、公開 URL、過期清理 |
| `src/bili2vrc/encoding/hwaccel.py` | 硬體編碼器偵測與 ffmpeg 參數 |
| `frontend/` | Nuxt 4 SPA（`bun run generate` 或 `bun run dev`） |
| `frontend/.output/public` | 建置後靜態檔，由 FastAPI 提供 |
| `pyproject.toml`／`uv.lock` | Python 專案與鎖定依賴（uv） |
| `requirements.txt` | 傳統 pip 清單（與主要依賴對照） |
| `start.sh`／`start.bat` | 自動安裝 uv／Bun、建置前端、`uv run app.py` |
| `build-image.sh` | Docker 映像建置腳本 |
| `Dockerfile` | 多階段：Bun 前端 + `uv sync` + Python 執行環境 |
| `userscripts/bili2vrc-bridge.user.js` | 可選油猴腳本（B 站 → bili2vrc） |
| `temp/` | 下載／轉碼暫存（gitignore） |

---

## 常見問題

| 狀況 | 檢查 |
|------|------|
| 提示 `請設定 R2 環境變數` | 填好 `src/bili2vrc/config.py` 或環境變數／`.env`，勿保留 `Fill in …` |
| 上傳失敗（403／簽章錯誤） | 重建 API Token；確認 bucket 名稱與權限 |
| 完成後沒有 HTTP 網址 | 設定 `R2_PUBLIC_BASE_URL`；在 bucket **Settings → Custom Domains** 綁定網域（或開啟 Public Development URL） |
| YouTube 獲取格式失敗 | 安裝 Node.js，確認 `node -version` |
| 找不到 `uv`／`bun` | 直接跑 `start.bat`／`start.sh`（會裝到 `.uv`／`.bun`），或依官方文件手動安裝 |
| 前端空白／找不到頁面 | 執行 `cd frontend && bun install && bun run generate` |
| Bilibili 很慢 | Windows：將 `aria2c.exe` 放在專案根目錄；或安裝 aria2 至 `PATH`。獲取格式時選擇非 H.264 來源編碼（如 AV1／H.265／VP9）也可加快下載 |
| 過期檔案仍在 bucket | 程式需持續運行才會清理；或等下一個掃描週期 |
| VRChat 無法播放／不能 seek | 輸出模式選 **H.264**；確認已設 `R2_PUBLIC_BASE_URL` |
| 倍速後檔案異常變大 | 改用 **CBR** 或較低 VBR 上限／CRF；確認碼率選的是自訂預設 |
| 「貼上」無法讀剪貼簿 | 請用 `http://127.0.0.1:5000` 或 HTTPS；區網 HTTP 請允許後改 Ctrl+V，或手動貼上網址 |
| HDR 過曝／灰階怪異 | 對 HDR 格式開啟 **HDR → SDR**，或換 **Mapping**（Mobius／BT.2390／Hable）。需 ffmpeg 含 **libplacebo** + Vulkan |
| 原速是否重編碼？ | 僅**保留原始**且未開 HDR→SDR：否（驗證 + faststart）。**AV1**／**H.264**／倍速／HDR→SDR 都會重編碼 |
