<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { BASE_URL } from '../../utils/api'
import { takeCheckImages, takeCheckRegions } from '../../utils/checkTransfer'

const originalPreview = ref('')
const processedPreview = ref('')
const checking = ref(false)
const result = ref<any>(null)
const error = ref('')
const reportTime = ref('')
// 图片数据源（原始 base64，无 data: 前缀）：手动上传或从脱敏页自动带入
let originalB64 = ''
let processedB64 = ''
// 从脱敏页带入的脱敏区域（检测只量这些区域，否则整图对比会被未脱敏背景拉高）
let checkRegions: Array<{ x: number; y: number; w: number; h: number }> = []

function setImage(kind: 'original' | 'processed', file: File) {
  const reader = new FileReader()
  reader.onload = () => {
    const b64 = (reader.result as string).split(',')[1]
    if (kind === 'original') { originalB64 = b64; originalPreview.value = URL.createObjectURL(file) }
    else { processedB64 = b64; processedPreview.value = URL.createObjectURL(file) }
  }
  reader.readAsDataURL(file)
}
function handleOriginal(e: Event) { const f = (e.target as HTMLInputElement).files?.[0]; if (f) setImage('original', f) }
function handleProcessed(e: Event) { const f = (e.target as HTMLInputElement).files?.[0]; if (f) setImage('processed', f) }

async function runCheck() {
  if (!originalB64 || !processedB64) return
  checking.value = true; error.value = ''; result.value = null
  try {
    const res = await fetch(BASE_URL + '/api/check', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ original_image_base64: originalB64, processed_image_base64: processedB64, regions: checkRegions.map(r => ({ rect: r })) }),
    })
    const data = await res.json()
    if (data.success) { result.value = data; reportTime.value = new Date().toLocaleString('zh-CN') } else { error.value = data.error || '检测失败' }
  } catch (e: any) { error.value = e.message || '检测请求失败，请确认后端服务已启动' } finally { checking.value = false }
}

function reset() { originalB64 = ''; processedB64 = ''; originalPreview.value = ''; processedPreview.value = ''; result.value = null; error.value = '' }

// P3 修复：交换原图/脱敏图（传反了不用重传）
function swapImages() {
  const b = originalB64; originalB64 = processedB64; processedB64 = b
  const p = originalPreview.value; originalPreview.value = processedPreview.value; processedPreview.value = p
  result.value = null; error.value = ''
}

// 从脱敏页跳转过来时自动带入原图/脱敏图 + 脱敏区域
onMounted(() => {
  const t = takeCheckImages()
  checkRegions = takeCheckRegions()
  if (t.original && t.processed) {
    originalB64 = t.original
    processedB64 = t.processed
    originalPreview.value = 'data:image/png;base64,' + t.original
    processedPreview.value = 'data:image/png;base64,' + t.processed
  }
})
function riskLevelColor(level: string): string { if (level==='safe') return '#22c55e'; if (level==='warning') return '#ffaa00'; return '#ff4444' }
function riskLabel(level: string): string { if (level==='safe') return '🟢 安全'; if (level==='warning') return '🟡 警告'; return '🔴 危险' }
const advRegions = computed(() => (result.value?.region_details || []).filter((d: any) => d.adversarial?.attacks?.length))

// 📊 综合评估雷达（4 维：隐私防护 / 内容可用性 / 纹理保留 / 噪声控制）
const radarRef = ref<HTMLCanvasElement | null>(null)
const RADAR_KEYS = ['privacy', 'usability', 'texture', 'noise_control'] as const

function drawRadar(print = false) {
  const canvas = radarRef.value
  if (!canvas || !result.value?.report) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const size = canvas.clientWidth || 300
  const dpr = window.devicePixelRatio || 1
  canvas.width = size * dpr
  canvas.height = size * dpr
  ctx.scale(dpr, dpr)

  // 打印用浅色调色板（白底可读）；屏幕用深色主题
  const c = print
    ? { grid: '#d8d8e8', label: '#555577', fill: 'rgba(108,99,255,0.18)', line: '#5a55d6', dot: '#5a55d6', value: '#3a35a8' }
    : { grid: '#2a2a4a', label: '#aaaacc', fill: 'rgba(108,99,255,0.25)', line: '#6c63ff', dot: '#6c63ff', value: '#6c63ff' }

  const cx = size / 2
  const cy = size / 2
  const radius = size / 2 - 30
  const dims = result.value.report.dimensions
  const labels = result.value.report.labels
  const n = RADAR_KEYS.length

  ctx.clearRect(0, 0, size, size)

  // 网格环（4 圈）
  ctx.strokeStyle = c.grid
  ctx.lineWidth = 1
  for (let ring = 1; ring <= 4; ring++) {
    const r = (radius * ring) / 4
    ctx.beginPath()
    for (let i = 0; i <= n; i++) {
      const angle = (i / n) * Math.PI * 2 - Math.PI / 2
      const x = cx + r * Math.cos(angle)
      const y = cy + r * Math.sin(angle)
      if (i === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
    }
    ctx.stroke()
  }

  // 4 条坐标轴（每轴 90°）
  for (let i = 0; i < n; i++) {
    const angle = (i / n) * Math.PI * 2 - Math.PI / 2
    ctx.beginPath()
    ctx.moveTo(cx, cy)
    ctx.lineTo(cx + radius * Math.cos(angle), cy + radius * Math.sin(angle))
    ctx.stroke()
  }

  // 数据多边形
  ctx.beginPath()
  RADAR_KEYS.forEach((key, i) => {
    const angle = (i / n) * Math.PI * 2 - Math.PI / 2
    const value = (Number(dims?.[key]) || 0) / 100
    const x = cx + radius * value * Math.cos(angle)
    const y = cy + radius * value * Math.sin(angle)
    if (i === 0) ctx.moveTo(x, y)
    else ctx.lineTo(x, y)
  })
  ctx.closePath()
  ctx.fillStyle = c.fill
  ctx.fill()
  ctx.strokeStyle = c.line
  ctx.lineWidth = 2
  ctx.stroke()

  // 顶点圆点
  RADAR_KEYS.forEach((key, i) => {
    const angle = (i / n) * Math.PI * 2 - Math.PI / 2
    const value = (Number(dims?.[key]) || 0) / 100
    const x = cx + radius * value * Math.cos(angle)
    const y = cy + radius * value * Math.sin(angle)
    ctx.beginPath()
    ctx.arc(x, y, 3.5, 0, Math.PI * 2)
    ctx.fillStyle = c.dot
    ctx.fill()
  })

  // 维度标签 + 数值
  RADAR_KEYS.forEach((key, i) => {
    const angle = (i / n) * Math.PI * 2 - Math.PI / 2
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillStyle = c.label
    ctx.font = '12px sans-serif'
    const lx = cx + (radius + 18) * Math.cos(angle)
    const ly = cy + (radius + 18) * Math.sin(angle)
    ctx.fillText(String(labels?.[key] || key), lx, ly)
    // 维度数值（沿轴内放，避免被标签遮挡）
    ctx.fillStyle = c.value
    ctx.font = 'bold 13px sans-serif'
    const vx = cx + radius * 0.6 * Math.cos(angle)
    const vy = cy + radius * 0.6 * Math.sin(angle)
    ctx.fillText(String(dims?.[key] ?? 0), vx, vy)
  })
}

// 结果变化时重绘雷达（等待模板渲染出 canvas）
watch(result, () => {
  if (result.value?.report) nextTick(() => drawRadar())
})

// 打印/打印预览时切换雷达浅色调色板
window.matchMedia('print').addEventListener('change', (e) => {
  if (result.value?.report) nextTick(() => drawRadar(e.matches))
})

function exportPDF() {
  if (!result.value?.report) return
  // Chrome/Edge 的 window.print() 同步阻塞，matchMedia('print') change 事件在阻塞期间不派发，
  // 所以打印前显式切浅色调色板；打印结束（对话框关闭）后按是否仍在打印模式决定是否恢复深色。
  // Safari 等非阻塞浏览器由下方 matchMedia 监听兜底处理退出打印。
  drawRadar(true)
  setTimeout(() => {
    window.print()
    if (!window.matchMedia('print').matches && result.value?.report) drawRadar(false)
  }, 60)
}
</script>

<template>
  <div class="page">
    <div class="hero"><h1 class="hero-title fade-up">🛡️ 脱敏强度检测</h1><p class="hero-sub fade-up" style="animation-delay:0.08s">⭐ 核心特色功能 — 基于信息安全专业能力，评估脱敏是否可被 AI 还原</p></div>
    <div class="help-card fade-in">
      <div class="help-header"><span>📖 这页做什么？</span></div>
      <div class="help-body">
        <p>上传<strong>脱敏前</strong>和<strong>脱敏后</strong>的图片，系统通过计算两张图的差异来评估：你打的码有没有可能被 AI 还原？</p>
        <p style="margin-top:8px;">评分规则：<span style="color:#22c55e">0-30 安全</span> | <span style="color:#ffaa00">30-60 建议加固</span> | <span style="color:#ff4444">60+ 危险，请重新脱敏</span></p>
        <p style="color:#8888aa;font-size:11px;margin-top:6px;">检测维度：SSIM（结构相似度）、PSNR（信噪比）、纹理熵（信息残留量）</p>
        <p style="color:#6c63ff;font-size:12px;margin-top:6px;">🧪 对抗还原测试：系统会尝试用超分/去模糊/边缘增强还原脱敏区域，验证"打了码就还原不了"</p>
      </div>
    </div>
    <div class="upload-dual stagger" v-if="!result">
      <div class="upload-box"><span class="upload-label">📤 原始图片</span>
        <div v-if="!originalPreview" class="upload-zone"><span class="upload-icon">+</span><input type="file" accept="image/*" @change="handleOriginal" class="file-input" /></div>
        <img v-else :src="originalPreview" class="preview-img" />
      </div>
      <div class="upload-box"><span class="upload-label">🔒 脱敏后图片</span>
        <div v-if="!processedPreview" class="upload-zone"><span class="upload-icon">+</span><input type="file" accept="image/*" @change="handleProcessed" class="file-input" /></div>
        <img v-else :src="processedPreview" class="preview-img" />
      </div>
    </div>
    <div v-if="!result && (!!originalPreview !== !!processedPreview)" class="hint-msg">⚠️ 需上传<strong>原图</strong>和<strong>脱敏后图</strong>两张才能检测</div>
    <div v-if="!result && originalPreview && processedPreview" class="action-row">
      <button class="btn btn-primary" @click="runCheck" :disabled="checking">{{ checking ? '🔍 正在检测中...' : '🔍 开始强度检测' }}</button>
      <button class="btn btn-secondary" @click="swapImages">⇄ 交换两张图</button>
    </div>
    <div class="result-panel reveal" v-if="result">
      <div class="report-head print-only">
        <h2 class="report-title">「隐盾」脱敏强度检测报告</h2>
        <p class="report-meta">检测时间：{{ reportTime }} · 风险评分 {{ result.global_risk_score }} · {{ riskLabel(result.global_risk_level) }}</p>
        <div class="report-imgs">
          <div class="report-img"><span>原始图片</span><img :src="originalPreview" /></div>
          <div class="report-img"><span>脱敏后图片</span><img :src="processedPreview" /></div>
        </div>
      </div>
      <button class="btn btn-primary" @click="exportPDF">🖨️ 导出 PDF 报告</button>
      <div class="score-card" :style="{ borderColor: riskLevelColor(result.global_risk_level) }">
        <span class="score-num" :style="{ color: riskLevelColor(result.global_risk_level) }">{{ result.global_risk_score }}</span>
        <span class="score-label">风险评分 (0=安全 100=危险)</span>
        <span class="score-level" :style="{ color: riskLevelColor(result.global_risk_level) }">{{ riskLabel(result.global_risk_level) }}</span>
        <span class="score-msg">{{ result.global_message }}</span>
      </div>
      <div class="radar-panel reveal" v-if="result.report" style="animation-delay:0.05s">
        <h3 class="details-title">📊 综合评估雷达</h3>
        <canvas ref="radarRef" class="radar-canvas"></canvas>
        <p class="suggestion">💡 {{ result.concrete_suggestion }}</p>
      </div>
      <div class="region-details stagger" v-if="result.region_details?.length">
        <h3 class="details-title">📊 逐区域分析 ({{ result.total_regions_checked }} 处)</h3>
        <div v-for="(detail, i) in result.region_details" :key="i" class="detail-card" :style="{ borderLeftColor: riskLevelColor(detail.risk_level) }">
          <div class="detail-header"><span class="detail-index">区域 #{{ detail.region_index + 1 }}</span><span class="detail-risk" :style="{ color: riskLevelColor(detail.risk_level) }">{{ riskLabel(detail.risk_level) }} · {{ detail.risk_score }}分</span></div>
          <div class="detail-metrics"><span class="metric">SSIM: {{ detail.ssim }}</span><span class="metric">PSNR: {{ detail.psnr }} dB</span><span class="metric">纹理熵: {{ detail.texture_entropy }}</span></div>
          <span class="detail-suggestion">💡 {{ detail.suggestion }}</span>
        </div>
      </div>
      <div class="adv-panel reveal" v-if="result.adversarial_summary" style="animation-delay:0.1s">
        <h3 class="details-title">🧪 对抗还原测试（以 AI 测 AI）</h3>
        <div class="adv-verdict" :style="{ borderLeftColor: riskLevelColor(result.adversarial_summary.verdict) }">
          <span class="adv-label" :style="{ color: riskLevelColor(result.adversarial_summary.verdict) }">{{ riskLabel(result.adversarial_summary.verdict) }} · 抗还原判定</span>
          <span class="adv-msg">{{ result.adversarial_summary.message }}</span>
        </div>
        <div v-if="advRegions.length">
          <div v-for="(detail, i) in advRegions" :key="i" class="adv-region">
            <div class="detail-header">
              <span class="detail-index">区域 #{{ detail.region_index + 1 }}</span>
              <span class="adv-region-verdict" :style="{ color: riskLevelColor(detail.adversarial!.verdict) }">{{ riskLabel(detail.adversarial!.verdict) }}</span>
            </div>
            <table class="adv-table">
              <thead><tr><th>还原手法</th><th>还原后 SSIM</th><th>还原后 PSNR</th></tr></thead>
              <tbody>
                <tr v-for="(atk, j) in detail.adversarial!.attacks" :key="j">
                  <td>{{ atk.name }}</td>
                  <td>{{ atk.restored_ssim }}</td>
                  <td>{{ atk.restored_psnr }} dB</td>
                </tr>
              </tbody>
            </table>
            <span class="detail-suggestion">💡 {{ detail.adversarial!.message }}</span>
          </div>
        </div>
        <p class="adv-note">还原手法为经典算法（超分插值 / Richardson-Lucy 去模糊 / 边缘增强）；接口预留了接入 Real-ESRGAN 等真超分模型的扩展位。</p>
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
    <div class="footer-note"><p>检测引擎基于 SSIM/PSNR/纹理熵 + 对抗还原测试（超分/去模糊/边缘增强），以还原手法检验脱敏不可逆性</p><p class="footer-tip">🖨️ 检测完成后可点击「导出 PDF 报告」打印留存</p></div>
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
.hint-msg { color: #ffaa00; font-size: 13px; margin: 12px 0; text-align: center; }
.action-row { display: flex; gap: 8px; margin: 12px 0; }
.action-row .btn { width: auto; margin: 0; flex: 1; }
.score-card { text-align: center; padding: 32px; border: 3px solid #3a3a5a; border-radius: 16px; background: #1a1a2e; margin: 16px 0; }
.score-num { font-size: 64px; font-weight: 800; display: block; } .score-label { color: #8888aa; font-size: 13px; display: block; margin: 4px 0; }
.score-level { font-size: 20px; font-weight: 700; display: block; margin: 8px 0; } .score-msg { color: #aaaacc; font-size: 14px; margin-top: 8px; display: block; }
.radar-panel { background: #1a1a2e; border: 1px solid #3a3a5a; border-radius: 12px; padding: 16px; margin: 16px 0; text-align: center; }
.radar-canvas { width: 100%; max-width: 360px; height: 280px; margin: 8px auto; display: block; }
.suggestion { margin-top: 10px; font-size: 13px; color: #b0b0d0; line-height: 1.6; }
.region-details { margin: 20px 0; } .details-title { font-size: 16px; font-weight: 600; margin-bottom: 12px; }
.detail-card { background: #1a1a2e; border-radius: 10px; border-left: 4px solid #3a3a5a; padding: 14px; margin: 8px 0; }
.detail-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.detail-index { font-weight: 600; font-size: 14px; } .detail-risk { font-size: 13px; font-weight: 600; }
.detail-metrics { display: flex; gap: 16px; margin: 6px 0; } .metric { font-size: 12px; color: #8888aa; font-family: monospace; }
.detail-suggestion { font-size: 13px; color: #b0b0d0; margin-top: 6px; display: block; }
.adv-panel { background: linear-gradient(135deg, #1a1a3e, #14142a); border: 1px solid #3a3a5a; border-radius: 12px; padding: 16px; margin: 16px 0; }
.adv-verdict { display: flex; flex-direction: column; gap: 6px; background: #1a1a2e; border-left: 4px solid #3a3a5a; border-radius: 8px; padding: 12px; margin-bottom: 12px; }
.adv-label { font-size: 15px; font-weight: 700; }
.adv-msg { font-size: 13px; color: #b0b0d0; line-height: 1.6; }
.adv-region { background: #1a1a2e; border-radius: 10px; padding: 12px; margin: 10px 0; }
.adv-region-verdict { font-size: 13px; font-weight: 600; }
.adv-table { width: 100%; border-collapse: collapse; margin: 8px 0; font-size: 12px; }
.adv-table th, .adv-table td { text-align: left; padding: 6px 8px; border-bottom: 1px solid #2a2a4a; color: #aaaacc; }
.adv-table th { color: #6c63ff; font-weight: 600; }
.adv-table td { font-family: monospace; }
.adv-note { font-size: 11px; color: #6666aa; margin-top: 10px; line-height: 1.6; }
.reinforce-guide { background: #1a1a2e; border-radius: 12px; padding: 16px; margin-top: 16px; }
.guide-title { font-size: 16px; font-weight: 600; margin-bottom: 10px; } .guide-item { font-size: 13px; color: #aaaacc; padding: 3px 0; }
.error { color: #ff4444; font-size: 13px; text-align: center; margin: 12px 0; }
.footer-note { text-align: center; padding: 24px; color: #6666aa; font-size: 12px; }
.footer-tip { margin-top: 6px; color: #6c63ff; }
.help-card { background: linear-gradient(135deg, #1a1a3e, #1a1a2e); border: 1px solid #2a2a4a; border-radius: 12px; margin-bottom: 16px; overflow: hidden; }
.help-header { padding: 12px 16px; font-weight: 600; color: #c0c0e0; }
.help-body { padding: 0 16px 14px; font-size: 13px; line-height: 1.8; color: #aaaacc; }
.help-body strong { color: #6c63ff; }

/* 打印报告头（默认隐藏，仅打印/预览时显示） */
.print-only { display: none; }
.report-title { font-size: 20px; font-weight: 800; color: #6c63ff; margin-bottom: 6px; }
.report-meta { font-size: 12px; color: #555577; margin-bottom: 10px; }
.report-imgs { display: flex; gap: 12px; margin-bottom: 16px; }
.report-img { flex: 1; }
.report-img span { display: block; font-size: 11px; color: #6666aa; margin-bottom: 4px; }
.report-img img { width: 100%; max-height: 220px; object-fit: contain; border: 1px solid #ddd; border-radius: 6px; background: #fafaff; }

/* 打印导出 PDF 报告：浅色专业排版 */
@media print {
  @page { margin: 12mm; }
  .hero, .help-card, .upload-dual, .action-row, .btn, .footer-note, .error { display: none !important; }
  .print-only { display: block !important; }
  .page { max-width: none; padding: 0; }
  .result-panel { animation: none !important; opacity: 1 !important; transform: none !important; }
  .score-card, .radar-panel, .detail-card, .adv-panel, .adv-verdict, .adv-region, .reinforce-guide {
    background: #fff !important; color: #222 !important; box-shadow: none !important;
    -webkit-print-color-adjust: exact; print-color-adjust: exact;
  }
  /* 评分卡边框保留 inline 风险色（绿/黄/红），其余卡片统一浅灰边框 */
  .radar-panel, .detail-card, .adv-panel, .adv-verdict, .adv-region, .reinforce-guide { border-color: #dde0ea !important; }
  .score-msg, .suggestion, .detail-suggestion, .adv-msg, .adv-note, .metric, .guide-item, .score-label, .adv-label, .report-meta, .report-img span { color: #333 !important; }
  .details-title, .guide-title, .detail-index, .report-title { color: #1a1a2e !important; }
  .adv-table th, .adv-table td { color: #333 !important; border-bottom-color: #e0e0ea !important; }
  .score-num, .score-level, .detail-risk, .adv-region-verdict, .adv-label {
    -webkit-print-color-adjust: exact; print-color-adjust: exact;
  }
  .score-card, .radar-panel, .detail-card, .adv-verdict, .adv-region, .reinforce-guide, .report-head {
    page-break-inside: avoid; break-inside: avoid;
  }
  .report-head { page-break-after: avoid; }
  .reveal, .reveal * { opacity: 1 !important; transform: none !important; animation: none !important; }
}
</style>
