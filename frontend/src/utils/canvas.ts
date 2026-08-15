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
  intensity: number = 1.0, // 0.0-1.0 强度
  level: number = 1 // 不可逆保护等级 1-3
): void {
  const { x, y, w, h } = region
  const imageData = ctx.getImageData(x, y, w, h)

  switch (method) {
    case 'pixelate':
      // 块尺寸自适应区域尺寸：小区域 → 块≈整个区域；同时保留 intensity 缩放
      pixelateRegion(imageData, w, h, Math.max(Math.min(w, h), Math.floor(12 * intensity)))
      break
    case 'gaussian':
      // ⭐ 高斯噪点混淆：强度驱动模糊半径 + 噪声（对齐后端"强模糊+噪点"语义）
      gaussianRegion(imageData, w, h, intensity)
      break
    case 'irreversible':
      // patch 自适应区域尺寸：小区域 → 整个区域一个 patch；同时保留 intensity 缩放
      irreversibleRegion(imageData, w, h, Math.max(Math.min(w, h), Math.floor(6 * intensity)), level)
      break
  }

  ctx.putImageData(imageData, x, y)
}

/**
 * ⭐ 高斯噪点混淆核心（可单测纯函数）：两次一维 box blur（打散文字结构）+ 高斯噪点注入。
 * 输入兼容 ImageData 结构 { data, width, height }（node 测试环境可手造，不依赖 canvas API）。
 * @param pixels 像素缓冲（原地修改）
 * @param radius 模糊半径（>=2），模糊把文字笔画弥散开，人眼/AI 无法再读
 * @param noiseLevel 噪点强度 0-255，对抗去噪模型
 */
export function applyGaussianMask(
  pixels: { data: Uint8ClampedArray; width: number; height: number },
  radius: number,
  noiseLevel: number
): void {
  const { data, width, height } = pixels
  const r = Math.max(2, Math.min(radius, Math.floor(Math.min(width, height) / 2)))
  const len = width * height * 4

  // ① 两次一维 box blur（水平 → 垂直），O(n*2r)，边界复制
  const tmp = new Float32Array(len)
  for (let y = 0; y < height; y++) {
    const row = y * width * 4
    for (let x = 0; x < width; x++) {
      let x0 = x - r, x1 = x + r
      if (x0 < 0) x0 = 0
      if (x1 >= width) x1 = width - 1
      const n = x1 - x0 + 1
      const idx = row + x * 4
      let sr = 0, sg = 0, sb = 0
      for (let k = x0; k <= x1; k++) {
        const ki = row + k * 4
        sr += data[ki]; sg += data[ki + 1]; sb += data[ki + 2]
      }
      tmp[idx] = sr / n; tmp[idx + 1] = sg / n; tmp[idx + 2] = sb / n; tmp[idx + 3] = data[idx + 3]
    }
  }
  for (let x = 0; x < width; x++) {
    for (let y = 0; y < height; y++) {
      let y0 = y - r, y1 = y + r
      if (y0 < 0) y0 = 0
      if (y1 >= height) y1 = height - 1
      const n = y1 - y0 + 1
      const idx = (y * width + x) * 4
      let sr = 0, sg = 0, sb = 0
      for (let k = y0; k <= y1; k++) {
        const ki = (k * width + x) * 4
        sr += tmp[ki]; sg += tmp[ki + 1]; sb += tmp[ki + 2]
      }
      data[idx] = sr / n; data[idx + 1] = sg / n; data[idx + 2] = sb / n
    }
  }

  // ② 逐像素高斯噪点（Box-Muller），破坏去噪模型可恢复性
  for (let i = 0; i < len; i += 4) {
    const g1 = Math.random()
    const g2 = Math.random()
    const gauss = Math.sqrt(-2 * Math.log(Math.max(g1, 0.001))) * Math.cos(2 * Math.PI * g2)
    const v = data[i] + gauss * noiseLevel
    data[i] = v < 0 ? 0 : v > 255 ? 255 : v
  }
}

/**
 * 高斯噪点混淆：模糊（打散结构）+ 噪点（对抗去噪）。
 * 强度 intensity(0-1) 同时驱动模糊半径与噪声大小。
 */
function gaussianRegion(
  imageData: ImageData,
  width: number,
  height: number,
  intensity: number
): void {
  const radius = Math.max(2, Math.round(Math.min(width, height) * 0.25 * intensity))
  const noise = Math.min(255, 20 + 40 * intensity)  // 对齐后端噪点量级（~12%），避免雪花感
  applyGaussianMask(imageData, radius, noise)
}

/**
 * 像素化：降采样 + 升采样 + 随机微扰
 * （导出供有效性评估脚本复刻同一算法与参数）
 */
export function pixelateRegion(
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
 * 不可逆像素替换：分块随机重排 + 值注入
 * (简化版 — 完整版在服务端 Python 实现)
 * （导出供有效性评估脚本复刻同一算法与参数）
 */
export function irreversibleRegion(
  imageData: ImageData,
  width: number,
  height: number,
  patchSize: number,
  level: number = 1 // 保护等级 1-3：轮数越多、噪声越大，打散越彻底
): void {
  const data = imageData.data
  const passes = level // 1/2/3 轮打散
  const noiseBase = 8 * level // 噪声范围 ±8/16/24

  // 多轮打散：Fisher-Yates 行级重排 + 写回伪随机噪声
  for (let pass = 0; pass < passes; pass++) {
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
            const noise = Math.floor(Math.random() * noiseBase * 2) - noiseBase
            data[idx] = Math.min(255, Math.max(0, pixels[pi][0] + noise))
            data[idx + 1] = Math.min(255, Math.max(0, pixels[pi][1] + noise))
            data[idx + 2] = Math.min(255, Math.max(0, pixels[pi][2] + noise))
            pi++
          }
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
