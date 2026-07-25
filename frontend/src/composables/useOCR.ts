import { ref, type Ref } from 'vue'
import { ocrDetect } from '../utils/api'

export interface OCRRegion {
  bbox: number[][]
  rect: { x: number; y: number; w: number; h: number }
  text: string
  confidence: number
  sensitive: { type: string; category: string; risk_level: string; matched_text: string } | null
}

export interface ObjectRegion {
  label: string
  confidence: number
  rect: { x: number; y: number; w: number; h: number }
}

export function useOCR() {
  const loading = ref(false)
  const textRegions: Ref<OCRRegion[]> = ref([])
  const objectRegions: Ref<ObjectRegion[]> = ref([])
  const error = ref('')

  async function detect(file: File, mode: string = 'full') {
    loading.value = true; error.value = ''; textRegions.value = []; objectRegions.value = []
    try {
      const result: any = await ocrDetect(file, mode)
      if (result.success) {
        textRegions.value = result.text_regions || []
        objectRegions.value = result.object_regions || []
      } else {
        error.value = result.error || '识别失败'
      }
    } catch (e: any) {
      error.value = e.message || '网络请求失败，请确认后端服务已启动'
    } finally {
      loading.value = false
    }
  }

  return { loading, textRegions, objectRegions, error, detect }
}
