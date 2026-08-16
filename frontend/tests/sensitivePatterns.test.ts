import { describe, it, expect } from 'vitest'
import { DEFAULT_PATTERNS, applyMask, classifyText } from '../src/utils/sensitivePatterns'

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

/** ⭐ 与后端 SENSITIVE_PATTERNS 对齐的必备类型（新增敏感类型需双端同步，此清单兜底） */
const SYNC_REQUIRED_TYPES = [
  '姓名', '出生日期', '身份证号', '手机号', '固定电话', '银行卡号',
  '电子邮箱', '家庭住址', '车牌号', '快递单号', '统一社会信用代码', '护照号',
]

describe('模式库前后端同步', () => {
  it('DEFAULT_PATTERNS 包含全部必备类型（与后端 SENSITIVE_PATTERNS 同步）', () => {
    const types = new Set(DEFAULT_PATTERNS.map(p => p.type))
    const missing = SYNC_REQUIRED_TYPES.filter(t => !types.has(t))
    expect(missing).toEqual([])
  })

  it('手机号命中「姓名紧贴手机号」且只定位号码（评估残留修复）', () => {
    const s = classifyText('柳予威18665533578')
    expect(s?.type).toBe('手机号')
    expect(s?.matched_text).toBe('18665533578')
    expect(s?.match_start).toBe(3)
  })

  it('手机号排除数字拼接', () => {
    expect(classifyText('12313800138000')?.matched_text).not.toBe('13800138000')
    expect(classifyText('138001380004567')?.matched_text).not.toBe('13800138000')
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

  it('检测并掩码统一社会信用代码（保留前3后4）', () => {
    const p = DEFAULT_PATTERNS.find(x => x.type === '统一社会信用代码')!
    const raw = '91310000MA1FL4XK9X'
    const masked = raw.replace(p.pattern, m => applyMask(m, p.keepFirst, p.keepLast))
    expect(masked).toBe('913***********XK9X')
  })

  it('统一社会信用代码模式不误配手机号', () => {
    const p = DEFAULT_PATTERNS.find(x => x.type === '统一社会信用代码')!
    const raw = '13812345678'
    expect(raw.replace(p.pattern, m => applyMask(m, p.keepFirst, p.keepLast))).toBe(raw)
  })

  it('模式库包含护照号条目', () => {
    const p = DEFAULT_PATTERNS.find(x => x.type === '护照号')!
    expect(p.category).toBe('identity')
    expect(p.riskLevel).toBe('high')
  })

  it('检测并掩码护照号（保留前2后2）', () => {
    const p = DEFAULT_PATTERNS.find(x => x.type === '护照号')!
    const masked = 'E12345678'.replace(p.pattern, m => applyMask(m, p.keepFirst, p.keepLast))
    expect(masked).toBe('E1*****78')
  })

  it('护照号模式不误配缺位数字', () => {
    const p = DEFAULT_PATTERNS.find(x => x.type === '护照号')!
    const raw = 'E1234567'
    expect(raw.replace(p.pattern, m => applyMask(m, p.keepFirst, p.keepLast))).toBe(raw)
  })

  it('护照号模式不误配嵌入字母数字串', () => {
    const p = DEFAULT_PATTERNS.find(x => x.type === '护照号')!
    const raw = 'AE12345678'
    expect(raw.replace(p.pattern, m => applyMask(m, p.keepFirst, p.keepLast))).toBe(raw)
  })

  it('模式库包含固定电话条目', () => {
    const p = DEFAULT_PATTERNS.find(x => x.type === '固定电话')!
    expect(p.category).toBe('contact')
    expect(p.riskLevel).toBe('medium')
    expect(p.keepFirst).toBe(3)
    expect(p.keepLast).toBe(4)
    expect(p.maskChar).toBe('*')
  })

  it('检测并掩码固定电话（带连字符，保留前3后4）', () => {
    const p = DEFAULT_PATTERNS.find(x => x.type === '固定电话')!
    const masked = '021-12345678'.replace(p.pattern, m => applyMask(m, p.keepFirst, p.keepLast))
    expect(masked).toBe('021*****5678')
  })

  it('检测并掩码固定电话（无连字符）', () => {
    const p = DEFAULT_PATTERNS.find(x => x.type === '固定电话')!
    const masked = '02112345678'.replace(p.pattern, m => applyMask(m, p.keepFirst, p.keepLast))
    expect(masked).toBe('021****5678')
  })

  it('固定电话模式不误配手机号', () => {
    const p = DEFAULT_PATTERNS.find(x => x.type === '固定电话')!
    const raw = '13812345678'
    expect(raw.replace(p.pattern, m => applyMask(m, p.keepFirst, p.keepLast))).toBe(raw)
  })

  it('固定电话模式不误配短号码', () => {
    const p = DEFAULT_PATTERNS.find(x => x.type === '固定电话')!
    const raw = '0211234'
    expect(raw.replace(p.pattern, m => applyMask(m, p.keepFirst, p.keepLast))).toBe(raw)
  })

  it('固定电话模式不误配含 0 的手机号', () => {
    const p = DEFAULT_PATTERNS.find(x => x.type === '固定电话')!
    const raw = '13901234567'
    expect(raw.replace(p.pattern, m => applyMask(m, p.keepFirst, p.keepLast))).toBe(raw)
  })
})
