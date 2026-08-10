import { describe, it, expect } from 'vitest'
import { classifyText } from '../src/utils/sensitivePatterns'
import { linesToRegions, wordsToRegions, parseHocr, groupRegionsToLines, isMeaningfulText, detectNameColumn } from '../src/utils/localOCR'

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

describe('parseHocr hOCR 原始输出兜底', () => {
  it('从真实格式解析（class 与 title 间有 id、bbox 后有 x_wconf）', () => {
    const hocr = `<span class='ocrx_word' id='word_1_1' title='bbox 33 12 64 27; x_wconf 76'>205</span><span class='ocrx_word' id='word_1_2' title='bbox 87 0 200 25; x_wconf 59'>13800138000</span>`
    const regions = parseHocr(hocr)
    expect(regions.length).toBe(2)
    expect(regions[0].rect).toEqual({ x: 33, y: 12, w: 31, h: 15 })
    expect(regions[1].sensitive?.type).toBe('手机号')
    expect(regions[0].sensitive).toBeNull()
  })

  it('支持 title 后有 lang 属性 + scale 映射', () => {
    const hocr = `<span class='ocrx_word' id='w' title='bbox 20 40 120 60; x_wconf 90' lang='chi_sim'>B24041701</span><span class='ocrx_word' id='x' title='bbox 1 1 2 2; x_wconf 0'> </span>`
    const regions = parseHocr(hocr, 2)
    expect(regions.length).toBe(1)
    expect(regions[0].rect).toEqual({ x: 10, y: 20, w: 50, h: 10 })
  })
})

describe('isMeaningfulText 过滤表格边框/符号', () => {
  it('纯符号/边框字符被剔除', () => {
    expect(isMeaningfulText('|')).toBe(false)
    expect(isMeaningfulText('[|')).toBe(false)
    expect(isMeaningfulText('——')).toBe(false)
    expect(isMeaningfulText('…')).toBe(false)
  })
  it('中文标点保留（作为分隔符）', () => {
    expect(isMeaningfulText('、')).toBe(true)
    expect(isMeaningfulText('，')).toBe(true)
  })
  it('含中英文/数字的文本保留', () => {
    expect(isMeaningfulText('13800138000')).toBe(true)
    expect(isMeaningfulText('B24041701')).toBe(true)
    expect(isMeaningfulText('计算机学院')).toBe(true)
  })
})

describe('detectNameColumn 姓名列检测', () => {
  const R = (x: number, text: string, w = 60) => ({ rect: { x, y: 0, w, h: 20 }, text })
  it('同一列的不同短中文 → 姓名列', () => {
    const regions = [R(100, '王舒琳'), R(100, '任雨涵'), R(100, '杨婉露'), R(100, '李思雨'), R(0, '信息安全'), R(0, '信息安全'), R(0, '信息安全')]
    const col = detectNameColumn(regions)
    expect(col).not.toBeNull()
    expect(col!.length).toBe(4)
    expect(col!.every(r => r.text.length === 3)).toBe(true)
  })
  it('重复字段列（4字）不判为姓名', () => {
    const regions = [R(0, '信息安全'), R(0, '信息安全'), R(0, '信息安全'), R(0, '信息安全')]
    expect(detectNameColumn(regions)).toBeNull()
  })
  it('少于 3 个 → null', () => {
    expect(detectNameColumn([R(0, '王舒琳'), R(0, '任雨涵')])).toBeNull()
  })
})

describe('groupRegionsToLines 按行合并碎片', () => {
  const W = (x: number, text: string, conf = 80): any => ({
    bbox: [[x, 0], [x + text.length * 8, 0], [x + text.length * 8, 15], [x, 15]],
    rect: { x, y: 0, w: text.length * 8, h: 15 },
    text, confidence: conf, sensitive: null,
  })
  it('紧挨的碎字合并成一个单元格区域', () => {
    const regions = groupRegionsToLines([W(0, '计算'), W(16, '机'), W(24, '学院'), W(120, '13800138000')])
    expect(regions.length).toBe(2)
    expect(regions[0].text).toBe('计算机学院')
    expect(regions[1].text).toBe('13800138000')
    expect(regions[1].sensitive?.type).toBe('手机号')
  })
  it('同一行但列间距大的保持独立', () => {
    const regions = groupRegionsToLines([W(0, '信息安全'), W(200, 'B24041701')])
    expect(regions.length).toBe(2)
  })
})
