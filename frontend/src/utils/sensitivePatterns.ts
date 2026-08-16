/**
 * ================================================================
 * 「隐盾」前端敏感信息模式库
 * ================================================================
 * 用于前端本地文本脱敏（纯浏览器端，不上传服务器）。
 * 可在此文件中添加/修改/删除敏感模式。
 */

export interface SensitivePattern {
  type: string
  pattern: RegExp
  category: string
  riskLevel: 'high' | 'medium' | 'low'
  /** 掩码保留前 N 位 */
  keepFirst: number
  /** 掩码保留后 N 位 */
  keepLast: number
  /** 掩码字符 */
  maskChar: string
  /** ⭐ 敏感值取第 N 捕获组（如「姓名：袁润熙」只取「袁润熙」，标签不打码/不掩码） */
  group?: number
}

/** ⚠️ 可修改扩展：在此数组添加新的敏感信息模式 */
export const DEFAULT_PATTERNS: SensitivePattern[] = [
  {
    type: '出生日期',
    pattern: /(?:出生)[:：\s]*(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日?)/g,
    category: 'identity',
    riskLevel: 'medium',
    keepFirst: 0,
    keepLast: 0,
    maskChar: '█',
    group: 1,
  },
  {
    type: '姓名',
    pattern: /(?:姓名|名字)[:：\s]*([\u4e00-\u9fa5·]{2,4})(?![0-9])/g,
    category: 'identity',
    riskLevel: 'high',
    keepFirst: 0,
    keepLast: 0,
    maskChar: '█',
    group: 1,
  },
  {
    type: '身份证号',
    pattern: /[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]/g,
    category: 'identity',
    riskLevel: 'high',
    keepFirst: 3,
    keepLast: 4,
    maskChar: '*',
  },
  {
    type: '手机号',
    // ⭐ 前后视排除数字拼接；中文前缀（姓名紧贴手机号）仍可命中（与后端对齐）
    pattern: /(?<![0-9])1[3-9]\d{9}(?![0-9])/g,
    category: 'contact',
    riskLevel: 'high',
    keepFirst: 3,
    keepLast: 4,
    maskChar: '*',
  },
  {
    type: '固定电话',
    pattern: /0\d{2,3}-?\d{7,8}/g,
    category: 'contact',
    riskLevel: 'medium',
    keepFirst: 3,
    keepLast: 4,
    maskChar: '*',
  },
  {
    type: '统一社会信用代码',
    pattern: /[0-9A-HJ-NPQRTUWXY]{2}\d{6}[0-9A-HJ-NPQRTUWXY]{10}/g,
    category: 'identity',
    riskLevel: 'high',
    keepFirst: 3,
    keepLast: 4,
    maskChar: '*',
  },
  {
    type: '护照号',
    pattern: /(?<![A-Za-z0-9])[EG]\d{8}(?![A-Za-z0-9])/g,
    category: 'identity',
    riskLevel: 'high',
    keepFirst: 2,
    keepLast: 2,
    maskChar: '*',
  },
  {
    type: '银行卡号',
    pattern: /(?:62|60|9\d|5[1-5]|4\d)\d{14,17}/g,
    category: 'finance',
    riskLevel: 'high',
    keepFirst: 4,
    keepLast: 4,
    maskChar: '*',
  },
  {
    type: '电子邮箱',
    pattern: /[\w.-]+@[\w.-]+\.\w{2,}/g,
    category: 'contact',
    riskLevel: 'medium',
    keepFirst: 1,
    keepLast: -1, // -1 表示保留 @ 及之后
    maskChar: '*',
  },
  {
    type: '家庭住址',
    // ⭐ 显式标签前缀（住址/地址/户籍/籍贯等，可选）——标签不进敏感值；
    //   强位置词（省/市/县/镇/乡/村/路/街/道/巷）：1-4 汉字前缀即可；
    //   弱位置词（区/号/栋/室/楼/单元）：要求 2-6 汉字前缀（挡「区图书馆」单字触发）；
    //   号(?!码) 排除「号码/单号」；后缀不吞标点；group=1 → 只打码地址内容（与后端同串）
    pattern: /(?:家庭住址|常住地址|现住地|住址|地址|户籍|籍贯)?((?:[\u4e00-\u9fa5]{1,4}(?:省|市|县|镇|乡|村|路|街|道|巷)|[\u4e00-\u9fa5]{2,6}(?:区|栋|室|楼|单元))[\u4e00-\u9fa5\d]{0,20})/g,
    category: 'location',
    riskLevel: 'high',
    keepFirst: 0,
    keepLast: 0,
    maskChar: '█',
    group: 1,
  },
  {
    type: '车牌号',
    pattern: /[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤川青藏琼宁][A-Z][A-HJ-NP-Z0-9]{4,5}[A-HJ-NP-Z0-9挂学警港澳]/g,
    category: 'identity',
    riskLevel: 'medium',
    keepFirst: 2,
    keepLast: 1,
    maskChar: '*',
  },
  {
    type: '快递单号',
    pattern: /(?:SF|YT|ZTO|STO|YUNDA|JD|DB|DEPPON|EMS)\d{10,18}/g,
    category: 'logistics',
    riskLevel: 'medium',
    keepFirst: 2,
    keepLast: 4,
    maskChar: '*',
  },
]

/**
 * 应用字符掩码
 * @param text 原始文本
 * @param keepFirst 保留前 N 位
 * @param keepLast 保留后 N 位 (-1 特殊处理)
 * @param maskChar 掩码字符
 */
export function applyMask(
  text: string,
  keepFirst: number,
  keepLast: number,
  maskChar: string = '*'
): string {
  if (text.length <= keepFirst + Math.abs(keepLast)) {
    return maskChar.repeat(text.length)
  }

  if (keepLast === -1) {
    // 特殊：邮箱 — 保留首字符和 @ 之后
    const atIdx = text.indexOf('@')
    if (atIdx > 0) {
      return text[0] + maskChar.repeat(atIdx - 1) + text.slice(atIdx)
    }
    return maskChar.repeat(text.length)
  }

  const midLen = text.length - keepFirst - keepLast
  if (midLen <= 0) return maskChar.repeat(text.length)

  // ⭐ keepLast=0 时 text.slice(-0) === slice(0)（整个字符串），会尾部残留原文——显式处理
  const tail = keepLast > 0 ? text.slice(-keepLast) : ''
  return text.slice(0, keepFirst) + maskChar.repeat(midLen) + tail
}

/** 敏感对象语义标签（对齐后端 SENSITIVE_OBJECT_LABELS） */
export const OBJECT_LABELS: Record<string, string> = {
  identity: '🪪 证件',
  contact: '📱 联系方式',
  finance: '💳 银行卡',
  location: '📍 地址',
  logistics: '📦 快递单',
  network: '🌐 网络',
  social: '👤 社交账号',
}

export interface SensitiveMatch {
  type: string
  category: string
  risk_level: 'high' | 'medium' | 'low'
  matched_text: string
  object_label: string
  /** ⭐ 敏感子串在整行文本中的字符区间（图片侧据此只打码内容，标签保留） */
  match_start: number
  match_end: number
}

/** ⭐ 带捕获组位置的 exec 结果（lib 版本不含 ES2022 indices 时的类型扩展） */
export type RegExpExecWithIndices = RegExpExecArray & {
  indices?: Array<[number, number] | undefined>
}

/** 对一段文本做敏感分类，返回第一个命中的类型（无命中返回 null）
 *  ⭐ 用 RegExp `d` flag 取捕获组位置（group 模式时 match 起点指向值部分） */
export function classifyText(text: string): SensitiveMatch | null {
  for (const p of DEFAULT_PATTERNS) {
    // 去掉 g 标志，避免 RegExp.lastIndex 跨调用残留；加 d 标志以读取捕获组位置
    const base = p.pattern.flags.replace('g', '')
    const regex = new RegExp(p.pattern.source, base.includes('d') ? base : base + 'd')
    const m = regex.exec(text) as RegExpExecWithIndices | null
    if (m) {
      const gi = p.group ?? 0
      const matched = m[gi] ?? m[0]
      let start = m.index
      let end = m.index + m[0].length
      if (m.indices?.[gi]) {
        start = m.indices[gi][0]
        end = m.indices[gi][1]
      }
      return {
        type: p.type,
        category: p.category,
        risk_level: p.riskLevel,
        matched_text: matched,
        object_label: OBJECT_LABELS[p.category] || p.type,
        match_start: start,
        match_end: end,
      }
    }
  }
  return null
}

export interface CustomWordMatch { start: number; end: number; text: string; type: string }

/**
 * 在文本中查找自定义敏感词的所有出现（去重、可单测）
 * - 逐词 indexOf 扫描，跳过与已命中词重叠的位置（避免同一处重复框选）
 * - 空词/空白词忽略
 * - 自定义词不受内置场景模板 activeTypes 过滤影响（用户显式指定的词恒生效）
 */
export function matchCustomWords(text: string, customWords: string[]): CustomWordMatch[] {
  const results: CustomWordMatch[] = []
  for (const rawWord of customWords) {
    const word = rawWord.trim()
    // 空词/空白词忽略
    if (!word) continue
    let fromIndex = 0
    while (fromIndex <= text.length) {
      const idx = text.indexOf(word, fromIndex)
      if (idx === -1) break
      const start = idx
      const end = idx + word.length
      // 跳过与已命中词重叠的位置（避免同一处重复框选）
      const isOverlapping = results.some(r => start < r.end && end > r.start)
      if (!isOverlapping) {
        results.push({ start, end, text: word, type: '自定义' })
      }
      // 跳过当前命中，从 end 继续扫描，避免同一词重复命中
      fromIndex = end
    }
  }
  results.sort((a, b) => a.start - b.start)
  return results
}
