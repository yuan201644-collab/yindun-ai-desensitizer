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

/**
 * ================================================================
 * 裸名 + 联系方式共现识别（「张三 电话138…」· 聊天场景）
 * ================================================================
 * 聊天记录里的姓名几乎都是裸出现（无「姓名：」前缀），纯正则/前缀标签捕不到。
 * 这里用一个强启发：名字与联系方式词/号码在同一邻窗口内出现，且名字首字是
 * 常见姓氏 —— 双约束压误报。「我们公司电话…」「今天张三…」这类不会被误当姓名。
 */

/** 常见单姓（用于裸名识别的首字强约束） */
const SURNAMES_SINGLE = new Set(
  '王李张刘陈杨赵黄周吴徐孙胡朱高林何郭马罗梁宋郑谢韩唐冯于董萧程曹袁邓许傅沈曾彭吕苏卢蒋蔡贾丁魏薛叶阎余潘杜戴夏钟汪田任姜范方石姚谭廖邹熊金陆郝孔白崔康毛邱秦江史顾侯邵孟龙万段钱汤尹黎易常武乔贺赖龚文'.split('')
)
/** 常见复姓 */
const SURNAMES_DOUBLE = ['欧阳', '司马', '上官', '诸葛', '东方', '夏侯', '皇甫', '尉迟', '公孙', '慕容', '司徒', '司空', '澹台', '端木', '令狐', '南宫']
/** 姓名尾缀/虚词（「张三的号码」剔除「的」；「老先生电话」剔除「先生」） */
const NAME_TAIL_GARBAGE = new Set(['的', '是', '叫', '了', '在', '给', '也', '还', '都', '被', '把', '就'])
const NAME_TAIL_DOUBLE = new Set(['先生', '女士', '老师', '同学', '老板', '同事', '朋友', '经理'])
/** 联系方式指示词（裸名的锚点：名字紧跟其后/其附近出现） */
const CONTACT_INDICATOR = /联系电话|手机号码|手机号|手机|联系方式|联系|电话|号码|拨打|call|tel/g

function isNameLike(name: string): boolean {
  if (name.length < 2 || name.length > 5) return false
  if (SURNAMES_SINGLE.has(name[0])) return true
  return SURNAMES_DOUBLE.some((s) => name.startsWith(s))
}

/** 中文/间隔符 */
function isHan(ch: string): boolean {
  const c = ch.codePointAt(0)!
  return (c >= 0x4e00 && c <= 0x9fa5) || ch === '·'
}
/** 空白或标点（名字与联系方式词之间允许夹这些「非语义字符」，但夹别的字则说明结构不对） */
const SPACE_OR_PUNCT = /[\s，。、；：！？""''（）…\-.，·]/

/**
 * 在主文本上捕捉「裸名 + 联系方式共现」的姓名 span。
 * @param text 原文
 * @param spans 已识别的 span（含 contact 类，也作为锚点）
 */
export function captureCooccurName(text: string, spans: SpanLike[]): SpanLike[] {
  const out = spans.map((s) => ({ ...s }))
  // 锚点1：联系方式指示词出现位置
  CONTACT_INDICATOR.lastIndex = 0
  const points: number[] = []
  let m: RegExpExecArray | null
  while ((m = CONTACT_INDICATOR.exec(text)) !== null) points.push(m.index)
  // 锚点2：已识别的联系方式 span（手机号/固话 …）
  for (const s of spans) if (s.category === 'contact') points.push(s.start)

  const WINDOW = 18 // 名字最多在指示词前这么远
  for (const P of points) {
    const win = Math.max(0, P - WINDOW)
    // 1) 从 P 往前剥掉名字后的「非语义字符」（空格/标点）
    let j = P
    while (j > win && j > 0 && SPACE_OR_PUNCT.test(text[j - 1])) j--
    // 2) 再剥名字尾部的虚词/称谓（「张三的」→「张三」）
    while (j > win && j > 0) {
      const two = text.slice(j - 2, j)
      const c2 = two.length === 2 && NAME_TAIL_DOUBLE.has(two)
      const c1 = NAME_TAIL_GARBAGE.has(text[j - 1])
      if (!c1 && !c2) break
      j -= (c2 ? 2 : 1)
    }
    // 3) 取紧邻往前的连续汉字块作为候选名
    let k = j
    while (k > win && isHan(text[k - 1])) k--
    const block = text.slice(k, j)
    if (!isNameLike(block)) continue
    const start = k
    const end = j
    if (out.some((s) => overlaps(s.start, s.end, start, end))) continue
    out.push({
      start,
      end,
      type: '姓名',
      category: 'social',
      riskLevel: 'high',
      matchText: block,
      maskChar: '█',
      contextConfirmed: true,
    })
  }
  return out.sort((a, b) => a.start - b.start)
}

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

  // 3) 上下文捕裸名：姓名 + 联系方式共现（聊天场景「张三 电话138…」）
  return captureCooccurName(text, out)
}
