import { describe, it, expect } from 'vitest'
import { SCENARIO_TEMPLATES, getTemplate, filterPatternsByTemplate } from '../src/utils/scenarioTemplates'
import { DEFAULT_PATTERNS } from '../src/utils/sensitivePatterns'

const patternTypes = DEFAULT_PATTERNS.map(p => p.type)

describe('场景模板库', () => {
  it('包含 4 个内置模板', () => {
    const ids = SCENARIO_TEMPLATES.map(t => t.id)
    expect(ids).toEqual(['general', 'express', 'chat', 'idcard'])
  })

  it('模板的 activeTypes/preferTypes 都存在于模式库中', () => {
    for (const t of SCENARIO_TEMPLATES) {
      for (const type of [...(t.activeTypes || []), ...(t.preferTypes || [])]) {
        expect(patternTypes).toContain(type)
      }
    }
  })

  it('每个模板都有默认算法', () => {
    for (const t of SCENARIO_TEMPLATES) {
      expect(['pixelate', 'gaussian', 'irreversible']).toContain(t.defaultMethod)
    }
  })

  it('getTemplate 找不到时回退到通用', () => {
    expect(getTemplate('not-exist').id).toBe('general')
  })
})

describe('filterPatternsByTemplate', () => {
  it('通用模板不过滤（保留全部）', () => {
    const general = getTemplate('general')
    const filtered = filterPatternsByTemplate(DEFAULT_PATTERNS, general)
    expect(filtered.length).toBe(DEFAULT_PATTERNS.length)
  })

  it('快递单模板只保留手机号/固话/地址/单号', () => {
    const express = getTemplate('express')
    const filtered = filterPatternsByTemplate(DEFAULT_PATTERNS, express)
    const types = filtered.map(p => p.type)
    expect(types).toEqual(['手机号', '固定电话', '家庭住址', '快递单号'])
  })

  it('聊天记录模板只保留手机号/邮箱/地址', () => {
    const chat = getTemplate('chat')
    const filtered = filterPatternsByTemplate(DEFAULT_PATTERNS, chat)
    expect(filtered.map(p => p.type)).toEqual(['手机号', '电子邮箱', '家庭住址'])
  })

  it('证件材料模板包含姓名与出生日期（图片自动选区 + 文本流均生效）', () => {
    const idcard = getTemplate('idcard')
    for (const type of ['姓名', '出生日期']) {
      expect(idcard.activeTypes).toContain(type)
      expect(idcard.preferTypes).toContain(type)
    }
    const filtered = filterPatternsByTemplate(DEFAULT_PATTERNS, idcard)
    expect(filtered.map(p => p.type)).toContain('姓名')
    expect(filtered.map(p => p.type)).toContain('出生日期')
  })
})
