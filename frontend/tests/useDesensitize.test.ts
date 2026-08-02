import { describe, it, expect } from 'vitest'
import { useDesensitize } from '../src/composables/useDesensitize'

describe('useDesensitize 脱敏状态管理', () => {
  it('addRegion 去除重复区域', () => {
    const { addRegion, selectedRegions } = useDesensitize()
    addRegion({ x: 0, y: 0, w: 10, h: 10 })
    addRegion({ x: 0, y: 0, w: 10, h: 10 })
    expect(selectedRegions.value.length).toBe(1)
  })

  it('addRegion 保留不同区域并附带当前方法', () => {
    const { addRegion, selectedRegions, method } = useDesensitize()
    addRegion({ x: 0, y: 0, w: 10, h: 10 })
    addRegion({ x: 20, y: 20, w: 5, h: 5 })
    expect(selectedRegions.value.length).toBe(2)
    expect(selectedRegions.value[0].method).toBe(method.value)
  })

  it('removeRegion 删除指定区域', () => {
    const { addRegion, removeRegion, selectedRegions } = useDesensitize()
    addRegion({ x: 0, y: 0, w: 10, h: 10 })
    addRegion({ x: 20, y: 20, w: 5, h: 5 })
    removeRegion(0)
    expect(selectedRegions.value.length).toBe(1)
    expect(selectedRegions.value[0].x).toBe(20)
  })

  it('clearRegions 清空选区并重置处理状态', () => {
    const { addRegion, clearRegions, selectedRegions, isProcessed, markProcessed } = useDesensitize()
    addRegion({ x: 1, y: 1, w: 5, h: 5 })
    markProcessed()
    expect(isProcessed.value).toBe(true)
    clearRegions()
    expect(selectedRegions.value.length).toBe(0)
    expect(isProcessed.value).toBe(false)
  })
})
