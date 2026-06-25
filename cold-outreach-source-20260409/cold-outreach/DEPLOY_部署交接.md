# 部署交接文件 — Cold Outreach 陌生開發系統

> 給下一位接手的工程師：改完 code 之後要怎麼上線、出問題時去哪裡查。
> 最後更新：2026-06-25

---

## 0. 一句話總結

**改完 code → `git push origin main` → 自動部署完成。**
前端和後端是「同一個 Docker image、同一個網址」一起部署的，你不需要分開處理。

- 正式網址（前端 + 後端 API 同源）：
  **https://cold-out-reach-603859135182.europe-west1.run.app**

---

## 1. 系統架構（部署相關）

| 元件 | 平台 | 說明 |
|------|------|------|
| 前端 + 後端 | **GCP Cloud Run** 服務 `cold-out-reach`（`europe-west1`） | 同一個容器，前端打包進後端的 `static/`，API 走相對路徑 `/api`，同源 |
| 資料庫 | **GCP Cloud SQL** `cold-outreach-db`（PostgreSQL 18, `europe-west1-b`） | 資料庫名 `cold_outreach` |
| 原始碼 | GitHub `github.com/xavierchen-ctrl/cold-out-reach`（branch `main`） | push 到 main 會觸發自動建置 |

- GCP 專案：`cold-out-reach-499608`（專案編號 `603859135182`）
- Cloud SQL 連線名稱：`cold-out-reach-499608:europe-west1:cold-outreach-db`
- Cloud Run 透過 **Unix socket** 連 DB（`--add-cloudsql-instances`），不走公開 IP

> 注意：repo 裡的 `backend/.env` 是**本機用的舊設定**，正式環境的 `DATABASE_URL` 是讀 Cloud Run 上的環境變數，不是這個檔案。改它不會影響線上。

---

## 2. 正常部署流程（90% 情況用這個）

```bash
# 在 cold-outreach-source-20260409/cold-outreach 目錄下
git add -u                 # 或 git add <你改的檔案>
git commit -m "feat: 你的修改說明"
git push origin main
```

push 之後：
1. GCP **Cloud Build** 會自動抓最新的 main，用 `Dockerfile`（多階段：先 build 前端 → 再裝進後端）建出新 image。
2. 建好後自動部署到 Cloud Run 服務 `cold-out-reach`。
3. 約 **3～6 分鐘**後，正式網址就是最新版（前端 + 後端都更新）。

> 為什麼 push 就好？因為 Cloud Run 已經連到這個 GitHub repo 設定了「持續部署 / Cloud Build 觸發器」，監看 `main` 分支。你只要 push，剩下它自己做。

### 確認部署狀態
- GCP Console → **Cloud Build → 記錄(History)**：看這次 build 是否成功（綠勾）。
- GCP Console → **Cloud Run → cold-out-reach → 修訂版本(Revisions)**：看是否有新的 revision、流量是否切到新版。
- 直接開正式網址，**強制重新整理（Ctrl+Shift+R）** 清快取後確認改動有上去。

---

## 3. 手動部署（備援：當自動觸發器失效時）

需先安裝 `gcloud` 並用**有權限的帳號**登入（見第 6 節）。

```bash
# 在 cold-outreach-source-20260409/cold-outreach 目錄下（Dockerfile 所在處）
gcloud config set project cold-out-reach-499608

gcloud run deploy cold-out-reach \
  --source . \
  --region europe-west1 \
  --add-cloudsql-instances cold-out-reach-499608:europe-west1:cold-outreach-db \
  --allow-unauthenticated
```

- `--source .` 會用當前目錄的 `Dockerfile` 在雲端 build 再部署。
- **環境變數不要在這裡覆蓋**（不要帶 `--set-env-vars`，否則會清掉現有的）。要改環境變數請走第 5 節。

---

## 4. 本機測試（push 前先在本機確認）

詳細看 `README.md`。最快的方式：

```bash
# 後端
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000      # http://localhost:8000/docs

# 前端（另一個終端）
cd frontend
npm install
npm run dev                                # http://localhost:5173
```

或一鍵 Docker（模擬正式的同源打包）：
```bash
cd cold-outreach
GEMINI_API_KEY=你的key docker compose up --build   # http://localhost:8000
```

> 前端有 TypeScript 型別檢查（`npm run build` = `tsc && vite build`）。
> **如果 `npm run build` 在本機就失敗，push 上去 Cloud Build 也會失敗**，所以建議改完前端先跑一次 build 確認沒有型別錯誤。

---

## 5. 環境變數（正式環境）

正式環境變數設在 **Cloud Run 服務上**，不是在 repo 檔案裡。

修改方式：GCP Console → Cloud Run → `cold-out-reach` → 編輯並部署新修訂版本 → 變數與密鑰。
或用指令（只加單一變數、保留其他）：
```bash
gcloud run services update cold-out-reach --region europe-west1 \
  --update-env-vars KEY=VALUE
```

主要變數（說明）：

| 變數 | 說明 |
|------|------|
| `DATABASE_URL` | Cloud SQL 連線字串（socket 形式：`postgresql://postgres:***@/cold_outreach?host=/cloudsql/cold-out-reach-499608:europe-west1:cold-outreach-db`） |
| `JWT_SECRET` | 登入 token 簽名密鑰 |
| `GEMINI_API_KEY` | Google Gemini AI 金鑰 |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `GOOGLE_REDIRECT_URI` | Gmail OAuth2 設定 |

> DB 密碼等機密存在本機 `db-migration/cloudsql_credentials.txt`（已 gitignore，**不要 commit**）。

---

## 6. 權限與帳號

- 有部署 / GCP 操作權限的 Google 帳號：**`wavenet_rd@wavenet.com.tw`**
  （注意：`xavier.chen` 那個帳號**沒有**權限）
- 第一次在新電腦操作：
  ```bash
  gcloud auth login          # 用 wavenet_rd@wavenet.com.tw 登入
  gcloud config set project cold-out-reach-499608
  ```
- GitHub push 權限：repo owner 是 `xavierchen-ctrl`，請確認你的帳號有 collaborator 權限。

---

## 7. 連線到正式資料庫（查資料 / 改資料時）

```bash
# 用 Cloud SQL Auth Proxy（建議），或在 Console 開 Cloud SQL Studio
gcloud sql connect cold-outreach-db --user=postgres --database=cold_outreach
```
> 密碼在 `db-migration/cloudsql_credentials.txt`。
> 改正式資料前**務必先備份**。歷史備份檔在 `db-migration/`（`railway_backup.sql` 等）。

---

## 8. 常見問題排查

| 症狀 | 可能原因 / 處理 |
|------|----------------|
| push 完網址沒變 | 1) 去 Cloud Build History 看 build 是否還在跑或失敗　2) 瀏覽器快取 → Ctrl+Shift+R |
| Cloud Build 失敗 | 多半是前端 `tsc` 型別錯或後端依賴問題。先在本機 `npm run build` / `pip install` 重現 |
| 網站 500 / 登入失敗 | Cloud Run → 記錄(Logs) 看錯誤。常見：DB 連不上、環境變數漏設 |
| DB 連線錯誤 | 確認 Cloud Run 有掛 `--add-cloudsql-instances`，且 runtime 服務帳號 `603859135182-compute@developer.gserviceaccount.com` 有 `roles/cloudsql.client` |
| 前端是舊版 | 確認是改到 `frontend/`、有 push、build 成功；Dockerfile 是多階段，會自動重建前端 |

---

## 9. 重要提醒 / 雷區

1. **不要動 `Dockerfile` 的多階段結構**：它故意在 build 階段刪掉 `frontend/.env.production` 和 `.env.local`，讓前端用相對路徑 `/api`（同源）。如果保留 `.env.production`，前端會把絕對網址寫死，本機/換網址時會壞。
2. **`backend/.env` 是舊的本機設定**，不是正式設定，改它不影響線上。
3. **機密檔案**（`db-migration/`、各種 `.env`）已被 gitignore，commit 前用 `git status` 確認沒把它們加進去。
4. 前端理論上也能單獨部署到 Firebase Hosting（`frontend/firebase.json`、`.firebaserc` 專案 `cold-out-reach-499608`），但**目前正式是統一走 Cloud Run 同源**，一般不需要動 Firebase。
5. Railway（舊資料庫）已停用，正式資料庫只有 Cloud SQL。

---

## 10. 一頁速查

```
改 code → 本機 npm run build 確認沒型別錯 → git push origin main → 等 3-6 分鐘 → 開正式網址 Ctrl+Shift+R 驗收
正式網址：https://cold-out-reach-603859135182.europe-west1.run.app
GCP 專案：cold-out-reach-499608 ｜ Cloud Run: cold-out-reach @ europe-west1
有權限帳號：wavenet_rd@wavenet.com.tw
出問題先看：Cloud Build History（build）+ Cloud Run Logs（runtime）
```
