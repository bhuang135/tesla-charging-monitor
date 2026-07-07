# 🗂️ 設定 Google Sheets 持久化儲存

## 為什麼需要這個？

Streamlit Cloud 的檔案系統是**臨時的（ephemeral）**：
- ❌ App reboot → 資料消失
- ❌ Server 重新部署 → 資料消失  
- ❌ 閒置一段時間後 → 資料消失

要在 Streamlit Cloud 上**永久保存**充電紀錄，最簡單免費的做法是用 **Google Sheets** 當資料庫。

> 💡 在 **localhost** 跑時不需要這個設定 — 本機 CSV 直接寫到磁碟即可。
> 這個指南只針對 **Streamlit Cloud 部署** 的情況。

---

## 完整步驟（15 分鐘搞定）

### Step 1 — 建立 Google Sheets 試算表

1. 開啟 https://sheets.google.com
2. 點「**+ 空白試算表**」
3. 命名為 `Tesla Charging Records`（隨意）
4. 複製網址 — 看起來像：
   ```
   https://docs.google.com/spreadsheets/d/1A2B3C4D5E6F7G8H9I0JKLMNopQRSTUVwxyz/edit
   ```
5. **保留**這個網址，後面會用到

### Step 2 — 建立 Google Cloud 服務帳戶（service account）

服務帳戶 = 機器讀寫用的 Google 帳號，不需要 OAuth 登入流程。

1. 開啟 https://console.cloud.google.com/projectcreate
2. 建立一個新專案（命名 `tesla-charging-monitor` 或任意）
3. 進入專案後，到 **API & Services → Enabled APIs & Services**
4. 點「**+ Enable APIs and Services**」
5. 搜尋並啟用以下 **兩個** API：
   - **Google Sheets API**
   - **Google Drive API**

### Step 3 — 建立 Service Account + 下載金鑰

1. 到 **IAM & Admin → Service Accounts**
2. 點「**+ Create Service Account**」
3. 填寫：
   - Service account name: `streamlit-tesla`
   - Service account ID: 自動產生即可
4. **Role** 跳過（這個帳戶只會用於 API 訪問，不需要 GCP 內部權限）
5. 點 **Done**
6. 在 Service Accounts 列表，點剛建立的帳戶
7. 切到 **Keys** 分頁
8. 點 **Add Key → Create new key → JSON → Create**
9. JSON 檔會自動下載 — **這個檔案就是你的憑證，請妥善保管不要外洩**

### Step 4 — 把 Service Account 加為試算表協作者

服務帳戶的 email 長這樣：
```
streamlit-tesla@your-project-id.iam.gserviceaccount.com
```

1. 開啟你剛建立的 Google Sheets 試算表
2. 右上角點「**Share / 共用**」
3. 把 service account email 貼上去
4. 權限選 **Editor / 編輯者**
5. **取消勾選**「Notify people」
6. 點 **Share / 共用**

### Step 5 — 在 Streamlit Cloud 加入憑證

1. 到 Streamlit Cloud → 你的 app → **⚙️ Settings → Secrets**
2. 貼入以下內容（用你 JSON 檔的實際值取代）：

```toml
[gcp_service_account]
type = "service_account"
project_id = "你的-project-id"
private_key_id = "..."
private_key = """-----BEGIN PRIVATE KEY-----
這裡貼上 JSON 的 private_key 內容
（每個 \n 換成真實換行）
-----END PRIVATE KEY-----
"""
client_email = "streamlit-tesla@your-project.iam.gserviceaccount.com"
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."
universe_domain = "googleapis.com"

[gsheets]
spreadsheet_url = "https://docs.google.com/spreadsheets/d/你的試算表ID/edit"

# Gemini OCR
GEMINI_API_KEY = "AIzaSy..."
```

3. 點 **Save** → Streamlit Cloud 會自動 reboot

> ⚠️ `private_key` 必須用 `"""..."""` 三引號包起來，且把 JSON 的 `\n` 轉成真實換行。

### Step 6 — 確認運作正常

1. 重新開啟 app
2. 進「🗂️ 資料」分頁
3. 應該看到綠色橫幅：
   ```
   ☁️ 使用 Google Sheets 儲存 — 資料會永久保存
   ```
4. 試新增一筆充電紀錄
5. 開啟你的 Google Sheets 試算表，應該看到新的一行

---

## 把現有的資料上傳到 Google Sheets

如果你本地有 437 筆歷史資料：

### 方法 1：透過 App 介面（推薦）
1. 從 localhost 用「資料 → 匯出 → 下載 CSV」拿到 `charging_records.csv`
2. 到部署版（已設好 Google Sheets）的 app
3. 「資料 → 從 Excel/CSV 匯入」上傳這個 CSV
4. 模式選「**清除舊資料並取代**」→ 匯入

### 方法 2：直接貼進 Google Sheets
1. 打開 `data/charging_records.csv`
2. 全選複製
3. 開啟 Google Sheets 試算表
4. 工作表名稱改成 `charging_records`（重要！）
5. A1 貼上

---

## 故障排除

| 症狀 | 原因 | 解法 |
|---|---|---|
| 🟠 看到「使用本地 CSV」警告 | secrets 沒讀到 | 檢查 Streamlit Cloud Settings → Secrets 是否儲存 |
| 🔴 `Permission denied` | 試算表沒分享給 service account email | 重做 Step 4 |
| 🔴 `Could not deserialize key data` | `private_key` 換行格式錯 | 確認用 `"""..."""` 三引號且換行正確 |
| 🔴 `Spreadsheet not found` | URL 錯或試算表被刪 | 檢查 `spreadsheet_url` |
| 🔴 `API not enabled` | 沒 enable Sheets / Drive API | 重做 Step 2 |
