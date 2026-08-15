/**
 * 占位符脱敏测试（AI 对话前置场景）
 * 覆盖：buildPlaceholderMask（占位符生成/映射/偏移安全）+ restorePlaceholders（还原）
 */

import { describe, it, expect } from 'vitest'
import { buildPlaceholderMask, restorePlaceholders } from '../src/utils/placeholderMask'

describe('buildPlaceholderMask', () => {
  it('单类型多值 → 【类型N】递增', () => {
    const text = 'A13800138000B13912345678C'
    const spans = [
      { start: 1, end: 12, type: '手机号', matchText: '13800138000' },
      { start: 13, end: 24, type: '手机号', matchText: '13912345678' },
    ]
    const { masked, mapping } = buildPlaceholderMask(text, spans)
    expect(masked).toBe('A【手机号1】B【手机号2】C')
    expect(mapping).toEqual({ '【手机号1】': '13800138000', '【手机号2】': '13912345678' })
  })

  it('多类型混合', () => {
    // 姓名：张三(3-5)，手机13800138000(8-19)
    const text = '姓名：张三，手机13800138000'
    const spans = [
      { start: 3, end: 5, type: '姓名', matchText: '张三' },
      { start: 8, end: 19, type: '手机号', matchText: '13800138000' },
    ]
    const { masked, mapping } = buildPlaceholderMask(text, spans)
    expect(masked).toBe('姓名：【姓名1】，手机【手机号1】')
    expect(mapping['【姓名1】']).toBe('张三')
    expect(mapping['【手机号1】']).toBe('13800138000')
  })

  it('从后往前替换不偏移（多个短 span）', () => {
    const text = '北京上海广州'
    const spans = [
      { start: 0, end: 2, type: '地点', matchText: '北京' },
      { start: 2, end: 4, type: '地点', matchText: '上海' },
      { start: 4, end: 6, type: '地点', matchText: '广州' },
    ]
    const { masked, mapping } = buildPlaceholderMask(text, spans)
    expect(masked).toBe('【地点1】【地点2】【地点3】')
    expect(mapping['【地点3】']).toBe('广州')
  })

  it('非法 span 安全跳过', () => {
    const text = 'abcdef'
    const { masked, mapping } = buildPlaceholderMask(text, [
      { start: -1, end: 2, type: 'X', matchText: 'ab' },
      { start: 5, end: 99, type: 'Y', matchText: 'f' },
    ])
    expect(masked).toBe('abcdef')
    expect(mapping).toEqual({})
  })

  it('空 spans 原样返回', () => {
    const { masked, mapping } = buildPlaceholderMask('今天天气不错', [])
    expect(masked).toBe('今天天气不错')
    expect(mapping).toEqual({})
  })
})

describe('restorePlaceholders', () => {
  it('还原占位符为原文', () => {
    const mapping = { '【手机号1】': '13800138000', '【姓名1】': '张三' }
    expect(restorePlaceholders('联系【姓名1】：【手机号1】', mapping)).toBe('联系张三：13800138000')
  })

  it('无占位符文本原样', () => {
    expect(restorePlaceholders('AI 回复没有占位符', {})).toBe('AI 回复没有占位符')
  })

  it('多占位符混合替换', () => {
    const mapping = { '【手机号1】': '138', '【手机号2】': '139' }
    expect(restorePlaceholders('【手机号1】和【手机号2】', mapping)).toBe('138和139')
  })
})

describe('往返一致性（build → restore === 原文）', () => {
  it('非重叠 spans 往返还原', () => {
    const text = '张三 13800138000 北京市朝阳区某某路100号'
    const spans = [
      { start: 0, end: 2, type: '姓名', matchText: '张三' },
      { start: 3, end: 14, type: '手机号', matchText: '13800138000' },
      { start: 15, end: 28, type: '地址', matchText: '北京市朝阳区某某路100号' },
    ]
    const { masked, mapping } = buildPlaceholderMask(text, spans)
    expect(restorePlaceholders(masked, mapping)).toBe(text)
  })
})
