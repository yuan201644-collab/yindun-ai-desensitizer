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
}

/** ⚠️ 可修改扩展：在此数组添加新的敏感信息模式 */
export const DEFAULT_PATTERNS: SensitivePattern[] = [
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
    pattern: /1[3-9]\d{9}/g,
    category: 'contact',
    riskLevel: 'high',
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
    pattern: /(?:省|市|区|县|镇|乡|村|路|街|巷|号|栋|单元|室|楼)\S{0,20}/g,
    category: 'location',
    riskLevel: 'high',
    keepFirst: 0,
    keepLast: 0,
    maskChar: '█',
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

  return text.slice(0, keepFirst) + maskChar.repeat(midLen) + text.slice(-keepLast)
}
