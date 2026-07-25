/**
 * ================================================================
 * 「隐盾」脱敏强度检测状态管理
 * ================================================================
 */
import { ref, type Ref } from 'vue'
import { checkStrength } from '../utils/api'

export interface CheckResult {
  global_risk_score: number
  global_risk_level: 'safe' | 'warning' | 'danger'
  global_message: string
  region_details: Array<{
    region_index: number
    ssim: number
    psnr: number
    texture_entropy: number
    risk_score: number
    risk_level: string
    suggestion: string
  }>
  total_regions_checked: number
}

export function useStrengthCheck() {
  const loading = ref(false)
  const result: Ref<CheckResult | null> = ref(null)
  const error = ref('')

  async function check(originalBase64: string, processedBase64: string, regions: any[]) {
    loading.value = true
    error.value = ''
    result.value = null

    try {
      const res: any = await checkStrength({
        original_image_base64: originalBase64,
        processed_image_base64: processedBase64,
        regions,
      })
      if (res.success) {
        result.value = res as CheckResult
      } else {
        error.value = res.error || '检测失败'
      }
    } catch (e: any) {
      error.value = e.message || '检测请求失败'
    } finally {
      loading.value = false
    }
  }

  return { loading, result, error, check }
}
