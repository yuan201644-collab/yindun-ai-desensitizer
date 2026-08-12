import { describe, it, expect } from 'vitest'
import { hitTestRegions, createRegionCycle, type Rect } from '../src/utils/regionSelect'

const big: Rect = { x: 0, y: 0, w: 100, h: 100 }
const small: Rect = { x: 20, y: 20, w: 30, h: 30 }
const far: Rect = { x: 300, y: 300, w: 50, h: 50 }
// DOM 顺序：big 在前、small 在后 → small 覆盖在上层
const rects = [big, small, far]

describe('hitTestRegions', () => {
  it('点在大框+小框重叠区 → 返回两个，上层（DOM靠后）在前', () => {
    const hit = hitTestRegions({ x: 30, y: 30 }, rects)
    expect(hit).toHaveLength(2)
    expect(hit[0]).toEqual(small)
    expect(hit[1]).toEqual(big)
  })
  it('点只在大框内 → 只返回大框', () => {
    const hit = hitTestRegions({ x: 60, y: 60 }, rects)
    expect(hit).toEqual([big])
  })
  it('点在空白 → 返回空', () => {
    expect(hitTestRegions({ x: 200, y: 200 }, rects)).toEqual([])
  })
  it('边界视为命中（含端点）', () => {
    expect(hitTestRegions({ x: 0, y: 0 }, rects)).toEqual([big])
    expect(hitTestRegions({ x: 100, y: 100 }, rects)).toEqual([big])
  })
})

describe('createRegionCycle', () => {
  // 栈按 hitTestRegions 约定：最上层在前（small 覆盖在 big 上）
  const stack = [small, big]
  it('同一位置连续点击 → 依次循环切换', () => {
    const c = createRegionCycle()
    expect(c.next(stack, { x: 30, y: 30 })).toEqual(small)  // 上层 small
    expect(c.next(stack, { x: 30, y: 30 })).toEqual(big)    // 推进 → big
    expect(c.next(stack, { x: 30, y: 30 })).toEqual(small)  // 回绕
  })
  it('换位置 → 游标重置回上层', () => {
    const c = createRegionCycle()
    c.next(stack, { x: 30, y: 30 })
    c.next(stack, { x: 30, y: 30 })
    expect(c.next(stack, { x: 40, y: 40 })).toEqual(small)
  })
  it('微小位移（≤容差）仍视为同一位置', () => {
    const c = createRegionCycle()
    c.next(stack, { x: 30, y: 30 })
    expect(c.next(stack, { x: 31, y: 32 })).toEqual(big)
  })
  it('reset 后回到初始状态', () => {
    const c = createRegionCycle()
    c.next(stack, { x: 30, y: 30 })
    c.reset()
    expect(c.next(stack, { x: 30, y: 30 })).toEqual(small)
  })
})
