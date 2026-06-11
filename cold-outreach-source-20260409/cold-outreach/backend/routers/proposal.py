import io
import json
import os
import re
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
from openai import OpenAI
from auth import get_current_user
from models import User

router = APIRouter(prefix="/api/proposal", tags=["proposal"])
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# ── Colors ────────────────────────────────────────────────────────────────────
C_NAVY   = (0x1B, 0x3A, 0x6B)
C_BLUE   = (0x21, 0x96, 0xF3)
C_LBLUE  = (0xE3, 0xF2, 0xFD)
C_ORANGE = (0xF5, 0x7C, 0x00)
C_LORANGE= (0xFF, 0xF3, 0xE0)
C_WHITE  = (0xFF, 0xFF, 0xFF)
C_LGRAY  = (0xF5, 0xF5, 0xF5)
C_DGRAY  = (0x42, 0x42, 0x42)
C_MGRAY  = (0x75, 0x75, 0x75)
C_BORDER = (0xDD, 0xDD, 0xDD)
C_LBLUE2 = (0xBB, 0xDE, 0xFB)


class ProposalRequest(BaseModel):
    client_name: str
    industry: str
    current_situation: str
    services: List[str]
    monthly_budget: str
    special_notes: Optional[str] = None
    year: int = 2026


@router.post("/generate")
async def generate_proposal(
    body: ProposalRequest,
    current_user: User = Depends(get_current_user),
):
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=503, detail="OpenAI API key not configured")

    try:
        content = await _generate_content(body)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 生成失敗：{str(e)}")

    try:
        pptx_bytes = _build_pptx(content, body)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PPTX 建立失敗：{str(e)}")

    filename = f"{body.client_name}_{body.year}_媒體提案.pptx"
    return StreamingResponse(
        io.BytesIO(pptx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


# ── AI content generation ─────────────────────────────────────────────────────

async def _generate_content(body: ProposalRequest) -> dict:
    services_str = "、".join(body.services)
    special = f"\n特殊需求：{body.special_notes}" if body.special_notes else ""
    budget_num = re.sub(r"[^\d]", "", body.monthly_budget) or "100"

    prompt = f"""你是潮網科技的資深數位行銷顧問，請根據以下資訊生成媒體提案內容（繁體中文）。

客戶：{body.client_name} | 產業：{body.industry}
月預算：{budget_num}萬 | 主推服務：{services_str}
品牌現況：{body.current_situation}{special}

輸出嚴格 JSON（根據客戶產業調整所有內容，勿使用預設範例）：

{{
  "subtitle": "副標題（20字內，描述品牌轉型方向）",
  "brand_strengths": ["商品線優勢1", "商品線優勢2", "商品線優勢3"],
  "brand_d2c": "D2C經營現況一句話說明（40字內）",
  "market_segments": [
    {{"age": "25-40歲", "name": "族群名稱", "needs": ["需求1", "需求2"], "decision": "決策關鍵"}},
    {{"age": "35-55歲", "name": "族群名稱", "needs": ["需求1", "需求2"], "decision": "決策關鍵"}},
    {{"age": "50+", "name": "族群名稱", "needs": ["需求1", "需求2"], "decision": "決策關鍵"}}
  ],
  "problems": [
    {{"title": "流量依賴廣告", "desc": "缺乏自生流量，獲客成本隨演算法波動"}},
    {{"title": "缺乏品牌搜尋量", "desc": "消費者以類別搜尋，品牌指名度低"}},
    {{"title": "會員回購率不足", "desc": "初購後流失率高，缺乏生命週期自動化"}}
  ],
  "kpis": [
    {{"label": "品牌聲量成長", "value": "+50%"}},
    {{"label": "官網流量增幅", "value": "+80%"}},
    {{"label": "會員總數成長", "value": "+40%"}},
    {{"label": "廣告平均ROAS", "value": "4.0+"}},
    {{"label": "會員回購率提升", "value": "+20%"}}
  ],
  "media_strategy": [
    {{"stage": "認知 (Awareness)", "tools": "媒體工具（逗號分隔）", "message": "溝通核心（20字）"}},
    {{"stage": "考慮 (Consideration)", "tools": "媒體工具", "message": "溝通核心"}},
    {{"stage": "轉換 (Conversion)", "tools": "媒體工具", "message": "溝通核心"}},
    {{"stage": "回購 (Retention)", "tools": "媒體工具", "message": "溝通核心"}}
  ],
  "meta_audiences": [
    {{"name": "核心族群1", "products": "主打商品", "creative": "廣告創意方向（15字）"}},
    {{"name": "核心族群2", "products": "主打商品", "creative": "廣告創意方向"}},
    {{"name": "核心族群3", "products": "主打商品", "creative": "廣告創意方向"}}
  ],
  "google_keywords": [
    {{"type": "推薦比較類", "keywords": "關鍵字1、關鍵字2、關鍵字3", "effect": "高CTR（點擊率）"}},
    {{"type": "功效解決類", "keywords": "關鍵字1、關鍵字2、關鍵字3", "effect": "精準需求鎖定"}},
    {{"type": "品牌防禦類", "keywords": "品牌詞1、品牌詞2", "effect": "守住回購訂單"}}
  ],
  "youtube_experts": [
    {{"role": "營養師／專業人士", "content": "內容方向（20字）"}},
    {{"role": "醫師／學術背書", "content": "內容方向"}},
    {{"role": "教練／KOL", "content": "內容方向"}}
  ],
  "kol_tiers": [
    {{"tier": "Tier 1  大型KOL", "purpose": "流量爆發", "desc": "25字以內說明"}},
    {{"tier": "Tier 2  專業人士", "purpose": "信任轉化", "desc": "25字以內說明"}},
    {{"tier": "Tier 3  微網紅(KOC)", "purpose": "社群擴散", "desc": "25字以內說明"}}
  ],
  "crm_steps": [
    {{"day": "Day 0",   "title": "綁定會員",   "desc": "領入會禮券"}},
    {{"day": "Day 1-7", "title": "產品使用教學", "desc": "建立使用習慣"}},
    {{"day": "Day 14",  "title": "知識推播",   "desc": "增加品牌黏度"}},
    {{"day": "Day 25",  "title": "補貨提醒",   "desc": "發放回購優惠券"}},
    {{"day": "Day 30+", "title": "再次購買",   "desc": "升級會員等級"}}
  ],
  "must_buy": ["Meta FB/IG 影音廣告、ASC購物廣告", "Google Search / PMax 效果最大化", "YouTube TrueView 引流", "LINE LAP成效廣告、官方帳號導購"],
  "bonus_resources": ["健康媒體原生文章合作（早安健康、康健）", "KOL 開箱體驗合作", "Podcast 節目冠名"],
  "quarterly_plan": [
    {{"quarter": "Q1  擴大新客", "goal": "衝刺官網新客數", "strategy": "Meta 50% / Google 30% / KOL獲客"}},
    {{"quarter": "Q2  品牌信任", "goal": "建立搜尋量與好感", "strategy": "YouTube 專家影音 / 內容合作"}},
    {{"quarter": "Q3  深耕會員", "goal": "提高忠誠度與回購", "strategy": "LINE CRM 自動化 / APP推播"}},
    {{"quarter": "Q4  業績爆發", "goal": "雙11與年終節慶爆發", "strategy": "PMax拉高 / 再行銷全開 / 團購KOL"}}
  ],
  "closing_message": "結語（80字以內，說明品牌需從買流量升級為全漏斗成長模式，強調品牌資產+會員資產）"
}}"""

    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)


# ── PPTX helpers ──────────────────────────────────────────────────────────────

def _rgb(r, g, b):
    from pptx.dml.color import RGBColor
    return RGBColor(r, g, b)


def _set_bg(slide, rgb):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = _rgb(*rgb)


def _rect(slide, l, t, w, h, fill=None, border=None, border_w=12700):
    from pptx.util import Emu
    shp = slide.shapes.add_shape(1, l, t, w, h)
    if fill:
        shp.fill.solid()
        shp.fill.fore_color.rgb = _rgb(*fill)
    else:
        shp.fill.background()
    if border:
        shp.line.color.rgb = _rgb(*border)
        shp.line.width = Emu(border_w)
    else:
        shp.line.fill.background()
    return shp


def _txt(slide, text, l, t, w, h, size=14, bold=False, color=None, align="left", italic=False, wrap=True):
    from pptx.util import Pt
    from pptx.enum.text import PP_ALIGN
    color = color or C_DGRAY
    align_map = {"left": PP_ALIGN.LEFT, "center": PP_ALIGN.CENTER, "right": PP_ALIGN.RIGHT}
    box = slide.shapes.add_textbox(l, t, w, h)
    tf = box.text_frame
    tf.word_wrap = wrap
    p = tf.paragraphs[0]
    p.alignment = align_map.get(align, PP_ALIGN.LEFT)
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = _rgb(*color)
    return box, tf


def _bullets(slide, items, l, t, w, h, size=12, color=None, title=None, title_size=15, title_color=None, title_bold=True):
    from pptx.util import Pt
    from pptx.enum.text import PP_ALIGN
    color = color or C_DGRAY
    title_color = title_color or C_NAVY
    box = slide.shapes.add_textbox(l, t, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    first = True
    if title:
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = title
        run.font.size = Pt(title_size)
        run.font.bold = title_bold
        run.font.color.rgb = _rgb(*title_color)
        first = False
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if (first and i == 0) else tf.add_paragraph()
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = f"· {item}"
        run.font.size = Pt(size)
        run.font.color.rgb = _rgb(*color)
    return box


def _header(slide, title):
    from pptx.util import Inches, Pt
    from pptx.enum.text import PP_ALIGN
    _rect(slide, Inches(0), Inches(0), Inches(13.33), Inches(1.05), fill=C_NAVY)
    _rect(slide, Inches(0.35), Inches(0.83), Inches(1.5), Inches(0.05), fill=C_BLUE)
    box = slide.shapes.add_textbox(Inches(0.35), Inches(0.1), Inches(12.5), Inches(0.72))
    tf = box.text_frame
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    run = p.add_run()
    run.text = title
    run.font.size = Pt(24)
    run.font.bold = True
    run.font.color.rgb = _rgb(*C_WHITE)


def _table(slide, headers, rows, l, t, w, h):
    from pptx.util import Pt
    from pptx.enum.text import PP_ALIGN
    ncols = len(headers)
    nrows = len(rows) + 1
    tbl_shape = slide.shapes.add_table(nrows, ncols, l, t, w, h)
    tbl = tbl_shape.table
    col_w = w // ncols
    for i in range(ncols):
        tbl.columns[i].width = col_w

    # Header row
    for ci, hdr in enumerate(headers):
        cell = tbl.cell(0, ci)
        cell.fill.solid()
        cell.fill.fore_color.rgb = _rgb(*C_NAVY)
        tf = cell.text_frame
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        run = p.add_run()
        run.text = hdr
        run.font.size = Pt(13)
        run.font.bold = True
        run.font.color.rgb = _rgb(*C_WHITE)

    # Data rows
    for ri, row in enumerate(rows):
        bg = C_LGRAY if ri % 2 == 0 else C_WHITE
        for ci, val in enumerate(row):
            cell = tbl.cell(ri + 1, ci)
            cell.fill.solid()
            cell.fill.fore_color.rgb = _rgb(*bg)
            tf = cell.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.LEFT if ci > 0 else PP_ALIGN.CENTER
            run = p.add_run()
            run.text = str(val)
            run.font.size = Pt(12)
            run.font.bold = (ci == 0)
            run.font.color.rgb = _rgb(*C_NAVY if ci == 0 else C_DGRAY)

    return tbl


# ── Individual slides ─────────────────────────────────────────────────────────

def _slide_cover(prs, layout, client_name, subtitle, year):
    from pptx.util import Inches, Pt
    from pptx.enum.text import PP_ALIGN
    slide = prs.slides.add_slide(layout)
    _set_bg(slide, C_NAVY)
    # Blue accent bar
    _rect(slide, Inches(0), Inches(3.0), Inches(13.33), Inches(0.08), fill=C_BLUE)
    # Client title
    box, tf = _txt(slide, f"{client_name} {year}", Inches(1.5), Inches(1.2), Inches(10), Inches(1.2),
                   size=40, bold=True, color=C_WHITE, align="center")
    # Main title
    box2, tf2 = _txt(slide, "數位媒體成長提案", Inches(1.5), Inches(2.2), Inches(10), Inches(0.9),
                     size=30, bold=True, color=C_BLUE, align="center")
    # Subtitle
    _txt(slide, subtitle, Inches(2), Inches(3.3), Inches(9.33), Inches(0.7),
         size=16, color=C_WHITE, align="center", italic=True)
    # Footer
    _txt(slide, "Powered by 潮網科技 Wavenet Technology", Inches(3), Inches(6.8), Inches(7.33), Inches(0.4),
         size=11, color=C_MGRAY, align="center")


def _slide_brand(prs, layout, strengths, d2c_desc):
    from pptx.util import Inches
    slide = prs.slides.add_slide(layout)
    _header(slide, "品牌現況分析")

    # Left card
    _rect(slide, Inches(0.4), Inches(1.25), Inches(5.8), Inches(5.5), fill=C_LGRAY, border=C_BORDER)
    _bullets(slide, strengths, Inches(0.6), Inches(1.45), Inches(5.4), Inches(5.0),
             title="商品線完整", title_size=16, size=14)

    # Right card
    _rect(slide, Inches(7.1), Inches(1.25), Inches(5.8), Inches(5.5), fill=C_LBLUE, border=C_BORDER)
    _txt(slide, "具備D2C經營基礎", Inches(7.3), Inches(1.5), Inches(5.4), Inches(0.5),
         size=16, bold=True, color=C_NAVY)
    _txt(slide, d2c_desc, Inches(7.3), Inches(2.1), Inches(5.4), Inches(2.0),
         size=13, color=C_DGRAY, wrap=True)
    # Highlight box
    _rect(slide, Inches(7.3), Inches(5.0), Inches(5.4), Inches(0.6), fill=C_LBLUE2)
    _txt(slide, "核心優勢：數據自主性高、會員導購潛力大。", Inches(7.5), Inches(5.05), Inches(5.0), Inches(0.5),
         size=12, bold=True, color=C_NAVY)


def _slide_market(prs, layout, segments, year):
    from pptx.util import Inches
    slide = prs.slides.add_slide(layout)
    _header(slide, f"{year} 市場三大成長族群")

    card_w = Inches(3.8)
    card_h = Inches(5.3)
    xs = [Inches(0.4), Inches(4.76), Inches(9.12)]

    for i, seg in enumerate(segments[:3]):
        x = xs[i]
        _rect(slide, x, Inches(1.25), card_w, card_h, fill=C_WHITE, border=C_BORDER)
        _txt(slide, seg.get("age", ""), x, Inches(1.4), card_w, Inches(0.4),
             size=12, color=C_MGRAY, align="center")
        _txt(slide, seg.get("name", ""), x, Inches(1.8), card_w, Inches(0.5),
             size=16, bold=True, color=C_NAVY, align="center")
        needs = seg.get("needs", [])
        _bullets(slide, needs, x + Inches(0.2), Inches(2.4), card_w - Inches(0.4), Inches(2.0),
                 title="需求：", title_size=13, size=13)
        _txt(slide, f"決策關鍵：{seg.get('decision', '')}", x + Inches(0.2), Inches(4.9),
             card_w - Inches(0.4), Inches(0.5), size=12, bold=True, color=C_ORANGE)


def _slide_problems(prs, layout, problems):
    from pptx.util import Inches
    slide = prs.slides.add_slide(layout)
    _header(slide, "品牌問題診斷")
    _txt(slide, "⚠", Inches(0.5), Inches(2.5), Inches(1.5), Inches(2.0),
         size=60, color=C_ORANGE, align="center")
    _txt(slide, "當前增長瓶頸", Inches(0.3), Inches(4.7), Inches(1.8), Inches(0.4),
         size=12, color=C_MGRAY, align="center")

    for i, prob in enumerate(problems[:4]):
        y = Inches(1.35) + i * Inches(1.35)
        _rect(slide, Inches(2.3), y, Inches(10.6), Inches(1.15), fill=C_LORANGE, border=C_BORDER)
        _txt(slide, prob.get("title", ""), Inches(2.55), y + Inches(0.1), Inches(10.0), Inches(0.4),
             size=15, bold=True, color=C_ORANGE)
        _txt(slide, prob.get("desc", ""), Inches(2.55), y + Inches(0.5), Inches(10.0), Inches(0.55),
             size=13, color=C_DGRAY)


def _slide_kpis(prs, layout, kpis, year):
    from pptx.util import Inches
    slide = prs.slides.add_slide(layout)
    _header(slide, f"{year} 數位媒體年度 KPI")

    positions = [
        (Inches(0.5),  Inches(1.8)),
        (Inches(4.5),  Inches(1.8)),
        (Inches(8.5),  Inches(1.8)),
        (Inches(2.3),  Inches(4.2)),
        (Inches(6.3),  Inches(4.2)),
    ]
    for i, kpi in enumerate(kpis[:5]):
        x, y = positions[i]
        _txt(slide, kpi.get("value", ""), x, y, Inches(3.5), Inches(1.2),
             size=44, bold=True, color=C_BLUE, align="center")
        _txt(slide, kpi.get("label", ""), x, y + Inches(1.0), Inches(3.5), Inches(0.4),
             size=13, color=C_DGRAY, align="center")


def _slide_funnel(prs, layout):
    from pptx.util import Inches
    slide = prs.slides.add_slide(layout)
    _header(slide, "全渠道消費者旅程佈局")

    stages = [
        ("TOFU 認知", "解決「我不認識你」的問題", C_NAVY),
        ("MOFU 比較", "解決「為什麼選你」的問題", (0x15, 0x65, 0xC0)),
        ("BOFU 購買", "解決「現在就下單」的問題", (0x0D, 0x47, 0xA1)),
        ("Loyalty 回購", "解決「品牌一生相隨」的問題", C_BLUE),
    ]
    w = Inches(10)
    for i, (stage, desc, color) in enumerate(stages):
        wi = w - Inches(i * 0.5)
        xi = Inches(1.67) + Inches(i * 0.25)
        yi = Inches(1.4) + i * Inches(1.3)
        _rect(slide, xi, yi, wi, Inches(1.1), fill=color)
        _txt(slide, stage, xi, yi + Inches(0.15), wi, Inches(0.45),
             size=16, bold=True, color=C_WHITE, align="center")
        _txt(slide, desc, xi, yi + Inches(0.55), wi, Inches(0.4),
             size=12, color=C_LBLUE, align="center")


def _slide_strategy(prs, layout, strategy):
    from pptx.util import Inches
    slide = prs.slides.add_slide(layout)
    _header(slide, "媒體策略戰術架構")
    headers = ["階段", "媒體工具", "溝通核心"]
    rows = [(s.get("stage", ""), s.get("tools", ""), s.get("message", "")) for s in strategy]
    _table(slide, headers, rows, Inches(0.5), Inches(1.3), Inches(12.33), Inches(5.5))


def _slide_budget(prs, layout, budget_rows, budget_total, budget_note):
    from pptx.util import Inches
    slide = prs.slides.add_slide(layout)
    _header(slide, f"預算資源分配（月預算 {budget_total}萬）")

    # Bar chart (simplified)
    bar_max_w = Inches(6.5)
    by = Inches(1.4)
    for channel, pct, amount in budget_rows:
        pct_num = int(re.sub(r"[^\d]", "", pct) or "0")
        bar_w = bar_max_w * pct_num / 35  # normalize to largest (35%)
        _txt(slide, channel, Inches(0.5), by, Inches(2.0), Inches(0.38), size=12, color=C_DGRAY)
        _rect(slide, Inches(2.6), by + Inches(0.04), min(bar_w, bar_max_w), Inches(0.3), fill=C_NAVY)
        _txt(slide, f"{pct} ({amount})", Inches(2.7), by + Inches(0.04), Inches(3.0), Inches(0.3),
             size=11, bold=True, color=C_WHITE)
        by += Inches(0.78)

    # Strategy notes
    _rect(slide, Inches(9.8), Inches(1.3), Inches(3.1), Inches(5.5), fill=C_LGRAY, border=C_BORDER)
    _txt(slide, "策略說明：", Inches(10.0), Inches(1.45), Inches(2.7), Inches(0.35),
         size=13, bold=True, color=C_NAVY)
    notes = [s.strip() for s in budget_note.split("。") if s.strip()][:4]
    for ni, note in enumerate(notes):
        _txt(slide, f"{ni+1}. {note}。", Inches(10.0), Inches(1.9) + ni * Inches(1.0),
             Inches(2.7), Inches(0.9), size=11, color=C_DGRAY, wrap=True)


def _slide_meta(prs, layout, audiences):
    from pptx.util import Inches
    slide = prs.slides.add_slide(layout)
    _header(slide, "Meta 獲客主力策略")
    _txt(slide, "運用 Advantage+ 購物廣告 (ASC) 結合動態創意，自動優化轉化率。",
         Inches(0.5), Inches(6.7), Inches(12.33), Inches(0.4),
         size=11, italic=True, color=C_MGRAY, align="center")

    card_w = Inches(3.8)
    xs = [Inches(0.4), Inches(4.77), Inches(9.14)]
    for i, aud in enumerate(audiences[:3]):
        x = xs[i]
        _rect(slide, x, Inches(1.3), card_w, Inches(5.2), fill=C_WHITE, border=C_BORDER)
        _txt(slide, aud.get("name", ""), x, Inches(1.6), card_w, Inches(0.5),
             size=16, bold=True, color=C_NAVY, align="center")
        _txt(slide, f"主打：{aud.get('products', '')}", x + Inches(0.2), Inches(2.3),
             card_w - Inches(0.4), Inches(0.4), size=13, color=C_DGRAY)
        _txt(slide, f"創意：{aud.get('creative', '')}", x + Inches(0.2), Inches(2.85),
             card_w - Inches(0.4), Inches(0.5), size=12, color=C_MGRAY, wrap=True)


def _slide_google(prs, layout, keywords):
    from pptx.util import Inches
    slide = prs.slides.add_slide(layout)
    _header(slide, "Google 高轉換關鍵字佈局")
    _rect(slide, Inches(0.5), Inches(1.2), Inches(12.33), Inches(0.55), fill=C_LGRAY, border=C_BORDER)
    _txt(slide, "核心邏輯：購買意圖強烈，必須佔據搜尋結果第一屏。",
         Inches(0.7), Inches(1.28), Inches(12.0), Inches(0.38),
         size=13, bold=True, color=C_NAVY)
    headers = ["關鍵字類別", "推薦關鍵字", "預期效果"]
    rows = [(k.get("type", ""), k.get("keywords", ""), k.get("effect", "")) for k in keywords]
    _table(slide, headers, rows, Inches(0.5), Inches(2.0), Inches(12.33), Inches(4.7))


def _slide_youtube(prs, layout, experts):
    from pptx.util import Inches
    slide = prs.slides.add_slide(layout)
    _header(slide, "YouTube 專家權威內容")

    _rect(slide, Inches(6.5), Inches(1.25), Inches(6.4), Inches(5.5), fill=C_LGRAY, border=C_BORDER)
    _txt(slide, "建立「不可忽視」的品牌信任", Inches(6.7), Inches(1.55), Inches(5.8), Inches(0.5),
         size=15, bold=True, color=C_NAVY)
    for i, exp in enumerate(experts[:3]):
        _txt(slide, f"· {exp.get('role', '')}：{exp.get('content', '')}", Inches(6.7),
             Inches(2.2) + i * Inches(0.75), Inches(5.8), Inches(0.6), size=13, color=C_DGRAY, wrap=True)

    _rect(slide, Inches(6.7), Inches(5.55), Inches(5.8), Inches(0.75), fill=C_NAVY)
    _txt(slide, "目標：將 YouTube 打造為品牌的「數位講堂」，提高信任轉化。",
         Inches(6.85), Inches(5.65), Inches(5.5), Inches(0.55), size=12, color=C_WHITE, wrap=True)

    # Left visual area
    _rect(slide, Inches(0.5), Inches(1.55), Inches(5.5), Inches(4.5), fill=C_LBLUE, border=C_BORDER)
    _txt(slide, "專家內容行銷", Inches(0.5), Inches(5.8), Inches(5.5), Inches(0.4),
         size=13, color=C_MGRAY, align="center")
    _txt(slide, "📹", Inches(1.5), Inches(2.8), Inches(3.5), Inches(1.5),
         size=64, align="center", color=C_NAVY)


def _slide_kol(prs, layout, tiers):
    from pptx.util import Inches
    slide = prs.slides.add_slide(layout)
    _header(slide, "KOL 三層式矩陣佈局")

    card_w = Inches(3.8)
    xs = [Inches(0.4), Inches(4.77), Inches(9.14)]
    bgs = [C_LGRAY, C_LBLUE, C_LGRAY]
    for i, tier in enumerate(tiers[:3]):
        x = xs[i]
        _rect(slide, x, Inches(1.3), card_w, Inches(5.2), fill=bgs[i], border=C_BORDER)
        _txt(slide, tier.get("tier", ""), x, Inches(1.7), card_w, Inches(0.55),
             size=16, bold=True, color=C_NAVY, align="center")
        _txt(slide, f"目的：{tier.get('purpose', '')}", x, Inches(2.35), card_w, Inches(0.4),
             size=13, bold=True, color=C_BLUE, align="center")
        _txt(slide, tier.get("desc", ""), x + Inches(0.2), Inches(3.0),
             card_w - Inches(0.4), Inches(2.0), size=13, color=C_DGRAY, wrap=True)


def _slide_crm(prs, layout, steps):
    from pptx.util import Inches
    slide = prs.slides.add_slide(layout)
    _header(slide, "LINE 自動化 CRM 回購旅程")
    _rect(slide, Inches(0.5), Inches(1.15), Inches(0.08), Inches(0.3), fill=C_BLUE)
    _txt(slide, "保健品牌的勝負在「回購」", Inches(0.7), Inches(1.15), Inches(6.0), Inches(0.35),
         size=14, bold=True, color=C_BLUE)

    n = len(steps[:5])
    step_w = Inches(12.33 / n)
    # Timeline line
    _rect(slide, Inches(0.5), Inches(3.55), Inches(12.33), Inches(0.06), fill=C_BORDER)

    for i, step in enumerate(steps[:5]):
        x = Inches(0.5) + i * step_w
        cx = x + step_w // 2 - Inches(0.35)
        # Circle
        _rect(slide, cx, Inches(3.1), Inches(0.7), Inches(0.7), fill=C_NAVY)
        # Day label
        _txt(slide, step.get("day", ""), x, Inches(2.4), step_w, Inches(0.35),
             size=11, bold=True, color=C_NAVY, align="center")
        # Title
        _txt(slide, step.get("title", ""), x, Inches(4.0), step_w, Inches(0.45),
             size=13, bold=True, color=C_DGRAY, align="center")
        # Desc
        _txt(slide, step.get("desc", ""), x, Inches(4.5), step_w, Inches(0.45),
             size=11, color=C_MGRAY, align="center")

    _rect(slide, Inches(0.5), Inches(5.3), Inches(12.33), Inches(0.85), fill=C_LGREEN if False else C_LGRAY, border=C_BORDER)
    _txt(slide, "重點：透過分眾標籤（已購產品、性別、年齡）實現精準自動化推播，降低手動操作成本。",
         Inches(0.7), Inches(5.4), Inches(12.0), Inches(0.6), size=12, bold=True, color=C_NAVY, wrap=True)


def _slide_resources(prs, layout, must_buy, bonus):
    from pptx.util import Inches
    slide = prs.slides.add_slide(layout)
    _header(slide, "必備媒體資源建議")

    _txt(slide, "主流必買工具 (Must Buy)", Inches(0.5), Inches(1.2), Inches(5.8), Inches(0.45),
         size=15, bold=True, color=C_NAVY)
    _rect(slide, Inches(0.5), Inches(1.65), Inches(5.8), Inches(0.05), fill=C_NAVY)
    _bullets(slide, must_buy, Inches(0.5), Inches(1.85), Inches(5.8), Inches(4.5), size=13)

    _txt(slide, "加分資源 (Bonus)", Inches(7.1), Inches(1.2), Inches(5.8), Inches(0.45),
         size=15, bold=True, color=C_NAVY)
    _rect(slide, Inches(7.1), Inches(1.65), Inches(5.8), Inches(0.05), fill=C_BLUE)
    _bullets(slide, bonus, Inches(7.1), Inches(1.85), Inches(5.8), Inches(4.5), size=13)


def _slide_quarterly(prs, layout, plan):
    from pptx.util import Inches
    slide = prs.slides.add_slide(layout)
    _header(slide, "年度實施藍圖")
    headers = ["季度", "核心目標", "配置策略"]
    rows = [(p.get("quarter", ""), p.get("goal", ""), p.get("strategy", "")) for p in plan]
    _table(slide, headers, rows, Inches(0.5), Inches(1.3), Inches(12.33), Inches(5.5))


def _slide_closing(prs, layout, client_name, closing_msg, year):
    from pptx.util import Inches
    slide = prs.slides.add_slide(layout)
    _set_bg(slide, C_NAVY)
    _txt(slide, f"{client_name} Growth Blueprint {year}", Inches(1), Inches(1.0), Inches(11.33), Inches(1.2),
         size=32, bold=True, color=C_WHITE, align="center")
    _rect(slide, Inches(4), Inches(2.3), Inches(5.33), Inches(0.07), fill=C_BLUE)
    _txt(slide, closing_msg, Inches(1.5), Inches(2.7), Inches(10.33), Inches(2.0),
         size=16, color=C_WHITE, align="center", wrap=True)
    _txt(slide, "「內容 × 搜尋 × CRM × 會員經營」全漏斗成長模式",
         Inches(1.5), Inches(5.0), Inches(10.33), Inches(0.7),
         size=18, bold=True, color=C_BLUE, align="center")
    _txt(slide, "潮網科技 Wavenet Technology", Inches(3), Inches(6.5), Inches(7.33), Inches(0.4),
         size=12, color=C_MGRAY, align="center")
