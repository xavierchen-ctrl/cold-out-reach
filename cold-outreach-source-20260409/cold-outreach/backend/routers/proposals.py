import os
import re
import json
from pathlib import Path

from openai import OpenAI
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import Lead, Proposal, ProposalStatus, User
from pptx_generator import generate_pptx, extract_design_tokens, embed_external_images

router = APIRouter(prefix="/api/proposals", tags=["proposals"])

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")


def _openai_json(prompt: str) -> dict:
    oai = OpenAI(api_key=OPENAI_API_KEY)
    return json.loads(oai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    ).choices[0].message.content)

# ── Wavenet 固定公司介紹（Phase 1）────────────────────────────────────────────

WAVENET_PHASE1 = {
    "title": "關於潮網科技",
    "headline": "您的全方位數位行銷夥伴",
    "stats": [
        {"label": "成立年份", "value": "2010年"},
        {"label": "合作品牌", "value": "500+ 家"},
        {"label": "年管理廣告預算", "value": "NT$5億+"},
        {"label": "頂級合作夥伴認證", "value": "Google / Meta / LINE"},
    ],
    "certifications": [
        "Google Premier Partner（全台前1%代理商）",
        "Meta Business Partner 認證代理商",
        "Criteo Certified Partner",
        "LINE官方認證代理商",
    ],
    "services": [
        "付費廣告代操（Google / Meta / LINE / Criteo / DSP）",
        "搜尋引擎最佳化（SEO）",
        "社群媒體行銷（FB / IG / LINE）",
        "KOL / 網紅行銷",
        "程序化廣告（Programmatic / Partnersales）",
        "數據分析與多觸點歸因",
        "電商全鏈路服務（GA4 / GTM / 再行銷）",
    ],
    "client_industries": [
        "3C 電子 / 消費電子", "美妝保健", "服飾時尚", "食品餐飲",
        "旅遊觀光 / 飯店", "金融保險", "B2B 企業",
    ],
}


# ── Request / Response Schemas ────────────────────────────────────────────────

class GenerateProposalRequest(BaseModel):
    lead_id: str
    product_focus: str = "廣告投放"
    budget_range: str = "50-100萬/月"
    extra_context: str = ""
    client_type: str = "b2c"  # b2c | b2b | b2b_biotech


class UpdateProposalRequest(BaseModel):
    title: str | None = None
    product_focus: str | None = None
    budget_range: str | None = None
    status: str | None = None
    content: dict | None = None
    email_subject: str | None = None
    email_body: str | None = None


# ── AI Prompt ─────────────────────────────────────────────────────────────────

def _build_prompt(lead: Lead, product_focus: str, budget_range: str, extra_context: str) -> str:
    tech = lead.tech_signals or {}
    ad = lead.ad_signals or {}
    score = lead.enriched_score or 0

    has_gtm = tech.get("gtm", False)
    has_pixel = tech.get("meta_pixel", False)
    has_ga4 = tech.get("ga4", False)
    has_meta_ads = ad.get("meta", {}).get("has_ads", False)
    has_google_ads = ad.get("google_ads", {}).get("has_ads", False)

    product_map = {
        "廣告投放": "Meta / Google / LINE 付費廣告代操，以 ROAS 最大化為核心目標",
        "SEO優化": "搜尋引擎自然排名優化，持續累積免費流量",
        "社群代操": "FB / IG / LINE 官方帳號內容經營與社群廣告",
        "整合行銷": "跨通路整合方案，串聯付費廣告 + SEO + 社群 + KOL",
        "KOL行銷": "精準 KOL / 網紅合作，觸及目標受眾並提升品牌聲量",
        "程序化廣告": "DSP / Programmatic 精準受眾定向投放",
    }
    product_desc = product_map.get(product_focus, product_focus)

    return f"""
你是潮網科技（Wavenet Technology）的資深提案顧問，請根據以下客戶資訊，
產生一份完整的數位行銷提案簡報大綱（繁體中文）。

## 客戶資訊
- 公司名稱：{lead.company_name}
- 聯絡人：{lead.contact_name or "行銷主管"}
- 職稱：{lead.title or "行銷主管"}
- 產業：{lead.industry or "電商零售"}
- 官網：{lead.website or "未提供"}
- 含金量分數：{score}/100
- 主推服務：{product_focus}（{product_desc}）
- 預算規模：{budget_range}
{f"- 補充背景：{extra_context}" if extra_context else ""}

## 客戶現況偵測（來自官網分析）
- Google Tag Manager：{"✅ 已安裝" if has_gtm else "❌ 未安裝"}
- Meta Pixel：{"✅ 已安裝" if has_pixel else "❌ 未安裝"}
- GA4：{"✅ 已安裝" if has_ga4 else "❌ 未安裝"}
- Meta 廣告：{"✅ 有在投放" if has_meta_ads else "❌ 未偵測到"}
- Google 廣告：{"✅ 有在投放" if has_google_ads else "❌ 未偵測到"}

## 輸出格式
請輸出一個 JSON 物件，包含以下結構：

{{
  "proposal_title": "提案標題（含客戶公司名稱）",
  "phase2": {{
    "title": "全漏斗策略規劃",
    "current_diagnosis": "根據客戶現況的2-3句診斷說明",
    "recommended_approach": "針對{lead.industry or "電商"}產業的整體行銷策略方向（2-3句）",
    "funnel": [
      {{
        "stage": "認知擴散",
        "objective": "目標說明",
        "channels": ["管道1", "管道2"],
        "audience": "目標受眾描述",
        "kpi": "主要KPI"
      }},
      {{
        "stage": "興趣培養",
        "objective": "目標說明",
        "channels": ["管道1", "管道2"],
        "audience": "目標受眾描述",
        "kpi": "主要KPI"
      }},
      {{
        "stage": "轉換促購",
        "objective": "目標說明",
        "channels": ["管道1", "管道2"],
        "audience": "目標受眾描述",
        "kpi": "主要KPI"
      }},
      {{
        "stage": "再行銷",
        "objective": "目標說明",
        "channels": ["管道1", "管道2"],
        "audience": "目標受眾描述",
        "kpi": "主要KPI"
      }}
    ],
    "key_insight": "針對此客戶的關鍵洞察（1句）"
  }},
  "phase3": {{
    "title": "市場數據洞察",
    "benchmarks": {{
      "industry_avg_roas": "產業平均 ROAS（如 3-5倍）",
      "industry_avg_cpc": "產業平均 CPC（如 NT$8-15）",
      "industry_avg_ctr": "產業平均 CTR（如 1.5-2.5%）",
      "industry_avg_cvr": "產業平均 CVR（如 2-4%）"
    }},
    "competitive_gap": "此客戶相較競爭對手的差距分析（2句）",
    "growth_opportunities": ["機會點1", "機會點2", "機會點3"]
  }},
  "phase4": {{
    "title": "廣告創意策略",
    "recommended_formats": ["建議廣告格式1", "格式2", "格式3"],
    "creative_dimensions": {{
      "trust_building": {{
        "name": "品牌信任維度",
        "description": "創意方向說明",
        "examples": ["素材範例1", "素材範例2"]
      }},
      "pain_point": {{
        "name": "痛點訴求維度",
        "description": "創意方向說明",
        "examples": ["素材範例1", "素材範例2"]
      }},
      "conversion": {{
        "name": "轉換促購維度",
        "description": "創意方向說明",
        "examples": ["素材範例1", "素材範例2"]
      }}
    }}
  }},
  "phase5": {{
    "title": "媒體預算規劃",
    "monthly_budget": "{budget_range}",
    "channel_allocation": [
      {{"channel": "管道名稱", "percentage": 35, "rationale": "配置理由"}},
      {{"channel": "管道名稱", "percentage": 25, "rationale": "配置理由"}},
      {{"channel": "管道名稱", "percentage": 20, "rationale": "配置理由"}},
      {{"channel": "管道名稱", "percentage": 20, "rationale": "配置理由"}}
    ],
    "key_campaigns": [
      {{"name": "活動名稱", "timing": "執行時間", "focus": "重點說明"}}
    ],
    "expected_roas": "預期ROAS範圍（如 4-6倍）",
    "timeline_note": "執行時程建議（1-2句）"
  }},
  "email_subject": "開發信主旨（含公司名稱，15字以內）",
  "email_body": "開發信正文（繁體中文，200-300字，包含：開場→痛點→解法→成效→CTA→簽名）"
}}

請確保所有內容都針對 {lead.company_name} 的 {lead.industry or "電商"} 業態量身訂製，
channel_allocation 的 percentage 加總必須等於 100。
"""


def _build_prompt_b2b_biotech(lead: Lead, product_focus: str, budget_range: str, extra_context: str) -> str:
    tech = lead.tech_signals or {}
    ad = lead.ad_signals or {}
    score = lead.enriched_score or 0
    has_gtm = tech.get("gtm", False)
    has_pixel = tech.get("meta_pixel", False)
    has_ga4 = tech.get("ga4", False)
    has_meta_ads = ad.get("meta", {}).get("has_ads", False)
    has_google_ads = ad.get("google_ads", {}).get("has_ads", False)

    product_map = {
        "LinkedIn ABM廣告": "LinkedIn 帳戶型廣告，精準觸及生技/製藥決策者",
        "生技媒體公關": "生技專業媒體投稿與PR，建立行業信任度",
        "Google Search/SEO": "技術關鍵字搜尋廣告與自然排名，捕捉主動評估需求",
        "會展行銷": "BIO USA / CPHI 等國際展會數位廣告與潛客開發",
        "思想領導力內容": "白皮書、Webinar、案例研究，建立技術權威地位",
        "Geo-fencing廣告": "展會現場與競爭對手辦公室精準地理圍欄廣告",
    }
    product_desc = product_map.get(product_focus, product_focus)

    return f"""
你是潮網科技（Wavenet Technology）的資深 B2B 生技產業行銷顧問。
請根據以下客戶資訊，產生一份完整的 B2B 生技/製藥數位行銷提案大綱（繁體中文）。

## 客戶資訊
- 公司名稱：{lead.company_name}
- 聯絡人：{lead.contact_name or "行銷/BD主管"}
- 職稱：{lead.title or "行銷主管"}
- 產業：{lead.industry or "生技/製藥"}
- 官網：{lead.website or "未提供"}
- 含金量分數：{score}/100
- 主推服務：{product_focus}（{product_desc}）
- 預算規模：{budget_range}
{f"- 補充背景：{extra_context}" if extra_context else ""}

## 客戶現況偵測
- Google Tag Manager：{"✅ 已安裝" if has_gtm else "❌ 未安裝"}
- Meta Pixel：{"✅ 已安裝" if has_pixel else "❌ 未安裝"}
- GA4：{"✅ 已安裝" if has_ga4 else "❌ 未安裝"}
- Meta 廣告：{"✅ 有在投放" if has_meta_ads else "❌ 未偵測到"}
- Google 廣告：{"✅ 有在投放" if has_google_ads else "❌ 未偵測到"}

## 輸出格式（嚴格 JSON，所有內容針對 B2B 生技決策者行銷）

{{
  "proposal_title": "提案標題（含公司名稱，強調B2B合作夥伴開發）",
  "phase2": {{
    "title": "B2B 決策者旅程規劃",
    "current_diagnosis": "根據客戶現況的2-3句診斷（強調生技B2B數位行銷不足之處）",
    "recommended_approach": "針對{lead.industry or "生技"}產業的整體B2B行銷策略方向（2-3句，強調精準觸及決策者）",
    "funnel": [
      {{
        "stage": "認知建立 (Awareness)",
        "objective": "讓目標決策者認識品牌",
        "channels": ["LinkedIn Sponsored Content", "生技媒體原生廣告"],
        "audience": "製藥公司採購/BD/研發主管",
        "kpi": "LinkedIn觸及率 / 官網訪問數"
      }},
      {{
        "stage": "評估考量 (Consideration)",
        "objective": "建立技術可信度，促進內容下載",
        "channels": ["白皮書/案例研究", "Google Search 技術關鍵字"],
        "audience": "已訪問官網的目標決策者",
        "kpi": "內容下載數 / 展示申請數"
      }},
      {{
        "stage": "技術驗證 (Validation)",
        "objective": "提供技術依據，推進商務洽談",
        "channels": ["Webinar/技術研討", "個人化 LinkedIn InMail"],
        "audience": "高意向決策者（下載過內容）",
        "kpi": "Webinar 報名數 / 商務會議安排數"
      }},
      {{
        "stage": "合作決策 (Decision)",
        "objective": "促成合作協議或技術授權",
        "channels": ["決策者再行銷", "ROI 計算工具", "媒體公關"],
        "audience": "進入商務流程的合作候選方",
        "kpi": "商務提案數 / 合作轉化率"
      }}
    ],
    "key_insight": "針對此生技客戶的關鍵洞察（1句，強調B2B決策週期長、需建立信任的特點）"
  }},
  "phase3": {{
    "title": "生技B2B市場數據洞察",
    "benchmarks": {{
      "industry_avg_roas": "B2B生技LinkedIn廣告平均CPL（如 NT$800-2000/潛客）",
      "industry_avg_cpc": "Google技術關鍵字平均CPC（如 NT$25-60）",
      "industry_avg_ctr": "LinkedIn Sponsored Content平均CTR（如 0.4-0.8%）",
      "industry_avg_cvr": "白皮書下載頁轉換率（如 8-15%）"
    }},
    "competitive_gap": "此生技客戶相較同類競品的數位行銷差距分析（2句）",
    "growth_opportunities": ["機會點1（針對生技B2B）", "機會點2", "機會點3"]
  }},
  "phase4": {{
    "title": "思想領導力內容策略",
    "recommended_formats": ["技術白皮書/研究報告", "網路研討會 (Webinar)", "同儕評審發表/生技媒體投稿"],
    "creative_dimensions": {{
      "trust_building": {{
        "name": "技術可信度建立",
        "description": "透過科學數據、臨床驗證、IP展示建立技術護城河形象",
        "examples": ["技術優勢比較表", "合作案例ROI展示"]
      }},
      "pain_point": {{
        "name": "合作夥伴痛點訴求",
        "description": "針對製藥公司、CRO、投資方的核心需求與挑戰提出解法",
        "examples": ["開發時程縮短案例", "法規合規解決方案"]
      }},
      "conversion": {{
        "name": "合作行動呼籲",
        "description": "引導至展示申請、技術洽談、展會見面等高意向行動",
        "examples": ["免費技術評估申請", "展會預約見面邀請"]
      }}
    }}
  }},
  "phase5": {{
    "title": "B2B媒體預算規劃",
    "monthly_budget": "{budget_range}",
    "channel_allocation": [
      {{"channel": "LinkedIn ABM廣告", "percentage": 35, "rationale": "精準觸及製藥/生技決策者，B2B最高效管道"}},
      {{"channel": "Google Search/SEO", "percentage": 25, "rationale": "捕捉主動評估技術供應商的高意向搜尋"}},
      {{"channel": "生技媒體公關", "percentage": 20, "rationale": "在專業媒體建立技術可信度"}},
      {{"channel": "內容行銷/Webinar", "percentage": 20, "rationale": "白皮書與研討會深化潛客關係"}}
    ],
    "key_campaigns": [
      {{"name": "LinkedIn 決策者ABM活動", "timing": "Q1-Q2持續投放", "focus": "Sponsored Content + InMail精準觸及"}},
      {{"name": "國際展會配套數位廣告", "timing": "展前1個月+展中", "focus": "Geo-fencing + 展後潛客再行銷"}}
    ],
    "expected_roas": "B2B生技預期CPL：NT$500-1500/合格潛客",
    "timeline_note": "建議簽約後第1個月完成官網優化與LinkedIn主頁建立，第2-3個月啟動廣告投放，第4個月起進入內容深化階段。"
  }},
  "email_subject": "開發信主旨（含公司名稱，15字以內，強調B2B合作）",
  "email_body": "開發信正文（繁體中文，200-300字，針對生技B2B決策者，包含：開場→技術現況→解法→B2B案例→CTA→簽名）"
}}

請確保所有內容都針對 {lead.company_name} 的 {lead.industry or "生技"} B2B業態量身訂製，
channel_allocation 的 percentage 加總必須等於 100。
"""


# ── Template management ───────────────────────────────────────────────────────

_TEMPLATES_DIR  = Path(os.getenv("TEMPLATES_DIR", str(Path(__file__).parent.parent / "templates")))
_DESIGN_TOKENS  = _TEMPLATES_DIR / "design_tokens.json"
_DEFAULT_TPL    = "wavenet_template.pptx"


@router.get("/templates")
async def list_templates(current_user: User = Depends(get_current_user)):
    _TEMPLATES_DIR.mkdir(exist_ok=True)
    # Determine which file is the active reference (from tokens file)
    active_source = ""
    if _DESIGN_TOKENS.exists():
        try:
            active_source = json.loads(_DESIGN_TOKENS.read_text()).get("source", "")
        except Exception:
            pass

    result = []
    for f in sorted(_TEMPLATES_DIR.glob("*.pptx"), key=lambda x: x.stat().st_mtime, reverse=True):
        result.append({
            "filename": f.name,
            "size_kb": round(f.stat().st_size / 1024),
            "active": f.name == active_source,
        })
    return result


@router.post("/templates/upload")
async def upload_template(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    # Check content-type OR filename extension (filename may be garbled for non-ASCII names)
    pptx_mime = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    fname = file.filename or ""
    is_pptx_mime = (file.content_type or "").lower() == pptx_mime
    is_pptx_ext  = fname.lower().endswith(".pptx")
    if not is_pptx_mime and not is_pptx_ext:
        raise HTTPException(400, "只支援 .pptx 檔案")

    try:
        _TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        raise HTTPException(500, f"無法建立目錄 {_TEMPLATES_DIR}: {e}")

    # Build a safe filename; keep CJK chars (they ARE \w in Python 3)
    base = re.sub(r"[^\w\-.]", "_", fname) if fname else "upload"
    if not base.lower().endswith(".pptx"):
        base = base + ".pptx"
    dest = _TEMPLATES_DIR / base
    try:
        import shutil
        with dest.open("wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        raise HTTPException(500, f"無法儲存檔案: {e}")

    # Pre-process: download externally-linked images and embed them so that
    # _copy_slide can later re-use them without PowerPoint's blocked-download warning.
    embedded = embed_external_images(str(dest))

    return {"ok": True, "filename": base, "embedded_images": embedded}


@router.put("/templates/{filename}/activate")
async def activate_template(
    filename: str,
    current_user: User = Depends(get_current_user),
):
    path = _TEMPLATES_DIR / filename
    if not path.exists():
        raise HTTPException(404, "範本不存在")
    try:
        tokens = extract_design_tokens(str(path))
    except Exception as e:
        raise HTTPException(500, f"無法解析檔案: {e}")
    # Always store source so generate_pptx can find the reference slides
    tokens["source"] = filename
    _TEMPLATES_DIR.mkdir(exist_ok=True)
    _DESIGN_TOKENS.write_text(json.dumps(tokens, ensure_ascii=False))
    return {"ok": True, "tokens": tokens}


@router.delete("/templates/{filename}")
async def delete_template(
    filename: str,
    current_user: User = Depends(get_current_user),
):
    if filename == _DEFAULT_TPL:
        raise HTTPException(400, "無法刪除預設範本")
    path = _TEMPLATES_DIR / filename
    if path.exists():
        path.unlink()
    # if deleted file was the active reference, clear design tokens
    if _DESIGN_TOKENS.exists():
        try:
            if json.loads(_DESIGN_TOKENS.read_text()).get("source") == filename:
                _DESIGN_TOKENS.unlink()
        except Exception:
            pass
    return {"ok": True}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/generate")
async def generate_proposal(
    body: GenerateProposalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """AI 產生 5 階段提案並存入資料庫"""
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=503, detail="OpenAI API key not configured")

    lead = db.query(Lead).filter(Lead.id == body.lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    if body.client_type == "b2b_biotech":
        prompt = _build_prompt_b2b_biotech(lead, body.product_focus, body.budget_range, body.extra_context)
    else:
        prompt = _build_prompt(lead, body.product_focus, body.budget_range, body.extra_context)

    try:
        data = _openai_json(prompt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 生成失敗：{str(e)}")

    content = {
        "phase1": WAVENET_PHASE1,
        "phase2": data.get("phase2", {}),
        "phase3": data.get("phase3", {}),
        "phase4": data.get("phase4", {}),
        "phase5": data.get("phase5", {}),
    }

    proposal = Proposal(
        lead_id=lead.id,
        title=data.get("proposal_title", f"{lead.company_name} 數位行銷提案"),
        product_focus=body.product_focus,
        budget_range=body.budget_range,
        status=ProposalStatus.draft,
        content=content,
        email_subject=data.get("email_subject", ""),
        email_body=data.get("email_body", ""),
        created_by=current_user.id,
    )
    db.add(proposal)
    db.commit()
    db.refresh(proposal)

    return _serialize(proposal)


@router.get("")
async def list_proposals(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    proposals = (
        db.query(Proposal)
        .order_by(Proposal.created_at.desc())
        .limit(200)
        .all()
    )
    return [_serialize(p) for p in proposals]


@router.get("/lead/{lead_id}")
async def list_lead_proposals(
    lead_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    proposals = (
        db.query(Proposal)
        .filter(Proposal.lead_id == lead_id)
        .order_by(Proposal.created_at.desc())
        .all()
    )
    return [_serialize(p) for p in proposals]


@router.get("/{proposal_id}")
async def get_proposal(
    proposal_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    proposal = db.query(Proposal).filter(Proposal.id == proposal_id).first()
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return _serialize(proposal)


@router.patch("/{proposal_id}")
async def update_proposal(
    proposal_id: str,
    body: UpdateProposalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    proposal = db.query(Proposal).filter(Proposal.id == proposal_id).first()
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")

    if body.title is not None:
        proposal.title = body.title
    if body.product_focus is not None:
        proposal.product_focus = body.product_focus
    if body.budget_range is not None:
        proposal.budget_range = body.budget_range
    if body.status is not None:
        proposal.status = body.status
    if body.content is not None:
        proposal.content = body.content
    if body.email_subject is not None:
        proposal.email_subject = body.email_subject
    if body.email_body is not None:
        proposal.email_body = body.email_body

    db.commit()
    db.refresh(proposal)
    return _serialize(proposal)


@router.get("/{proposal_id}/export-pptx")
async def export_proposal_pptx(
    proposal_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """產生並下載提案 .pptx 檔案"""
    proposal = db.query(Proposal).filter(Proposal.id == proposal_id).first()
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")

    try:
        buf = generate_pptx(_serialize(proposal))
    except BaseException as e:
        raise HTTPException(status_code=500, detail=f"PPT 產生失敗：{str(e)}")

    # Content-Disposition filename must be ASCII-safe for proxies/edge nodes
    ascii_title = re.sub(r"[^\x00-\x7F]", "", proposal.title or "proposal").strip()
    filename = f"{(ascii_title or 'proposal')[:60]}.pptx"

    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/{proposal_id}")
async def delete_proposal(
    proposal_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    proposal = db.query(Proposal).filter(Proposal.id == proposal_id).first()
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    db.delete(proposal)
    db.commit()
    return {"ok": True}


# ── Serializer ────────────────────────────────────────────────────────────────

def _serialize(p: Proposal) -> dict:
    return {
        "id": str(p.id),
        "lead_id": str(p.lead_id),
        "company_name": p.lead.company_name if p.lead else "",
        "lead_industry": p.lead.industry if p.lead else "",
        "title": p.title,
        "product_focus": p.product_focus,
        "budget_range": p.budget_range,
        "status": p.status.value if p.status else "draft",
        "content": p.content,
        "email_subject": p.email_subject,
        "email_body": p.email_body,
        "created_by": str(p.created_by) if p.created_by else None,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }
