import { describe, it, expect } from 'vitest'
import { classifyComplexity } from '../src/utils/imageComplexity'

describe('classifyComplexity 识别模式分流引导', () => {
  it('网格线多（表格）→ complex，推荐精准增强', () => {
    const r = classifyComplexity(0.1, 0.08)
    expect(r.level).toBe('complex')
    expect(r.reason).toContain('推荐精准增强')
  })

  it('边缘密集（内容多/小字）→ complex', () => {
    expect(classifyComplexity(0.2, 0.001).level).toBe('complex')
  })

  it('中等密度 → medium', () => {
    expect(classifyComplexity(0.08, 0.001).level).toBe('medium')
  })

  it('简单（大字/截图）→ simple，两种模式都可用', () => {
    const r = classifyComplexity(0.02, 0.001)
    expect(r.level).toBe('simple')
  })
})
