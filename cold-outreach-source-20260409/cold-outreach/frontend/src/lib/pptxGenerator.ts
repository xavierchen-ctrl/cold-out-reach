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
  navy:      '1A376C',
  accent:    '008CD7',
  accentLt:  'E8F4FB',
  white:     'FFFFFF',
  text:      '1A1A2E',
  subtext:   '555577',
  footerTxt: '99AABB',
  badgeNum:  '88AADD',
  coverSub:  '99BBEE',
  stripe:    '0070B8',
}

const FONT = 'Arial'

function addCoverSlide(pptx: pptxgen, companyName: string, industry: string) {
  const slide = pptx.addSlide()

  // Full dark-blue background
  slide.addShape(pptx.ShapeType.rect, {
    x: 0, y: 0, w: '100%', h: '100%',
    fill: { color: C.navy },
    line: { type: 'none' },
  })

  // Accent diagonal stripe (top-right decorative block)
  slide.addShape(pptx.ShapeType.rect, {
    x: 10.5, y: 0, w: 2.84, h: 2.5,
    fill: { color: C.accent },
    line: { type: 'none' },
  })

  // White top-left corner bar
  slide.addShape(pptx.ShapeType.rect, {
    x: 0, y: 0, w: 0.14, h: '100%',
    fill: { color: C.accent },
    line: { type: 'none' },
  })

  // Wavenet branding — top right
  slide.addText('潮網科技  Wavenet Technology', {
    x: 7.0, y: 0.2, w: 5.9, h: 0.45,
    fontSize: 11,
    fontFace: FONT,
    color: C.coverSub,
    align: 'right',
    italic: true,
  })

  // Main company name
  slide.addText(companyName, {
    x: 0.55, y: 2.4, w: 11.8, h: 1.8,
    fontSize: 48,
    bold: true,
    fontFace: FONT,
    color: C.white,
    breakLine: false,
  })

  // Subtitle
  slide.addText('數位行銷提案', {
    x: 0.55, y: 4.25, w: 8, h: 0.7,
    fontSize: 24,
    fontFace: FONT,
    color: C.coverSub,
  })

  // Industry tag (if available)
  if (industry) {
    slide.addShape(pptx.ShapeType.rect, {
      x: 0.55, y: 5.1, w: industry.length * 0.22 + 0.5, h: 0.42,
      fill: { color: C.accent },
      line: { type: 'none' },
    })
    slide.addText(industry, {
      x: 0.55, y: 5.1, w: industry.length * 0.22 + 0.5, h: 0.42,
      fontSize: 12,
      fontFace: FONT,
      color: C.white,
      align: 'center',
      valign: 'middle',
    })
  }

  // Bottom footer line
  slide.addShape(pptx.ShapeType.line, {
    x: 0.55, y: 6.9, w: 12.2, h: 0,
    line: { color: C.stripe, width: 1, dashType: 'solid' },
  })

  slide.addText('Confidential  ·  潮網科技業務團隊', {
    x: 0.55, y: 7.0, w: 12.2, h: 0.35,
    fontSize: 10,
    fontFace: FONT,
    color: C.footerTxt,
  })
}

function addContentSlide(
  pptx: pptxgen,
  idx: number,
  total: number,
  title: string,
  bullets: string[],
  companyName: string,
) {
  const slide = pptx.addSlide()

  // White background
  slide.addShape(pptx.ShapeType.rect, {
    x: 0, y: 0, w: '100%', h: '100%',
    fill: { color: C.white },
    line: { type: 'none' },
  })

  // Dark-blue header bar
  slide.addShape(pptx.ShapeType.rect, {
    x: 0, y: 0, w: '100%', h: 1.7,
    fill: { color: C.navy },
    line: { type: 'none' },
  })

  // Accent stripe on left edge
  slide.addShape(pptx.ShapeType.rect, {
    x: 0, y: 1.7, w: 0.1, h: 5.8,
    fill: { color: C.accent },
    line: { type: 'none' },
  })

  // Slide number badge
  slide.addText(`${idx} / ${total}`, {
    x: 11.8, y: 0.3, w: 1.3, h: 0.5,
    fontSize: 12,
    fontFace: FONT,
    color: C.badgeNum,
    align: 'right',
  })

  // Title
  slide.addText(title, {
    x: 0.4, y: 0.25, w: 11.3, h: 1.25,
    fontSize: 26,
    bold: true,
    fontFace: FONT,
    color: C.white,
    valign: 'middle',
  })

  // Accent dot below header
  slide.addShape(pptx.ShapeType.rect, {
    x: 0.4, y: 1.78, w: 0.5, h: 0.08,
    fill: { color: C.accent },
    line: { type: 'none' },
  })

  // Bullet items
  const bulletTop = 2.0
  const bulletH = (5.8 - bulletTop + 1.7 - 0.6) / Math.max(bullets.length, 1)
  const cappedH = Math.min(bulletH, 1.05)

  bullets.forEach((bullet, j) => {
    const yPos = bulletTop + j * cappedH

    // Bullet marker dot
    slide.addShape(pptx.ShapeType.ellipse, {
      x: 0.32, y: yPos + cappedH / 2 - 0.08,
      w: 0.15, h: 0.15,
      fill: { color: C.accent },
      line: { type: 'none' },
    })

    slide.addText(bullet, {
      x: 0.6, y: yPos, w: 12.3, h: cappedH,
      fontSize: 17,
      fontFace: FONT,
      color: C.text,
      valign: 'middle',
      breakLine: false,
    })
  })

  // Footer separator
  slide.addShape(pptx.ShapeType.line, {
    x: 0.4, y: 7.1, w: 12.5, h: 0,
    line: { color: 'DDDDEE', width: 1 },
  })

  // Footer text
  slide.addText(companyName + '  ·  潮網科技 Wavenet Technology', {
    x: 0.4, y: 7.15, w: 12.5, h: 0.3,
    fontSize: 9,
    fontFace: FONT,
    color: C.footerTxt,
  })
}

export async function generatePptxBlob(data: PptxContentResponse): Promise<Blob> {
  const pptx = new pptxgen()
  pptx.layout = 'LAYOUT_WIDE'  // 13.33" × 7.5"
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
