"""
Wavenet 提案 PPT 產生器
Template-based: loads real Wavenet PPTX, keeps first 10 slides,
then appends content slides that visually continue the template style.

Template design language (reverse-engineered from real PPTX):
  - Primary navy  : #002338
  - Accent orange : #ED7D31
  - Teal          : #0097A7
  - Font          : Microsoft YaHei (YaHei used in template)
  - Layout        : number badge top-left + title, white bg
"""
import os
from io import BytesIO
from datetime import datetime

from pptx import Presentation
from pptx.util import Pt, Emu, Inches
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "templates", "wavenet_template.pptx")

# ── Slide geometry (12192000 × 6858000 EMU = 13.33 × 7.5 in) ─────────────────
SW   = Emu(12192000)
SH   = Emu(6858000)
ML   = Inches(0.35)          # left margin
MR   = Inches(0.35)          # right margin
UW   = SW - ML - MR          # usable width  ≈ 12.63 in

# ── Wavenet brand palette (from template analysis) ────────────────────────────
NAVY    = RGBColor(0x00, 0x23, 0x38)   # #002338 – primary
ORANGE  = RGBColor(0xED, 0x7D, 0x31)   # #ED7D31 – accent
TEAL    = RGBColor(0x00, 0x97, 0xA7)   # #0097A7 – teal
WHITE   = RGBColor(0xFF, 0xFF, 0xFF)
DARK    = RGBColor(0x21, 0x21, 0x21)   # #212121
GRAY    = RGBColor(0x75, 0x75, 0x75)
L_NAVY  = RGBColor(0xE3, 0xE8, 0xEC)   # light navy bg
L_ORNG  = RGBColor(0xFD, 0xEF, 0xE4)   # light orange bg
L_TEAL  = RGBColor(0xE0, 0xF5, 0xF7)   # light teal bg
L_GRAY  = RGBColor(0xF5, 0xF5, 0xF5)   # very light gray bg
MIDGRAY = RGBColor(0xE0, 0xE0, 0xE0)

FONT = "Microsoft YaHei"

# ── Slide key y-positions ──────────────────────────────────────────────────────
HDR_H   = Inches(1.05)         # header area height (number + title)
CONT_T  = Inches(1.15)         # content area top
CONT_H  = SH - CONT_T - Inches(0.25)  # max content height (≈6.1 in)


# ─────────────────────────── Low-level helpers ────────────────────────────────

def _rect(slide, l, t, w, h, color: RGBColor):
    """Add a solid-filled rectangle with no border."""
    shp = slide.shapes.add_shape(1, l, t, w, h)
    shp.fill.solid()
    shp.fill.fore_color.rgb = color
    shp.line.fill.background()
    return shp


def _box(slide, l, t, w, h, *,
         fill: RGBColor = None,
         text: str = "",
         size: int = 11,
         bold: bool = False,
         color: RGBColor = None,
         align: PP_ALIGN = PP_ALIGN.LEFT,
         ml: float = 0.12,          # left/right inner margin in inches
         mt: float = 0.06):         # top/bottom inner margin in inches
    shp = slide.shapes.add_textbox(l, t, w, h)
    tf = shp.text_frame
    tf.word_wrap = True
    tf.margin_left  = Inches(ml)
    tf.margin_right = Inches(ml)
    tf.margin_top   = Inches(mt)
    tf.margin_bottom = Inches(mt)
    if fill:
        shp.fill.solid()
        shp.fill.fore_color.rgb = fill
    else:
        shp.fill.background()
    shp.line.fill.background()
    if text:
        p = tf.paragraphs[0]
        p.alignment = align
        r = p.add_run()
        r.text = text
        r.font.size = Pt(size)
        r.font.bold = bold
        r.font.color.rgb = color or DARK
        r.font.name = FONT
    return shp, tf


def _para(tf, text: str, *,
          size: int = 10,
          bold: bool = False,
          color: RGBColor = None,
          align: PP_ALIGN = PP_ALIGN.LEFT,
          space_before: int = 0,
          italic: bool = False):
    p = tf.add_paragraph()
    p.alignment = align
    if space_before:
        p.space_before = Pt(space_before)
    if text:
        r = p.add_run()
        r.text = text
        r.font.size = Pt(size)
        r.font.bold = bold
        r.font.italic = italic
        r.font.color.rgb = color or DARK
        r.font.name = FONT
    return p


def _trunc(s, n):
    if not s:
        return ""
    s = str(s)
    return s[:n] + ("..." if len(s) > n else "")


# ─────────────────────────── Shared design chrome ─────────────────────────────

def _page_header(slide, number: str, title: str,
                 number_bg: RGBColor = NAVY,
                 title_color: RGBColor = NAVY):
    """
    Mimics the template's top-left number badge + title pattern.
    Slides 11, 13, etc. use this exact layout.
    """
    # Top-left number badge
    badge_w, badge_h = Inches(0.55), Inches(0.55)
    _rect(slide, ML, Inches(0.25), badge_w, badge_h, number_bg)
    _box(slide, ML, Inches(0.25), badge_w, badge_h,
         text=number, size=16, bold=True, color=WHITE,
         align=PP_ALIGN.CENTER, ml=0, mt=0.05)

    # Title text
    _box(slide, ML + badge_w + Inches(0.12), Inches(0.25),
         UW - badge_w - Inches(0.12), badge_h,
         text=title, size=18, bold=True, color=title_color, ml=0.05, mt=0.06)

    # Thin orange underline beneath header area
    _rect(slide, ML, Inches(0.85), UW, Inches(0.04), ORANGE)


def _footer(slide):
    """Small footer bar matching template style."""
    _box(slide, ML, SH - Inches(0.28), UW, Inches(0.24),
         text="潮網科技 Wavenet Technology  ·  Digital Marketing Proposal",
         size=8, color=GRAY, align=PP_ALIGN.RIGHT, ml=0, mt=0.03)


def _section_label(slide, text: str, l, t, color: RGBColor = NAVY):
    """Small uppercase category label above a content block."""
    _box(slide, l, t, UW, Inches(0.22),
         text=text.upper(), size=7, bold=True, color=color, ml=0, mt=0)


# ─────────────────────────── Slide deletion helper ────────────────────────────

def _delete_slides_from(prs: Presentation, keep_count: int):
    sldIdLst = prs.slides._sldIdLst
    NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    while len(prs.slides) > keep_count:
        idx = len(prs.slides) - 1
        rId = sldIdLst[idx].get(NS)
        if rId:
            prs.part.drop_rel(rId)
        del sldIdLst[idx]


def _add_slide(prs: Presentation):
    for layout in prs.slide_layouts:
        if "blank" in layout.name.lower():
            return prs.slides.add_slide(layout)
    return prs.slides.add_slide(prs.slide_layouts[0])


# ─────────────────────────── Cover update ─────────────────────────────────────

def _update_cover(slide, proposal: dict):
    company  = proposal.get("company_name", "")
    title    = proposal.get("title", "數位行銷策略提案")
    date_str = datetime.now().strftime("%Y%m%d")
    subs = {
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
                for old, new in subs.items():
                    if old in run.text:
                        run.text = run.text.replace(old, new)


# ─────────────────────────── Section divider slide ────────────────────────────

def _slide_section(prs, section_num: str, title: str, accent: RGBColor = NAVY):
    slide = _add_slide(prs)
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = WHITE

    # Left accent strip matching template sidebar style
    _rect(slide, Inches(0), Inches(0), Inches(0.18), SH, accent)

    # Large section number — matches template's big number style
    _box(slide, Inches(0.3), Inches(1.5), Inches(1.5), Inches(1.5),
         text=section_num, size=72, bold=True, color=accent, ml=0, mt=0)

    # Section title
    _box(slide, Inches(0.3), Inches(3.2), UW - Inches(0.3), Inches(1.0),
         text=title, size=28, bold=True, color=DARK, ml=0, mt=0)

    # Accent underline
    _rect(slide, Inches(0.3), Inches(4.3), Inches(2.5), Inches(0.07), accent)

    # Wavenet branding bottom right
    _box(slide, ML, SH - Inches(0.45), UW, Inches(0.35),
         text="潮網科技 Wavenet Technology",
         size=9, color=GRAY, align=PP_ALIGN.RIGHT, ml=0, mt=0)


# ─────────────────────────── Phase 2 slides ───────────────────────────────────

def _slide_phase2a(prs, p2: dict, phase_num: str = "01"):
    """Phase 2-a: Current diagnosis + strategy direction."""
    slide = _add_slide(prs)
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = WHITE

    _page_header(slide, phase_num, "全漏斗策略規劃 — 現況診斷與方向")
    _footer(slide)

    diag     = _trunc(p2.get("current_diagnosis", ""), 95)
    approach = _trunc(p2.get("recommended_approach", ""), 95)
    insight  = _trunc(p2.get("key_insight", ""), 70)

    half_w = (UW - Inches(0.2)) / 2
    ty = CONT_T

    # Left: Diagnosis
    _rect(slide, ML, ty, half_w, Inches(0.32), NAVY)
    _box(slide, ML, ty, half_w, Inches(0.32),
         text="客戶現況診斷", size=10, bold=True, color=WHITE, ml=0.1, mt=0.06)
    _, tf = _box(slide, ML, ty + Inches(0.32), half_w, Inches(1.95), fill=L_NAVY)
    _para(tf, diag, size=10, color=DARK)

    # Right: Strategy
    rx = ML + half_w + Inches(0.2)
    _rect(slide, rx, ty, half_w, Inches(0.32), ORANGE)
    _box(slide, rx, ty, half_w, Inches(0.32),
         text="策略方向建議", size=10, bold=True, color=WHITE, ml=0.1, mt=0.06)
    _, tf = _box(slide, rx, ty + Inches(0.32), half_w, Inches(1.95), fill=L_ORNG)
    _para(tf, approach, size=10, color=DARK)

    # Key insight bar
    if insight:
        bar_t = ty + Inches(2.5)
        _rect(slide, ML, bar_t, Inches(0.06), Inches(0.48), ORANGE)
        _box(slide, ML + Inches(0.12), bar_t, UW - Inches(0.12), Inches(0.48),
             fill=L_ORNG,
             text=f"Key Insight  |  {insight}",
             size=10, bold=True, color=NAVY, ml=0.12, mt=0.1)


def _slide_phase2b(prs, p2: dict, phase_num: str = "02"):
    """Phase 2-b: 4-stage funnel cards."""
    slide = _add_slide(prs)
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = WHITE

    _page_header(slide, phase_num, "四階段全漏斗媒體規劃")
    _footer(slide)

    funnel = p2.get("funnel", [])
    palette = [
        (NAVY,   L_NAVY),
        (TEAL,   L_TEAL),
        (ORANGE, L_ORNG),
        (RGBColor(0x3C,0x5A,0xA0), RGBColor(0xE8,0xED,0xF7)),
    ]

    col_w = (UW - Inches(0.45)) / 4
    max_cont_h = SH - CONT_T - Inches(0.35)   # stays within slide

    for i, stage in enumerate(funnel[:4]):
        lx  = ML + i * (col_w + Inches(0.15))
        fg, bg = palette[i % 4]

        # Stage header bar
        _rect(slide, lx, CONT_T, col_w, Inches(0.38), fg)
        _box(slide, lx, CONT_T, col_w, Inches(0.38),
             text=_trunc(stage.get("stage", f"Phase {i+1}"), 8),
             size=11, bold=True, color=WHITE, align=PP_ALIGN.CENTER, ml=0.04, mt=0.06)

        # Content box
        cont_t = CONT_T + Inches(0.38)
        cont_h = max_cont_h - Inches(0.38)
        _, tf = _box(slide, lx, cont_t, col_w, cont_h, fill=bg, ml=0.08, mt=0.08)

        _para(tf, "目標", size=8, bold=True, color=fg)
        _para(tf, _trunc(stage.get("objective", ""), 48), size=9, color=DARK)
        _para(tf, "媒體管道", size=8, bold=True, color=fg, space_before=4)
        channels = "、".join(stage.get("channels", []))
        _para(tf, _trunc(channels, 35), size=9, color=DARK)
        _para(tf, "目標受眾", size=8, bold=True, color=fg, space_before=4)
        _para(tf, _trunc(stage.get("audience", ""), 35), size=9, color=DARK)
        _para(tf, "KPI", size=8, bold=True, color=fg, space_before=4)
        _para(tf, _trunc(stage.get("kpi", ""), 28), size=9, bold=True, color=fg)


# ─────────────────────────── Phase 3 ──────────────────────────────────────────

def _slide_phase3(prs, p3: dict, phase_num: str = "03"):
    slide = _add_slide(prs)
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = WHITE

    _page_header(slide, phase_num, "市場數據洞察", TEAL, TEAL)
    _footer(slide)

    bm = p3.get("benchmarks", {})
    kpi_items = [
        ("ROAS",  bm.get("industry_avg_roas", "—")),
        ("CPC",   bm.get("industry_avg_cpc",  "—")),
        ("CTR",   bm.get("industry_avg_ctr",  "—")),
        ("CVR",   bm.get("industry_avg_cvr",  "—")),
    ]

    kpi_w = (UW - Inches(0.45)) / 4
    for i, (label, val) in enumerate(kpi_items):
        lx = ML + i * (kpi_w + Inches(0.15))
        _rect(slide, lx, CONT_T, kpi_w, Inches(0.08), TEAL)
        _, tf = _box(slide, lx, CONT_T + Inches(0.08), kpi_w, Inches(1.1), fill=L_TEAL, ml=0.05, mt=0.08)
        _para(tf, _trunc(str(val), 12), size=17, bold=True, color=TEAL, align=PP_ALIGN.CENTER)
        _para(tf, f"產業平均 {label}", size=8, color=GRAY, align=PP_ALIGN.CENTER, space_before=2)

    # Gap + Opportunities (side by side)
    ty2 = CONT_T + Inches(1.35)
    half_w = (UW - Inches(0.2)) / 2

    gap_text = _trunc(p3.get("competitive_gap", ""), 90)
    _section_label(slide, "競爭差距分析", ML, ty2, TEAL)
    _, tf = _box(slide, ML, ty2 + Inches(0.24), half_w, Inches(1.6), fill=L_TEAL, ml=0.1, mt=0.1)
    _para(tf, gap_text, size=9, color=DARK)

    opps = p3.get("growth_opportunities", [])
    rx = ML + half_w + Inches(0.2)
    _section_label(slide, "成長機會", rx, ty2, ORANGE)
    _, tf = _box(slide, rx, ty2 + Inches(0.24), half_w, Inches(1.6), fill=L_ORNG, ml=0.1, mt=0.1)
    for opp in opps[:4]:
        _para(tf, f"- {_trunc(opp, 35)}", size=9, color=DARK)


# ─────────────────────────── Phase 4 ──────────────────────────────────────────

def _slide_phase4(prs, p4: dict, phase_num: str = "04"):
    slide = _add_slide(prs)
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = WHITE

    PURPLE = RGBColor(0x5C, 0x35, 0xA8)
    L_PURP = RGBColor(0xEF, 0xEC, 0xF9)
    _page_header(slide, phase_num, "廣告創意策略", PURPLE, PURPLE)
    _footer(slide)

    # Format tags row
    formats = p4.get("recommended_formats", [])
    fx = ML
    tag_h = Inches(0.32)
    _section_label(slide, "建議廣告格式", ML, CONT_T, PURPLE)
    for fmt in formats[:5]:
        tag_w = Inches(1.7)
        if fx + tag_w > ML + UW:
            break
        _rect(slide, fx, CONT_T + Inches(0.24), tag_w, tag_h, L_PURP)
        _box(slide, fx, CONT_T + Inches(0.24), tag_w, tag_h,
             text=_trunc(fmt, 12), size=9, bold=True,
             color=PURPLE, align=PP_ALIGN.CENTER, ml=0.05, mt=0.04)
        fx += tag_w + Inches(0.12)

    # 3 creative dimensions
    dims = p4.get("creative_dimensions", {})
    dim_data = [
        ("trust_building", "品牌信任", NAVY,   L_NAVY),
        ("pain_point",     "痛點訴求", ORANGE, L_ORNG),
        ("conversion",     "轉換促購", TEAL,   L_TEAL),
    ]
    col_w = (UW - Inches(0.3)) / 3
    ty2   = CONT_T + Inches(0.78)
    max_cont_h = SH - ty2 - Inches(0.35)

    for i, (key, default_name, fg, bg) in enumerate(dim_data):
        lx = ML + i * (col_w + Inches(0.15))
        dim = dims.get(key, {})
        name = _trunc(dim.get("name", default_name), 8)
        desc = _trunc(dim.get("description", ""), 75)
        examples = dim.get("examples", [])

        _rect(slide, lx, ty2, col_w, Inches(0.35), fg)
        _box(slide, lx, ty2, col_w, Inches(0.35),
             text=name, size=11, bold=True, color=WHITE,
             align=PP_ALIGN.CENTER, ml=0.05, mt=0.06)

        body_h = max_cont_h - Inches(0.35)
        _, tf = _box(slide, lx, ty2 + Inches(0.35), col_w, body_h, fill=bg, ml=0.1, mt=0.08)
        _para(tf, desc, size=9, color=DARK)
        if examples:
            _para(tf, "素材範例", size=7, bold=True, color=fg, space_before=4)
            for ex in examples[:2]:
                _para(tf, f"- {_trunc(ex, 28)}", size=8, color=GRAY)


# ─────────────────────────── Phase 5 slides ───────────────────────────────────

def _slide_phase5a(prs, p5: dict, phase_num: str = "05"):
    """Phase 5-a: Budget allocation bar chart."""
    slide = _add_slide(prs)
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = WHITE

    _page_header(slide, phase_num, "媒體預算配置", ORANGE, ORANGE)
    _footer(slide)

    budget = _trunc(str(p5.get("monthly_budget", "—")), 15)
    roas   = _trunc(str(p5.get("expected_roas",  "—")), 15)
    alloc  = p5.get("channel_allocation", [])

    # Summary pills
    pill_w = Inches(2.2)
    for j, (val, label, c) in enumerate([
        (budget, "月預算規模", NAVY),
        (roas,   "預期 ROAS", TEAL),
    ]):
        px = ML + j * (pill_w + Inches(0.2))
        _rect(slide, px, CONT_T, pill_w, Inches(0.9), c)
        _box(slide, px, CONT_T, pill_w, Inches(0.55),
             text=val, size=18, bold=True, color=WHITE,
             align=PP_ALIGN.CENTER, ml=0.05, mt=0.08)
        _box(slide, px, CONT_T + Inches(0.55), pill_w, Inches(0.35),
             text=label, size=8, color=RGBColor(0xCC,0xDD,0xE5),
             align=PP_ALIGN.CENTER, ml=0.05, mt=0.02)

    # Bar chart
    ty = CONT_T + Inches(1.1)
    _section_label(slide, "媒體管道配置", ML, ty, ORANGE)
    ty += Inches(0.25)

    bar_max   = UW * 0.38
    row_h     = Inches(0.5)
    ch_col_w  = Inches(1.5)
    max_rows  = int((SH - ty - Inches(0.3)) / row_h)

    for ch in alloc[:min(6, max_rows)]:
        channel = _trunc(ch.get("channel", ""), 10)
        pct     = min(int(ch.get("percentage", 0)), 100)
        reason  = _trunc(ch.get("rationale", ""), 32)

        _box(slide, ML, ty, ch_col_w, row_h,
             text=channel, size=9, bold=True, color=DARK, ml=0, mt=0.12)

        bar_x = ML + ch_col_w + Inches(0.1)
        _rect(slide, bar_x, ty + Inches(0.12), bar_max, Inches(0.26), MIDGRAY)
        if pct > 0:
            _rect(slide, bar_x, ty + Inches(0.12),
                  bar_max * pct / 100, Inches(0.26), ORANGE)
        _box(slide, bar_x + bar_max + Inches(0.08), ty, Inches(0.5), row_h,
             text=f"{pct}%", size=9, bold=True, color=ORANGE,
             align=PP_ALIGN.CENTER, ml=0, mt=0.12)
        _box(slide, bar_x + bar_max + Inches(0.65), ty,
             UW - ch_col_w - Inches(0.1) - bar_max - Inches(0.65), row_h,
             text=reason, size=8, color=GRAY, ml=0, mt=0.12)
        ty += row_h


def _slide_phase5b(prs, p5: dict, phase_num: str = "06"):
    """Phase 5-b: Campaign schedule table + CTA."""
    slide = _add_slide(prs)
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = WHITE

    _page_header(slide, phase_num, "關鍵節點與執行時程", ORANGE, ORANGE)
    _footer(slide)

    campaigns = p5.get("key_campaigns", [])
    tl_note   = _trunc(p5.get("timeline_note", ""), 85)

    # Table header
    ty  = CONT_T
    cws = [Inches(2.2), Inches(1.7), UW - Inches(4.1)]
    hdrs = ["活動名稱", "執行時間", "重點說明"]
    lx  = ML
    for h, w in zip(hdrs, cws):
        _rect(slide, lx, ty, w - Inches(0.04), Inches(0.36), NAVY)
        _box(slide, lx, ty, w - Inches(0.04), Inches(0.36),
             text=h, size=9, bold=True, color=WHITE, align=PP_ALIGN.CENTER,
             ml=0.06, mt=0.06)
        lx += w

    ty += Inches(0.36)
    row_h = Inches(0.5)
    max_rows = int((SH - ty - Inches(1.2)) / row_h)

    for i, c in enumerate(campaigns[:min(5, max_rows)]):
        bg = L_GRAY if i % 2 == 0 else WHITE
        lx = ML
        vals = [_trunc(c.get("name",""),18), _trunc(c.get("timing",""),14),
                _trunc(c.get("focus",""),42)]
        for val, w in zip(vals, cws):
            _rect(slide, lx, ty, w - Inches(0.04), row_h, bg)
            _box(slide, lx, ty, w - Inches(0.04), row_h,
                 text=val, size=9, color=DARK, ml=0.08, mt=0.1)
            lx += w
        ty += row_h

    # Timeline note
    if tl_note:
        _rect(slide, ML, ty + Inches(0.12), UW, Inches(0.42), L_ORNG)
        _box(slide, ML + Inches(0.1), ty + Inches(0.12), UW - Inches(0.1), Inches(0.42),
             text=f"執行建議  |  {tl_note}", size=9, color=NAVY, ml=0.08, mt=0.1)
        ty += Inches(0.58)

    # CTA
    cta_t = SH - Inches(0.85)
    _rect(slide, Inches(0), cta_t, SW, Inches(0.75), NAVY)
    _box(slide, ML, cta_t, UW, Inches(0.75),
         text="立即聯繫潮網科技  ·  讓我們為您打造專屬數位行銷方案",
         size=13, bold=True, color=WHITE, align=PP_ALIGN.CENTER, ml=0.1, mt=0.18)


# ─────────────────────────── Main entry ───────────────────────────────────────

def generate_pptx(proposal: dict) -> BytesIO:
    prs = Presentation(TEMPLATE_PATH)

    _update_cover(prs.slides[0], proposal)
    _delete_slides_from(prs, keep_count=10)

    content = proposal.get("content") or {}
    p2 = content.get("phase2") or {}
    p3 = content.get("phase3") or {}
    p4 = content.get("phase4") or {}
    p5 = content.get("phase5") or {}

    _slide_section(prs, "01", "數位行銷策略提案", NAVY)
    _slide_phase2a(prs, p2, "01")
    _slide_phase2b(prs, p2, "02")
    _slide_section(prs, "02", "市場數據洞察", TEAL)
    _slide_phase3(prs, p3, "03")
    _slide_section(prs, "03", "廣告創意策略", RGBColor(0x5C, 0x35, 0xA8))
    _slide_phase4(prs, p4, "04")
    _slide_section(prs, "04", "媒體預算規劃", ORANGE)
    _slide_phase5a(prs, p5, "05")
    _slide_phase5b(prs, p5, "06")

    buf = BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf
