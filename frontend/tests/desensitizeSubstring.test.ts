/**
 * 脱敏只打码内容不打标签 — 前端全链路测试
 * 覆盖：
 * 1. classifyText 子串定位（姓名 group / 身份证标签后值 / 地址 / 「号码」防误命中）
 * 2. shrinkRectToMatch 纯函数（localOCR 收缩，与后端 shrink_rect_to_match 一致）
 * 3. 文本掩码语义（group 模式只掩码值，标签保留）
 */

import { describe, it, expect } from 'vitest'
import { classifyText, applyMask, DEFAULT_PATTERNS } from '../src/utils/sensitivePatterns'
import { shrinkRectToMatch } from '../src/utils/localOCR'

describe('classifyText 子串定位（只打码内容不打标签）', () => {
  it('姓名：只定位人名，不含标签（group=1）', () => {
    const s = classifyText('姓名：袁润熙')
    expect(s?.type).toBe('姓名')
    expect(s?.matched_text).toBe('袁润熙')
    expect(s?.match_start).toBe(3)
    expect(s?.match_end).toBe(6)
  })

  it('姓名 + 空格分隔（PaddleOCR/Tesseract 常见输出）', () => {
    const s = classifyText('姓名 袁润熙')
    expect(s?.type).toBe('姓名')
    expect(s?.matched_text).toBe('袁润熙')
    expect(s?.match_start).toBe(3)
    expect(s?.match_end).toBe(6)
  })

  it('姓名 无分隔符同行', () => {
    const s = classifyText('姓名袁润熙')
    expect(s?.type).toBe('姓名')
    expect(s?.matched_text).toBe('袁润熙')
    expect(s?.match_start).toBe(2)
  })

  it('身份证：号码在标签后，start 指向号码（不含标签）', () => {
    const s = classifyText('公民身份号码321324200608290077')
    expect(s?.type).toBe('身份证号')
    expect(s?.matched_text).toBe('321324200608290077')
    expect(s?.match_start).toBe(6)
    expect(s?.match_end).toBe(24)
  })

  it('身份证标签行不误命中地址（号(?!码) 修复）', () => {
    expect(classifyText('公民身份号码')).toBeNull()
    expect(classifyText('身份号码')).toBeNull()
  })

  it('纯标签行不误伤', () => {
    expect(classifyText('性别 男')).toBeNull()
    expect(classifyText('民族 汉')).toBeNull()
    expect(classifyText('出生')).toBeNull()
  })

  it('地址：只定位地址值（从「省」字起），标签保留', () => {
    const s = classifyText('住址：江苏省泗洪县青阳镇人民南路10号')
    expect(s?.type).toBe('家庭住址')
    expect(s?.matched_text.startsWith('省')).toBe(true)
    expect(s?.match_start).toBe(5)
    expect('住址：').not.toBe(s?.matched_text)
  })
})

describe('shrinkRectToMatch（localOCR 收缩，对齐后端）', () => {
  const rect = { x: 100, y: 200, w: 240, h: 30 }

  it('整行即值不收缩', () => {
    expect(shrinkRectToMatch(rect, '321324200608290077', 0, 18)).toEqual(rect)
  })

  it('标签+值同行 → 只收缩到值', () => {
    const got = shrinkRectToMatch(rect, '姓名袁润熙', 2, 5)
    expect(got.x).toBe(100 + Math.round(240 * 2 / 5)) // 196
    expect(got.w).toBe(Math.max(1, Math.round(240 * 3 / 5))) // 144
    expect(got.y).toBe(200)
    expect(got.h).toBe(30)
  })

  it('身份证标签+号码 → 收缩到号码', () => {
    const got = shrinkRectToMatch(rect, '公民身份号码321324200608290077', 6, 24)
    expect(got.x).toBe(100 + Math.round(240 * 6 / 24)) // 160
    expect(got.w).toBe(Math.round(240 * 18 / 24)) // 180
  })

  it('边界安全（越界/空文本/无效区间原样返回）', () => {
    expect(shrinkRectToMatch(rect, 'abc', -1, 2)).toEqual(rect)
    expect(shrinkRectToMatch(rect, 'abc', 0, 99)).toEqual(rect)
    expect(shrinkRectToMatch(rect, '', 0, 0)).toEqual(rect)
    expect(shrinkRectToMatch(rect, 'abc', 2, 2)).toEqual(rect)
  })
})

describe('文本掩码语义（group 模式只掩码值，标签保留）', () => {
  it('「姓名：袁润熙」→ 掩码后为「姓名：███」', () => {
    const text = '姓名：袁润熙'
    const s = classifyText(text)!
    const mp = DEFAULT_PATTERNS.find(p => p.type === s.type)!
    const masked = applyMask(s.matched_text, mp.keepFirst, mp.keepLast, mp.maskChar)
    const result = text.slice(0, s.match_start) + masked + text.slice(s.match_end)
    expect(result).toBe('姓名：███')
  })

  it('「公民身份号码3213…」→ 标签保留、号码全掩码', () => {
    const text = '公民身份号码321324200608290077'
    const s = classifyText(text)!
    const mp = DEFAULT_PATTERNS.find(p => p.type === s.type)!
    const masked = applyMask(s.matched_text, mp.keepFirst, mp.keepLast, mp.maskChar)
    const result = text.slice(0, s.match_start) + masked + text.slice(s.match_end)
    expect(result.startsWith('公民身份号码')).toBe(true)
    expect(result.slice(6)).not.toContain('321324200608290077')
  })
})
