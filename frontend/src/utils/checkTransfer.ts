/**
 * ================================================================
 * 「隐盾」检测页图片自动带入中转
 * ================================================================
 * 脱敏页完成脱敏后，跳转到强度检测页时自动带上原图/脱敏图，
 * 用户无需重新上传。数据存于模块内存（同会话内有效，不进 URL）。
 */

let pendingOriginal: string | null = null
let pendingProcessed: string | null = null
let pendingRegions: Array<{ x: number; y: number; w: number; h: number }> = []

/** 脱敏页跳转前调用：写入待带入的两张图（原始 base64，无 data: 前缀）+ 脱敏区域 */
export function setCheckImages(originalB64: string, processedB64: string) {
  pendingOriginal = originalB64
  pendingProcessed = processedB64
}

export function setCheckRegions(regions: Array<{ x: number; y: number; w: number; h: number }>) {
  pendingRegions = regions
}

/** 检测页挂载时调用：读取并清空中转数据（一次性） */
export function takeCheckImages(): { original: string | null; processed: string | null } {
  const result = { original: pendingOriginal, processed: pendingProcessed }
  pendingOriginal = null
  pendingProcessed = null
  return result
}

export function takeCheckRegions(): Array<{ x: number; y: number; w: number; h: number }> {
  const result = pendingRegions
  pendingRegions = []
  return result
}
