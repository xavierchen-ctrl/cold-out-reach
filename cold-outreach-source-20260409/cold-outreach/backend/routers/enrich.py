"""
Enrichment router — 用 Lusha API 補電話（background job）
"""
import asyncio
import logging
import os
import uuid as uuid_module
from typing import List, Optional, Dict
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db, SessionLocal
from models import User, Lead
from auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/enrich", tags=["enrich"])

LUSHA_API_URL = "https://api.lusha.com/v2"

# In-memory job status store
_jobs: Dict[str, dict] = {}


class EnrichRequest(BaseModel):
    lead_ids: Optional[List[UUID]] = None
    limit: int = 20


async def _enrich_one(client: httpx.AsyncClient, api_key: str, email: str):
    """
    回傳值：
      dict  (有資料)  → 找到聯絡人
      None            → Lusha 查無此人 (EMPTY_DATA / 200 but no data)
      False           → API 錯誤 (non-200 / exception)
    """
    try:
        resp = await client.get(
            f"{LUSHA_API_URL}/person",
            params={"email": email},
            headers={"api_key": api_key},
            timeout=15,
        )
        if resp.status_code == 429:
            logger.warning(f"Lusha rate limit for {email}")
            return False
        if resp.status_code == 200:
            data = resp.json().get("contact", {}).get("data")
            return data if data else None   # None = 查無資料
        logger.warning(f"Lusha non-200 ({resp.status_code}) for {email}")
        return False
    except Exception as e:
        logger.warning(f"Lusha enrich error ({email}): {e}")
        return False


async def _run_enrich_job(job_id: str, lead_ids_str: Optional[List[str]], limit: int):
    """Background job: 批量用 Lusha 補電話"""
    api_key = os.getenv("LUSHA_API_KEY", "")
    if not api_key:
        _jobs[job_id] = {"status": "failed", "error": "LUSHA_API_KEY not set", "enriched": 0, "skipped": 0, "failed": 0, "total": 0}
        return

    _jobs[job_id]["status"] = "running"
    db = SessionLocal()
    try:
        if lead_ids_str:
            leads = db.query(Lead).filter(
                Lead.id.in_(lead_ids_str),
                Lead.email.isnot(None),
            ).limit(limit).all()
        else:
            leads = db.query(Lead).filter(
                Lead.email.isnot(None),
                Lead.email != "",
                Lead.phone.is_(None),
            ).limit(limit).all()

        total = len(leads)
        _jobs[job_id]["total"] = total
        enriched = skipped = failed = 0

        async with httpx.AsyncClient(timeout=20) as client:
            for i, lead in enumerate(leads):
                _jobs[job_id]["progress"] = i + 1
                if not lead.email:
                    skipped += 1
                    continue
                data = await _enrich_one(client, api_key, lead.email)
                if data is False:
                    # API 錯誤（non-200 / exception）
                    failed += 1
                elif data is None:
                    # Lusha 查無此人（EMPTY_DATA）
                    skipped += 1
                else:
                    phones = data.get("phoneNumbers", [])
                    if phones:
                        phone = phones[0].get("internationalNumber") or phones[0].get("localNumber")
                        if phone:
                            lead.phone = phone
                            enriched += 1
                        else:
                            skipped += 1
                    else:
                        skipped += 1
                    if not lead.contact_name and data.get("fullName"):
                        lead.contact_name = data["fullName"]
                    if not lead.title:
                        job = data.get("jobTitle", {})
                        if job:
                            lead.title = job.get("title")

                db.commit()  # 每筆 commit，避免 timeout 後全丟
                await asyncio.sleep(13)  # rate limit: 5/min (60/5=12, +1 buffer)

        _jobs[job_id].update({"status": "done", "enriched": enriched, "skipped": skipped, "failed": failed, "total": total})
        logger.info(f"Lusha enrich job {job_id} done: {enriched}/{total} enriched")

    except Exception as e:
        logger.error(f"Lusha enrich job {job_id} error: {e}")
        db.rollback()
        _jobs[job_id].update({"status": "failed", "error": str(e)})
    finally:
        db.close()


@router.post("/lusha/phone")
async def enrich_phone_start(
    body: EnrichRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """啟動 Lusha 補電話 background job，立刻回傳 job_id"""
    api_key = os.getenv("LUSHA_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=500, detail="LUSHA_API_KEY not configured")

    lim = min(body.limit or 20, 50)
    lead_ids_str = [str(lid) for lid in body.lead_ids] if body.lead_ids else None

    job_id = str(uuid_module.uuid4())
    _jobs[job_id] = {"status": "pending", "enriched": 0, "skipped": 0, "failed": 0, "total": 0, "progress": 0}

    asyncio.create_task(_run_enrich_job(job_id, lead_ids_str, lim))

    return {"job_id": job_id, "status": "pending", "message": f"開始補電話，每筆約 12 秒（rate limit）"}


@router.get("/lusha/phone/{job_id}")
def enrich_phone_status(job_id: str, current_user: User = Depends(get_current_user)):
    """查詢補電話 job 進度"""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job_id, **job}
