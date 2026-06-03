"""
Wavenet 提案 PPT 產生器
Template-based approach: loads the real Wavenet PPTX template,
keeps company-intro slides 1-6 intact, removes client-specific slides,
then appends AI-generated 5-phase content slides.
"""
import os
from io import BytesIO
from datetime import datetime

from pptx import Presentation
from pptx.util import Cm, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

# ── Template path ─────────────────────────────────────────────────────────────
TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "templates", "wavenet_template.pptx")

# ── Slide geometry (from template: 12192000 x 6858000 EMU) ────────────────────
SW = Emu(12192000)
SH = Emu(6858000)
ML = Cm(1.4)
MR = Cm(1.4)
UW = SW - ML - MR
CT = Cm(2.2)   # content top (below header bar)

# ── Brand palette (from real Wavenet proposals) ───────────────────────────────
NAVY      = RGBColor(0x1B, 0x2F, 0x5C)   # deep navy
TEAL      = RGBColor(0x36, 0xA1, 0xAE)   # Wavenet teal
ORANGE    = RGBColor(0xF0, 0x6B, 0x1E)   # accent orange
LIGHT_BG  = RGBColor(0xF5, 0xF7, 0xFA)
WHITE     = RGBColor(0xFF, 0xFF, 0xFF)
DARK      = RGBColor(0x2D, 0x2D, 0x2D)
GRAY      = RGBColor(0x6B, 0x72, 0x80)
TEAL_BG   = RGBColor(0xE6, 0xF6, 0xF7)
ORANGE_BG = RGBColor(0xFD, 0xF0, 0xE7)
NAVY_BG   = RGBColor(0xE8, 0xEB, 0xF4)


# ── Slide deletion helper ─────────────────────────────────────────────────────

def _delete_slides_from(prs: Presentation, keep_count: int):
    """Remove all slides after keep_count (0-indexed: keep slides 0..keep_count-1)."""
    sldIdLst = prs.slides._sldIdLst
    while len(prs.slides) > keep_count:
        idx = len(prs.slides) - 1
        rId = sldIdLst[idx].get(
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        )
        if rId:
            prs.part.drop_rel(rId)
        del sldIdLst[idx]


# ── Text helpers ──────────────────────────────────────────────────────────────

def _get_blank_layout(prs: Presentation):
    """Return the blank slide layout (last resort: layout index 0)."""
    for layout in prs.slide_layouts:
        if "blank" in layout.name.lower() or layout.name == "":
            return layout
    return prs.slide_layouts[0]


def _add_slide(prs: Presentation):
    layout = _get_blank_layout(prs)
    return prs.slides.add_slide(layout)


def _box(slide, l, t, w, h, *,
         fill: RGBColor = None,
         text: str = "",
         size: int = 11,
         bold: bool = False,
         color: RGBColor = None,
         align: PP_ALIGN = PP_ALIGN.LEFT,
         margin_cm: float = 0.2):
    shape = slide.shapes.add_textbox(l, t, w, h)
    tf = shape.text_frame
    tf.word_wrap = True
    m = Cm(margin_cm)
    tf.margin_left = m; tf.margin_right = m
    tf.margin_top = Cm(0.08); tf.margin_bottom = Cm(0.08)
    if fill:
        shape.fill.solid()
        shape.fill.fore_color.rgb = fill
    else:
        shape.fill.background()
    shape.line.fill.background()
    if text:
        para = tf.paragraphs[0]
        para.alignment = align
        run = para.add_run()
        run.text = text
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = color or DARK
        run.font.name = "Microsoft JhengHei"
    return shape, tf


def _para(tf, text: str, *, size=11, bold=False, color=None,
          align=PP_ALIGN.LEFT, space_before=0):
    para = tf.add_paragraph()
    para.alignment = align
    if space_before:
        para.space_before = Pt(space_before)
    if text:
        run = para.add_run()
        run.text = text
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = color or DARK
        run.font.name = "Microsoft JhengHei"
    return para


def _header_bar(slide, label: str, accent: RGBColor = NAVY):
    """Colored header bar spanning full width."""
    _box(slide, Emu(0), Emu(0), SW, Cm(1.9),
         fill=accent, text=label,
         size=14, bold=True, color=WHITE,
         align=PP_ALIGN.LEFT, margin_cm=0.5)


def _trunc(text: str, n: int = 180) -> str:
    if not text:
        return ""
    return text[:n] + ("..." if len(text) > n else "")


# ── Cover slide modifier ───────────────────────────────────────────────────────

def _update_cover(slide, proposal: dict):
    """Update the template cover slide (slide index 0) with client info."""
    company = proposal.get("company_name", "")
    title   = proposal.get("title", "數位行銷策略提案")
    date_str = datetime.now().strftime("%Y%m%d")

    replacements = {
        "富悅國際行銷": company,
        "有限公司": "",
        "20260316": date_str,
        "數位行銷規劃": title,
    }
    for shape in slide.shapes:
        if not shape.has_text_frame:
            continue
        for para in shape.text_frame.paragraphs:
            for run in para.runs:
                for old, new in replacements.items():
                    if old in run.text:
                        run.text = run.text.replace(old, new)


# ── Content slide builders ────────────────────────────────────────────────────

def _slide_section(prs, label: str, accent: RGBColor = NAVY):
    """Chapter divider slide."""
    slide = _add_slide(prs)
    # Left accent strip
    shape = slide.shapes.add_shape(
        1,  # MSO_SHAPE_TYPE.RECTANGLE
        Emu(0), Emu(0), Cm(1.2), SH
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = accent
    shape.line.fill.background()

    # Background
    bg = slide.background.fill
    bg.solid()
    bg.fore_color.rgb = NAVY_BG

    _box(slide, Cm(2.0), Cm(2.5), UW - Cm(1), Cm(1.5),
         text=label, size=32, bold=True, color=NAVY,
         margin_cm=0)
    _box(slide, Cm(2.0), SH - Cm(1.0), Cm(8), Cm(0.8),
         text="潮網科技 Wavenet Technology",
         size=9, color=GRAY, margin_cm=0)
    return slide


def _slide_phase2(prs, p2: dict):
    """Phase 2 – Full-funnel strategy (two slides)."""
    diag     = _trunc(p2.get("current_diagnosis", ""), 220)
    approach = _trunc(p2.get("recommended_approach", ""), 220)
    insight  = _trunc(p2.get("key_insight", ""), 120)
    funnel   = p2.get("funnel", [])

    # 2-a: Diagnosis + Approach
    slide = _add_slide(prs)
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = WHITE
    _header_bar(slide, "Phase 2  ·  全漏斗策略規劃 — 現況診斷與方向", NAVY)

    ty = CT
    _box(slide, ML, ty, UW, Cm(0.5),
         text="CLIENT DIAGNOSIS", size=8, bold=True, color=TEAL, margin_cm=0)
    _, tf = _box(slide, ML, ty + Cm(0.55), UW, Cm(2.4), fill=TEAL_BG)
    _para(tf, diag, size=11, color=DARK)

    ty2 = ty + Cm(3.2)
    _box(slide, ML, ty2, UW, Cm(0.5),
         text="STRATEGY DIRECTION", size=8, bold=True, color=ORANGE, margin_cm=0)
    _, tf = _box(slide, ML, ty2 + Cm(0.55), UW, Cm(2.4), fill=ORANGE_BG)
    _para(tf, approach, size=11, color=DARK)

    if insight:
        _box(slide, ML, SH - Cm(1.0), UW, Cm(0.7),
             fill=NAVY, text=f"Key Insight:  {insight}",
             size=10, bold=True, color=WHITE, margin_cm=0.4)

    # 2-b: Funnel
    slide2 = _add_slide(prs)
    slide2.background.fill.solid()
    slide2.background.fill.fore_color.rgb = WHITE
    _header_bar(slide2, "Phase 2  ·  四階段全漏斗媒體規劃", NAVY)

    colors = [
        (TEAL,   TEAL_BG),
        (RGBColor(0x3C,0x5A,0xA0), RGBColor(0xE8,0xED,0xF7)),
        (RGBColor(0x05,0x96,0x69), RGBColor(0xE6,0xF9,0xF1)),
        (ORANGE, ORANGE_BG),
    ]
    bw = (UW - Cm(1.5)) / 4
    for i, stage in enumerate(funnel[:4]):
        lx = ML + i * (bw + Cm(0.5))
        fg, bg = colors[i % 4]
        _box(slide2, lx, CT, bw, Cm(0.85),
             fill=fg, text=stage.get("stage", f"Phase {i+1}"),
             size=11, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
        _, tf = _box(slide2, lx, CT + Cm(0.9), bw, SH - CT - Cm(1.5), fill=bg)
        _para(tf, "目標", size=8, bold=True, color=fg)
        _para(tf, _trunc(stage.get("objective",""), 70), size=9, color=DARK)
        _para(tf, "媒體", size=8, bold=True, color=fg, space_before=3)
        _para(tf, "、".join(stage.get("channels",[]))[:55], size=9, color=DARK)
        _para(tf, "KPI", size=8, bold=True, color=fg, space_before=3)
        _para(tf, _trunc(stage.get("kpi",""), 40), size=9, bold=True, color=fg)


def _slide_phase3(prs, p3: dict):
    """Phase 3 – Market data insights."""
    slide = _add_slide(prs)
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = WHITE
    _header_bar(slide, "Phase 3  ·  市場數據洞察", TEAL)

    bm = p3.get("benchmarks", {})
    kpi_items = [
        ("產業平均 ROAS", bm.get("industry_avg_roas", "—")),
        ("產業平均 CPC",  bm.get("industry_avg_cpc",  "—")),
        ("產業平均 CTR",  bm.get("industry_avg_ctr",  "—")),
        ("產業平均 CVR",  bm.get("industry_avg_cvr",  "—")),
    ]
    bw = (UW - Cm(1.5)) / 4
    for i, (label, val) in enumerate(kpi_items):
        lx = ML + i * (bw + Cm(0.5))
        _, tf = _box(slide, lx, CT, bw, Cm(2.0), fill=TEAL_BG)
        _para(tf, str(val), size=18, bold=True, color=TEAL, align=PP_ALIGN.CENTER)
        _para(tf, label, size=9, color=GRAY, align=PP_ALIGN.CENTER)

    gap  = _trunc(p3.get("competitive_gap", ""), 200)
    opps = p3.get("growth_opportunities", [])
    ty2  = CT + Cm(2.5)
    _box(slide, ML, ty2, UW, Cm(0.5),
         text="COMPETITIVE GAP", size=8, bold=True, color=TEAL, margin_cm=0)
    _, tf = _box(slide, ML, ty2 + Cm(0.55), UW / 2 - Cm(0.3), Cm(1.9), fill=TEAL_BG)
    _para(tf, gap, size=10, color=DARK)

    ty3 = ty2 + Cm(2.75)
    _box(slide, ML, ty3, UW, Cm(0.5),
         text="GROWTH OPPORTUNITIES", size=8, bold=True, color=ORANGE, margin_cm=0)
    half = UW / 2 - Cm(0.3)
    _, tf1 = _box(slide, ML, ty3 + Cm(0.55), half, Cm(1.9), fill=ORANGE_BG)
    _, tf2 = _box(slide, ML + half + Cm(0.5), ty3 + Cm(0.55), half, Cm(1.9), fill=ORANGE_BG)
    for j, opp in enumerate(opps[:6]):
        (_para(tf1, f"- {_trunc(opp,55)}", size=10, color=DARK)
         if j < 3 else
         _para(tf2, f"- {_trunc(opp,55)}", size=10, color=DARK))


def _slide_phase4(prs, p4: dict):
    """Phase 4 – Creative strategy."""
    slide = _add_slide(prs)
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = WHITE
    _header_bar(slide, "Phase 4  ·  廣告創意策略", RGBColor(0x7C, 0x3A, 0xED))

    formats = p4.get("recommended_formats", [])
    _box(slide, ML, CT, UW, Cm(0.5),
         text="RECOMMENDED AD FORMATS", size=8, bold=True,
         color=RGBColor(0x7C,0x3A,0xED), margin_cm=0)
    fx = ML
    fmt_w = Cm(4.6)
    for fmt in formats[:6]:
        _, tf = _box(slide, fx, CT + Cm(0.55), fmt_w, Cm(0.7),
                     fill=RGBColor(0xF5,0xF3,0xFF),
                     text=fmt, size=10, bold=True,
                     color=RGBColor(0x7C,0x3A,0xED), align=PP_ALIGN.CENTER)
        fx += fmt_w + Cm(0.3)

    dims = p4.get("creative_dimensions", {})
    dim_data = [
        ("trust_building", "品牌信任",   NAVY,   NAVY_BG),
        ("pain_point",     "痛點訴求",   ORANGE, ORANGE_BG),
        ("conversion",     "轉換促購",   TEAL,   TEAL_BG),
    ]
    bw = (UW - Cm(1.0)) / 3
    ty2 = CT + Cm(1.6)
    for i, (key, default_name, fg, bg) in enumerate(dim_data):
        lx = ML + i * (bw + Cm(0.5))
        dim = dims.get(key, {})
        name = dim.get("name", default_name)
        desc = _trunc(dim.get("description", ""), 110)
        examples = dim.get("examples", [])
        _box(slide, lx, ty2, bw, Cm(0.75),
             fill=fg, text=name,
             size=11, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
        _, tf = _box(slide, lx, ty2 + Cm(0.8), bw, SH - ty2 - Cm(1.4), fill=bg)
        _para(tf, desc, size=10, color=DARK)
        if examples:
            _para(tf, "範例", size=8, bold=True, color=fg, space_before=5)
            for ex in examples[:2]:
                _para(tf, f"- {_trunc(ex,45)}", size=9, color=GRAY)


def _slide_phase5(prs, p5: dict):
    """Phase 5 – Budget (two slides)."""
    budget = p5.get("monthly_budget", "—")
    roas   = p5.get("expected_roas", "—")
    alloc  = p5.get("channel_allocation", [])
    camps  = p5.get("key_campaigns", [])
    tl_note = _trunc(p5.get("timeline_note", ""), 160)

    # 5-a: Budget allocation
    slide = _add_slide(prs)
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = WHITE
    _header_bar(slide, "Phase 5  ·  媒體預算配置", ORANGE)

    hw = (UW - Cm(0.5)) / 2
    _, tf = _box(slide, ML, CT, hw, Cm(1.6), fill=ORANGE_BG)
    _para(tf, str(budget), size=20, bold=True, color=ORANGE, align=PP_ALIGN.CENTER)
    _para(tf, "月預算規模", size=9, color=GRAY, align=PP_ALIGN.CENTER)
    _, tf2 = _box(slide, ML + hw + Cm(0.5), CT, hw, Cm(1.6), fill=TEAL_BG)
    _para(tf2, str(roas), size=20, bold=True, color=TEAL, align=PP_ALIGN.CENTER)
    _para(tf2, "預期 ROAS", size=9, color=GRAY, align=PP_ALIGN.CENTER)

    ty = CT + Cm(2.1)
    _box(slide, ML, ty, UW, Cm(0.5),
         text="CHANNEL ALLOCATION", size=8, bold=True, color=ORANGE, margin_cm=0)
    ty += Cm(0.55)
    bar_max = UW * 0.42
    for ch in alloc[:6]:
        channel = ch.get("channel", "")
        pct = min(int(ch.get("percentage", 0)), 100)
        reason  = _trunc(ch.get("rationale", ""), 55)
        row_h = Cm(1.0)
        _box(slide, ML, ty, Cm(5.0), row_h,
             text=channel, size=10, bold=True, color=DARK, margin_cm=0.1)
        bg_bar = slide.shapes.add_shape(1, ML + Cm(5.2), ty + Cm(0.2),
                                         bar_max, Cm(0.55))
        bg_bar.fill.solid(); bg_bar.fill.fore_color.rgb = RGBColor(0xE5,0xE7,0xEB)
        bg_bar.line.fill.background()
        if pct > 0:
            fill_bar = slide.shapes.add_shape(1, ML + Cm(5.2), ty + Cm(0.2),
                                               bar_max * pct / 100, Cm(0.55))
            fill_bar.fill.solid(); fill_bar.fill.fore_color.rgb = ORANGE
            fill_bar.line.fill.background()
        _box(slide, ML + Cm(5.2) + bar_max + Cm(0.2), ty, Cm(1.3), row_h,
             text=f"{pct}%", size=10, bold=True, color=ORANGE,
             align=PP_ALIGN.CENTER, margin_cm=0)
        _box(slide, ML + Cm(5.2) + bar_max + Cm(1.7), ty,
             UW - Cm(5.2) - bar_max - Cm(1.8), row_h,
             text=reason, size=8, color=GRAY, margin_cm=0.05)
        ty += row_h

    # 5-b: Campaign schedule
    slide2 = _add_slide(prs)
    slide2.background.fill.solid()
    slide2.background.fill.fore_color.rgb = WHITE
    _header_bar(slide2, "Phase 5  ·  關鍵節點與執行時程", ORANGE)

    ty = CT
    col_w = [Cm(6), Cm(5.5), UW - Cm(12.0)]
    headers = ["活動名稱", "執行時間", "重點說明"]
    lx = ML
    for h, w in zip(headers, col_w):
        _box(slide2, lx, ty, w - Cm(0.1), Cm(0.75),
             fill=NAVY, text=h, size=10, bold=True,
             color=WHITE, align=PP_ALIGN.CENTER)
        lx += w
    ty += Cm(0.8)
    for i, c in enumerate(camps[:6]):
        bg = LIGHT_BG if i % 2 == 0 else WHITE
        lx = ML
        for val, w in zip([c.get("name",""), c.get("timing",""), c.get("focus","")], col_w):
            _box(slide2, lx, ty, w - Cm(0.1), Cm(0.95),
                 fill=bg, text=_trunc(val, 45), size=9, color=DARK, margin_cm=0.15)
            lx += w
        ty += Cm(0.95)
    if tl_note:
        _box(slide2, ML, ty + Cm(0.2), UW, Cm(0.85),
             fill=ORANGE_BG, text=f"[!] {tl_note}", size=10, color=ORANGE)

    # CTA
    _box(slide2, ML, SH - Cm(1.8), UW, Cm(1.2),
         fill=NAVY,
         text="立即聯繫潮網科技  ·  讓我們為您打造專屬數位行銷方案",
         size=12, bold=True, color=WHITE, align=PP_ALIGN.CENTER)


# ── Main entry point ──────────────────────────────────────────────────────────

def generate_pptx(proposal: dict) -> BytesIO:
    """
    Load the Wavenet PPTX template, keep the company-intro slides,
    replace cover content, then append AI-generated 5-phase slides.
    """
    prs = Presentation(TEMPLATE_PATH)

    # Update cover (slide 0)
    _update_cover(prs.slides[0], proposal)

    # Keep only first 10 slides (company intro / certifications / cases)
    _delete_slides_from(prs, keep_count=10)

    # Section + phase slides
    content = proposal.get("content") or {}
    p2 = content.get("phase2") or {}
    p3 = content.get("phase3") or {}
    p4 = content.get("phase4") or {}
    p5 = content.get("phase5") or {}

    _slide_section(prs, "數位行銷策略提案", NAVY)
    _slide_phase2(prs, p2)
    _slide_section(prs, "市場數據洞察", TEAL)
    _slide_phase3(prs, p3)
    _slide_section(prs, "廣告創意策略", RGBColor(0x7C, 0x3A, 0xED))
    _slide_phase4(prs, p4)
    _slide_section(prs, "媒體預算規劃", ORANGE)
    _slide_phase5(prs, p5)

    buf = BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf
