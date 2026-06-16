/**
 * 將 PDF 前 10 頁（封面 + 公司介紹 P2-P10）轉為圖片
 * 嵌入 PPTX，後段接 P11-P18 客戶專屬投影片
 */

import { createCanvas } from '@napi-rs/canvas'
import * as pdfjsLib from 'pdfjs-dist/legacy/build/pdf.mjs'
import pptxgen from 'pptxgenjs'
import { writeFileSync, mkdirSync, existsSync } from 'fs'
import { resolve, join } from 'path'

const PDF_PATH = 'C:\\Users\\eric1\\Downloads\\drive-download-20260602T080101Z-3-001\\潮網科技_全聯小時達數位媒體提案_0318_V1.pdf'
const CLIENT_NAME = '全聯福利中心'
const PROPOSAL_TITLE = 'PXGo 小時達首購會員成長媒體提案'

const COMPANY_INTRO_PAGES = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10] // 1-indexed: cover + p2-p10
const SCALE = 2.0  // higher = better quality

const W = 13.33
const H = 7.5
const C = {
  navy:'1E3A6E', blue:'2B5CB7', blueLt:'4A90D9', red:'E63946',
  white:'FFFFFF', offWhite:'F5F7FA', text:'1A1A2E', subtext:'4A5568',
  muted:'8A9BB0', border:'D0DAEA', green:'059669', purple:'7C3AED', amber:'D97706',
}
const FONT = 'Arial'

// ── Step 1: PDF → PNG images ──────────────────────────────────────────────
console.log('正在將 PDF 頁面轉換為圖片...')

const tmpDir = resolve('tmp-pdf-pages')
if (!existsSync(tmpDir)) mkdirSync(tmpDir)

const pdfData = new Uint8Array(
  (await import('fs')).default.readFileSync(PDF_PATH)
)

const loadingTask = pdfjsLib.getDocument({
  data: pdfData,
  verbosity: 0,
})
const pdf = await loadingTask.promise
console.log(`PDF 共 ${pdf.numPages} 頁`)

const pagePaths = []

for (const pageNum of COMPANY_INTRO_PAGES) {
  if (pageNum > pdf.numPages) break

  const page = await pdf.getPage(pageNum)
  const viewport = page.getViewport({ scale: SCALE })

  const canvas = createCanvas(viewport.width, viewport.height)
  const ctx = canvas.getContext('2d')

  // white background
  ctx.fillStyle = '#FFFFFF'
  ctx.fillRect(0, 0, viewport.width, viewport.height)

  await page.render({
    canvasContext: ctx,
    viewport,
  }).promise

  const pngBuffer = canvas.toBuffer('image/png')
  const pngPath = join(tmpDir, `page-${String(pageNum).padStart(2,'0')}.png`)
  writeFileSync(pngPath, pngBuffer)
  pagePaths.push(pngPath)
  console.log(`  ✓ Page ${pageNum} → ${pngPath}`)
}

// ── Step 2: Build PPTX ────────────────────────────────────────────────────
console.log('\n正在建立 PPTX...')

const pptx = new pptxgen()
pptx.layout  = 'LAYOUT_WIDE'
pptx.company = '潮網科技'
pptx.title   = `${CLIENT_NAME} ${PROPOSAL_TITLE}`

// Embed each PDF page as a full-slide image
for (const imgPath of pagePaths) {
  const s = pptx.addSlide()
  s.addImage({ path: imgPath, x:0, y:0, w:W, h:H })
}

// ── Step 3: Client slides P11–P18 ─────────────────────────────────────────

function footer(s) {
  s.addText('Wavenet Technology Confidential', { x:0, y:H-0.3, w:W, h:0.28,
    fontSize:9, fontFace:FONT, color:C.muted, align:'center' })
}

function sidebarSlide(label, title, subtitle, pageNum, contentFn) {
  const s = pptx.addSlide()
  s.addShape('rect', { x:0, y:0, w:4.55, h:H, fill:{color:C.navy}, line:{type:'none'} })
  s.addShape('rect', { x:0, y:H-0.14, w:4.55, h:0.14, fill:{color:C.red}, line:{type:'none'} })
  s.addShape('ellipse', { x:-0.6, y:-0.6, w:2.2, h:2.2, fill:{color:C.blue, transparency:80}, line:{type:'none'} })
  s.addText(label, { x:0.3, y:0.42, w:4.0, h:0.38,
    fontSize:10, bold:true, charSpacing:2, fontFace:FONT, color:'8AAFD4' })
  s.addShape('rect', { x:0.3, y:0.88, w:3.9, h:0.04, fill:{color:C.red}, line:{type:'none'} })
  const lines = title.split('\n')
  lines.forEach((line, li) => {
    const isAccent = ['新客','策略','KPI','成本','時程'].some(k => line.includes(k))
    s.addText(line, { x:0.3, y:1.1+li*0.78, w:4.0, h:0.72,
      fontSize:lines.length > 3 ? 20 : 24, bold:true, fontFace:FONT,
      color: isAccent ? C.red : C.white, valign:'middle' })
  })
  s.addText(subtitle, { x:0.3, y:H-1.05, w:3.95, h:0.82,
    fontSize:11, fontFace:FONT, color:'8AAFD4', valign:'middle', breakLine:true })
  s.addText(pageNum, { x:0.3, y:H-0.52, w:1.0, h:0.36,
    fontSize:11, bold:true, fontFace:FONT, color:'8AAFD4' })
  s.addShape('rect', { x:4.6, y:0, w:W-4.6, h:H, fill:{color:C.white}, line:{type:'none'} })
  contentFn(s)
  return s
}

function bulletList(s, bullets, topY) {
  const bX = 5.0, bW = W-bX-0.3
  const itemH = Math.min((H-topY-0.4)/bullets.length, 1.3)
  bullets.forEach((b, j) => {
    const y = topY+j*itemH
    s.addShape('rect', { x:bX, y:y+itemH/2-0.03, w:0.28, h:0.06, fill:{color:C.red}, line:{type:'none'} })
    s.addText(b, { x:bX+0.38, y, w:bW-0.38, h:itemH,
      fontSize:13, fontFace:FONT, color:C.text, valign:'middle', breakLine:true })
    if (j < bullets.length-1)
      s.addShape('rect', { x:bX, y:y+itemH-0.04, w:bW, h:0.02, fill:{color:C.border}, line:{type:'none'} })
  })
}

// P11 - PROPOSAL OBJECTIVE (icon bullets)
sidebarSlide('PROPOSAL OBJECTIVE',
  `本次提案\n要解決的\n不是訂單不夠\n而是${CLIENT_NAME}的\n新客不夠`,
  '從追求全站轉單，升級為首購會員成長策略', '11',
  s => {
    const bullets = [
      '核心目標重定義：不再只追求全站訂單或整體ROAS，回歸最在意的 KPI——首次加入會員並完成購買的新客數量',
      '產品力優勢：最快30分鐘送達 / 外送店內價無價差 / 天天享免運 / 生鮮日用品齊全',
      '攔截失敗：有需求但未被媒體接住 → 流量進站未轉成首購 → 須重建完整轉換漏斗',
    ]
    const ICONS = ['◆', '▲', '●']
    const ICON_COLORS = [C.blue, C.red, C.amber]
    bullets.forEach((b, i) => {
      const y = 0.55 + i * 2.0
      s.addShape('ellipse', { x:4.85, y:y+0.42, w:0.76, h:0.76, fill:{color:ICON_COLORS[i]}, line:{type:'none'} })
      s.addText(ICONS[i], { x:4.85, y:y+0.42, w:0.76, h:0.76, fontSize:20, fontFace:FONT, color:C.white, align:'center', valign:'middle' })
      s.addText(b, { x:5.76, y:y, w:W-5.96, h:1.85, fontSize:12.5, fontFace:FONT, color:C.text, valign:'middle', breakLine:true })
      if (i < 2) s.addShape('rect', { x:4.8, y:y+1.85, w:W-5.0, h:0.02, fill:{color:C.border}, line:{type:'none'} })
    })
  })

// P12 - Full-width 3-column problem cards
;(() => {
  const s = pptx.addSlide()
  const problems = [
    { no:'01', title:'新客獲取成本偏高', desc:'首次購買轉換率僅 3.2%，遠低於行業平均 8%。攔截需求的廣告觸及率不足，大量潛在首購用戶流失。', color:C.red },
    { no:'02', title:'媒體投放缺乏整合', desc:'各媒體各自為政，無跨渠道數據串連，無法判別哪個媒體真正促成首購，導致預算配置失準。', color:C.amber },
    { no:'03', title:'轉換漏斗數據盲區', desc:'站外廣告點擊到站內行為追蹤斷鏈，無法優化「點擊→加購→結帳」的每一段損耗。', color:C.purple },
  ]
  s.addShape('rect', { x:0, y:0, w:W, h:H, fill:{color:C.offWhite}, line:{type:'none'} })
  s.addShape('rect', { x:0, y:0, w:W, h:1.18, fill:{color:C.navy}, line:{type:'none'} })
  s.addShape('rect', { x:0, y:1.18, w:W, h:0.07, fill:{color:C.red}, line:{type:'none'} })
  s.addShape('ellipse', { x:-0.5, y:-0.5, w:2.0, h:2.0, fill:{color:C.blue, transparency:78}, line:{type:'none'} })
  s.addText('DIAGNOSIS', { x:0.45, y:0.18, w:5, h:0.38, fontSize:10, bold:true, charSpacing:3, fontFace:FONT, color:'8AAFD4' })
  s.addText('現況三大課題診斷', { x:0.45, y:0.53, w:7, h:0.56, fontSize:26, bold:true, fontFace:FONT, color:C.white })
  s.addText('找出制約成長的瓶頸，才能對症下藥', { x:7.2, y:0.62, w:5.8, h:0.38, fontSize:12, fontFace:FONT, color:'8AAFD4', align:'right' })
  s.addText('12', { x:W-0.75, y:0.2, w:0.5, h:0.3, fontSize:11, bold:true, fontFace:FONT, color:'8AAFD4', align:'right' })
  const colW = (W - 0.65) / 3 - 0.12
  problems.forEach((p, i) => {
    const cx = 0.33 + i * (colW + 0.12)
    const cy = 1.33, ch = H - 1.33 - 0.35
    s.addShape('rect', { x:cx, y:cy, w:colW, h:ch, fill:{color:C.white}, line:{color:p.color, width:1} })
    s.addShape('rect', { x:cx, y:cy, w:colW, h:0.08, fill:{color:p.color}, line:{type:'none'} })
    s.addShape('ellipse', { x:cx+colW/2-0.75, y:cy+0.35, w:1.5, h:1.5, fill:{color:p.color, transparency:10}, line:{type:'none'} })
    s.addText('!', { x:cx+colW/2-0.75, y:cy+0.35, w:1.5, h:1.5, fontSize:52, bold:true, fontFace:FONT, color:C.white, align:'center', valign:'middle' })
    s.addText(p.no, { x:cx+colW-0.62, y:cy+0.15, w:0.5, h:0.3, fontSize:11, bold:true, fontFace:FONT, color:p.color, align:'right' })
    s.addText(p.title, { x:cx+0.12, y:cy+2.02, w:colW-0.24, h:0.65, fontSize:15, bold:true, fontFace:FONT, color:C.navy, align:'center', breakLine:true })
    s.addShape('rect', { x:cx+colW/2-0.8, y:cy+2.74, w:1.6, h:0.05, fill:{color:p.color, transparency:40}, line:{type:'none'} })
    s.addText(p.desc, { x:cx+0.18, y:cy+2.86, w:colW-0.36, h:2.8, fontSize:11, fontFace:FONT, color:C.subtext, align:'center', valign:'top', breakLine:true })
  })
  footer(s)
})()

// P13 - Full-width 3-column persona cards
;(() => {
  const s = pptx.addSlide()
  const tas = [
    { no:'TA1', label:'都市便利型媽媽', age:'25–38歲', traits:'雙薪家庭・外送重度用戶・重視CP值', trigger:'下班前30分鐘搜尋晚餐食材', color:'2B5CB7' },
    { no:'TA2', label:'都市上班族',     age:'22–35歲', traits:'午休訂便當・週末懶人購物・慣用App', trigger:'午休時段、週末前一天高需求',     color:'059669' },
    { no:'TA3', label:'銀髮樂活族',    age:'55–70歲', traits:'重視生鮮品質・不想出門購物・信賴全聯', trigger:'早上10–11點瀏覽需求最高',  color:'D97706' },
  ]
  s.addShape('rect', { x:0, y:0, w:W, h:H, fill:{color:C.offWhite}, line:{type:'none'} })
  s.addShape('rect', { x:0, y:0, w:W, h:1.18, fill:{color:C.navy}, line:{type:'none'} })
  s.addShape('rect', { x:0, y:1.18, w:W, h:0.07, fill:{color:'2B9AB7'}, line:{type:'none'} })
  s.addShape('ellipse', { x:W-1.5, y:-0.5, w:2.0, h:2.0, fill:{color:C.blue, transparency:78}, line:{type:'none'} })
  s.addText('TARGET AUDIENCE', { x:0.45, y:0.18, w:7, h:0.38, fontSize:10, bold:true, charSpacing:3, fontFace:FONT, color:'8AAFD4' })
  s.addText('三大核心 TA 受眾定義', { x:0.45, y:0.53, w:7, h:0.56, fontSize:26, bold:true, fontFace:FONT, color:C.white })
  s.addText('精準分群，讓每一分廣告預算接住最有價值的新客', { x:6.5, y:0.62, w:6.5, h:0.38, fontSize:11.5, fontFace:FONT, color:'8AAFD4', align:'right' })
  s.addText('13', { x:W-0.75, y:0.2, w:0.5, h:0.3, fontSize:11, bold:true, fontFace:FONT, color:'8AAFD4', align:'right' })
  const colW = (W - 0.65) / 3 - 0.12
  tas.forEach((ta, i) => {
    const cx = 0.33 + i * (colW + 0.12)
    const cy = 1.33, ch = H - 1.33 - 0.35
    s.addShape('rect', { x:cx, y:cy, w:colW, h:ch, fill:{color:C.white}, line:{color:ta.color, width:1} })
    s.addShape('rect', { x:cx, y:cy, w:colW, h:0.62, fill:{color:ta.color}, line:{type:'none'} })
    s.addText(ta.no, { x:cx+0.15, y:cy+0.14, w:0.85, h:0.36, fontSize:14, bold:true, fontFace:FONT, color:C.white })
    s.addShape('ellipse', { x:cx+colW/2-0.75, y:cy+0.75, w:1.5, h:1.5, fill:{color:ta.color, transparency:12}, line:{type:'none'} })
    s.addShape('ellipse', { x:cx+colW/2-0.25, y:cy+0.9,  w:0.5, h:0.5, fill:{color:ta.color}, line:{type:'none'} })
    s.addShape('rect',    { x:cx+colW/2-0.32, y:cy+1.42, w:0.64, h:0.72, fill:{color:ta.color}, line:{type:'none'} })
    s.addText(ta.label, { x:cx+0.1, y:cy+2.38, w:colW-0.2, h:0.58, fontSize:15, bold:true, fontFace:FONT, color:C.navy, align:'center' })
    s.addShape('rect', { x:cx+colW/2-0.9, y:cy+3.02, w:1.8, h:0.05, fill:{color:ta.color, transparency:35}, line:{type:'none'} })
    s.addText(`年齡：${ta.age}`, { x:cx+0.12, y:cy+3.12, w:colW-0.24, h:0.36, fontSize:11.5, fontFace:FONT, color:C.subtext, align:'center' })
    s.addText(ta.traits, { x:cx+0.12, y:cy+3.52, w:colW-0.24, h:0.58, fontSize:10.5, fontFace:FONT, color:C.subtext, align:'center', breakLine:true })
    s.addShape('rect', { x:cx+0.18, y:cy+4.22, w:colW-0.36, h:0.5, fill:{color:ta.color, transparency:85}, line:{type:'none'} })
    s.addText(`觸發：${ta.trigger}`, { x:cx+0.22, y:cy+4.22, w:colW-0.44, h:0.5, fontSize:10, bold:true, fontFace:FONT, color:ta.color, align:'center', valign:'middle', breakLine:true })
  })
  footer(s)
})()

// P14 - CORE STRATEGY with visual funnel
sidebarSlide('CORE STRATEGY', '首購成長\n三層媒體\n攔截策略', '不是多投廣告，而是把需求分三段打', '14', s => {
  const layers = [
    { no:'LAYER 01', title:'攔截需求', media:'Google Search', pct:'30%', lw:8.0,  color:C.blue },
    { no:'LAYER 02', title:'創造需求', media:'Meta FB / IG',  pct:'30%', lw:6.6,  color:'3B5998' },
    { no:'LAYER 03', title:'追擊轉換', media:'Pmax + Criteo', pct:'40%', lw:5.35, color:C.green },
  ]
  const centerX = 4.65 + (W - 4.65) / 2
  layers.forEach((ly, i) => {
    const lx = centerX - ly.lw / 2
    const ly_y = 0.55 + i * 2.1
    s.addShape('rect', { x:lx, y:ly_y, w:ly.lw, h:1.85, fill:{color:ly.color}, line:{type:'none'} })
    s.addShape('rect', { x:lx, y:ly_y, w:ly.lw, h:0.07, fill:{color:C.white, transparency:60}, line:{type:'none'} })
    s.addShape('rect', { x:lx+0.12, y:ly_y+0.18, w:1.5, h:0.4, fill:{color:C.white, transparency:25}, line:{type:'none'} })
    s.addText(ly.no, { x:lx+0.12, y:ly_y+0.18, w:1.5, h:0.4, fontSize:9, bold:true, fontFace:FONT, color:C.white, align:'center', valign:'middle' })
    s.addText(ly.title, { x:lx+1.78, y:ly_y+0.1, w:3.8, h:0.58, fontSize:19, bold:true, fontFace:FONT, color:C.white })
    s.addText(ly.media, { x:lx+1.78, y:ly_y+0.68, w:4.5, h:0.38, fontSize:13, fontFace:FONT, color:C.white })
    s.addShape('ellipse', { x:lx+ly.lw-1.1, y:ly_y+0.52, w:0.82, h:0.82, fill:{color:C.white, transparency:22}, line:{type:'none'} })
    s.addText(ly.pct, { x:lx+ly.lw-1.1, y:ly_y+0.52, w:0.82, h:0.82, fontSize:16, bold:true, fontFace:FONT, color:C.white, align:'center', valign:'middle' })
    if (i < 2) {
      s.addShape('rect', { x:centerX-0.35, y:ly_y+1.85, w:0.7, h:0.25, fill:{color:C.border}, line:{type:'none'} })
      s.addText('▼', { x:centerX-0.35, y:ly_y+1.85, w:0.7, h:0.25, fontSize:10, fontFace:FONT, color:C.navy, align:'center', valign:'middle' })
    }
  })
})

// P15
sidebarSlide('BUDGET ALLOCATION', '9個月總\n預算配置表\n(4月–12月)', '總預算規模 NT$ 9,000,000', '15', s => {
  const budgets = [
    { media:'Google Search',  budget:'NT$ 2,337,662', pct:30, color:C.blue },
    { media:'Meta Ads (FB+IG)', budget:'NT$ 2,337,662', pct:30, color:'3B5998' },
    { media:'Google Pmax',    budget:'NT$ 1,948,052', pct:25, color:C.blueLt },
    { media:'Criteo GO',      budget:'NT$ 1,168,831', pct:15, color:C.amber },
  ]
  const tx = 4.75
  s.addShape('rect', { x:tx, y:0.5, w:8.35, h:0.45, fill:{color:C.navy}, line:{type:'none'} })
  s.addText('媒體', { x:tx+0.1, y:0.5, w:3.5, h:0.45, fontSize:11, bold:true, fontFace:FONT, color:C.white, valign:'middle' })
  s.addText('預算', { x:tx+3.6, y:0.5, w:2.5, h:0.45, fontSize:11, bold:true, fontFace:FONT, color:C.white, align:'center', valign:'middle' })
  s.addText('佔比', { x:tx+6.2, y:0.5, w:2.0, h:0.45, fontSize:11, bold:true, fontFace:FONT, color:C.white, align:'center', valign:'middle' })
  budgets.forEach((b, i) => {
    const by = 1.05+i*0.95
    const bg = i%2===0 ? C.white : C.offWhite
    s.addShape('rect', { x:tx, y:by, w:8.35, h:0.88, fill:{color:bg}, line:{color:C.border, width:0.5} })
    s.addShape('rect', { x:tx, y:by, w:0.1, h:0.88, fill:{color:b.color}, line:{type:'none'} })
    s.addText(b.media, { x:tx+0.2, y:by, w:3.3, h:0.88, fontSize:14, bold:true, fontFace:FONT, color:C.navy, valign:'middle' })
    s.addText(b.budget, { x:tx+3.6, y:by, w:2.5, h:0.88, fontSize:13, fontFace:FONT, color:C.subtext, align:'center', valign:'middle' })
    const bw = (b.pct/35)*2.0
    s.addShape('rect', { x:tx+6.15, y:by+0.32, w:2.0, h:0.24, fill:{color:C.border}, line:{type:'none'} })
    s.addShape('rect', { x:tx+6.15, y:by+0.32, w:bw,  h:0.24, fill:{color:b.color}, line:{type:'none'} })
    s.addText(`${b.pct}%`, { x:tx+8.2, y:by, w:0.8, h:0.88, fontSize:13, bold:true, fontFace:FONT, color:b.color, valign:'middle' })
  })
  s.addShape('rect', { x:tx, y:4.9, w:8.35, h:0.5, fill:{color:C.navy, transparency:10}, line:{color:C.navy, width:1} })
  s.addText('服務費(10%) + 稅(5%) 另計  →  含稅總計 NT$ 9,000,000', {
    x:tx+0.15, y:4.9, w:8.0, h:0.5, fontSize:12, bold:true, fontFace:FONT, color:C.navy, valign:'middle' })
  s.addText('* 各月份預算可依成效彈性調配，保留 15% 機動預算', {
    x:tx+0.1, y:5.55, w:8.2, h:0.4, fontSize:10, fontFace:FONT, color:C.muted, italic:true })
})

// P16
sidebarSlide('KPI TARGETS', '成效 KPI\n驗收指標', '清晰可量測的目標，確保每一分錢都有回報', '16', s => {
  const kpis = [
    { label:'首購新客數/月', target:'50,000', unit:'人',  color:C.blue,   sub:'較目前+120%' },
    { label:'首購轉換率',    target:'15',     unit:'%',   color:C.green,  sub:'目前 3.2% → 目標 15%' },
    { label:'整體 ROAS',     target:'3.5',    unit:'x',   color:C.amber,  sub:'月均維持 3.5x 以上' },
    { label:'首購 CPA 成本', target:'150',    unit:'NT$', color:C.purple, sub:'平均每位新客成本上限' },
  ]
  kpis.forEach((kpi, i) => {
    const col = i%2, row = Math.floor(i/2)
    const kx = 4.85+col*4.15, ky = 0.55+row*3.0
    s.addShape('rect', { x:kx, y:ky, w:3.85, h:2.7, fill:{color:kpi.color, transparency:88}, line:{color:kpi.color, width:1.5} })
    s.addShape('rect', { x:kx, y:ky, w:3.85, h:0.08, fill:{color:kpi.color}, line:{type:'none'} })
    s.addText(kpi.label, { x:kx+0.15, y:ky+0.2, w:3.55, h:0.6, fontSize:14, bold:true, fontFace:FONT, color:C.navy, align:'center' })
    s.addText(kpi.target, { x:kx, y:ky+0.85, w:3.85, h:1.1, fontSize:52, bold:true, fontFace:FONT, color:kpi.color, align:'center', valign:'middle' })
    s.addText(kpi.unit, { x:kx+2.8, y:ky+0.85, w:0.9, h:0.8, fontSize:16, bold:true, fontFace:FONT, color:kpi.color, valign:'bottom' })
    s.addText(kpi.sub, { x:kx+0.1, y:ky+2.22, w:3.65, h:0.38, fontSize:10, fontFace:FONT, color:C.subtext, align:'center' })
  })
})

// P17 - Full-width horizontal timeline
;(() => {
  const s = pptx.addSlide()
  const phases = [
    { phase:'Phase 1', period:'4–5月', label:'測試期', color:C.blue,
      items:['建立廣告帳戶架構，完成代碼追蹤串接','上線 Google Search + Meta 基礎受眾測試','A/B 測試素材與受眾，找出最優解'] },
    { phase:'Phase 2', period:'6–9月', label:'放量期', color:C.green,
      items:['加入 Pmax + Criteo 強化再行銷','基於 P1 數據優化受眾與出價策略','每月 Finding 報告，滾動調整預算'] },
    { phase:'Phase 3', period:'10–12月', label:'衝刺期', color:C.red,
      items:['雙11、雙12購物檔期重兵投入','全渠道整合，打造節慶首購高峰','Q4 成效總結 + 隔年策略提案'] },
  ]
  s.addShape('rect', { x:0, y:0, w:W, h:H, fill:{color:C.offWhite}, line:{type:'none'} })
  s.addShape('rect', { x:0, y:0, w:W, h:1.18, fill:{color:C.navy}, line:{type:'none'} })
  s.addShape('rect', { x:0, y:1.18, w:W, h:0.07, fill:{color:C.green}, line:{type:'none'} })
  s.addShape('ellipse', { x:-0.5, y:-0.5, w:2.0, h:2.0, fill:{color:C.blue, transparency:78}, line:{type:'none'} })
  s.addText('TIMELINE', { x:0.45, y:0.18, w:5, h:0.38, fontSize:10, bold:true, charSpacing:3, fontFace:FONT, color:'8AAFD4' })
  s.addText('9個月執行時程規劃', { x:0.45, y:0.53, w:7, h:0.56, fontSize:26, bold:true, fontFace:FONT, color:C.white })
  s.addText('分三階段，穩步達成首購會員成長目標', { x:7.2, y:0.62, w:5.8, h:0.38, fontSize:12, fontFace:FONT, color:'8AAFD4', align:'right' })
  s.addText('17', { x:W-0.75, y:0.2, w:0.5, h:0.3, fontSize:11, bold:true, fontFace:FONT, color:'8AAFD4', align:'right' })
  const lineY = 2.55
  s.addShape('rect', { x:0.5, y:lineY, w:W-1.0, h:0.06, fill:{color:C.border}, line:{type:'none'} })
  const colW = (W - 0.65) / 3 - 0.12
  phases.forEach((ph, i) => {
    const cx = 0.33 + i * (colW + 0.12)
    s.addShape('rect', { x:cx, y:1.33, w:colW, h:0.95, fill:{color:ph.color}, line:{type:'none'} })
    s.addShape('rect', { x:cx, y:1.33, w:colW, h:0.07, fill:{color:C.white, transparency:50}, line:{type:'none'} })
    s.addText(ph.phase, { x:cx+0.15, y:1.37, w:2.5, h:0.36, fontSize:11, bold:true, fontFace:FONT, color:C.white })
    s.addText(ph.period, { x:cx+0.15, y:1.74, w:colW-0.3, h:0.5, fontSize:19, bold:true, fontFace:FONT, color:C.white })
    s.addShape('ellipse', { x:cx+colW/2-0.27, y:lineY-0.27, w:0.54, h:0.54, fill:{color:ph.color}, line:{color:C.white, width:2} })
    s.addShape('rect', { x:cx, y:2.75, w:colW, h:H-2.75-0.35, fill:{color:C.white}, line:{color:ph.color, width:1} })
    s.addShape('rect', { x:cx, y:2.75, w:colW, h:0.07, fill:{color:ph.color}, line:{type:'none'} })
    s.addText(ph.label, { x:cx+0.15, y:2.86, w:colW-0.3, h:0.52, fontSize:17, bold:true, fontFace:FONT, color:ph.color })
    ph.items.forEach((item, j) => {
      const iy = 3.5 + j * 1.08
      s.addShape('ellipse', { x:cx+0.18, y:iy+0.2, w:0.26, h:0.26, fill:{color:ph.color, transparency:20}, line:{type:'none'} })
      s.addText(item, { x:cx+0.52, y:iy, w:colW-0.68, h:0.95, fontSize:11, fontFace:FONT, color:C.subtext, valign:'middle', breakLine:true })
    })
  })
  footer(s)
})()

// P18 - Full-width 5-step horizontal flow
;(() => {
  const s = pptx.addSlide()
  const steps = [
    { no:'01', title:'合約簽署 &\n帳戶開通', desc:'確認預算規模、服務條款，完成廣告帳戶授權與BM串接', days:'Day 1–3',   color:C.navy },
    { no:'02', title:'代碼追蹤\n建置',       desc:'GA4、Meta Pixel、Criteo Tag 全部到位，確保首購事件正確記錄', days:'Day 4–7',   color:C.blue },
    { no:'03', title:'素材準備 &\n審核',      desc:'提供品牌素材，潮網製作廣告圖文/影音，通過各平台審核', days:'Day 5–10',  color:'2E86AB' },
    { no:'04', title:'廣告\n上線',           desc:'Google Search & Meta 率先上線，開始累積初期首購轉換數據', days:'Day 11–14', color:C.green },
    { no:'05', title:'首次報告 &\n優化',      desc:'上線兩週後召開首次成效會議，確認數據方向，啟動優化循環', days:'Day 21',    color:C.red },
  ]
  s.addShape('rect', { x:0, y:0, w:W, h:H, fill:{color:C.offWhite}, line:{type:'none'} })
  s.addShape('rect', { x:0, y:0, w:W, h:1.18, fill:{color:C.navy}, line:{type:'none'} })
  s.addShape('rect', { x:0, y:1.18, w:W, h:0.07, fill:{color:C.red}, line:{type:'none'} })
  s.addShape('ellipse', { x:W-1.5, y:-0.5, w:2.0, h:2.0, fill:{color:C.blue, transparency:78}, line:{type:'none'} })
  s.addText('NEXT STEPS', { x:0.45, y:0.18, w:5, h:0.38, fontSize:10, bold:true, charSpacing:3, fontFace:FONT, color:'8AAFD4' })
  s.addText('合作啟動五步驟', { x:0.45, y:0.53, w:7, h:0.56, fontSize:26, bold:true, fontFace:FONT, color:C.white })
  s.addText('最快兩週內讓廣告上線，開始累積首購數據', { x:7.0, y:0.62, w:6.0, h:0.38, fontSize:12, fontFace:FONT, color:'8AAFD4', align:'right' })
  s.addText('18', { x:W-0.75, y:0.2, w:0.5, h:0.3, fontSize:11, bold:true, fontFace:FONT, color:'8AAFD4', align:'right' })
  const stW = (W - 0.55) / 5 - 0.1
  steps.forEach((st, i) => {
    const sx = 0.28 + i * (stW + 0.1)
    const sy = 1.35, sh = H - 1.35 - 0.35
    s.addShape('rect', { x:sx, y:sy, w:stW, h:sh, fill:{color:C.white}, line:{color:st.color, width:1.5} })
    s.addShape('rect', { x:sx, y:sy, w:stW, h:0.62, fill:{color:st.color}, line:{type:'none'} })
    s.addShape('ellipse', { x:sx+stW/2-0.38, y:sy+0.1, w:0.76, h:0.76, fill:{color:C.white}, line:{type:'none'} })
    s.addText(st.no, { x:sx+stW/2-0.38, y:sy+0.1, w:0.76, h:0.76, fontSize:17, bold:true, fontFace:FONT, color:st.color, align:'center', valign:'middle' })
    s.addText(st.title, { x:sx+0.1, y:sy+0.82, w:stW-0.2, h:0.88, fontSize:13, bold:true, fontFace:FONT, color:C.navy, align:'center', breakLine:true })
    s.addShape('rect', { x:sx+0.15, y:sy+1.78, w:stW-0.3, h:0.04, fill:{color:st.color, transparency:50}, line:{type:'none'} })
    s.addText(st.desc, { x:sx+0.12, y:sy+1.88, w:stW-0.24, h:3.1, fontSize:10.5, fontFace:FONT, color:C.subtext, align:'center', valign:'top', breakLine:true })
    s.addShape('rect', { x:sx+0.15, y:sy+sh-0.6, w:stW-0.3, h:0.42, fill:{color:st.color, transparency:85}, line:{type:'none'} })
    s.addText(st.days, { x:sx+0.15, y:sy+sh-0.6, w:stW-0.3, h:0.42, fontSize:10, bold:true, fontFace:FONT, color:st.color, align:'center', valign:'middle' })
    if (i < 4)
      s.addText('▶', { x:sx+stW+0.01, y:sy+sh/2-0.2, w:0.1, h:0.4, fontSize:10, fontFace:FONT, color:st.color, align:'center', valign:'middle' })
  })
  footer(s)
})()

// ── Output ─────────────────────────────────────────────────────────────────
const outputPath = resolve('test-output-full.pptx')
const buffer = await pptx.write({ outputType: 'nodebuffer' })
writeFileSync(outputPath, buffer)

console.log(`\n=== 產出完成 ===`)
console.log(`客戶：${CLIENT_NAME}`)
console.log(`檔案：${outputPath}`)
console.log(`投影片：${pagePaths.length + 8} 張（PDF原頁面 ${pagePaths.length} 張 + 客戶專屬 8 張）`)
