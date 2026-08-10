/**
 * ================================================================
 * 「隐盾」本地 OCR（端侧优先 / 隐私卖点）
 * ================================================================
 * 用 Tesseract.js WASM 在浏览器端跑 OCR，图片不出设备。
 * 识别结果转换为与云端 /api/ocr 相同的区域结构，复用下游脱敏流程。
 *
 * 纯函数（linesToRegions / classifyText）与 tesseract 调用分离，
 * 便于单测且不污染 node 测试环境。
 */

import { classifyText, type SensitiveMatch } from './sensitivePatterns'

export interface LocalOCRRegion {
  bbox: number[][]
  rect: { x: number; y: number; w: number; h: number }
  text: string
  confidence: number
  sensitive: SensitiveMatch | null
}

interface TesseractLine {
  bbox?: { x0: number; y0: number; x1: number; y1: number }
  text?: string
  confidence?: number
}

interface TesseractWord {
  bbox?: { x0: number; y0: number; x1: number; y1: number }
  text?: string
  confidence?: number
}

/** 过滤无意义词条：表格边框/纯符号（| [| —— …）等不应成为脱敏区域 */
export function isMeaningfulText(text: string): boolean {
  return /[一-龥A-Za-z0-9]/.test(text)
}

/** 纯函数：Tesseract line → OCRRegion（与云端区域结构一致，供单测）
 *  scale：预处理放大倍数，坐标除以 scale 映射回原始图片坐标 */
export function linesToRegions(lines: TesseractLine[], scale = 1): LocalOCRRegion[] {
  return lines
    .filter(l => l.text && l.text.trim() && isMeaningfulText(l.text))
    .map(l => {
      const { x0, y0, x1, y1 } = l.bbox ?? { x0: 0, y0: 0, x1: 0, y1: 0 }
      const text = (l.text || '').trim()
      return {
        bbox: [[x0 / scale, y0 / scale], [x1 / scale, y0 / scale], [x1 / scale, y1 / scale], [x0 / scale, y1 / scale]],
        rect: {
          x: Math.round(x0 / scale),
          y: Math.round(y0 / scale),
          w: Math.max(1, Math.round((x1 - x0) / scale)),
          h: Math.max(1, Math.round((y1 - y0) / scale)),
        },
        text,
        confidence: l.confidence ?? 0,
        sensitive: classifyText(text),
      }
    })
}

/**
 * 纯函数：从 hOCR 原始输出解析词框（tesseract.js 的 words/lines 解析在某些浏览器为空时的兜底）
 * 真实格式：<span class='ocrx_word' id='word_1_1' title='bbox x0 y0 x1 y1; x_wconf 76' [lang='xx']>text</span>
 */
export function parseHocr(hocr: string, scale = 1): LocalOCRRegion[] {
  const regions: LocalOCRRegion[] = []
  const re = /<span[^>]*?\bclass='ocrx_word'[^>]*?\btitle='([^']*)'[^>]*>([^<]*)<\/span>/g
  let m: RegExpExecArray | null
  while ((m = re.exec(hocr)) !== null) {
    const title = m[1] || ''
    const bboxMatch = title.match(/bbox\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)/)
    if (!bboxMatch) continue
    const text = (m[2] || '').trim()
    if (!isMeaningfulText(text)) continue  // 过滤表格边框/纯符号
    const confMatch = title.match(/x_wconf\s+(\d+)/)
    if (confMatch && +confMatch[1] < 5) continue  // 极低置信度
    const x0 = +bboxMatch[1], y0 = +bboxMatch[2], x1 = +bboxMatch[3], y1 = +bboxMatch[4]
    regions.push({
      bbox: [[x0 / scale, y0 / scale], [x1 / scale, y0 / scale], [x1 / scale, y1 / scale], [x0 / scale, y1 / scale]],
      rect: {
        x: Math.round(x0 / scale), y: Math.round(y0 / scale),
        w: Math.max(1, Math.round((x1 - x0) / scale)), h: Math.max(1, Math.round((y1 - y0) / scale)),
      },
      text,
      confidence: confMatch ? +confMatch[1] : 0,
      sensitive: classifyText(text),
    })
  }
  return regions
}

/** 纯函数：Tesseract word → OCRRegion（表格/复杂版面 lines 为空时的回退方案） */
export function wordsToRegions(words: TesseractWord[], scale = 1): LocalOCRRegion[] {
  return words
    .filter(w => w.text && w.text.trim() && isMeaningfulText(w.text))
    .map(w => {
      const { x0, y0, x1, y1 } = w.bbox ?? { x0: 0, y0: 0, x1: 0, y1: 0 }
      const text = (w.text || '').trim()
      return {
        bbox: [[x0 / scale, y0 / scale], [x1 / scale, y0 / scale], [x1 / scale, y1 / scale], [x0 / scale, y1 / scale]],
        rect: {
          x: Math.round(x0 / scale),
          y: Math.round(y0 / scale),
          w: Math.max(1, Math.round((x1 - x0) / scale)),
          h: Math.max(1, Math.round((y1 - y0) / scale)),
        },
        text,
        confidence: w.confidence ?? 0,
        sensitive: classifyText(text),
      }
    })
}

/**
 * 纯函数：把词级区域按行合并成"单元格/文本行"区域（缓解中文碎字，保留表格列间距）。
 * 同一 y 行的词，若水平间隙小于阈值则连成一条（区域文本合并）；列间距大则保持独立。
 */
export function groupRegionsToLines(regions: LocalOCRRegion[]): LocalOCRRegion[] {
  if (regions.length <= 1) return regions
  const items = regions.map(r => ({ r, x0: r.rect.x, y0: r.rect.y, x1: r.rect.x + r.rect.w, y1: r.rect.y + r.rect.h }))
  items.sort((a, b) => a.y0 - b.y0 || a.x0 - b.x0)
  // 按 y 重叠分组
  const lines: Array<{ y0: number; y1: number; items: typeof items }> = []
  for (const it of items) {
    let placed = false
    for (const line of lines) {
      const overlap = Math.min(it.y1, line.y1) - Math.max(it.y0, line.y0)
      const minH = Math.min(it.y1 - it.y0, line.y1 - line.y0)
      if (overlap > minH * 0.5) { line.items.push(it); line.y0 = Math.min(line.y0, it.y0); line.y1 = Math.max(line.y1, it.y1); placed = true; break }
    }
    if (!placed) lines.push({ y0: it.y0, y1: it.y1, items: [it] })
  }
  // 组内按 x 排序，按间隙切成段（碎片合并成单元格，列间距大则保持独立）
  const out: LocalOCRRegion[] = []
  for (const line of lines) {
    line.items.sort((a, b) => a.x0 - b.x0)
    const gapThreshold = Math.max(4, (line.y1 - line.y0) * 0.3)
    let seg: typeof line.items = []
    const flush = () => {
      if (!seg.length) return
      const sx0 = Math.min(...seg.map(i => i.x0))
      const sx1 = Math.max(...seg.map(i => i.x1))
      const text = seg.map((i, idx) => (idx > 0 && i.x0 - seg[idx - 1].x1 > gapThreshold ? ' ' : '') + i.r.text).join('')
      out.push({
        bbox: [[sx0, line.y0], [sx1, line.y0], [sx1, line.y1], [sx0, line.y1]],
        rect: { x: sx0, y: line.y0, w: Math.max(1, sx1 - sx0), h: Math.max(1, line.y1 - line.y0) },
        text,
        confidence: seg[0].r.confidence,
        sensitive: classifyText(text),
      })
      seg = []
    }
    for (let i = 0; i < line.items.length; i++) {
      const it = line.items[i]
      if (seg.length && it.x0 - line.items[i - 1].x1 > gapThreshold) flush()
      seg.push(it)
    }
    flush()
  }
  return out
}

/**
 * 预处理：灰度 + 对比度增强 + 小图放大（宽 <900px 放大到约 2x）。
 * Tesseract 对真实照片/低对比度/小字很弱，预处理能显著提升识别率。
 * 返回 canvas + 放大倍数（用于把识别框坐标映射回原图）。
 */
export async function preprocessImage(image: Blob): Promise<{ canvas: HTMLCanvasElement; scale: number }> {
  const url = URL.createObjectURL(image)
  const img = new Image()
  await new Promise<void>((res, rej) => {
    img.onload = () => res()
    img.onerror = () => rej(new Error('图片加载失败'))
    img.src = url
  })
  URL.revokeObjectURL(url)

  const scale = Math.min(2, Math.max(1, Math.ceil(900 / img.width)))
  const w = img.width * scale
  const h = img.height * scale
  const canvas = document.createElement('canvas')
  canvas.width = w
  canvas.height = h
  const ctx = canvas.getContext('2d')!
  ctx.drawImage(img, 0, 0, w, h)

  // 灰度 + 对比度拉伸（浅的更浅、深的更深）
  const id = ctx.getImageData(0, 0, w, h)
  const d = id.data
  for (let i = 0; i < d.length; i += 4) {
    const g = 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2]
    const v = g < 128 ? Math.max(0, g - 30) : Math.min(255, g + 30)
    d[i] = d[i + 1] = d[i + 2] = v
  }
  ctx.putImageData(id, 0, 0)
  return { canvas, scale }
}

let _workerPromise: Promise<any> | null = null

/** 懒加载 Tesseract worker（单例复用），语言：中文 + 英文
 *  资源本地打包在 public/tesseract/，不依赖 CDN（国内 jsdelivr 常不可达） */
async function getWorker(): Promise<any> {
  if (!_workerPromise) {
    const Tesseract = (await import('tesseract.js')).default
    _workerPromise = Tesseract.createWorker(['eng', 'chi_sim'], 1, {
      workerPath: '/tesseract/worker.min.js',
      corePath: '/tesseract/core/',
      langPath: '/tesseract/tessdata/',
    })
  }
  return _workerPromise
}

/**
 * 本地 OCR：图片不出浏览器，识别前做预处理（灰度+对比度+放大）提升真实照片识别率。
 * worker/核心/语言包已本地打包在 public/tesseract/，零 CDN 依赖。
 */
export async function recognizeLocal(image: Blob): Promise<LocalOCRRegion[]> {
  const worker = await getWorker()
  const { canvas, scale } = await preprocessImage(image)
  // 同时请求 text + hocr 原始输出（hocr 作为 words/lines 解析失败的兜底）
  const { data } = await worker.recognize(canvas, {}, { text: true, hocr: true })
  const lines = data.lines ?? []
  const words = data.words ?? []
  console.log('[localOCR] lines:', lines.length, '| words:', words.length, '| hocr 词条:', (data.hocr || '').includes('ocrx_word') ? '有' : '无')
  if (lines.length > 0) return linesToRegions(lines, scale)
  // words 或 hOCR 词级结果 → 过滤边框垃圾 → 按行合并成单元格区域
  let wordRegions: LocalOCRRegion[] = []
  if (words.length > 0) wordRegions = wordsToRegions(words, scale)
  else if (data.hocr) wordRegions = parseHocr(data.hocr, scale)
  if (wordRegions.length > 0) return groupRegionsToLines(wordRegions)
  console.warn('[localOCR] 无任何识别结果（lines/words/hocr 均为空）')
  return []
}
