/**
 * canvas 脱敏核心测试（首个！此前 canvas.ts 零单测——高斯"只有噪点无模糊"缺陷漏网的原因）
 * 覆盖：applyGaussianMask 脱敏有效性（结构破坏）+ 边界安全
 * 度量：条纹图（模拟文字笔画）应用高斯后**对比度**显著下降（模糊抹平笔画）；
 *       对比度对逐像素噪声免疫（噪声均值≈0），确定性验证"文字不可读"。
 */

import { describe, it, expect } from 'vitest'
import { applyGaussianMask } from '../src/utils/canvas'

interface Pixels { data: Uint8ClampedArray; width: number; height: number }

/** 构造"文字模拟"：10px 周期垂直条纹（深色笔画 vs 浅背景，对比强烈） */
function makeStripes(w: number, h: number): Pixels {
  const data = new Uint8ClampedArray(w * h * 4)
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const v = (x % 10 < 5) ? 30 : 220
      const i = (y * w + x) * 4
      data[i] = v; data[i + 1] = v; data[i + 2] = v; data[i + 3] = 255
    }
  }
  return { data, width: w, height: h }
}

/** 笔画区 vs 背景区 灰度均值差（文字可读性的代理指标） */
function contrast(p: Pixels): number {
  const { data, width: w, height: h } = p
  let dark = 0, light = 0, dn = 0, ln = 0
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const v = data[(y * w + x) * 4]
      if (x % 10 < 5) { dark += v; dn++ } else { light += v; ln++ }
    }
  }
  return Math.abs(dark / dn - light / ln)
}

describe('applyGaussianMask 脱敏有效性（结构破坏）', () => {
  it('模糊+噪点后文字笔画对比度显著下降（>60%）', () => {
    const img = makeStripes(120, 60)
    const before = contrast(img)
    applyGaussianMask(img, 8, 40)
    const after = contrast(img)
    expect(after).toBeLessThan(before * 0.4)  // 对比度下降 >60%
  })

  it('低强度（radius=2, noise=20）也可见地破坏结构', () => {
    const img = makeStripes(80, 40)
    const before = contrast(img)
    applyGaussianMask(img, 2, 20)
    // radius=2 弥散 2px 笔画边缘：对比度显著下降（>40%），区别于旧实现"只加噪、对比度≈不变"
    expect(contrast(img)).toBeLessThan(before * 0.6)
  })

  it('超大半径边界安全（不崩、原地修改）', () => {
    const img = makeStripes(30, 20)
    const snapshot = Array.from(img.data)
    applyGaussianMask(img, 9999, 10)
    expect(Array.from(img.data)).not.toEqual(snapshot)  // 像素有变化
  })

  it('缓冲区尺寸不变', () => {
    const img = makeStripes(40, 40)
    const len = img.data.length
    applyGaussianMask(img, 6, 30)
    expect(img.data.length).toBe(len)
  })

  it('半径 0 时退化为仅加噪（仍改变像素）', () => {
    const img = makeStripes(40, 40)
    const snapshot = Array.from(img.data)
    applyGaussianMask(img, 0, 50)
    expect(Array.from(img.data)).not.toEqual(snapshot)
  })
})
