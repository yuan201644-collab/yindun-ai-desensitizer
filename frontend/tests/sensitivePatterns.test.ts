import { describe, it, expect } from 'vitest'
import { DEFAULT_PATTERNS, applyMask } from '../src/utils/sensitivePatterns'

describe('applyMask', () => {
  it('masks middle digits keeping first 3 and last 4', () => {
    expect(applyMask('13812345678', 3, 4, '*')).toBe('138****5678')
  })

  it('fully masks short text', () => {
    expect(applyMask('abc', 3, 4, '*')).toBe('***')
  })

  it('email keeps first char and @ suffix', () => {
    expect(applyMask('test@example.com', 1, -1, '*')).toBe('t***@example.com')
  })
})

describe('DEFAULT_PATTERNS 模式库', () => {
  it('检测并掩码身份证号（保留前3后4）', () => {
    const p = DEFAULT_PATTERNS.find(x => x.type === '身份证号')!
    const raw = '11010119900101123X'
    const masked = raw.replace(p.pattern, m => applyMask(m, p.keepFirst, p.keepLast))
    expect(masked).toBe('110***********123X')
  })

  it('检测并掩码手机号（保留前3后4）', () => {
    const p = DEFAULT_PATTERNS.find(x => x.type === '手机号')!
    const masked = '13812345678'.replace(p.pattern, m => applyMask(m, p.keepFirst, p.keepLast))
    expect(masked).toBe('138****5678')
  })
})
