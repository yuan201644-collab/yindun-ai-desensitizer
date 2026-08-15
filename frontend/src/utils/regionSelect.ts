/**
 * 「隐盾」重叠脱敏框的命中测试与循环选择（纯函数，可单测）
 * 多个框重叠时浏览器只把点击交给最上层框，被覆盖的小框点不到；
 * 通过命中测试收集所有覆盖框，同一位置连续点击依次循环切换选择。
 */
export interface Rect { x: number; y: number; w: number; h: number }

/** 返回包含点 p 的所有框，最上层在前（rects 按 DOM 顺序，靠后=上层） */
export function hitTestRegions(p: { x: number; y: number }, rects: Rect[]): Rect[] {
  return rects
    .filter(r => p.x >= r.x && p.x <= r.x + r.w && p.y >= r.y && p.y <= r.y + r.h)
    .reverse()
}

/** 循环选择游标：同一位置连续点击推进，换位置重置 */
export function createRegionCycle(tolerance = 3) {
  let point = { x: -1, y: -1 }
  let cursor = 0
  return {
    next(stack: Rect[], p: { x: number; y: number }): Rect {
      if (Math.abs(p.x - point.x) > tolerance || Math.abs(p.y - point.y) > tolerance) {
        point = p
        cursor = 0
      } else {
        cursor = (cursor + 1) % stack.length
      }
      return stack[cursor]
    },
    reset() {
      point = { x: -1, y: -1 }
      cursor = 0
    },
  }
}

/** ⭐ 可全选的文本区域：只含敏感内容行（OCR 已把 rect 收缩到敏感值，字段标签保留）。
 *  非敏感行（出生/民族/性别等标签行）与对象区域不进全选——"全选"= 全部敏感内容，
 *  满足"只打码内容不打标签"诉求（用户反馈"出生年月和民族被全选打码"的根因）。 */
export function selectableTextRegions(
  textRegions: Array<{ rect: Rect; sensitive: unknown }>
): Rect[] {
  return textRegions
    .filter(r => r.sensitive != null)
    .map(r => ({ x: r.rect.x, y: r.rect.y, w: r.rect.w, h: r.rect.h }))
}
