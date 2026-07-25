/**
 * ================================================================
 * 「隐盾」图片上传状态管理
 * ================================================================
 * 处理：选择图片 → 预览 → 尺寸校验 → Canvas 渲染
 */
import { ref, type Ref } from 'vue'

export interface UploadState {
  file: File | null
  previewUrl: string
  width: number
  height: number
  status: 'idle' | 'loading' | 'ready' | 'error'
  errorMessage: string
}

export function useImageUpload() {
  const state: Ref<UploadState> = ref({
    file: null,
    previewUrl: '',
    width: 0,
    height: 0,
    status: 'idle',
    errorMessage: '',
  })

  const MAX_SIZE_MB = 20
  const MAX_DIMENSION = 4096

  function handleFile(file: File) {
    // 重置
    state.value = {
      file: null,
      previewUrl: '',
      width: 0,
      height: 0,
      status: 'loading',
      errorMessage: '',
    }

    // 大小校验
    if (file.size > MAX_SIZE_MB * 1024 * 1024) {
      state.value.status = 'error'
      state.value.errorMessage = `图片不能超过 ${MAX_SIZE_MB}MB`
      return
    }

    // 格式校验
    const allowedTypes = ['image/png', 'image/jpeg', 'image/webp', 'image/bmp']
    if (!allowedTypes.includes(file.type)) {
      state.value.status = 'error'
      state.value.errorMessage = '仅支持 PNG / JPG / WebP / BMP 格式'
      return
    }

    // 创建预览
    const url = URL.createObjectURL(file)
    const img = new Image()

    img.onload = () => {
      const w = img.width
      const h = img.height
      if (Math.max(w, h) > MAX_DIMENSION) {
        state.value.status = 'error'
        state.value.errorMessage = `图片尺寸不能超过 ${MAX_DIMENSION}px`
        URL.revokeObjectURL(url)
        return
      }

      state.value = {
        file,
        previewUrl: url,
        width: w,
        height: h,
        status: 'ready',
        errorMessage: '',
      }
    }

    img.onerror = () => {
      state.value.status = 'error'
      state.value.errorMessage = '图片加载失败，请检查文件完整性'
      URL.revokeObjectURL(url)
    }

    img.src = url
  }

  function reset() {
    if (state.value.previewUrl) {
      URL.revokeObjectURL(state.value.previewUrl)
    }
    state.value = {
      file: null,
      previewUrl: '',
      width: 0,
      height: 0,
      status: 'idle',
      errorMessage: '',
    }
  }

  return { state, handleFile, reset }
}
