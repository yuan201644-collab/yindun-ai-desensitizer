/**
 * ================================================================
 * 「隐盾」云端 OCR 耗时统计（用于预估识别时间，非臆测）
 * ================================================================
 * 记录每次云端 OCR 的实际耗时（客户端测量：请求发出到响应返回），
 * 取最近 N 次平均作为下次预估。无历史数据时返回 null（显示"首次稍慢"）。
 */

const STORAGE_KEY = 'yindun_ocr_durations'
const MAX_RECORDS = 10

/** 预估下一次云端 OCR 耗时（ms）；无历史返回 null */
export function getOcrEstimateMs(): number | null {
  try {
    const list: number[] = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
    if (!list.length) return null
    return Math.round(list.reduce((s, v) => s + v, 0) / list.length)
  } catch {
    return null
  }
}

/** 记录一次云端 OCR 实际耗时（ms），保留最近 MAX_RECORDS 条 */
export function recordOcrDuration(ms: number) {
  try {
    const list: number[] = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
    list.push(ms)
    if (list.length > MAX_RECORDS) list.shift()
    localStorage.setItem(STORAGE_KEY, JSON.stringify(list))
  } catch {
    /* localStorage 不可用则忽略 */
  }
}
