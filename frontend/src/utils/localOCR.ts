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

/** 纯函数：Tesseract line → OCRRegion（与云端区域结构一致，供单测）
 *  scale：预处理放大倍数，坐标除以 scale 映射回原始图片坐标 */
export function linesToRegions(lines: TesseractLine[], scale = 1): LocalOCRRegion[] {
  return lines
    .filter(l => l.text && l.text.trim())
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

/** 纯函数：Tesseract word → OCRRegion（表格/复杂版面 lines 为空时的回退方案） */
export function wordsToRegions(words: TesseractWord[], scale = 1): LocalOCRRegion[] {
  return words
    .filter(w => w.text && w.text.trim())
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
  const { data } = await worker.recognize(canvas)
  // 表格/复杂版面时 Tesseract 的行分组会失败（data.lines 为空但 words 有内容）→ 回退按词
  const lines = data.lines ?? []
  if (lines.length > 0) return linesToRegions(lines, scale)
  return wordsToRegions(data.words ?? [], scale)
}
