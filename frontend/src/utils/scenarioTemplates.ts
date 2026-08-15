/**
 * ================================================================
 * 「隐盾」场景模板库
 * ================================================================
 * 场景模板 = 按使用场景预设的检测/脱敏策略。
 * - 文本流：activeTypes 控制只检测哪些敏感类型（空 = 全部）
 * - 图片流：preferTypes 控制自动选中哪些类型 + defaultMethod/intensity
 * 在此添加新的场景模板。
 */

export type DesensitizeMethod = 'pixelate' | 'gaussian' | 'irreversible'

export interface ScenarioTemplate {
  id: string
  name: string
  icon: string
  desc: string
  /** ⭐ 打码范围人话提示（分流卡片展示，让用户知道本场景会处理哪些类型） */
  scopeLabel?: string
  /** 文本流：只启用这些敏感类型检测（空 = 全部） */
  activeTypes?: string[]
  /** 图片流：自动选中这些敏感类型（空 = 按风险等级全选） */
  preferTypes?: string[]
  /** 图片流默认脱敏算法 */
  defaultMethod?: DesensitizeMethod
  defaultIntensity?: number
}

export const SCENARIO_TEMPLATES: ScenarioTemplate[] = [
  {
    id: 'general',
    name: '通用',
    icon: '🌐',
    desc: '识别所有敏感信息',
    scopeLabel: '所有敏感类型',
    defaultMethod: 'pixelate',
    defaultIntensity: 0.8,
  },
  {
    id: 'express',
    name: '快递单',
    icon: '📦',
    desc: '只打码手机号/固话/地址/单号，晒单不泄露客户隐私',
    scopeLabel: '手机号 · 固话 · 地址 · 快递单号',
    activeTypes: ['手机号', '固定电话', '家庭住址', '快递单号'],
    preferTypes: ['手机号', '固定电话', '家庭住址', '快递单号'],
    defaultMethod: 'irreversible',
    defaultIntensity: 0.9,
  },
  {
    id: 'chat',
    name: '聊天记录',
    icon: '🗨️',
    desc: '只打码手机号/邮箱/地址，截图分享更安全',
    scopeLabel: '手机号 · 邮箱 · 地址',
    activeTypes: ['手机号', '电子邮箱', '家庭住址'],
    preferTypes: ['手机号', '电子邮箱', '家庭住址'],
    defaultMethod: 'gaussian',
    defaultIntensity: 0.85,
  },
  {
    id: 'idcard',
    name: '证件照',
    icon: '🪪',
    desc: '身份证/护照/银行卡等强信息，全局高强脱敏',
    scopeLabel: '证件号 · 银行卡 · 姓名 · 出生日期 · 地址',
    activeTypes: ['身份证号', '护照号', '银行卡号', '家庭住址', '姓名', '出生日期'],
    preferTypes: ['身份证号', '护照号', '银行卡号', '家庭住址', '姓名', '出生日期'],
    defaultMethod: 'irreversible',
    defaultIntensity: 1.0,
  },
]

export function getTemplate(id: string): ScenarioTemplate {
  return SCENARIO_TEMPLATES.find(t => t.id === id) || SCENARIO_TEMPLATES[0]
}

/**
 * 文本流：按模板过滤应启用的模式。
 * @param patterns 完整模式列表（如 DEFAULT_PATTERNS）
 * @param template 场景模板
 * @returns 过滤后的模式列表
 */
export function filterPatternsByTemplate<T extends { type: string }>(
  patterns: T[],
  template: ScenarioTemplate
): T[] {
  if (!template.activeTypes || template.activeTypes.length === 0) return patterns
  return patterns.filter(p => template.activeTypes!.includes(p.type))
}
