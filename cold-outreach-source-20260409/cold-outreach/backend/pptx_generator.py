"""
Wavenet 提案 PPT 產生器
8 slides covering the 5-phase proposal structure.
"""
from io import BytesIO
from datetime import datetime

from pptx import Presentation
from pptx.util import Cm, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

# ── Slide geometry (16:9 widescreen) ──────────────────────────────────────────
SW = Cm(33.867)
SH = Cm(19.05)
ML = Cm(1.5)          # left/right margin
UW = SW - ML * 2      # usable width  ≈ 30.87 cm
HH = Cm(2.0)          # header height
CT = Cm(2.5)          # content top (below header)
CH = SH - CT - Cm(0.5)  # content height

# ── Brand palette ─────────────────────────────────────────────────────────────
DARK_BLUE  = RGBColor(0x1B, 0x3A, 0x6B)
BLUE       = RGBColor(0x25, 0x63, 0xEB)
BLUE_BG    = RGBColor(0xDB, 0xEA, 0xFE)
ORANGE     = RGBColor(0xF9, 0x73, 0x16)
ORANGE_BG  = RGBColor(0xFF, 0xF7, 0xED)
GREEN      = RGBColor(0x05, 0x96, 0x69)
GREEN_BG   = RGBColor(0xEC, 0xFD, 0xF5)
TEAL       = RGBColor(0x0D, 0x94, 0x88)
TEAL_BG    = RGBColor(0xF0, 0xFD, 0xFA)
PURPLE     = RGBColor(0x7C, 0x3A, 0xED)
PURPLE_BG  = RGBColor(0xF5, 0xF3, 0xFF)
AMBER      = RGBColor(0xD9, 0x77, 0x06)
AMBER_BG   = RGBColor(0xFF, 0xFB, 0xEB)
INDIGO     = RGBColor(0x46, 0x38, 0xBE)
INDIGO_BG  = RGBColor(0xEE, 0xF2, 0xFF)
WHITE      = RGBColor(0xFF, 0xFF, 0xFF)
GRAY       = RGBColor(0x6B, 0x72, 0x80)
DARK       = RGBColor(0x1F, 0x29, 0x37)
LIGHT_GRAY = RGBColor(0xF3, 0xF4, 0xF6)
ROSE       = RGBColor(0xE1, 0x1D, 0x48)
ROSE_BG    = RGBColor(0xFF, 0xF1, 0xF2)


# ── Low-level helpers ─────────────────────────────────────────────────────────

def _blank_slide(prs: Presentation):
    """Add a new blank slide (layout index 6)."""
    return prs.slides.add_slide(prs.slide_layouts[6])


def _bg(slide, color: RGBColor):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color


def _box(slide, l, t, w, h, *,
         fill: RGBColor = None,
         text: str = "",
         size: int = 11,
         bold: bool = False,
         italic: bool = False,
         color: RGBColor = None,
         align: PP_ALIGN = PP_ALIGN.LEFT,
         v_anchor: str = "top",
         wrap: bool = True,
         margin: float = 0.15):
    """
    Add a text-box with optional solid fill.
    Returns (shape, text_frame) for further customisation.
    """
    shape = slide.shapes.add_textbox(l, t, w, h)
    tf = shape.text_frame
    tf.word_wrap = wrap

    m = Cm(margin)
    tf.margin_left = m
    tf.margin_right = m
    tf.margin_top = Cm(0.1)
    tf.margin_bottom = Cm(0.1)

    if fill:
        shape.fill.solid()
        shape.fill.fore_color.rgb = fill
    else:
        shape.fill.background()

    shape.line.fill.background()   # no border

    if text:
        para = tf.paragraphs[0]
        para.alignment = align
        run = para.add_run()
        run.text = text
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.italic = italic
        run.font.color.rgb = color or DARK

    return shape, tf


def _para(tf, text: str, *,
          size: int = 11,
          bold: bool = False,
          italic: bool = False,
          color: RGBColor = None,
          align: PP_ALIGN = PP_ALIGN.LEFT,
          space_before: int = 0):
    """Append a paragraph to a text frame."""
    para = tf.add_paragraph()
    para.alignment = align
    if space_before:
        para.space_before = Pt(space_before)
    if text:
        run = para.add_run()
        run.text = text
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.italic = italic
        run.font.color.rgb = color or DARK
    return para


def _header(slide, label: str, accent: RGBColor = DARK_BLUE):
    """Full-width header bar with phase label."""
    _box(slide, Cm(0), Cm(0), SW, HH,
         fill=accent, text=label,
         size=14, bold=True, color=WHITE,
         align=PP_ALIGN.LEFT, margin=0.5)


def _section_label(slide, text: str, l, t, color: RGBColor = GRAY):
    """Small uppercase section label above a block."""
    _box(slide, l, t, UW, Cm(0.5),
         text=text.upper(), size=8, bold=True, color=color, margin=0)


def _truncate(text: str, max_len: int = 200) -> str:
    if not text:
        return ""
    return text[:max_len] + ("…" if len(text) > max_len else "")


# ── Slide builders ────────────────────────────────────────────────────────────

def _slide_cover(prs, proposal: dict):
    """Slide 0: Cover"""
    slide = _blank_slide(prs)
    _bg(slide, DARK_BLUE)

    # Top stripe
    _box(slide, Cm(0), Cm(0), SW, Cm(0.5), fill=ORANGE)

    # Bottom stripe
    _box(slide, Cm(0), SH - Cm(0.5), SW, Cm(0.5), fill=BLUE)

    # Company & title
    company = proposal.get("company_name", "")
    title   = proposal.get("title", "數位行銷提案")
    product = proposal.get("product_focus", "")
    budget  = proposal.get("budget_range", "")
    date_str = datetime.now().strftime("%Y.%m")

    _box(slide, ML, Cm(2.5), UW, Cm(2.0),
         text="DIGITAL MARKETING PROPOSAL",
         size=10, bold=True, color=BLUE_BG, margin=0)

    _box(slide, ML, Cm(4.2), UW, Cm(3.5),
         text=company,
         size=36, bold=True, color=WHITE, margin=0)

    _box(slide, ML, Cm(7.5), UW, Cm(1.5),
         text=title,
         size=16, color=BLUE_BG, margin=0)

    # Tags row
    if product:
        _, tf = _box(slide, ML, Cm(9.5), Cm(5), Cm(0.8),
                     fill=BLUE, text=product,
                     size=10, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    if budget:
        _box(slide, ML + Cm(5.5), Cm(9.5), Cm(5), Cm(0.8),
             fill=RGBColor(0x2D, 0x4E, 0x8A), text=budget,
             size=10, color=WHITE, align=PP_ALIGN.CENTER)

    # Wavenet footer
    _box(slide, ML, SH - Cm(2.2), UW, Cm(0.7),
         text="潮網科技 Wavenet Technology  ·  Google Premier Partner  ·  Meta Business Partner",
         size=9, color=GRAY, margin=0)

    _box(slide, ML, SH - Cm(1.5), Cm(5), Cm(0.6),
         text=f"© {date_str}  潮網科技 · 機密文件",
         size=8, color=GRAY, margin=0)


def _slide_phase1(prs, p1: dict):
    """Slide 1: Phase 1 — 關於潮網科技"""
    slide = _blank_slide(prs)
    _bg(slide, WHITE)
    _header(slide, "Phase 1  ·  關於潮網科技", DARK_BLUE)

    stats = (p1 or {}).get("stats", [
        {"label": "成立年份", "value": "2010年"},
        {"label": "合作品牌", "value": "500+ 家"},
        {"label": "年管理預算", "value": "NT$5億+"},
        {"label": "合作夥伴認證", "value": "Google/Meta/LINE"},
    ])

    # 4 stat boxes
    bw = (UW - Cm(1.5)) / 4
    for i, s in enumerate(stats[:4]):
        lx = ML + i * (bw + Cm(0.5))
        _, tf = _box(slide, lx, CT, bw, Cm(2.2), fill=BLUE_BG)
        _para(tf, s.get("value", ""), size=16, bold=True, color=DARK_BLUE, align=PP_ALIGN.CENTER)
        _para(tf, s.get("label", ""), size=9, color=GRAY, align=PP_ALIGN.CENTER)

    # Certifications
    certs = (p1 or {}).get("certifications", [
        "Google Premier Partner（全台前1%代理商）",
        "Meta Business Partner 認證代理商",
        "Criteo Certified Partner",
        "LINE官方認證代理商",
    ])
    lx = ML
    ty = CT + Cm(2.6)
    _section_label(slide, "合作夥伴認證", lx, ty, DARK_BLUE)
    _, tf = _box(slide, lx, ty + Cm(0.55), UW / 2 - Cm(0.5), Cm(4.5), fill=INDIGO_BG)
    for c in certs:
        _para(tf, f"✓  {c}", size=10, color=INDIGO)

    # Services
    services = (p1 or {}).get("services", [
        "付費廣告代操（Google / Meta / LINE / Criteo）",
        "搜尋引擎最佳化（SEO）",
        "社群媒體行銷（FB / IG / LINE）",
        "KOL / 網紅行銷",
        "程序化廣告（DSP / Programmatic）",
        "數據分析與多觸點歸因",
        "電商全鏈路服務",
    ])
    lx2 = ML + UW / 2 + Cm(0.5)
    _section_label(slide, "七大服務", lx2, ty, DARK_BLUE)
    _, tf = _box(slide, lx2, ty + Cm(0.55), UW / 2 - Cm(0.5), Cm(4.5), fill=BLUE_BG)
    for sv in services:
        _para(tf, f"·  {sv}", size=10, color=DARK_BLUE)

    # Headline
    headline = (p1 or {}).get("headline", "您的全方位數位行銷夥伴")
    _box(slide, ML, SH - Cm(1.2), UW, Cm(0.8),
         text=headline, size=10, italic=True, color=GRAY, margin=0)


def _slide_phase2a(prs, p2: dict):
    """Slide 2: Phase 2 — 現況診斷 & 策略方向"""
    slide = _blank_slide(prs)
    _bg(slide, WHITE)
    _header(slide, "Phase 2  ·  全漏斗策略規劃  —  現況診斷", INDIGO)

    diag = _truncate((p2 or {}).get("current_diagnosis", ""), 300)
    approach = _truncate((p2 or {}).get("recommended_approach", ""), 300)
    insight = _truncate((p2 or {}).get("key_insight", ""), 200)

    # Diagnosis box
    _section_label(slide, "客戶現況診斷", ML, CT, AMBER)
    _, tf = _box(slide, ML, CT + Cm(0.55), UW, Cm(3.2), fill=AMBER_BG)
    _para(tf, diag, size=11, color=DARK)

    # Strategy box
    ty2 = CT + Cm(4.1)
    _section_label(slide, "策略方向建議", ML, ty2, INDIGO)
    _, tf = _box(slide, ML, ty2 + Cm(0.55), UW, Cm(3.2), fill=INDIGO_BG)
    _para(tf, approach, size=11, color=DARK)

    # Key insight
    if insight:
        ty3 = ty2 + Cm(4.1)
        _, tf = _box(slide, ML, ty3, UW, Cm(1.2),
                     fill=BLUE_BG, text=f"💡 關鍵洞察：{insight}",
                     size=10, bold=True, color=DARK_BLUE)


def _slide_phase2b(prs, p2: dict):
    """Slide 3: Phase 2 — 四階段漏斗"""
    slide = _blank_slide(prs)
    _bg(slide, WHITE)
    _header(slide, "Phase 2  ·  四階段全漏斗規劃", INDIGO)

    funnel = (p2 or {}).get("funnel", [])
    colors = [
        (BLUE,   BLUE_BG),
        (INDIGO, INDIGO_BG),
        (GREEN,  GREEN_BG),
        (ORANGE, ORANGE_BG),
    ]
    bw = (UW - Cm(1.5)) / 4
    for i, stage in enumerate(funnel[:4]):
        lx = ML + i * (bw + Cm(0.5))
        fg, bg = colors[i % 4]

        # Stage header
        _box(slide, lx, CT, bw, Cm(0.9),
             fill=fg,
             text=stage.get("stage", f"階段{i+1}"),
             size=11, bold=True, color=WHITE, align=PP_ALIGN.CENTER)

        # Content
        _, tf = _box(slide, lx, CT + Cm(0.95), bw, SH - CT - Cm(1.6), fill=bg)

        obj = _truncate(stage.get("objective", ""), 80)
        channels = "、".join(stage.get("channels", []))[:60]
        audience = _truncate(stage.get("audience", ""), 60)
        kpi = stage.get("kpi", "")

        _para(tf, "目標", size=8, bold=True, color=fg)
        _para(tf, obj, size=9, color=DARK)
        _para(tf, "媒體管道", size=8, bold=True, color=fg, space_before=4)
        _para(tf, channels, size=9, color=DARK)
        _para(tf, "目標受眾", size=8, bold=True, color=fg, space_before=4)
        _para(tf, audience, size=9, color=DARK)
        _para(tf, "KPI", size=8, bold=True, color=fg, space_before=4)
        _para(tf, kpi, size=9, bold=True, color=fg)


def _slide_phase3(prs, p3: dict):
    """Slide 4: Phase 3 — 市場數據洞察"""
    slide = _blank_slide(prs)
    _bg(slide, WHITE)
    _header(slide, "Phase 3  ·  市場數據洞察", TEAL)

    bm = (p3 or {}).get("benchmarks", {})
    kpi_items = [
        ("產業平均 ROAS", bm.get("industry_avg_roas", "—")),
        ("產業平均 CPC",  bm.get("industry_avg_cpc",  "—")),
        ("產業平均 CTR",  bm.get("industry_avg_ctr",  "—")),
        ("產業平均 CVR",  bm.get("industry_avg_cvr",  "—")),
    ]

    # KPI boxes
    bw = (UW - Cm(1.5)) / 4
    for i, (label, val) in enumerate(kpi_items):
        lx = ML + i * (bw + Cm(0.5))
        _, tf = _box(slide, lx, CT, bw, Cm(2.0), fill=TEAL_BG)
        _para(tf, val, size=16, bold=True, color=TEAL, align=PP_ALIGN.CENTER)
        _para(tf, label, size=9, color=GRAY, align=PP_ALIGN.CENTER)

    # Competitive gap
    gap = _truncate((p3 or {}).get("competitive_gap", ""), 250)
    ty2 = CT + Cm(2.4)
    _section_label(slide, "競爭差距分析", ML, ty2, ROSE)
    _, tf = _box(slide, ML, ty2 + Cm(0.55), UW, Cm(2.0), fill=ROSE_BG)
    _para(tf, gap, size=10, color=DARK)

    # Growth opportunities
    opps = (p3 or {}).get("growth_opportunities", [])
    ty3 = ty2 + Cm(2.9)
    _section_label(slide, "成長機會", ML, ty3, GREEN)
    half = UW / 2 - Cm(0.25)
    _, tf1 = _box(slide, ML, ty3 + Cm(0.55), half, Cm(3.5), fill=GREEN_BG)
    _, tf2 = _box(slide, ML + half + Cm(0.5), ty3 + Cm(0.55), half, Cm(3.5), fill=GREEN_BG)
    for j, opp in enumerate(opps[:6]):
        target_tf = tf1 if j < 3 else tf2
        _para(target_tf, f"✓  {_truncate(opp, 60)}", size=10, color=DARK)


def _slide_phase4(prs, p4: dict):
    """Slide 5: Phase 4 — 廣告創意策略"""
    slide = _blank_slide(prs)
    _bg(slide, WHITE)
    _header(slide, "Phase 4  ·  廣告創意策略", PURPLE)

    # Recommended formats
    formats = (p4 or {}).get("recommended_formats", [])
    _section_label(slide, "建議廣告格式", ML, CT, PURPLE)
    fx = ML
    for fmt in formats[:6]:
        _, tf = _box(slide, fx, CT + Cm(0.55), Cm(4.5), Cm(0.7),
                     fill=PURPLE_BG, text=fmt,
                     size=10, bold=True, color=PURPLE, align=PP_ALIGN.CENTER)
        fx += Cm(5.0)

    # 3 creative dimensions
    dims = (p4 or {}).get("creative_dimensions", {})
    dim_data = [
        ("trust_building", "品牌信任維度", BLUE,   BLUE_BG),
        ("pain_point",     "痛點訴求維度", ORANGE, ORANGE_BG),
        ("conversion",     "轉換促購維度", GREEN,  GREEN_BG),
    ]
    bw = (UW - Cm(1.0)) / 3
    ty2 = CT + Cm(1.6)
    for i, (key, default_name, fg, bg) in enumerate(dim_data):
        lx = ML + i * (bw + Cm(0.5))
        dim = dims.get(key, {})
        name = dim.get("name", default_name)
        desc = _truncate(dim.get("description", ""), 120)
        examples = dim.get("examples", [])

        # Header
        _box(slide, lx, ty2, bw, Cm(0.75),
             fill=fg, text=name,
             size=11, bold=True, color=WHITE, align=PP_ALIGN.CENTER)

        # Body
        _, tf = _box(slide, lx, ty2 + Cm(0.8), bw, SH - ty2 - Cm(1.4), fill=bg)
        _para(tf, desc, size=10, color=DARK)
        if examples:
            _para(tf, "範例素材", size=8, bold=True, color=fg, space_before=6)
            for ex in examples[:2]:
                _para(tf, f"→ {_truncate(ex, 50)}", size=9, color=GRAY)


def _slide_phase5a(prs, p5: dict):
    """Slide 6: Phase 5 — 預算配置"""
    slide = _blank_slide(prs)
    _bg(slide, WHITE)
    _header(slide, "Phase 5  ·  媒體預算規劃  —  管道配置", ORANGE)

    budget  = (p5 or {}).get("monthly_budget", "—")
    roas    = (p5 or {}).get("expected_roas", "—")
    alloc   = (p5 or {}).get("channel_allocation", [])

    # Summary boxes
    hw = (UW - Cm(0.5)) / 2
    _, tf = _box(slide, ML, CT, hw, Cm(1.6), fill=ORANGE_BG)
    _para(tf, budget, size=20, bold=True, color=ORANGE, align=PP_ALIGN.CENTER)
    _para(tf, "月預算規模", size=9, color=GRAY, align=PP_ALIGN.CENTER)

    _, tf = _box(slide, ML + hw + Cm(0.5), CT, hw, Cm(1.6), fill=GREEN_BG)
    _para(tf, roas, size=20, bold=True, color=GREEN, align=PP_ALIGN.CENTER)
    _para(tf, "預期 ROAS", size=9, color=GRAY, align=PP_ALIGN.CENTER)

    # Channel allocation table
    ty2 = CT + Cm(2.0)
    _section_label(slide, "媒體管道配置", ML, ty2, ORANGE)

    if alloc:
        row_h = Cm(1.1)
        ty3 = ty2 + Cm(0.55)
        bar_max = UW * 0.45

        for ch in alloc[:6]:
            channel = ch.get("channel", "")
            pct     = min(int(ch.get("percentage", 0)), 100)
            reason  = _truncate(ch.get("rationale", ""), 60)

            # Channel name
            _box(slide, ML, ty3, Cm(5.5), row_h - Cm(0.1),
                 text=channel, size=10, bold=True, color=DARK, margin=0.1)

            # Bar background
            _box(slide, ML + Cm(5.7), ty3 + Cm(0.2), bar_max, Cm(0.6), fill=LIGHT_GRAY)

            # Bar fill
            if pct > 0:
                _box(slide, ML + Cm(5.7), ty3 + Cm(0.2),
                     bar_max * pct / 100, Cm(0.6), fill=ORANGE)

            # Percentage label
            _box(slide, ML + Cm(5.7) + bar_max + Cm(0.2), ty3, Cm(1.5), row_h,
                 text=f"{pct}%", size=10, bold=True, color=ORANGE, align=PP_ALIGN.CENTER, margin=0)

            # Rationale
            _box(slide, ML + Cm(5.7) + bar_max + Cm(2.0), ty3, UW - Cm(5.7) - bar_max - Cm(2.1), row_h,
                 text=reason, size=8, color=GRAY, margin=0.05)

            ty3 += row_h


def _slide_phase5b(prs, p5: dict):
    """Slide 7: Phase 5 — 關鍵節點 & 收尾"""
    slide = _blank_slide(prs)
    _bg(slide, WHITE)
    _header(slide, "Phase 5  ·  關鍵節點與執行時程", ORANGE)

    campaigns    = (p5 or {}).get("key_campaigns", [])
    timeline_note = _truncate((p5 or {}).get("timeline_note", ""), 200)

    # Campaign table header
    ty = CT
    col_w = [Cm(6), Cm(6), UW - Cm(12.5)]
    headers = ["活動名稱", "執行時間", "重點說明"]
    lx = ML
    for j, (h, w) in enumerate(zip(headers, col_w)):
        _box(slide, lx, ty, w - Cm(0.1), Cm(0.75),
             fill=DARK_BLUE, text=h,
             size=10, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
        lx += w

    # Rows
    ty += Cm(0.8)
    for i, c in enumerate(campaigns[:6]):
        bg = LIGHT_GRAY if i % 2 == 0 else WHITE
        row_h = Cm(1.0)
        lx = ML
        vals = [c.get("name", ""), c.get("timing", ""), c.get("focus", "")]
        for val, w in zip(vals, col_w):
            _box(slide, lx, ty, w - Cm(0.1), row_h,
                 fill=bg, text=_truncate(val, 50),
                 size=9, color=DARK, margin=0.15)
            lx += w
        ty += row_h

    # Timeline note
    if timeline_note:
        ty2 = ty + Cm(0.3)
        _box(slide, ML, ty2, UW, Cm(1.0),
             fill=ORANGE_BG, text=f"⏱  {timeline_note}",
             size=10, color=AMBER)

    # CTA footer
    _box(slide, ML, SH - Cm(1.8), UW, Cm(1.2),
         fill=DARK_BLUE,
         text="立即聯繫潮網科技  ·  讓我們為您打造專屬數位行銷方案",
         size=12, bold=True, color=WHITE, align=PP_ALIGN.CENTER)


# ── Main entry point ──────────────────────────────────────────────────────────

def generate_pptx(proposal: dict) -> BytesIO:
    """
    Build an 8-slide branded PPT from a proposal dict.
    Returns a BytesIO object containing the .pptx file.
    """
    prs = Presentation()
    prs.slide_width  = SW
    prs.slide_height = SH

    content = proposal.get("content") or {}
    p1 = content.get("phase1") or {}
    p2 = content.get("phase2") or {}
    p3 = content.get("phase3") or {}
    p4 = content.get("phase4") or {}
    p5 = content.get("phase5") or {}

    _slide_cover(prs, proposal)
    _slide_phase1(prs, p1)
    _slide_phase2a(prs, p2)
    _slide_phase2b(prs, p2)
    _slide_phase3(prs, p3)
    _slide_phase4(prs, p4)
    _slide_phase5a(prs, p5)
    _slide_phase5b(prs, p5)

    buf = BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf
