import { describe, it, expect } from 'vitest'
import { enhanceContext } from '../src/utils/contextEnhance'

function names(text: string) {
  return enhanceContext(text, [], 20).filter(s => s.type === '姓名')
}

describe('裸名 + 联系方式共现识别（聊天场景核心修复）', () => {
  it('「张三的电话是13800138000」识别出 张三', () => {
    const n = names('张三的电话是13800138000')
    expect(n.some(s => s.matchText === '张三' && s.riskLevel === 'high')).toBe(true)
  })

  it('「王小明 联系电话：13912345678」识别出 王小明', () => {
    const n = names('王小明 联系电话：13912345678')
    expect(n.some(s => s.matchText === '王小明')).toBe(true)
  })

  it('「李四，手机 13867390432」识别出 李四', () => {
    const n = names('李四，手机 13867390432')
    expect(n.some(s => s.matchText === '李四')).toBe(true)
  })
})

describe('不误报 / 不回归', () => {
  it('无联系方式共现时，不把普通词当裸名（今天张三和王小明约了在朱雀大街）', () => {
    const t = '今天张三和王小明约了在朱雀大街见面'
    expect(names(t)).toHaveLength(0)
  })

  it('非姓名词 + 电话 不误报（我们公司电话是138…）', () => {
    const t = '我们公司电话是13800138000'
    expect(names(t)).toHaveLength(0)
  })

  it('带标签「姓名：张三」仍识别（回归）', () => {
    const n = names('姓名：张三，电话13800138000')
    expect(n.some(s => s.matchText === '张三')).toBe(true)
  })
})