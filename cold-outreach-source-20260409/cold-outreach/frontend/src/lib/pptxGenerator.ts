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
  accentLt: '4DB8FF',
  teal:     '00C2A8',
  orange:   'F6803A',
  white:    'FFFFFF',
  offWhite: 'F5F7FA',
  cardBg:   'EEF4FA',
  text:     '1A1A2E',
  subtext:  '4A5568',
  muted:    'A0AEC0',
  deco:     'C5D8F0',  // light blue for decorative circles
}

const CARD_COLORS = ['0099E6', '00C2A8', 'F6803A', 'E05C8B', '7C5CBF', '38B2AC']
const FONT = 'Arial'

type PptxSlide = ReturnType<InstanceType<typeof pptxgen>['addSlide']>

// ── Decorative background circles (Wavenet-style) ──────────────────────────────
function addDecoCircles(slide: PptxSlide) {
  // Top-right large blob
  slide.addShape('ellipse' as pptxgen.SHAPE_NAME, {
    x: 10.8, y: -1.2, w: 3.8, h: 3.8,
    fill: { color: C.deco, transparency: 82 },
    line: { type: 'none' },
  })
  // Top-right smaller
  slide.addShape('ellipse' as pptxgen.SHAPE_NAME, {
    x: 11.6, y: 0.4, w: 2.2, h: 2.2,
    fill: { color: C.accent, transparency: 90 },
    line: { type: 'none' },
  })
  // Bottom-left large blob
  slide.addShape('ellipse' as pptxgen.SHAPE_NAME, {
    x: -1.0, y: 5.4, w: 3.6, h: 3.6,
    fill: { color: C.deco, transparency: 82 },
    line: { type: 'none' },
  })
  // Bottom-left smaller
  slide.addShape('ellipse' as pptxgen.SHAPE_NAME, {
    x: 0.2, y: 6.0, w: 2.0, h: 2.0,
    fill: { color: C.accent, transparency: 90 },
    line: { type: 'none' },
  })
}

// ── Footer bar ─────────────────────────────────────────────────────────────────
function addFooter(slide: PptxSlide, companyName: string, slideTitle: string) {
  const today = new Date().toISOString().slice(0, 10)

  slide.addShape('rect' as pptxgen.SHAPE_NAME, {
    x: 0, y: 7.05, w: 13.33, h: 0.45,
    fill: { color: C.navy },
    line: { type: 'none' },
  })
  // Orange left accent strip
  slide.addShape('rect' as pptxgen.SHAPE_NAME, {
    x: 0, y: 7.05, w: 0.18, h: 0.45,
    fill: { color: C.orange },
    line: { type: 'none' },
  })

  const footerText = `${companyName}  |  ${today}  |  ${slideTitle}`
  slide.addText(footerText, {
    x: 0.3, y: 7.06, w: 12.7, h: 0.42,
    fontSize: 9,
    fontFace: FONT,
    color: '7A9BC0',
    align: 'left',
    valign: 'middle',
  })
  slide.addText('潮網科技  Wavenet Technology', {
    x: 0.3, y: 7.06, w: 12.7, h: 0.42,
    fontSize: 9,
    fontFace: FONT,
    color: '5A7A9A',
    align: 'right',
    valign: 'middle',
    italic: true,
  })
}

// ── Cover slide ────────────────────────────────────────────────────────────────
function addCoverSlide(pptx: pptxgen, companyName: string, industry: string) {
  const slide = pptx.addSlide()

  // Full dark navy background
  slide.addShape('rect' as pptxgen.SHAPE_NAME, {
    x: 0, y: 0, w: 13.33, h: 7.5,
    fill: { color: C.navy },
    line: { type: 'none' },
  })

  // Subtle grid/tech texture — horizontal lines
  for (let i = 0; i < 12; i++) {
    slide.addShape('rect' as pptxgen.SHAPE_NAME, {
      x: 0, y: i * 0.62, w: 13.33, h: 0.01,
      fill: { color: '2A4A80', transparency: 60 },
      line: { type: 'none' },
    })
  }

  // Large decorative circle — top right
  slide.addShape('ellipse' as pptxgen.SHAPE_NAME, {
    x: 9.5, y: -2.5, w: 6.0, h: 6.0,
    fill: { color: '1E4890', transparency: 65 },
    line: { type: 'none' },
  })
  slide.addShape('ellipse' as pptxgen.SHAPE_NAME, {
    x: 10.5, y: -1.2, w: 4.0, h: 4.0,
    fill: { color: '0060A8', transparency: 75 },
    line: { type: 'none' },
  })

  // Orange accent bar left edge
  slide.addShape('rect' as pptxgen.SHAPE_NAME, {
    x: 0, y: 0, w: 0.22, h: 7.5,
    fill: { color: C.orange },
    line: { type: 'none' },
  })

  // Teal accent stripe top
  slide.addShape('rect' as pptxgen.SHAPE_NAME, {
    x: 0.22, y: 0, w: 13.11, h: 0.1,
    fill: { color: C.teal },
    line: { type: 'none' },
  })

  // "提案簡報" pill tag
  slide.addShape('rect' as pptxgen.SHAPE_NAME, {
    x: 0.55, y: 0.85, w: 2.0, h: 0.44,
    fill: { color: C.orange },
    line: { type: 'none' },
  })
  slide.addText('提案簡報', {
    x: 0.55, y: 0.85, w: 2.0, h: 0.44,
    fontSize: 13,
    bold: true,
    fontFace: FONT,
    color: C.white,
    align: 'center',
    valign: 'middle',
  })

  // Industry tag
  if (industry) {
    slide.addShape('rect' as pptxgen.SHAPE_NAME, {
      x: 2.72, y: 0.85, w: 2.0, h: 0.44,
      fill: { color: C.accent, transparency: 20 },
      line: { type: 'none' },
    })
    slide.addText(industry, {
      x: 2.72, y: 0.85, w: 2.0, h: 0.44,
      fontSize: 12,
      fontFace: FONT,
      color: C.white,
      align: 'center',
      valign: 'middle',
    })
  }

  // Large company name
  slide.addText(companyName, {
    x: 0.5, y: 1.55, w: 8.0, h: 2.6,
    fontSize: companyName.length > 10 ? 52 : companyName.length > 6 ? 62 : 72,
    bold: true,
    fontFace: FONT,
    color: C.white,
    valign: 'middle',
  })

  // Accent line under company name
  slide.addShape('rect' as pptxgen.SHAPE_NAME, {
    x: 0.5, y: 4.28, w: 3.0, h: 0.07,
    fill: { color: C.orange },
    line: { type: 'none' },
  })
  slide.addShape('rect' as pptxgen.SHAPE_NAME, {
    x: 3.65, y: 4.28, w: 1.0, h: 0.07,
    fill: { color: C.teal },
    line: { type: 'none' },
  })

  // Subtitle
  slide.addText('數位行銷整合提案', {
    x: 0.5, y: 4.48, w: 7.0, h: 0.6,
    fontSize: 22,
    fontFace: FONT,
    color: '8AAECC',
    valign: 'middle',
  })

  // ── RIGHT: Info cards ────────────────────────────────────────────────────────
  const infoItems = [
    { label: '客戶', value: companyName },
    { label: '產業', value: industry || '數位行銷' },
    { label: '提案單位', value: '潮網科技' },
    { label: '文件性質', value: '機密' },
  ]

  infoItems.forEach((item, i) => {
    const y = 1.1 + i * 1.18
    const accentC = CARD_COLORS[i % CARD_COLORS.length]

    // Card (semi-transparent dark bg)
    slide.addShape('rect' as pptxgen.SHAPE_NAME, {
      x: 9.1, y, w: 3.9, h: 0.96,
      fill: { color: '0A2040', transparency: 30 },
      line: { color: accentC, width: 1, transparency: 40 },
    })
    // Top accent border
    slide.addShape('rect' as pptxgen.SHAPE_NAME, {
      x: 9.1, y, w: 3.9, h: 0.08,
      fill: { color: accentC },
      line: { type: 'none' },
    })
    // Icon circle
    slide.addShape('ellipse' as pptxgen.SHAPE_NAME, {
      x: 9.22, y: y + 0.2, w: 0.52, h: 0.52,
      fill: { color: accentC, transparency: 20 },
      line: { type: 'none' },
    })
    // Label
    slide.addText(item.label, {
      x: 9.88, y: y + 0.1, w: 3.0, h: 0.3,
      fontSize: 9,
      fontFace: FONT,
      color: '7AAAC8',
    })
    // Value
    slide.addText(item.value, {
      x: 9.88, y: y + 0.42, w: 3.0, h: 0.42,
      fontSize: 14,
      bold: true,
      fontFace: FONT,
      color: C.white,
    })
  })

  // Bottom Wavenet brand bar
  slide.addShape('rect' as pptxgen.SHAPE_NAME, {
    x: 0, y: 6.9, w: 13.33, h: 0.6,
    fill: { color: '0A1828', transparency: 20 },
    line: { type: 'none' },
  })
  slide.addText('潮網科技  Wavenet Technology  ·  數位行銷整合服務', {
    x: 0.4, y: 6.92, w: 12.5, h: 0.48,
    fontSize: 10,
    fontFace: FONT,
    color: '5A7A9A',
    italic: true,
    align: 'center',
    valign: 'middle',
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

  // Off-white background
  slide.addShape('rect' as pptxgen.SHAPE_NAME, {
    x: 0, y: 0, w: 13.33, h: 7.5,
    fill: { color: C.offWhite },
    line: { type: 'none' },
  })

  // Decorative background circles (Wavenet-style)
  addDecoCircles(slide as PptxSlide)

  // ── LEFT title zone (40% width) ─────────────────────────────────────────────

  // Thin orange left edge stripe
  slide.addShape('rect' as pptxgen.SHAPE_NAME, {
    x: 0, y: 0, w: 0.18, h: 7.05,
    fill: { color: C.orange },
    line: { type: 'none' },
  })

  // Navy header band top
  slide.addShape('rect' as pptxgen.SHAPE_NAME, {
    x: 0.18, y: 0, w: 13.15, h: 0.08,
    fill: { color: C.navy },
    line: { type: 'none' },
  })

  // Slide number pill
  slide.addShape('rect' as pptxgen.SHAPE_NAME, {
    x: 0.35, y: 0.22, w: 0.78, h: 0.38,
    fill: { color: C.navy },
    line: { type: 'none' },
  })
  slide.addText(`${String(idx).padStart(2, '0')}`, {
    x: 0.35, y: 0.22, w: 0.78, h: 0.38,
    fontSize: 12,
    bold: true,
    fontFace: FONT,
    color: C.white,
    align: 'center',
    valign: 'middle',
  })

  // Total count beside pill
  slide.addText(`/ ${total}`, {
    x: 1.2, y: 0.24, w: 0.6, h: 0.34,
    fontSize: 10,
    fontFace: FONT,
    color: C.muted,
    valign: 'middle',
  })

  // Giant title text — left 45% of slide, vertically centered
  const titleFontSize = title.length > 16 ? 32 : title.length > 10 ? 38 : 44
  slide.addText(title, {
    x: 0.35, y: 0.85, w: 5.5, h: 5.9,
    fontSize: titleFontSize,
    bold: true,
    fontFace: FONT,
    color: C.navy,
    valign: 'middle',
    breakLine: true,
  })

  // Orange accent dots below title area
  slide.addShape('ellipse' as pptxgen.SHAPE_NAME, {
    x: 0.35, y: 6.55, w: 0.22, h: 0.22,
    fill: { color: C.orange },
    line: { type: 'none' },
  })
  slide.addShape('ellipse' as pptxgen.SHAPE_NAME, {
    x: 0.66, y: 6.59, w: 0.15, h: 0.15,
    fill: { color: C.teal },
    line: { type: 'none' },
  })
  slide.addShape('ellipse' as pptxgen.SHAPE_NAME, {
    x: 0.92, y: 6.62, w: 0.11, h: 0.11,
    fill: { color: C.muted },
    line: { type: 'none' },
  })

  // Vertical divider between title and content
  slide.addShape('rect' as pptxgen.SHAPE_NAME, {
    x: 6.1, y: 0.2, w: 0.04, h: 6.6,
    fill: { color: 'D0DAEA' },
    line: { type: 'none' },
  })

  // ── RIGHT content zone (cards) ──────────────────────────────────────────────
  const cardX = 6.35
  const cardW = 6.7
  const totalCards = Math.min(bullets.length, 5)
  const cardH = totalCards > 0 ? Math.min(6.4 / totalCards, 1.18) : 1.15
  const startY = (7.05 - totalCards * cardH) / 2

  bullets.slice(0, 5).forEach((bullet, j) => {
    const y = startY + j * cardH
    const accentColor = CARD_COLORS[j % CARD_COLORS.length]

    // Card background
    slide.addShape('rect' as pptxgen.SHAPE_NAME, {
      x: cardX, y: y + 0.06, w: cardW, h: cardH - 0.12,
      fill: { color: C.white },
      line: { color: 'E2E8F0', width: 1 },
    })

    // Colored top accent border on card
    slide.addShape('rect' as pptxgen.SHAPE_NAME, {
      x: cardX, y: y + 0.06, w: cardW, h: 0.07,
      fill: { color: accentColor },
      line: { type: 'none' },
    })

    // Icon circle (navy bg, white "number")
    const circleY = y + (cardH - 0.16) / 2 - 0.22
    slide.addShape('ellipse' as pptxgen.SHAPE_NAME, {
      x: cardX + 0.22, y: circleY, w: 0.5, h: 0.5,
      fill: { color: C.navy },
      line: { type: 'none' },
    })
    slide.addText(`${j + 1}`, {
      x: cardX + 0.22, y: circleY, w: 0.5, h: 0.5,
      fontSize: 12,
      bold: true,
      fontFace: FONT,
      color: C.white,
      align: 'center',
      valign: 'middle',
    })

    // Bullet text
    slide.addText(bullet, {
      x: cardX + 0.9, y: y + 0.06, w: cardW - 1.05, h: cardH - 0.12,
      fontSize: 14,
      fontFace: FONT,
      color: C.text,
      valign: 'middle',
      breakLine: false,
    })
  })

  addFooter(slide as PptxSlide, companyName, title)
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
