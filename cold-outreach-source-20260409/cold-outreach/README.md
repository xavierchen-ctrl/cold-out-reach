# Cold Outreach Platform — 陌生開發系統

業務陌生開發工具：建立目標名單（數位行銷產業）、AI 個人化發信、追蹤 Pipeline 狀態。

---

## 功能概覽

- 📋 **名單管理** — CRUD、狀態 Pipeline、搜尋篩選
- 📥 **CSV 匯入** — 批量新增名單
- 🕷️ **會展爬取** — TAITRA / MEET TAIPEI / TWAA / DMA 廠商自動爬取匯入
- ✉️ **Gmail 發信** — OAuth2 授權，AI 草稿一鍵生成
- 🤖 **Gemini AI** — 個人化開發信（intro / followup / proposal）
- 📊 **Dashboard** — Pipeline 漏斗、業務排行（admin only）

---

## Local Dev 啟動

### 前提
- Python 3.11+
- Node 20+
- PostgreSQL 15（或用 Docker）

### 1. 資料庫

```bash
# Docker 啟動 PostgreSQL
docker run -d --name cold-pg \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=cold_outreach \
  -p 5432:5432 postgres:15-alpine
```

### 2. 後端

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium   # 若需 JS 爬取

cp .env.example .env
# 編輯 .env，填入 DATABASE_URL / JWT_SECRET / GEMINI_API_KEY

python seed.py               # 建立 admin 帳號
uvicorn main:app --reload --port 8000
```

> API Docs: http://localhost:8000/docs

### 3. 前端

```bash
cd frontend
npm install
npm run dev    # http://localhost:5173
```

Vite dev server 已設定 proxy → backend:8000

---

## Docker 一鍵啟動

```bash
cd cold-outreach
GEMINI_API_KEY=你的key docker compose up --build
```

- 訪問：http://localhost:8000
- 首次需在另一個終端執行 seed：
  ```bash
  docker compose exec app python seed.py
  ```

---

## 預設帳號

| Email | 密碼 | 角色 |
|-------|------|------|
| joelou989@gmail.com | Ajo0114# | admin |

---

## 環境變數

| 變數 | 說明 |
|------|------|
| `DATABASE_URL` | PostgreSQL 連線字串 |
| `JWT_SECRET` | JWT 簽名密鑰（生產環境請換） |
| `GEMINI_API_KEY` | Google Gemini API Key |
| `GOOGLE_CLIENT_ID` | Gmail OAuth2 Client ID |
| `GOOGLE_CLIENT_SECRET` | Gmail OAuth2 Client Secret |
| `GOOGLE_REDIRECT_URI` | OAuth2 回調 URL |

---

## 允許登入的 Email

- `@wavenet.com.tw` 網域
- `joelou989@gmail.com`

---

## 爬取來源

| Source Key | 名稱 | 預設 URL |
|---|---|---|
| `taitra` | TAITRA 外貿協會 | https://www.taitra.org.tw/Events_Content.aspx?nid=165 |
| `meet_taipei` | MEET TAIPEI 新創大會 | https://meettaipei.tw/exhibitor |
| `twaa` | TWAA 台灣廣告主協會 | https://www.twaa.org.tw/member/ |
| `dma` | DMA 數位行銷學院 | https://www.dma.org.tw/member |

爬取策略：httpx + BeautifulSoup 靜態解析，頁面若需 JS 渲染自動 fallback 到 Playwright。
