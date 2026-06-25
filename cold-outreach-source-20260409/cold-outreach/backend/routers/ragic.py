"""
Ragic 中台 API 代理
封裝 ragic.middleplatform.punwave.com 的 3 支 API，避免前端直接持有 token：
  - GET existing client table  (既有客戶表)
  - GET new client table       (陌生開發表)
  - EDIT new client table      (寫入陌生開發表)
"""
import logging
import os
import re
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import User, Lead, UserRole, LeadStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ragic", tags=["ragic"])

_BASE = "https://ragic.middleplatform.punwave.com/api/v1"
_TOKEN = os.getenv("RAGIC_TOKEN", "ej031l4hk4g4")
_TIMEOUT = 60.0


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_TOKEN}",
        "Content-Type": "application/json",
    }


# ── Request schemas ────────────────────────────────────────────────────────────

class GetExistingClientReq(BaseModel):
    company_code: Optional[str] = None
    company_name: Optional[str] = None
    tax_id: Optional[str] = None
    am: Optional[str] = None
    client_department: Optional[str] = None
    client_contact: Optional[str] = None
    return_mode: Optional[str] = "skip"  # skip | full


class GetNewClientReq(BaseModel):
    company_name: Optional[str] = None
    am: Optional[str] = None
    client_contact: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    return_mode: Optional[str] = "skip"


class EditNewClientReq(BaseModel):
    # 必填
    company_name: str
    client_contact: str
    phone: str
    am: str
    # 選填
    email: Optional[str] = None
    website: Optional[str] = None
    status: Optional[str] = None
    customer_type: Optional[str] = None
    industry: Optional[str] = None
    title: Optional[str] = None
    extension: Optional[str] = None
    mobile: Optional[str] = None
    remark: Optional[str] = None
    department: Optional[str] = None
    manager: Optional[str] = None
    result: Optional[str] = None
    project_id: Optional[str] = None
    media: Optional[str] = None
    client_department: Optional[str] = None
    uid: Optional[str] = None


class BulkCheckReq(BaseModel):
    """批次檢查公司名稱：同時查兩張表，回報每家公司是否已存在"""
    company_names: List[str]


# ── Internal helper ────────────────────────────────────────────────────────────

async def _post(endpoint: str, body: dict) -> dict:
    """呼叫 Ragic 中台 API，統一錯誤處理"""
    payload = {k: v for k, v in body.items() if v is not None and v != ""}
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(f"{_BASE}/{endpoint}", headers=_headers(), json=payload)
        data = resp.json()
    except httpx.HTTPError as e:
        logger.warning(f"Ragic {endpoint} HTTP error: {e}")
        raise HTTPException(status_code=502, detail=f"Ragic 連線錯誤: {e}")
    except ValueError as e:
        raise HTTPException(status_code=502, detail=f"Ragic 回傳非 JSON: {e}")

    if resp.status_code != 200 or data.get("status") != "OK":
        msg = data.get("message") or f"HTTP {resp.status_code}"
        logger.warning(f"Ragic {endpoint} error: {msg} (payload={payload})")
        raise HTTPException(status_code=resp.status_code or 502, detail=f"Ragic: {msg}")

    return data


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/get-existing-clients")
async def get_existing_clients(
    body: GetExistingClientReq,
    current_user: User = Depends(get_current_user),
):
    """查詢既有客戶表（forms31/41）"""
    return await _post("get_existing_client_table", body.model_dump())


@router.post("/get-new-clients")
async def get_new_clients(
    body: GetNewClientReq,
    current_user: User = Depends(get_current_user),
):
    """查詢陌生開發表（forms31/46）"""
    return await _post("get_new_client_table", body.model_dump())


@router.post("/upsert-new-client")
async def upsert_new_client(
    body: EditNewClientReq,
    current_user: User = Depends(get_current_user),
):
    """新增或更新陌生開發表資料（以客戶名稱比對）"""
    return await _post("edit_new_client_table", body.model_dump())


@router.post("/bulk-check")
async def bulk_check_companies(
    body: BulkCheckReq,
    current_user: User = Depends(get_current_user),
):
    """
    批次檢查：給一串公司名稱，回報每家是否已存在於 既有客戶表 或 陌開表
    回傳結構：[{ company_name, in_existing, in_new, existing_am, new_am }]
    用於 CSV/爬蟲匯入前的去重提示。
    """
    import asyncio

    async def _check_one(name: str) -> dict:
        if not name or not name.strip():
            return {"company_name": name, "in_existing": False, "in_new": False}
        try:
            existing_task = _post("get_existing_client_table", {"company_name": name})
            new_task = _post("get_new_client_table", {"company_name": name})
            existing, new = await asyncio.gather(existing_task, new_task, return_exceptions=True)
        except Exception as e:
            logger.warning(f"bulk-check error {name!r}: {e}")
            return {"company_name": name, "in_existing": False, "in_new": False, "error": str(e)}

        existing_rows = [] if isinstance(existing, Exception) else existing.get("data", [])
        new_rows = [] if isinstance(new, Exception) else new.get("data", [])

        return {
            "company_name": name,
            "in_existing": len(existing_rows) > 0,
            "in_new": len(new_rows) > 0,
            "existing_am": existing_rows[0].get("接洽人") if existing_rows else None,
            "new_am": new_rows[0].get("接洽人") if new_rows else None,
        }

    # 限制併發避免壓垮中台 (10 同時)
    sem = asyncio.Semaphore(10)

    async def _wrapped(name: str):
        async with sem:
            return await _check_one(name)

    results = await asyncio.gather(*[_wrapped(n) for n in body.company_names])
    return {"results": results}


# ── 公司名正規化（與名單防呆一致，用於去重）──────────────────────────────────
_SUFFIXES = [
    "股份有限公司", "有限公司", "股份公司", "企業社", "工作室", "公司",
    "co.,ltd.", "co., ltd.", "co.ltd", "co ltd", "ltd.", "ltd", "inc.", "inc",
    "corporation", "corp.", "corp", "company", "co.", "group", "集團",
]


def _norm_company(name: str) -> str:
    n = (name or "").strip().lower()
    for s in _SUFFIXES:
        n = n.replace(s, "")
    n = re.sub(r"台灣|臺灣|分公司|总公司|總公司", "", n)
    n = re.sub(r"[\s\-_、,.()（）&·.]", "", n)
    return n


def _val(row: dict, key: str, maxlen: int = None) -> Optional[str]:
    v = (row.get(key) or "").strip()
    if not v:
        return None
    return v[:maxlen] if maxlen else v


@router.post("/sync-to-leads")
async def sync_to_leads(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """把 Ragic 既有客戶表 + 陌開表的客戶同步成系統名單。
    依公司名去重（系統已存在或本次重複的會跳過）；既有客戶優先於陌開表。
    """
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="僅管理員可執行 Ragic 同步")

    existing = await _post("get_existing_client_table", {})
    new = await _post("get_new_client_table", {})
    existing_rows = existing.get("data", []) or []
    new_rows = new.get("data", []) or []

    # 系統現有公司（正規化）→ 用於去重
    seen = set()
    for (cn,) in db.query(Lead.company_name).all():
        seen.add(_norm_company(cn or ""))

    created_existing = 0
    created_new = 0
    skipped = 0
    to_add: List[Lead] = []

    def _build(row: dict, source: str):
        nonlocal skipped
        company = _val(row, "公司")
        if not company:
            skipped += 1
            return None
        n = _norm_company(company)
        if not n or n in seen:
            skipped += 1
            return None
        seen.add(n)
        am = _val(row, "接洽人")
        st = _val(row, "狀態")
        notes_parts = []
        if am:
            notes_parts.append(f"Ragic 接洽人：{am}")
        if st:
            notes_parts.append(f"狀態：{st}")
        # 既有客戶＝已成交；陌開有接洽人＝已聯繫，否則新名單
        if source == "ragic_既有客戶":
            status = LeadStatus.won
        else:
            status = LeadStatus.contacted if am else LeadStatus.new
        return Lead(
            company_name=company[:255],
            contact_name=_val(row, "聯絡人", 255),
            email=_val(row, "Email", 255),
            phone=_val(row, "電話", 50),
            website=_val(row, "官網", 500),
            source=source,
            notes="；".join(notes_parts) or None,
            status=status,
        )

    # 既有客戶優先
    for row in existing_rows:
        lead = _build(row, "ragic_既有客戶")
        if lead:
            to_add.append(lead)
            created_existing += 1
    for row in new_rows:
        lead = _build(row, "ragic_陌開")
        if lead:
            to_add.append(lead)
            created_new += 1

    if to_add:
        db.add_all(to_add)
        db.commit()

    # 回補既有 Ragic 名單狀態：
    #  既有客戶 → 已成交（won）；陌開有接洽人 → 已聯繫（contacted）
    bf1 = db.query(Lead).filter(
        Lead.source == "ragic_既有客戶",
        Lead.status.in_([LeadStatus.new, LeadStatus.claiming, LeadStatus.contacted]),
    ).update({Lead.status: LeadStatus.won}, synchronize_session=False)
    bf2 = db.query(Lead).filter(
        Lead.source == "ragic_陌開",
        Lead.status.in_([LeadStatus.new, LeadStatus.claiming]),
        Lead.notes.ilike("%Ragic 接洽人：%"),
    ).update({Lead.status: LeadStatus.contacted}, synchronize_session=False)
    backfilled = bf1 + bf2
    db.commit()

    return {
        "ok": True,
        "created_existing": created_existing,
        "created_new": created_new,
        "created_total": created_existing + created_new,
        "skipped": skipped,
        "status_backfilled": backfilled,
        "ragic_existing_rows": len(existing_rows),
        "ragic_new_rows": len(new_rows),
    }


@router.get("/health")
async def health(current_user: User = Depends(get_current_user)):
    """簡單健康檢查：能否連到中台、token 是否有效"""
    try:
        await _post("get_new_client_table", {"company_name": "__health_check__"})
        return {"ok": True, "token_set": bool(os.getenv("RAGIC_TOKEN"))}
    except HTTPException as e:
        return {"ok": False, "detail": e.detail, "token_set": bool(os.getenv("RAGIC_TOKEN"))}
