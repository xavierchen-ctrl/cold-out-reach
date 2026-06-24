"""Email template library — CRUD + default seeding."""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import EmailTemplate, User

router = APIRouter(prefix="/api/templates", tags=["templates"])

# ── Schemas ───────────────────────────────────────────────────────────────────

class TemplateCreate(BaseModel):
    name: str
    subject: str
    body: str
    template_type: str = "custom"


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    template_type: Optional[str] = None


class TemplateOut(BaseModel):
    id: UUID
    name: str
    subject: str
    body: str
    template_type: str
    created_by: Optional[UUID]
    created_at: datetime

    class Config:
        from_attributes = True


# ── Default templates ─────────────────────────────────────────────────────────

DEFAULT_TEMPLATES = [
    {
        "name": "初次開發信",
        "subject": "[WAVENET] 數位行銷合作邀請 — {{company_name}}",
        "body": """您好 {{contact_name}}，

我是 WAVENET 的業務代表，專注於協助企業提升數位行銷效益。

得知貴公司 {{company_name}} 在 {{industry}} 領域的卓越表現，我們相信透過精準的數位行銷策略，能進一步擴大您的市場影響力。

WAVENET 提供：
• 精準受眾投放（Google / Meta / LINE）
• 數據驅動的行銷策略規劃
• 完整的成效追蹤與優化

不知是否方便安排 15 分鐘通話，讓我們具體說明如何協助？

期待您的回覆！

敬祝 商祺
WAVENET 業務團隊""",
        "template_type": "intro",
    },
    {
        "name": "跟進信",
        "subject": "[WAVENET] 關於上次的合作邀請 — {{company_name}}",
        "body": """您好 {{contact_name}}，

先前曾向您介紹 WAVENET 數位行銷服務，不知您是否有機會看到那封信？

我們最近協助幾家 {{industry}} 領域的客戶，在 3 個月內將轉換率提升了 40%。

如果您對以下任一方向有興趣，歡迎告訴我：
• 降低廣告成本
• 提升品牌知名度
• 增加線上詢問量

只需 15 分鐘，我們可以針對 {{company_name}} 的狀況給出具體建議。

感謝您的時間！

WAVENET 業務團隊""",
        "template_type": "followup",
    },
    {
        "name": "提案信",
        "subject": "[WAVENET] 專屬提案 — {{company_name}} 數位行銷方案",
        "body": """您好 {{contact_name}}，

感謝您與我們的洽談，以下是針對 {{company_name}} 量身規劃的數位行銷方案：

【方案概述】
• 目標：提升品牌曝光與轉換率
• 執行期間：3 個月起
• 服務範圍：廣告投放 + 內容策略 + 數據分析

【預期效益】
• 品牌聲量提升 30%+
• 廣告 ROI 改善 25%+
• 月度詳細報告

我們願意先提供一次免費的數位健診，讓您了解目前的狀況與改善空間。

請問您方便本週安排正式提案會議嗎？

期待合作機會！

WAVENET 提案團隊""",
        "template_type": "proposal",
    },
]


def seed_default_templates(db: Session):
    """Seed default templates if none exist."""
    count = db.query(EmailTemplate).count()
    if count == 0:
        for t in DEFAULT_TEMPLATES:
            db.add(EmailTemplate(**t))
        db.commit()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=List[TemplateOut])
def list_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    seed_default_templates(db)
    # 每位 user 只看得到「自己建立的」+「系統預設（created_by 為空，共用）」
    return (
        db.query(EmailTemplate)
        .filter(or_(EmailTemplate.created_by == current_user.id, EmailTemplate.created_by.is_(None)))
        .order_by(EmailTemplate.created_at)
        .all()
    )


@router.post("", response_model=TemplateOut)
def create_template(
    body: TemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tmpl = EmailTemplate(**body.model_dump(), created_by=current_user.id)
    db.add(tmpl)
    db.commit()
    db.refresh(tmpl)
    return tmpl


@router.put("/{template_id}", response_model=TemplateOut)
def update_template(
    template_id: UUID,
    body: TemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tmpl = db.query(EmailTemplate).filter(EmailTemplate.id == template_id).first()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    if tmpl.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="只能編輯自己建立的模板（系統預設模板不可編輯）")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(tmpl, k, v)
    db.commit()
    db.refresh(tmpl)
    return tmpl


@router.delete("/{template_id}")
def delete_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tmpl = db.query(EmailTemplate).filter(EmailTemplate.id == template_id).first()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    if tmpl.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="只能刪除自己建立的模板（系統預設模板不可刪除）")
    db.delete(tmpl)
    db.commit()
    return {"ok": True}
