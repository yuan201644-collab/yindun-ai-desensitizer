/**
 * ================================================================
 * 「隐盾」占位符脱敏（AI 对话前置场景）
 * ================================================================
 * 普通掩码（███）不可还原；发给大模型前需要"可还原的脱敏"：
 *   敏感值 → 【类型N】占位符 → 发给 AI → 拿到回复后 → 占位符还原为原文
 * 纯函数，可单测。
 */

export interface PlaceholderSpan {
  start: number
  end: number
  type: string
  matchText: string
}

/**
 * 占位符脱敏：把敏感值替换为【类型N】占位符。
 * @param text 原始文本
 * @param spans 敏感区间（按位置升序即可，内部从后往前替换避免偏移）
 * @returns masked 占位符文本；mapping 占位符 → 原文 的映射表
 */
export function buildPlaceholderMask(
  text: string,
  spans: PlaceholderSpan[]
): { masked: string; mapping: Record<string, string> } {
  const counts: Record<string, number> = {}
  const mapping: Record<string, string> = {}

  // 第一遍：按 start 升序编号（【类型1】= 文本中第一个出现的该类型），跳过非法 span
  const numbered: Array<{ span: PlaceholderSpan; ph: string }> = []
  for (const s of [...spans].sort((a, b) => a.start - b.start)) {
    if (s.start < 0 || s.end > text.length || s.end <= s.start) continue
    counts[s.type] = (counts[s.type] || 0) + 1
    numbered.push({ span: s, ph: `【${s.type}${counts[s.type]}】` })
  }

  // 第二遍：从后往前替换（占位符长度 ≤ 原文长度，前面的 start 不受影响）
  let result = text
  for (const { span, ph } of [...numbered].sort((a, b) => b.span.start - a.span.start)) {
    mapping[ph] = span.matchText
    result = result.slice(0, span.start) + ph + result.slice(span.end)
  }
  return { masked: result, mapping }
}

/**
 * 还原：把文本中的占位符替换回原文。
 * @param text AI 回复（可能包含占位符）
 * @param mapping buildPlaceholderMask 返回的映射表
 */
export function restorePlaceholders(text: string, mapping: Record<string, string>): string {
  let result = text
  for (const [ph, original] of Object.entries(mapping)) {
    result = result.split(ph).join(original)
  }
  return result
}
