/**
 * ================================================================
 * 「隐盾」Canvas 脱敏渲染引擎 (纯前端)
 * ================================================================
 * 核心隐私保障：图片处理完全在浏览器端完成，原始数据不上传。
 *
 * 支持三种脱敏模式：
 * 1. pixelate  — 像素化（马赛克）
 * 2. gaussian   — 高斯噪点混淆
 * 3. irreversible — 不可逆像素替换（简化版）
 *
 * ⚠️ 如需新增算法，在 applyDesensitize 的 switch 中添加 case 即可。
 */

export type DesensitizeMethod = 'pixelate' | 'gaussian' | 'irreversible'

export interface Region {
  x: number
  y: number
  w: number
  h: number
  method?: DesensitizeMethod
}

/**
 * 在 Canvas 上对指定区域应用脱敏
 */
export function applyDesensitize(
  ctx: CanvasRenderingContext2D,
  region: Region,
  method: DesensitizeMethod = 'pixelate',
  intensity: number = 1.0 // 0.0-1.0 强度
): void {
  const { x, y, w, h } = region
  const imageData = ctx.getImageData(x, y, w, h)

  switch (method) {
    case 'pixelate':
      pixelateRegion(imageData, w, h, Math.max(4, Math.floor(12 * intensity)))
      break
    case 'gaussian':
      gaussianRegion(imageData, w, h, 5 + 20 * intensity)
      break
    case 'irreversible':
      irreversibleRegion(imageData, w, h, Math.max(2, Math.floor(6 * intensity)))
      break
  }

  ctx.putImageData(imageData, x, y)
}

/**
 * 像素化：降采样 + 升采样 + 随机微扰
 */
function pixelateRegion(
  imageData: ImageData,
  width: number,
  height: number,
  blockSize: number
): void {
  const data = imageData.data
  // 对每个 block 取均值
  for (let by = 0; by < height; by += blockSize) {
    for (let bx = 0; bx < width; bx += blockSize) {
      const bw = Math.min(blockSize, width - bx)
      const bh = Math.min(blockSize, height - by)
      let r = 0, g = 0, b = 0, count = 0

      for (let py = 0; py < bh; py++) {
        for (let px = 0; px < bw; px++) {
          const idx = ((by + py) * width + (bx + px)) * 4
          r += data[idx]
          g += data[idx + 1]
          b += data[idx + 2]
          count++
        }
      }

      // ⭐ 加随机微扰动 (0-8 像素值) — 破坏插值还原
      const noiseR = Math.floor(Math.random() * 8)
      const noiseG = Math.floor(Math.random() * 8)
      const noiseB = Math.floor(Math.random() * 8)

      const avgR = Math.min(255, Math.floor(r / count) + noiseR)
      const avgG = Math.min(255, Math.floor(g / count) + noiseG)
      const avgB = Math.min(255, Math.floor(b / count) + noiseB)

      for (let py = 0; py < bh; py++) {
        for (let px = 0; px < bw; px++) {
          const idx = ((by + py) * width + (bx + px)) * 4
          data[idx] = avgR
          data[idx + 1] = avgG
          data[idx + 2] = avgB
        }
      }
    }
  }
}

/**
 * 高斯噪点混淆：逐像素加噪 + 邻域混合
 */
function gaussianRegion(
  imageData: ImageData,
  width: number,
  height: number,
  noiseLevel: number
): void {
  const data = imageData.data
  const noise = noiseLevel * 2.55 // 转 0-255 范围

  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const idx = (y * width + x) * 4
      // Box-Muller 近似高斯噪点
      const g1 = Math.random()
      const g2 = Math.random()
      const gauss = Math.sqrt(-2 * Math.log(Math.max(g1, 0.001))) * Math.cos(2 * Math.PI * g2)

      data[idx] = Math.min(255, Math.max(0, data[idx] + gauss * noise))
      data[idx + 1] = Math.min(255, Math.max(0, data[idx + 1] + gauss * noise))
      data[idx + 2] = Math.min(255, Math.max(0, data[idx + 2] + gauss * noise))
    }
  }
}

/**
 * 不可逆像素替换：分块随机重排 + 值注入
 * (简化版 — 完整版在服务端 Python 实现)
 */
function irreversibleRegion(
  imageData: ImageData,
  width: number,
  height: number,
  patchSize: number
): void {
  const data = imageData.data
  // Fisher-Yates 行级重排
  for (let py = 0; py < height; py += patchSize) {
    for (let px = 0; px < width; px += patchSize) {
      const pw = Math.min(patchSize, width - px)
      const ph = Math.min(patchSize, height - py)
      const pixels: number[][] = []

      for (let y = 0; y < ph; y++) {
        for (let x = 0; x < pw; x++) {
          const idx = ((py + y) * width + (px + x)) * 4
          pixels.push([data[idx], data[idx + 1], data[idx + 2], data[idx + 3]])
        }
      }

      // 随机重排
      for (let i = pixels.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [pixels[i], pixels[j]] = [pixels[j], pixels[i]]
      }

      // 写回 + 伪随机噪声
      let pi = 0
      for (let y = 0; y < ph; y++) {
        for (let x = 0; x < pw; x++) {
          const idx = ((py + y) * width + (px + x)) * 4
          const noise = Math.floor(Math.random() * 16) - 8
          data[idx] = Math.min(255, Math.max(0, pixels[pi][0] + noise))
          data[idx + 1] = Math.min(255, Math.max(0, pixels[pi][1] + noise))
          data[idx + 2] = Math.min(255, Math.max(0, pixels[pi][2] + noise))
          pi++
        }
      }
    }
  }
}

/**
 * 将图片文件绘制到 Canvas
 */
export function drawImageToCanvas(
  canvas: HTMLCanvasElement,
  file: File | Blob
): Promise<void> {
  return new Promise((resolve, reject) => {
    const ctx = canvas.getContext('2d')
    const img = new Image()
    const url = URL.createObjectURL(file)

    img.onload = () => {
      canvas.width = img.width
      canvas.height = img.height
      ctx!.drawImage(img, 0, 0)
      URL.revokeObjectURL(url)
      resolve()
    }
    img.onerror = () => {
      URL.revokeObjectURL(url)
      reject(new Error('图片加载失败'))
    }
    img.src = url
  })
}

/**
 * Canvas → Blob（下载用）
 */
export function canvasToBlob(canvas: HTMLCanvasElement): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      blob ? resolve(blob) : reject(new Error('导出失败'))
    }, 'image/png')
  })
}
