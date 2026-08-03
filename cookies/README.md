# Cookie 說明

Cookie 儲存在**瀏覽器 localStorage**，不會上傳到伺服器永久保存。每次下載請求會將 cookie 內容隨 JSON 一併傳送，伺服器僅寫入暫存檔供 yt-dlp 使用後立即刪除。

## 如何取得 cookies.txt

1. 安裝 Chrome 插件「**Get cookies.txt LOCALLY**」
2. 登入 bilibili.com 或 youtube.com
3. 點插件圖示 → Export → 儲存為任意檔名（例如 `cookies.txt`）
4. 在本工具頁面上傳檔案 → **依檔案內容中的域名自動辨識**平台

## 平台辨識規則

系統會讀取 cookies.txt 內的 **domain 欄位**（非檔名）：

| 域名包含 | 儲存為 |
|----------|--------|
| `bilibili.com` / `b23.tv` | Bilibili cookie |
| `youtube.com` / `youtu.be` | YouTube cookie |

同一檔案若同時包含兩站域名，會同時儲存到兩個 slot。

## 注意事項

- Cookie 會過期，需定期重新匯出並上傳
- 不要分享 cookie 檔案給他人
- 影片網址會自動匹配對應平台的 cookie
