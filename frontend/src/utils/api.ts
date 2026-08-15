/**
 * [隐盾] API 请求封装
 * 通过 Vite proxy 转发到后端，避免跨域问题
 */

export const BASE_URL = ''

/**
 * 可选 API Key 鉴权头（部署端开启 YINDUN_API_KEY 时使用）
 * 未配置 VITE_API_KEY 时不发送任何额外头，行为与之前完全一致
 */
function authHeaders(): Record<string, string> {
  const key = (import.meta as any).env?.VITE_API_KEY as string | undefined
  return key ? { 'X-API-Key': key } : {}
}

async function request<T = any>(url: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(BASE_URL + url, {
    headers: { 'Content-Type': 'application/json', ...authHeaders(), ...options.headers as any },
    ...options,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error((body as any).error || `请求失败: ${res.status}`)
  }
  return res.json()
}

export async function ocrDetect(file: File, mode: string = 'full'): Promise<any> {
  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch(`/api/ocr?mode=${mode}&with_detection=true`, {
    method: 'POST',
    headers: authHeaders(),
    body: formData,
  })
  if (!res.ok) throw new Error('OCR 请求失败')
  return res.json()
}

export async function desensitizeImage(data: any) {
  return request('/api/desensitize/image', { method: 'POST', body: JSON.stringify(data) })
}

export async function desensitizeText(text: string, customPatterns?: any[]) {
  return request('/api/desensitize/text', {
    method: 'POST',
    body: JSON.stringify({ text, custom_patterns: customPatterns }),
  })
}

export async function checkStrength(data: any) {
  return request('/api/check', { method: 'POST', body: JSON.stringify(data) })
}

export async function healthCheck() {
  return request('/api/health')
}
