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

/** 纯函数：Tesseract line → OCRRegion（与云端区域结构一致，供单测） */
export function linesToRegions(lines: TesseractLine[]): LocalOCRRegion[] {
  return lines
    .filter(l => l.text && l.text.trim())
    .map(l => {
      const { x0, y0, x1, y1 } = l.bbox ?? { x0: 0, y0: 0, x1: 0, y1: 0 }
      const text = (l.text || '').trim()
      return {
        bbox: [[x0, y0], [x1, y0], [x1, y1], [x0, y1]],
        rect: {
          x: Math.round(x0),
          y: Math.round(y0),
          w: Math.max(1, Math.round(x1 - x0)),
          h: Math.max(1, Math.round(y1 - y0)),
        },
        text,
        confidence: l.confidence ?? 0,
        sensitive: classifyText(text),
      }
    })
}

let _workerPromise: Promise<any> | null = null

/** 懒加载 Tesseract worker（单例复用），语言：中文 + 英文 */
async function getWorker(): Promise<any> {
  if (!_workerPromise) {
    const Tesseract = (await import('tesseract.js')).default
    _workerPromise = Tesseract.createWorker(['eng', 'chi_sim'])
  }
  return _workerPromise
}

/**
 * 本地 OCR：图片不出浏览器。
 * 首次调用需下载语言包（chi_sim+eng ~10-15MB）+ WASM，之后 worker 复用。
 */
export async function recognizeLocal(image: Blob): Promise<LocalOCRRegion[]> {
  const worker = await getWorker()
  const { data } = await worker.recognize(image)
  return linesToRegions(data.lines ?? [])
}
