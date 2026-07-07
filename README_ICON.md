# Tesla 充電健康監測

## iPhone「加入主畫面」圖示說明 ⚠️

### Streamlit 的架構限制

Streamlit 是一個 **React-based SPA**。當 Safari 第一次載入網頁時，會立刻去
讀取 HTML `<head>` 中既有的 `<link rel="apple-touch-icon">`。

問題在於：
1. **Streamlit 沒有提供方式修改初始 HTML 的 `<head>`**
2. 我們只能用 `components.html` 在 **React app 載入後**才注入 meta tag
3. **此時 Safari 已經抓完並快取了預設的 Streamlit logo** ❌

換句話說，要 100% 解決需要：
- Reverse proxy（Nginx / Cloudflare Worker）在 response 中改寫 HTML
- 或自架 server，不使用 Streamlit Cloud

**但** 我們的程式碼已經盡可能優化了：
- ✅ 注入多個尺寸（120/152/180）的 apple-touch-icon
- ✅ 注入 precomposed icon（舊 iOS 相容）
- ✅ 用 cache-busting query param 強制 Safari 重新下載
- ✅ 注入完整 PWA meta tags（title / capable / status-bar）
- ✅ 動態修改 document.title

### 部署後的 Git 步驟

```bash
git add static/app_icon.png static/apple-touch-icon.png static/favicon.png \
        .streamlit/config.toml app.py
git commit -m "Fix iPhone home screen app icon"
git pull --rebase origin main
git push origin main
```

然後到 Streamlit Cloud → Manage app → **Reboot app**。

### iPhone 測試步驟（重要！）

如果你之前已經把 app 加到主畫面，iPhone 會快取舊圖示。**必須照下列順序操作**：

#### Step 1：刪除舊的主畫面捷徑
1. 長按桌面上現有的 Tesla 圖示
2. 點「移除書籤」/「Remove Bookmark」

#### Step 2：清除 Safari 快取（重要）
1. 設定 → Safari → **清除瀏覽記錄與網站資料**
2. 確認清除

#### Step 3：用帶 cache-buster 的網址重新開啟
1. 開啟 Safari
2. 輸入網址：`https://your-app.streamlit.app/?v=2`
3. （`?v=2` 強迫 Safari 把它當成全新網址，不使用快取）

#### Step 4：重新加入主畫面
1. 點分享按鈕（底部中央）
2. 選「加入主畫面」/「Add to Home Screen」
3. 圖示預覽應該看到 Tesla Model 3
4. 如果還是預設 Streamlit 圖示 → 換 `?v=3`、`?v=4` 試
5. 仍失敗 → 進入「設定 → Safari → 進階 → 網站資料」找到你的 app，左滑刪除

#### Step 5：開啟主畫面捷徑
- 點桌面新增的 Tesla 圖示
- 應該看到 Tesla Model 3 圖示
- 開啟後狀態列為黑色透明（PWA 全螢幕風格）

### 已知的常見失敗情境

| 症狀 | 可能原因 | 解法 |
|---|---|---|
| iPhone 桌面仍是預設 Streamlit logo | Safari 快取 | Step 2 清快取 + Step 3 換 ?v=N |
| 圖示變成黑底白字 | Streamlit static serving 沒啟用 | 確認 `.streamlit/config.toml` 有 `enableStaticServing = true` 並 Reboot app |
| 圖示是裁切過頭或扭曲 | PNG 透明背景 | 我們已用 RGB 模式無透明背景，不應發生 |
| 開啟後跳到 Safari 而非全螢幕 | 加入主畫面時 meta 還沒注入 | 重新 Step 1~4 |
| 桌面瀏覽器 tab 圖示也錯 | 同上 | 換 `?v=N` 並 hard refresh (Ctrl+Shift+R) |

### 修改 cache 版本號

當你想再次強迫 iPhone 重新抓圖示時（例如又換了新圖），修改 `app.py` 裡：

```python
ICON_VERSION = "2"   # 改成 "3", "4", ...
```

push 到 GitHub → reboot Streamlit Cloud → iPhone 用 `?v=新版本號` 重訪 → 重新加入主畫面。
