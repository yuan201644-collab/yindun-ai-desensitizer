/**
 * 「隐盾」上下文关键词增强识别（规则正则 + 上下文语义 双通道）
 *
 * NER 双引擎（模型体积/端侧约束）太重，用轻量规则上下文关键词做等价增强：
 * 1. 风险升级：命中框附近出现同类上下文关键词（如"邮箱""单号"）→ 语义确认并提升风险等级
 * 2. 上下文补漏：捕捉正则规则抓不到的结构化隐私（"姓名：张三" "微信号：abc12345" "QQ：123456789"）
 * 纯函数、零外部依赖、端侧可跑。
 */

export type RiskLevel = 'high' | 'medium' | 'low'

export interface SpanLike {
  start: number
  end: number
  type: string
  category: string
  riskLevel: RiskLevel
  matchText: string
  maskChar: string
  /** 上下文关键词语义确认标记 */
  contextConfirmed?: boolean
}

/** 每类敏感信息的确认关键词：同类别关键词出现在命中附近 → 语义确认 */
export const CONTEXT_KEYWORDS: Record<string, string[]> = {
  identity: ['身份证', '证件', '护照', '编号', 'id', 'ID'],
  contact: ['手机', '电话', '联系电话', '号码', '联系', '拨打', '邮箱', '邮件', 'tel', '手机号', '手机号码'],
  finance: ['银行卡', '卡号', '开户', '账户', '银行', '信用卡', '储蓄卡'],
  location: ['地址', '住址', '收货地址', '家庭住址', '住所', '街道', '小区', '现居'],
  logistics: ['快递', '单号', '运单', '物流', '包裹', '订单号'],
  network: ['微信', 'QQ', '账号', 'username', '昵称'],
  social: ['姓名', '名字', '称呼', '性别'],
}

interface CaptureRule {
  type: string
  category: string
  riskLevel: RiskLevel
  pattern: RegExp
  group: number
  maskChar: string
}

/** 上下文补漏：正则规则抓不到、但上下文明确指向的结构化隐私 */
const CAPTURE_RULES: CaptureRule[] = [
  {
    type: '姓名',
    category: 'social',
    riskLevel: 'high',
    maskChar: '█',
    // 要求关键词后带分隔符/连接词，避免把"姓名栏填写"这类普通文本误当姓名
    pattern: /(?:姓名|名字|收件人|户名)(?:[:：\s]+|[为是叫][:：\s]*)([一-龥]{2,4})/g,
    group: 1,
  },
  {
    type: '微信号',
    category: 'network',
    riskLevel: 'medium',
    maskChar: '█',
    pattern: /(?:微信号?|微信)[:：\s]+([A-Za-z][A-Za-z0-9_-]{4,19})/g,
    group: 1,
  },
  {
    type: 'QQ号',
    category: 'network',
    riskLevel: 'medium',
    maskChar: '█',
    pattern: /(?:QQ号?|企鹅号)[:：\s]+([1-9]\d{4,10})/g,
    group: 1,
  },
]

const RISK_ORDER: RiskLevel[] = ['low', 'medium', 'high']

function upgradeRisk(r: RiskLevel): RiskLevel {
  const i = RISK_ORDER.indexOf(r)
  return i < RISK_ORDER.length - 1 ? RISK_ORDER[i + 1] : r
}

function overlaps(aStart: number, aEnd: number, bStart: number, bEnd: number): boolean {
  return aStart < bEnd && bStart < aEnd
}

/**
 * 上下文增强：返回新的 span 列表（已升级风险 + 补漏捕捉 + 按位置排序）
 * @param text 原文
 * @param spans 正则/自定义词已识别的 span
 * @param windowSize 风险升级的上下文窗口（命中前后字符数）
 */
export function enhanceContext(text: string, spans: SpanLike[], windowSize = 20): SpanLike[] {
  const out = spans.map(s => ({ ...s }))

  // 1) 风险升级：命中窗口内出现同类上下文关键词 → 语义确认 + 升一级
  for (const s of out) {
    const kw = CONTEXT_KEYWORDS[s.category]
    if (!kw) continue
    const start = Math.max(0, s.start - windowSize)
    const end = Math.min(text.length, s.end + windowSize)
    if (kw.some(k => text.slice(start, end).includes(k))) {
      s.riskLevel = upgradeRisk(s.riskLevel)
      s.contextConfirmed = true
    }
  }

  // 2) 上下文补漏：捕捉 姓名/微信号/QQ 等结构隐私（不与已有命中重叠）
  for (const rule of CAPTURE_RULES) {
    const regex = new RegExp(rule.pattern.source, rule.pattern.flags)
    let m: RegExpExecArray | null
    while ((m = regex.exec(text)) !== null) {
      const val = m[rule.group]
      if (!val) continue
      const start = m.index + m[0].indexOf(val)
      const end = start + val.length
      const covered = out.some(s => overlaps(s.start, s.end, start, end))
      if (!covered) {
        out.push({
          start,
          end,
          type: rule.type,
          category: rule.category,
          riskLevel: rule.riskLevel,
          matchText: val,
          maskChar: rule.maskChar,
          contextConfirmed: true,
        })
      }
    }
  }

  return out.sort((a, b) => a.start - b.start)
}
