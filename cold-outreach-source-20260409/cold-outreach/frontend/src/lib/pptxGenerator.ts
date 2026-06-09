import pptxgen from 'pptxgenjs'

export interface SlideData {
  title: string
  bullets: string[]
}

export interface PptxContentResponse {
  company_name: string
  industry: string
  slides: SlideData[]
}

// ── Design tokens ──────────────────────────────────────────────────────────────
const C = {
  navy:     '1A376C',
  navyMid:  '1E4080',
  accent:   '0099E6',
  accentDk: '0070B0',
  teal:     '00C2A8',
  white:    'FFFFFF',
  offWhite: 'F5F7FA',
  cardBg:   'EEF4FA',
  text:     '1A1A2E',
  subtext:  '4A5568',
  muted:    'A0AEC0',
  gold:     'F6AD55',
}

// Palette cycling for card accents
const CARD_COLORS = ['0099E6', '00C2A8', 'F6AD55', 'E05C8B', '7C5CBF', '38B2AC']

const FONT = 'Arial'

// ── Cover slide ────────────────────────────────────────────────────────────────
function addCoverSlide(pptx: pptxgen, companyName: string, industry: string) {
  const slide = pptx.addSlide()

  // Left panel — full dark navy
  slide.addShape(pptx.ShapeType.rect, {
    x: 0, y: 0, w: 7.0, h: 7.5,
    fill: { color: C.navy },
    line: { type: 'none' },
  })

  // Right panel — off-white
  slide.addShape(pptx.ShapeType.rect, {
    x: 7.0, y: 0, w: 6.33, h: 7.5,
    fill: { color: C.offWhite },
    line: { type: 'none' },
  })

  // Decorative large initial letter (watermark)
  const initial = companyName.slice(0, 1)
  slide.addText(initial, {
    x: 3.5, y: 0.5, w: 4, h: 4,
    fontSize: 260,
    bold: true,
    fontFace: FONT,
    color: '243A6E',
    align: 'center',
    valign: 'top',
    transparency: 70,
  })

  // Accent stripe on left edge
  slide.addShape(pptx.ShapeType.rect, {
    x: 0, y: 0, w: 0.18, h: 7.5,
    fill: { color: C.accent },
    line: { type: 'none' },
  })

  // Teal diagonal decorative block top-right of left panel
  slide.addShape(pptx.ShapeType.rect, {
    x: 5.6, y: 0, w: 1.4, h: 0.9,
    fill: { color: C.teal },
    line: { type: 'none' },
  })

  // LEFT PANEL content ─────────────────────────────────

  // "提案簡報" tag
  slide.addShape(pptx.ShapeType.rect, {
    x: 0.45, y: 1.35, w: 1.9, h: 0.42,
    fill: { color: C.accent },
    line: { type: 'none' },
  })
  slide.addText('提案簡報', {
    x: 0.45, y: 1.35, w: 1.9, h: 0.42,
    fontSize: 13,
    bold: true,
    fontFace: FONT,
    color: C.white,
    align: 'center',
    valign: 'middle',
  })

  // Company name (large)
  slide.addText(companyName, {
    x: 0.38, y: 2.0, w: 6.35, h: 2.2,
    fontSize: companyName.length > 8 ? 38 : 46,
    bold: true,
    fontFace: FONT,
    color: C.white,
    valign: 'middle',
    breakLine: false,
  })

  // Separator line
  slide.addShape(pptx.ShapeType.rect, {
    x: 0.38, y: 4.28, w: 2.0, h: 0.06,
    fill: { color: C.accent },
    line: { type: 'none' },
  })

  // Subtitle
  slide.addText('數位行銷整合提案', {
    x: 0.38, y: 4.46, w: 6.3, h: 0.55,
    fontSize: 18,
    fontFace: FONT,
    color: 'A8C4E0',
  })

  // Wavenet brand
  slide.addText('潮網科技  Wavenet Technology', {
    x: 0.38, y: 6.8, w: 6.3, h: 0.45,
    fontSize: 11,
    fontFace: FONT,
    color: '6888AA',
    italic: true,
  })

  // RIGHT PANEL content ────────────────────────────────

  // Info cards on right
  const infoItems = [
    { label: '客戶', value: companyName },
    { label: '產業', value: industry || '數位行銷' },
    { label: '提案單位', value: '潮網科技' },
    { label: '文件性質', value: '機密' },
  ]

  infoItems.forEach((item, i) => {
    const y = 1.5 + i * 1.1
    // Card background
    slide.addShape(pptx.ShapeType.rect, {
      x: 7.25, y, w: 5.7, h: 0.85,
      fill: { color: C.white },
      line: { color: 'DDDDEE', width: 1 },
    })
    // Color left accent on card
    slide.addShape(pptx.ShapeType.rect, {
      x: 7.25, y, w: 0.12, h: 0.85,
      fill: { color: CARD_COLORS[i % CARD_COLORS.length] },
      line: { type: 'none' },
    })
    // Label
    slide.addText(item.label, {
      x: 7.5, y: y + 0.04, w: 1.2, h: 0.35,
      fontSize: 10,
      fontFace: FONT,
      color: C.muted,
      bold: false,
    })
    // Value
    slide.addText(item.value, {
      x: 7.5, y: y + 0.38, w: 5.2, h: 0.38,
      fontSize: 14,
      fontFace: FONT,
      color: C.text,
      bold: true,
    })
  })

  // Bottom right decoration
  slide.addShape(pptx.ShapeType.rect, {
    x: 7.0, y: 6.9, w: 6.33, h: 0.6,
    fill: { color: C.navy },
    line: { type: 'none' },
  })
  slide.addText('Confidential', {
    x: 7.1, y: 6.95, w: 6.1, h: 0.45,
    fontSize: 10,
    fontFace: FONT,
    color: '6888AA',
    align: 'right',
    italic: true,
  })
}

// ── Content slide ──────────────────────────────────────────────────────────────
function addContentSlide(
  pptx: pptxgen,
  idx: number,
  total: number,
  title: string,
  bullets: string[],
  companyName: string,
) {
  const slide = pptx.addSlide()

  // Off-white full background
  slide.addShape(pptx.ShapeType.rect, {
    x: 0, y: 0, w: '100%', h: '100%',
    fill: { color: C.offWhite },
    line: { type: 'none' },
  })

  // LEFT sidebar
  slide.addShape(pptx.ShapeType.rect, {
    x: 0, y: 0, w: 3.4, h: 7.5,
    fill: { color: C.navy },
    line: { type: 'none' },
  })

  // Teal accent bar at top of sidebar
  slide.addShape(pptx.ShapeType.rect, {
    x: 0, y: 0, w: 3.4, h: 0.12,
    fill: { color: C.accent },
    line: { type: 'none' },
  })

  // Slide number circle in sidebar (top)
  slide.addShape(pptx.ShapeType.ellipse, {
    x: 0.25, y: 0.28, w: 0.55, h: 0.55,
    fill: { color: C.accent },
    line: { type: 'none' },
  })
  slide.addText(`${idx}`, {
    x: 0.25, y: 0.28, w: 0.55, h: 0.55,
    fontSize: 14,
    bold: true,
    fontFace: FONT,
    color: C.white,
    align: 'center',
    valign: 'middle',
  })

  // Total indicator
  slide.addText(`/ ${total}`, {
    x: 0.85, y: 0.32, w: 0.6, h: 0.4,
    fontSize: 10,
    fontFace: FONT,
    color: '6888AA',
    valign: 'middle',
  })

  // Title text in sidebar
  slide.addText(title, {
    x: 0.2, y: 1.1, w: 2.95, h: 4.5,
    fontSize: 20,
    bold: true,
    fontFace: FONT,
    color: C.white,
    valign: 'top',
    breakLine: true,
  })

  // Decorative teal dot bottom of sidebar
  slide.addShape(pptx.ShapeType.ellipse, {
    x: 0.28, y: 6.7, w: 0.4, h: 0.4,
    fill: { color: C.teal },
    line: { type: 'none' },
  })
  slide.addShape(pptx.ShapeType.ellipse, {
    x: 0.82, y: 6.76, w: 0.28, h: 0.28,
    fill: { color: C.accent },
    line: { type: 'none' },
  })
  slide.addShape(pptx.ShapeType.ellipse, {
    x: 1.24, y: 6.8, w: 0.2, h: 0.2,
    fill: { color: '6888AA' },
    line: { type: 'none' },
  })

  // Company branding at bottom of sidebar
  slide.addText(companyName, {
    x: 0.18, y: 6.88, w: 3.0, h: 0.4,
    fontSize: 9,
    fontFace: FONT,
    color: '4A6888',
    italic: true,
  })

  // ── RIGHT content area: bullet cards ──────────────────
  const cardX = 3.65
  const cardW = 9.35
  const totalCards = Math.min(bullets.length, 5)
  const cardH = totalCards > 0 ? Math.min((6.8) / totalCards, 1.22) : 1.2
  const startY = (7.5 - totalCards * cardH) / 2

  bullets.slice(0, 5).forEach((bullet, j) => {
    const y = startY + j * cardH
    const accentColor = CARD_COLORS[j % CARD_COLORS.length]

    // Card background
    slide.addShape(pptx.ShapeType.rect, {
      x: cardX, y: y + 0.08, w: cardW, h: cardH - 0.16,
      fill: { color: C.white },
      line: { color: 'E2E8F0', width: 1 },
    })

    // Colored left accent on card
    slide.addShape(pptx.ShapeType.rect, {
      x: cardX, y: y + 0.08, w: 0.14, h: cardH - 0.16,
      fill: { color: accentColor },
      line: { type: 'none' },
    })

    // Number circle
    slide.addShape(pptx.ShapeType.ellipse, {
      x: cardX + 0.28, y: y + cardH / 2 - 0.28,
      w: 0.55, h: 0.55,
      fill: { color: accentColor },
      line: { type: 'none' },
    })
    slide.addText(`${j + 1}`, {
      x: cardX + 0.28, y: y + cardH / 2 - 0.28,
      w: 0.55, h: 0.55,
      fontSize: 13,
      bold: true,
      fontFace: FONT,
      color: C.white,
      align: 'center',
      valign: 'middle',
    })

    // Bullet text
    slide.addText(bullet, {
      x: cardX + 1.0, y: y + 0.08, w: cardW - 1.2, h: cardH - 0.16,
      fontSize: 15,
      fontFace: FONT,
      color: C.text,
      valign: 'middle',
      breakLine: false,
    })
  })
}

// ── Public entry point ─────────────────────────────────────────────────────────
export async function generatePptxBlob(data: PptxContentResponse): Promise<Blob> {
  const pptx = new pptxgen()
  pptx.layout  = 'LAYOUT_WIDE'
  pptx.author  = 'Wavenet Technology'
  pptx.company = '潮網科技'
  pptx.subject = `${data.company_name} 數位行銷提案`
  pptx.title   = `${data.company_name} 提案簡報`

  addCoverSlide(pptx, data.company_name, data.industry)

  data.slides.forEach((sd, i) => {
    addContentSlide(pptx, i + 1, data.slides.length, sd.title, sd.bullets, data.company_name)
  })

  return await pptx.write({ outputType: 'blob' }) as Blob
}
