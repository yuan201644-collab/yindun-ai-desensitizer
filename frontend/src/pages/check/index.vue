<script setup lang="ts">
import { ref } from 'vue'
import { BASE_URL } from '../../utils/api'

const originalFile = ref<File | null>(null)
const processedFile = ref<File | null>(null)
const originalPreview = ref('')
const processedPreview = ref('')
const checking = ref(false)
const result = ref<any>(null)
const error = ref('')

function handleOriginal(e: Event) {
  const target = e.target as HTMLInputElement
  if (target.files?.[0]) { originalFile.value = target.files[0]; originalPreview.value = URL.createObjectURL(target.files[0]) }
}
function handleProcessed(e: Event) {
  const target = e.target as HTMLInputElement
  if (target.files?.[0]) { processedFile.value = target.files[0]; processedPreview.value = URL.createObjectURL(target.files[0]) }
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => { const r = reader.result as string; resolve(r.split(',')[1]) }
    reader.onerror = reject; reader.readAsDataURL(file)
  })
}

async function runCheck() {
  if (!originalFile.value || !processedFile.value) return
  checking.value = true; error.value = ''; result.value = null
  try {
    const origB64 = await fileToBase64(originalFile.value)
    const procB64 = await fileToBase64(processedFile.value)
    const res = await fetch(BASE_URL + '/api/check', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ original_image_base64: origB64, processed_image_base64: procB64, regions: [] }),
    })
    const data = await res.json()
    if (data.success) { result.value = data } else { error.value = data.error || '检测失败' }
  } catch (e: any) { error.value = e.message || '检测请求失败，请确认后端服务已启动' } finally { checking.value = false }
}

function reset() { originalFile.value = null; processedFile.value = null; originalPreview.value = ''; processedPreview.value = ''; result.value = null; error.value = '' }
function riskLevelColor(level: string): string { if (level==='safe') return '#22c55e'; if (level==='warning') return '#ffaa00'; return '#ff4444' }
function riskLabel(level: string): string { if (level==='safe') return '🟢 安全'; if (level==='warning') return '🟡 警告'; return '🔴 危险' }
</script>

<template>
  <div class="page">
    <div class="hero"><h1 class="hero-title">🛡️ 脱敏强度检测</h1><p class="hero-sub">⭐ 核心特色功能 — 基于信息安全专业能力，评估脱敏是否可被 AI 还原</p></div>
    <div class="help-card">
      <div class="help-header"><span>📖 这页做什么？</span></div>
      <div class="help-body">
        <p>上传<strong>脱敏前</strong>和<strong>脱敏后</strong>的图片，系统通过计算两张图的差异来评估：你打的码有没有可能被 AI 还原？</p>
        <p style="margin-top:8px;">评分规则：<span style="color:#22c55e">0-30 安全</span> | <span style="color:#ffaa00">30-60 建议加固</span> | <span style="color:#ff4444">60+ 危险，请重新脱敏</span></p>
        <p style="color:#8888aa;font-size:11px;margin-top:6px;">检测维度：SSIM（结构相似度）、PSNR（信噪比）、纹理熵（信息残留量）</p>
      </div>
    </div>
    <div class="upload-dual" v-if="!result">
      <div class="upload-box"><span class="upload-label">📤 原始图片</span>
        <div v-if="!originalPreview" class="upload-zone"><span class="upload-icon">+</span><input type="file" accept="image/*" @change="handleOriginal" class="file-input" /></div>
        <img v-else :src="originalPreview" class="preview-img" />
      </div>
      <div class="upload-box"><span class="upload-label">🔒 脱敏后图片</span>
        <div v-if="!processedPreview" class="upload-zone"><span class="upload-icon">+</span><input type="file" accept="image/*" @change="handleProcessed" class="file-input" /></div>
        <img v-else :src="processedPreview" class="preview-img" />
      </div>
    </div>
    <button v-if="!result && originalPreview && processedPreview" class="btn btn-primary" @click="runCheck" :disabled="checking">{{ checking ? '🔍 正在检测中...' : '🔍 开始强度检测' }}</button>
    <div class="result-panel" v-if="result">
      <div class="score-card" :style="{ borderColor: riskLevelColor(result.global_risk_level) }">
        <span class="score-num" :style="{ color: riskLevelColor(result.global_risk_level) }">{{ result.global_risk_score }}</span>
        <span class="score-label">风险评分 (0=安全 100=危险)</span>
        <span class="score-level" :style="{ color: riskLevelColor(result.global_risk_level) }">{{ riskLabel(result.global_risk_level) }}</span>
        <span class="score-msg">{{ result.global_message }}</span>
      </div>
      <div class="region-details" v-if="result.region_details?.length">
        <h3 class="details-title">📊 逐区域分析 ({{ result.total_regions_checked }} 处)</h3>
        <div v-for="(detail, i) in result.region_details" :key="i" class="detail-card" :style="{ borderLeftColor: riskLevelColor(detail.risk_level) }">
          <div class="detail-header"><span class="detail-index">区域 #{{ detail.region_index + 1 }}</span><span class="detail-risk" :style="{ color: riskLevelColor(detail.risk_level) }">{{ riskLabel(detail.risk_level) }} · {{ detail.risk_score }}分</span></div>
          <div class="detail-metrics"><span class="metric">SSIM: {{ detail.ssim }}</span><span class="metric">PSNR: {{ detail.psnr }} dB</span><span class="metric">纹理熵: {{ detail.texture_entropy }}</span></div>
          <span class="detail-suggestion">💡 {{ detail.suggestion }}</span>
        </div>
      </div>
      <button class="btn btn-secondary" @click="reset">🔄 检测其他图片</button>
      <div class="reinforce-guide">
        <h4 class="guide-title">🔧 脱敏加固指南</h4>
        <p class="guide-item">• 风险评分 < 30：脱敏强度充足，可放心使用</p>
        <p class="guide-item">• 风险评分 30-60：建议加大脱敏强度，或切换"不可逆替换"算法</p>
        <p class="guide-item">• 风险评分 > 60：立即更换脱敏算法，当前处理可被 AI 还原</p>
        <p class="guide-item" style="margin-top:8px;color:#6c63ff;">⭐ 推荐使用「不可逆像素替换」算法 — 信息论级别不可逆</p>
      </div>
    </div>
    <div v-if="error" class="error">{{ error }}</div>
    <div class="footer-note"><p>检测引擎基于 SSIM/PSNR/纹理熵 综合分析，评估 AI 超分模型还原风险</p></div>
  </div>
</template>

<style scoped>
.page { max-width: 800px; margin: 0 auto; padding: 16px; }
.hero { text-align: center; padding: 24px 0; }
.hero-title { font-size: 28px; font-weight: 700; color: #e0e0f0; }
.hero-sub { color: #8888aa; font-size: 14px; margin-top: 8px; line-height: 1.6; }
.upload-dual { display: flex; gap: 16px; margin: 16px 0; }
.upload-box { flex: 1; }
.upload-label { font-size: 14px; font-weight: 600; color: #aaaacc; display: block; margin-bottom: 8px; }
.upload-zone { background: #111122; border: 2px dashed #3a3a5a; border-radius: 12px; height: 200px; display: flex; align-items: center; justify-content: center; position: relative; }
.upload-icon { font-size: 48px; color: #4a4a6a; }
.file-input { position: absolute; inset: 0; opacity: 0; cursor: pointer; }
.preview-img { width: 100%; height: 200px; object-fit: contain; background: #111122; border-radius: 12px; }
.btn { display: block; width: 100%; padding: 14px; border-radius: 10px; border: none; font-size: 16px; font-weight: 600; cursor: pointer; margin: 12px 0; }
.btn-primary { background: #6c63ff; color: #fff; } .btn-secondary { background: #2a2a4a; color: #c0c0e0; }
.btn:disabled { opacity: 0.4; cursor: not-allowed; }
.score-card { text-align: center; padding: 32px; border: 3px solid #3a3a5a; border-radius: 16px; background: #1a1a2e; margin: 16px 0; }
.score-num { font-size: 64px; font-weight: 800; display: block; } .score-label { color: #8888aa; font-size: 13px; display: block; margin: 4px 0; }
.score-level { font-size: 20px; font-weight: 700; display: block; margin: 8px 0; } .score-msg { color: #aaaacc; font-size: 14px; margin-top: 8px; display: block; }
.region-details { margin: 20px 0; } .details-title { font-size: 16px; font-weight: 600; margin-bottom: 12px; }
.detail-card { background: #1a1a2e; border-radius: 10px; border-left: 4px solid #3a3a5a; padding: 14px; margin: 8px 0; }
.detail-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.detail-index { font-weight: 600; font-size: 14px; } .detail-risk { font-size: 13px; font-weight: 600; }
.detail-metrics { display: flex; gap: 16px; margin: 6px 0; } .metric { font-size: 12px; color: #8888aa; font-family: monospace; }
.detail-suggestion { font-size: 13px; color: #b0b0d0; margin-top: 6px; display: block; }
.reinforce-guide { background: #1a1a2e; border-radius: 12px; padding: 16px; margin-top: 16px; }
.guide-title { font-size: 16px; font-weight: 600; margin-bottom: 10px; } .guide-item { font-size: 13px; color: #aaaacc; padding: 3px 0; }
.error { color: #ff4444; font-size: 13px; text-align: center; margin: 12px 0; }
.footer-note { text-align: center; padding: 24px; color: #6666aa; font-size: 12px; }
.help-card { background: linear-gradient(135deg, #1a1a3e, #1a1a2e); border: 1px solid #2a2a4a; border-radius: 12px; margin-bottom: 16px; overflow: hidden; }
.help-header { padding: 12px 16px; font-weight: 600; color: #c0c0e0; }
.help-body { padding: 0 16px 14px; font-size: 13px; line-height: 1.8; color: #aaaacc; }
.help-body strong { color: #6c63ff; }
</style>
