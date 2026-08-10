import { describe, it, expect } from 'vitest'
import { classifyText } from '../src/utils/sensitivePatterns'
import { linesToRegions, wordsToRegions } from '../src/utils/localOCR'

describe('classifyText 敏感分类', () => {
  it('命中身份证号并带对象标签', () => {
    const r = classifyText('身份证号11010119900101123X')
    expect(r?.type).toBe('身份证号')
    expect(r?.object_label).toBe('🪪 证件')
    expect(r?.risk_level).toBe('high')
  })

  it('命中手机号', () => {
    const r = classifyText('电话13800138000')
    expect(r?.type).toBe('手机号')
    expect(r?.object_label).toBe('📱 联系方式')
  })

  it('无命中返回 null', () => {
    expect(classifyText('今天天气不错')).toBeNull()
  })
})

describe('linesToRegions Tesseract line 转区域', () => {
  it('正确换算 rect/bbox/敏感分类', () => {
    const regions = linesToRegions([
      { bbox: { x0: 10, y0: 20, x1: 200, y1: 40 }, text: 'ID 11010119900101123X', confidence: 0.9 },
    ])
    expect(regions.length).toBe(1)
    expect(regions[0].rect).toEqual({ x: 10, y: 20, w: 190, h: 20 })
    expect(regions[0].bbox.length).toBe(4)
    expect(regions[0].confidence).toBe(0.9)
    expect(regions[0].sensitive?.type).toBe('身份证号')
  })

  it('过滤空白行', () => {
    const regions = linesToRegions([
      { bbox: { x0: 0, y0: 0, x1: 10, y1: 10 }, text: '   ', confidence: 0 },
      { bbox: { x0: 5, y0: 5, x1: 100, y1: 25 }, text: '13800138000', confidence: 0.8 },
    ])
    expect(regions.length).toBe(1)
  })

  it('无 bbox 的 line 不崩', () => {
    const regions = linesToRegions([{ text: 'abc' }])
    expect(regions.length).toBe(1)
    expect(regions[0].rect.x).toBe(0)
  })

  it('支持 scale 缩放（预处理放大后映射回原图坐标）', () => {
    const regions = linesToRegions([
      { bbox: { x0: 20, y0: 40, x1: 400, y1: 80 }, text: '13800138000', confidence: 0.9 },
    ], 2)
    expect(regions[0].rect).toEqual({ x: 10, y: 20, w: 190, h: 20 })
    expect(regions[0].bbox[0]).toEqual([10, 20])
  })
})

describe('wordsToRegions 词级区域（表格/复杂版面回退）', () => {
  it('按词生成区域并分类', () => {
    const regions = wordsToRegions([
      { bbox: { x0: 10, y0: 20, x1: 120, y1: 40 }, text: '13800138000', confidence: 0.9 },
      { bbox: { x0: 5, y0: 5, x1: 50, y1: 20 }, text: '姓名' },
    ])
    expect(regions.length).toBe(2)
    expect(regions[0].sensitive?.type).toBe('手机号')
    expect(regions[1].sensitive).toBeNull()
  })

  it('支持 scale 映射', () => {
    const regions = wordsToRegions([
      { bbox: { x0: 20, y0: 40, x1: 120, y1: 60 }, text: 'B24041701' },
    ], 2)
    expect(regions[0].rect).toEqual({ x: 10, y: 20, w: 50, h: 10 })
  })
})
