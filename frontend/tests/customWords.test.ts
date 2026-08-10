import { describe, it, expect } from 'vitest'
import { matchCustomWords } from '../src/utils/sensitivePatterns'

describe('matchCustomWords 自定义敏感词匹配', () => {
  it('命中多次', () => {
    // '雷霆项目启动，雷霆项目完成' 中第二个词在 index 7（中文逗号占 1 位）
    const spans = matchCustomWords('雷霆项目启动，雷霆项目完成', ['雷霆项目'])
    expect(spans).toEqual([
      { start: 0, end: 4, text: '雷霆项目', type: '自定义' },
      { start: 7, end: 11, text: '雷霆项目', type: '自定义' },
    ])
  })

  it('多词命中 + 忽略空词', () => {
    const spans = matchCustomWords('张伟联系了李四', ['张伟', '', '   ', '李四'])
    expect(spans.length).toBe(2)
    expect(spans[0].text).toBe('张伟')
    expect(spans[1].text).toBe('李四')
  })

  it('跳过与已命中词重叠的位置', () => {
    // "雷霆项目"命中 0-4，子串"项目"在 2-4 与其重叠 → 跳过
    const spans = matchCustomWords('雷霆项目组', ['雷霆项目', '项目'])
    expect(spans.length).toBe(1)
    expect(spans[0].text).toBe('雷霆项目')
  })

  it('相邻不同词互不干扰', () => {
    const spans = matchCustomWords('王小明在雷霆项目', ['王小明', '雷霆项目'])
    expect(spans.length).toBe(2)
    expect(spans[0].text).toBe('王小明')
    expect(spans[1].text).toBe('雷霆项目')
  })

  it('无命中返回空数组', () => {
    expect(matchCustomWords('今天天气不错', ['机密代号'])).toEqual([])
  })

  it('结果按位置排序', () => {
    const spans = matchCustomWords('B号机密A号机密', ['机密'])
    expect(spans[0].start).toBeLessThan(spans[1].start)
  })
})
