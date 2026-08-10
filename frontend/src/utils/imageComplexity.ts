/**
 * ================================================================
 * 「隐盾」图片复杂度评估（识别模式分流引导）
 * ================================================================
 * 上传后轻量分析：边缘密度 + 网格线占比 → 判断简单/中等/复杂版面。
 * - 简单场景：本地/精准均可（推荐任一）
 * - 复杂版面（表格/密集文档）：推荐精准增强（PaddleOCR 精度高，Tesseract 会碎字）
 *
 * 纯函数 classifyComplexity 可单测；assessComplexity 依赖浏览器 canvas。
 */

export type ComplexityLevel = 'simple' | 'medium' | 'complex'

export interface ComplexityResult {
  level: ComplexityLevel
  edgeDensity: number
  gridRatio: number
  reason: string
}

/** 纯函数：按边缘密度/网格线占比分类（可单测） */
export function classifyComplexity(edgeDensity: number, gridRatio: number): ComplexityResult {
  let level: ComplexityLevel
  let reason: string
  if (gridRatio > 0.04) {
    level = 'complex'
    reason = '检测到网格/表格结构（表格、账单等复杂版面），推荐精准增强识别'
  } else if (edgeDensity > 0.12) {
    level = 'complex'
    reason = '内容密集、布局复杂（文字多/小字），推荐精准增强识别'
  } else if (edgeDensity > 0.06) {
    level = 'medium'
    reason = '内容较多，本地/精准均可，精准更准'
  } else {
    level = 'simple'
    reason = '内容简单（大字/截图文本），本地/精准均可'
  }
  return { level, edgeDensity: +edgeDensity.toFixed(3), gridRatio: +gridRatio.toFixed(4), reason }
}

/** 浏览器端：对上传图片做复杂度评估（缩小加速分析） */
export async function assessComplexity(image: Blob): Promise<ComplexityResult> {
  const url = URL.createObjectURL(image)
  const img = new Image()
  await new Promise<void>((res, rej) => {
    img.onload = () => res()
    img.onerror = () => rej(new Error('图片加载失败'))
    img.src = url
  })
  URL.revokeObjectURL(url)

  const scale = Math.min(1, 320 / img.width)
  const w = Math.max(1, Math.round(img.width * scale))
  const h = Math.max(1, Math.round(img.height * scale))
  const canvas = document.createElement('canvas')
  canvas.width = w
  canvas.height = h
  const ctx = canvas.getContext('2d')!
  ctx.drawImage(img, 0, 0, w, h)
  const d = ctx.getImageData(0, 0, w, h).data
  const gray = new Uint8Array(w * h)
  for (let i = 0; i < d.length; i += 4) {
    gray[i / 4] = Math.round(0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2])
  }

  // 边缘密度：相邻像素差超过阈值
  let edges = 0
  for (let y = 1; y < h; y++) {
    for (let x = 1; x < w; x++) {
      const g = gray[y * w + x]
      if (Math.abs(g - gray[y * w + x - 1]) > 40 || Math.abs(g - gray[(y - 1) * w + x]) > 40) edges++
    }
  }
  const edgeDensity = edges / (w * h)

  // 网格线：行/列中暗像素占多数 → 水平/垂直线
  let hLines = 0
  for (let y = 0; y < h; y++) {
    let dark = 0
    for (let x = 0; x < w; x++) if (gray[y * w + x] < 128) dark++
    if (dark > w * 0.6) hLines++
  }
  let vLines = 0
  for (let x = 0; x < w; x++) {
    let dark = 0
    for (let y = 0; y < h; y++) if (gray[y * w + x] < 128) dark++
    if (dark > h * 0.6) vLines++
  }
  const gridRatio = (hLines + vLines) / (w + h)

  return classifyComplexity(edgeDensity, gridRatio)
}
