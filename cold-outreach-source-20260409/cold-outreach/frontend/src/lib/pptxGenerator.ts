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
  const SW = 13.33, SH = 7.5
  const slide = pptx.addSlide()

  // ── LEFT SIDEBAR ────────────────────────────────────────────────────────────
  slide.addShape('rect' as pptxgen.SHAPE_NAME, {
    x: 0, y: 0, w: 4.15, h: SH,
    fill: { color: C.navy }, line: { type: 'none' },
  })
  slide.addShape('rect' as pptxgen.SHAPE_NAME, {
    x: 0, y: SH - 0.16, w: 4.15, h: 0.16,
    fill: { color: C.orange }, line: { type: 'none' },
  })
  // Decorative circle
  slide.addShape('ellipse' as pptxgen.SHAPE_NAME, {
    x: -0.7, y: -0.7, w: 2.2, h: 2.2,
    fill: { color: '253A6E', transparency: 55 }, line: { type: 'none' },
  })

  // Category label
  const LABELS = ['OVERVIEW', 'STRATEGY', 'ANALYSIS', 'EXECUTION', 'RESULTS', 'PROPOSAL']
  slide.addText(LABELS[(idx - 1) % LABELS.length], {
    x: 0.3, y: 0.4, w: 3.8, h: 0.38,
    fontSize: 10, bold: true, charSpacing: 2, fontFace: FONT, color: '7AAAC8',
  })
  // Separator
  slide.addShape('rect' as pptxgen.SHAPE_NAME, {
    x: 0.3, y: 0.86, w: 3.6, h: 0.04,
    fill: { color: C.orange }, line: { type: 'none' },
  })
  // Title
  const fs = title.length > 18 ? 20 : title.length > 12 ? 24 : 28
  slide.addText(title, {
    x: 0.3, y: 1.1, w: 3.7, h: 4.2,
    fontSize: fs, bold: true, fontFace: FONT,
    color: C.white, valign: 'middle', breakLine: true,
  })
  // Page counter
  slide.addText(`${String(idx).padStart(2, '0')} / ${String(total).padStart(2, '0')}`, {
    x: 0.3, y: SH - 0.52, w: 3.6, h: 0.36,
    fontSize: 11, bold: true, fontFace: FONT, color: '7AAAC8',
  })

  // ── RIGHT PANEL ─────────────────────────────────────────────────────────────
  slide.addShape('rect' as pptxgen.SHAPE_NAME, {
    x: 4.2, y: 0, w: SW - 4.2, h: SH,
    fill: { color: C.offWhite }, line: { type: 'none' },
  })

  const ICON_SYMBOLS = ['★', '◆', '▲', '●', '■']
  const ICON_COLORS  = [C.accent, C.teal, C.orange, 'E05C8B', '7C5CBF']

  const count   = Math.min(bullets.length, 5)
  const cardH   = Math.min(1.38, Math.max(0.9, (SH - 0.9) / count))
  const startY  = (SH - cardH * count) / 2

  bullets.slice(0, 5).forEach((bullet, j) => {
    const y     = startY + j * cardH
    const color = ICON_COLORS[j % ICON_COLORS.length]

    // Card
    slide.addShape('rect' as pptxgen.SHAPE_NAME, {
      x: 4.4, y: y + 0.07, w: SW - 4.6, h: cardH - 0.14,
      fill: { color: C.white }, line: { color: 'E2E8F0', width: 1 },
    })
    // Left accent strip
    slide.addShape('rect' as pptxgen.SHAPE_NAME, {
      x: 4.4, y: y + 0.07, w: 0.1, h: cardH - 0.14,
      fill: { color: color }, line: { type: 'none' },
    })
    // Icon circle
    const iconY = y + cardH / 2 - 0.3
    slide.addShape('ellipse' as pptxgen.SHAPE_NAME, {
      x: 4.63, y: iconY, w: 0.6, h: 0.6,
      fill: { color: color, transparency: 18 }, line: { type: 'none' },
    })
    slide.addText(ICON_SYMBOLS[j % ICON_SYMBOLS.length], {
      x: 4.63, y: iconY, w: 0.6, h: 0.6,
      fontSize: 15, fontFace: FONT, color: C.white, align: 'center', valign: 'middle',
    })
    // Bullet text
    slide.addText(bullet, {
      x: 5.36, y: y + 0.07, w: SW - 5.58, h: cardH - 0.14,
      fontSize: 13, fontFace: FONT, color: C.text, valign: 'middle', breakLine: true,
    })
    // Divider
    if (j < count - 1) {
      slide.addShape('rect' as pptxgen.SHAPE_NAME, {
        x: 4.5, y: y + cardH - 0.08, w: SW - 4.7, h: 0.02,
        fill: { color: C.deco }, line: { type: 'none' },
      })
    }
  })
}

// ── Company intro slides (P2-P10 from Wavenet reference PDF, pre-rendered as images) ──
async function addCompanyIntroSlides(pptx: pptxgen) {
  const origin = typeof window !== 'undefined' ? window.location.origin : ''
  for (let i = 2; i <= 10; i++) {
    const slide = pptx.addSlide()
    const pageNum = String(i).padStart(2, '0')
    slide.addImage({
      path: `${origin}/company-slides/page-${pageNum}.png`,
      x: 0, y: 0, w: 13.33, h: 7.5,
    })
  }
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
  await addCompanyIntroSlides(pptx)

  data.slides.forEach((sd, i) => {
    addContentSlide(pptx, i + 1, data.slides.length, sd.title, sd.bullets, data.company_name)
  })

  return await pptx.write({ outputType: 'blob' }) as Blob
}
