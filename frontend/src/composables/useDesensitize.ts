/**
 * ================================================================
 * 「隐盾」脱敏操作状态管理
 * ================================================================
 * 管理：已选脱敏区域、脱敏模式、强度参数
 */
import { ref, reactive, type Ref } from 'vue'
import type { DesensitizeMethod, Region } from '../utils/canvas'

export function useDesensitize() {
  const selectedRegions: Ref<Region[]> = ref([])
  const method: Ref<DesensitizeMethod> = ref('pixelate')
  const intensity = ref(0.7) // 0-1 脱敏强度
  const isProcessed = ref(false)

  const methodOptions = [
    { value: 'pixelate' as const, label: '像素化（马赛克）', desc: '通用打码，观感友好' },
    { value: 'gaussian' as const, label: '高斯噪点混淆', desc: '强模糊+噪点，抗AI还原' },
    { value: 'irreversible' as const, label: '不可逆替换 ⭐', desc: '像素重排，信息论不可逆' },
  ]

  function addRegion(region: Region) {
    // 避免重复添加
    const exists = selectedRegions.value.some(
      r => r.x === region.x && r.y === region.y && r.w === region.w && r.h === region.h
    )
    if (!exists) {
      selectedRegions.value.push({ ...region, method: method.value })
    }
  }

  function removeRegion(index: number) {
    selectedRegions.value.splice(index, 1)
  }

  function clearRegions() {
    selectedRegions.value = []
    isProcessed.value = false
  }

  function markProcessed() {
    isProcessed.value = true
  }

  return {
    selectedRegions,
    method,
    intensity,
    isProcessed,
    methodOptions,
    addRegion,
    removeRegion,
    clearRegions,
    markProcessed,
  }
}
