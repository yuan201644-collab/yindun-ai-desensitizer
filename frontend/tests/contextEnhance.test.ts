import { describe, it, expect } from 'vitest'
import { enhanceContext, CONTEXT_KEYWORDS, type SpanLike } from '../src/utils/contextEnhance'

function span(start: number, end: number, type: string, category: string, riskLevel: SpanLike['riskLevel']): SpanLike {
  return { start, end, type, category, riskLevel, matchText: 'x'.repeat(end - start), maskChar: '*' }
}

describe('CONTEXT_KEYWORDS', () => {
  it('每个敏感类别都有确认关键词', () => {
    for (const cat of ['identity', 'contact', 'finance', 'location', 'logistics', 'network', 'social']) {
      expect(CONTEXT_KEYWORDS[cat].length).toBeGreaterThan(0)
    }
  })
})

describe('enhanceContext 风险升级', () => {
  it('邮箱命中附近出现"邮箱"关键词 → 升为 high 且语义确认', () => {
    const text = '联系邮箱abc@x.com，谢谢。'
    const at = text.indexOf('abc@x.com')
    const out = enhanceContext(text, [span(at, at + 9, '电子邮箱', 'contact', 'medium')])
    expect(out[0].riskLevel).toBe('high')
    expect(out[0].contextConfirmed).toBe(true)
  })
  it('快递单号附近出现"单号" → 升为 high', () => {
    const text = '快递单号YT1234567890123'
    const at = text.indexOf('YT1234567890123')
    const out = enhanceContext(text, [span(at, at + 16, '快递单号', 'logistics', 'medium')])
    expect(out[0].riskLevel).toBe('high')
  })
  it('已是 high 的命中遇关键词不降级、标记确认', () => {
    const text = '手机号13800138000'
    const at = text.indexOf('13800138000')
    const out = enhanceContext(text, [span(at, at + 11, '手机号', 'contact', 'high')])
    expect(out[0].riskLevel).toBe('high')
    expect(out[0].contextConfirmed).toBe(true)
  })
  it('附近无关键词 → 风险不变、不标记确认', () => {
    const text = '随机数字12345678出现'
    const at = text.indexOf('12345678')
    const out = enhanceContext(text, [span(at, at + 8, '固定电话', 'contact', 'medium')])
    expect(out[0].riskLevel).toBe('medium')
    expect(out[0].contextConfirmed).toBeUndefined()
  })
})

describe('enhanceContext 上下文补漏', () => {
  it('捕捉"姓名：张三"（high）', () => {
    const text = '收货人姓名：张三，电话13800138000'
    const out = enhanceContext(text, [])
    const name = out.find(s => s.type === '姓名')
    expect(name).toBeDefined()
    expect(name!.matchText).toBe('张三')
    expect(name!.riskLevel).toBe('high')
    expect(name!.contextConfirmed).toBe(true)
  })
  it('捕捉"收件人：王小明"与"户名：李四"', () => {
    const t1 = '收件人：王小明'
    const n1 = enhanceContext(t1, []).find(s => s.type === '姓名')
    expect(n1!.matchText).toBe('王小明')
    const t2 = '开户行中国工商银行，户名：李四'
    const n2 = enhanceContext(t2, []).find(s => s.type === '姓名')
    expect(n2!.matchText).toBe('李四')
  })
  it('捕捉"微信号：abc12345"（medium）', () => {
    const text = '我的微信号：abc12345，欢迎添加'
    const out = enhanceContext(text, [])
    const w = out.find(s => s.type === '微信号')
    expect(w).toBeDefined()
    expect(w!.matchText).toBe('abc12345')
    expect(w!.riskLevel).toBe('medium')
  })
  it('捕捉"QQ号：123456789"（medium）', () => {
    const text = '加我QQ号：123456789'
    const q = enhanceContext(text, []).find(s => s.type === 'QQ号')
    expect(q!.matchText).toBe('123456789')
    expect(q!.riskLevel).toBe('medium')
  })
  it('普通文本不误捕：无分隔符的"姓名栏填写"不产出姓名框', () => {
    const text = '请在姓名栏填写完整信息，谢谢'
    const out = enhanceContext(text, [])
    expect(out.filter(s => s.type === '姓名')).toHaveLength(0)
  })
  it('"微信"单独出现无 ID 值 → 不产出微信号框', () => {
    const out = enhanceContext('请添加我的微信，谢谢', [])
    expect(out.filter(s => s.type === '微信号')).toHaveLength(0)
  })
  it('姓名已被其他命中覆盖 → 不重复添加', () => {
    // "张三"已被当作 custom span 覆盖时，不重复捕姓名
    const text = '姓名：张三'
    const at = text.indexOf('张三')
    const out = enhanceContext(text, [span(at, at + 2, '自定义', 'custom', 'high')])
    expect(out.filter(s => s.type === '姓名')).toHaveLength(0)
  })
})

describe('enhanceContext 输出排序', () => {
  it('返回的 span 按位置升序', () => {
    const text = '姓名：张三，手机13800138000'
    const phoneAt = text.indexOf('13800138000')
    const out = enhanceContext(text, [span(phoneAt, phoneAt + 11, '手机号', 'contact', 'high')])
    for (let i = 1; i < out.length; i++) expect(out[i].start).toBeGreaterThanOrEqual(out[i - 1].start)
  })
})

describe('enhanceContext 端到端样例', () => {
  it('快递单样例：同时补漏收件人姓名 + 单号被上下文升级', () => {
    const text = '【快递单】收件人：王小明，电话13812345678，单号：YT1234567890123'
    const ytAt = text.indexOf('YT1234567890123')
    const out = enhanceContext(text, [span(ytAt, ytAt + 16, '快递单号', 'logistics', 'medium')])
    const name = out.find(s => s.type === '姓名')
    const tn = out.find(s => s.type === '快递单号')
    expect(name!.matchText).toBe('王小明')
    expect(tn!.riskLevel).toBe('high') // "单号"上下文升级
  })
})
