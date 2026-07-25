<script setup lang="ts">
import { ref, onUnmounted } from 'vue'
import { useImageUpload } from '../../composables/useImageUpload'
import { useOCR } from '../../composables/useOCR'
import { useDesensitize } from '../../composables/useDesensitize'
import { applyDesensitize, drawImageToCanvas, canvasToBlob } from '../../utils/canvas'

const { state: uploadState, handleFile, reset: resetUpload } = useImageUpload()
const { loading: ocrLoading, textRegions, objectRegions, error: ocrError, detect: ocrDetect } = useOCR()
const { selectedRegions, method, intensity, isProcessed, methodOptions, addRegion, removeRegion, clearRegions, markProcessed } = useDesensitize()

const canvasRef = ref<HTMLCanvasElement | null>(null)
const originalImage = ref('')
const processedImage = ref('')
const processingMode = ref<'local' | 'cloud'>('cloud')
const activeTab = ref<'detect' | 'desensitize' | 'result'>('detect')
const showHelp = ref(true)

function onFileSelected(e: Event) {
  const target = e.target as HTMLInputElement
  if (target.files?.[0]) {
    handleFile(target.files[0])
    activeTab.value = 'detect'
    clearRegions()
  }
}

async function runOCR() {
  if (!uploadState.value.file || uploadState.value.status !== 'ready') return
  if (processingMode.value === 'cloud') {
    await ocrDetect(uploadState.value.file, 'full')
  } else {
    ocrError.value = '本地OCR模式开发中，请使用云端增强模式'
  }
  if (textRegions.value.length > 0) {
    textRegions.value.forEach((r: any) => {
      if (r.sensitive && r.sensitive.risk_level !== 'low') {
        addRegion({ x: r.rect.x, y: r.rect.y, w: r.rect.w, h: r.rect.h })
      }
    })
  }
  objectRegions.value.forEach((r: any) => {
    addRegion({ x: r.rect.x, y: r.rect.y, w: r.rect.w, h: r.rect.h })
  })
  activeTab.value = 'desensitize'
}

async function runDesensitize() {
  if (!canvasRef.value || selectedRegions.value.length === 0) return
  await drawImageToCanvas(canvasRef.value, uploadState.value.file!)
  const ctx = canvasRef.value.getContext('2d')!
  originalImage.value = canvasRef.value.toDataURL('image/png').split(',')[1]
  selectedRegions.value.forEach((region) => {
    applyDesensitize(ctx, region, region.method || method.value, intensity.value)
  })
  processedImage.value = canvasRef.value.toDataURL('image/png').split(',')[1]
  markProcessed()
  activeTab.value = 'result'
}

async function downloadImage() {
  if (!canvasRef.value) return
  const blob = await canvasToBlob(canvasRef.value)
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = 'yindun_desensitized.png'; a.click()
  URL.revokeObjectURL(url)
}

function toggleRegion(region: {x:number,y:number,w:number,h:number}) {
  const idx = selectedRegions.value.findIndex(r => r.x === region.x && r.y === region.y)
  idx >= 0 ? removeRegion(idx) : addRegion(region)
}

function isRegionSelected(region: {x:number,y:number,w:number,h:number}): boolean {
  return selectedRegions.value.some(r => r.x === region.x && r.y === region.y)
}

function startOver() {
  resetUpload(); clearRegions(); originalImage.value = ''; processedImage.value = ''; activeTab.value = 'detect'
}

const fileInputRef = ref<HTMLInputElement | null>(null)
function triggerUpload() { fileInputRef.value?.click() }

onUnmounted(() => { resetUpload() })
</script>

<template>
  <div class="page">
    <div class="hero">
      <h1 class="hero-title">🛡️ 「隐盾」图片智能脱敏</h1>
      <p class="hero-sub">上传图片 → 自动识别敏感信息 → 一键脱敏 → 安全分享</p>
    </div>

    <!-- 使用说明 -->
    <div class="help-card" v-if="showHelp">
      <div class="help-header" @click="showHelp = false">
        <span>📖 怎么用？</span>
        <button class="help-close">✕</button>
      </div>
      <div class="help-body">
        <p><strong>①</strong> 上传一张包含敏感信息的截图（身份证、手机号、快递单、聊天记录等）</p>
        <p><strong>②</strong> 点击「开始识别」，AI 自动找出图中的敏感信息并用 <span style="color:#ff4444">红框</span> / <span style="color:#ffaa00">黄框</span> 标注</p>
        <p><strong>③</strong> 点击图上的框来选择要脱敏的区域，然后在右侧选择脱敏方式：</p>
        <div class="help-methods">
          <span class="help-tag">马赛克：日常够用，观感好</span>
          <span class="help-tag" style="background:rgba(108,99,255,0.2)">⭐ 不可逆替换：像素打散，AI还原不了</span>
          <span class="help-tag">高斯噪点：强模糊+噪声，二次防护</span>
        </div>
        <p><strong>④</strong> 点击「应用脱敏」→ 预览效果 → 下载。全程无需注册，免费使用。</p>
      </div>
    </div>

    <!-- 步骤指示器 -->
    <div class="steps">
      <div class="step" :class="{ active: activeTab === 'detect', done: activeTab !== 'detect' }">
        <span class="step-num">1</span><span class="step-label">上传图片</span>
      </div>
      <span class="step-line" :class="{ done: activeTab !== 'detect' }"></span>
      <div class="step" :class="{ active: activeTab === 'desensitize', done: activeTab === 'result' }">
        <span class="step-num">2</span><span class="step-label">确认脱敏</span>
      </div>
      <span class="step-line" :class="{ done: activeTab === 'result' }"></span>
      <div class="step" :class="{ active: activeTab === 'result' }">
        <span class="step-num">3</span><span class="step-label">下载图片</span>
      </div>
    </div>

    <!-- 上传区 -->
    <div class="upload-section" v-if="uploadState.status !== 'ready'">
      <div class="upload-zone" @click="triggerUpload">
        <span class="upload-icon">📤</span>
        <p class="upload-text">点击上传或拖拽图片到此处</p>
        <p class="upload-hint">支持 PNG / JPG / WebP，最大 20MB</p>
      </div>
      <input ref="fileInputRef" type="file" accept="image/png,image/jpeg,image/webp,image/bmp" style="display:none" @change="onFileSelected" />
      <div class="mode-selector">
        <p class="mode-label">识别模式：</p>
        <label class="mode-option"><input type="radio" v-model="processingMode" value="cloud" /> 云端增强（PaddleOCR GPU · 精准）</label>
        <label class="mode-option"><input type="radio" v-model="processingMode" value="local" /> 本地处理（浏览器端 · 隐私优先）</label>
      </div>
      <div v-if="uploadState.status === 'error'" class="error-msg">⚠️ {{ uploadState.errorMessage }}</div>
    </div>

    <!-- 工作区 -->
    <div class="workspace" v-if="uploadState.status === 'ready'">
      <div class="image-panel">
        <canvas v-show="isProcessed" ref="canvasRef" class="preview-canvas" />
        <img v-show="!isProcessed" :src="uploadState.previewUrl" class="preview-image" />
        <div v-if="!isProcessed && (textRegions.length > 0 || objectRegions.length > 0)" class="overlay">
          <div v-for="(region, i) in textRegions" :key="'t'+i" class="region-box"
            :class="{
              'risk-high': region.sensitive?.risk_level === 'high',
              'risk-medium': region.sensitive?.risk_level === 'medium',
              'risk-low': region.sensitive?.risk_level === 'low',
              selected: isRegionSelected({x: region.rect.x, y: region.rect.y, w: region.rect.w, h: region.rect.h}),
            }"
            :style="{
              left: (region.rect.x / uploadState.width * 100) + '%',
              top: (region.rect.y / uploadState.height * 100) + '%',
              width: (region.rect.w / uploadState.width * 100) + '%',
              height: (region.rect.h / uploadState.height * 100) + '%',
            }"
            @click.stop="toggleRegion({x: region.rect.x, y: region.rect.y, w: region.rect.w, h: region.rect.h})">
            <span class="region-label">{{ region.sensitive?.type || region.text }}</span>
          </div>
          <div v-for="(region, i) in objectRegions" :key="'o'+i" class="region-box object-region"
            :class="{ selected: isRegionSelected({x: region.rect.x, y: region.rect.y, w: region.rect.w, h: region.rect.h}) }"
            :style="{
              left: (region.rect.x / uploadState.width * 100) + '%',
              top: (region.rect.y / uploadState.height * 100) + '%',
              width: (region.rect.w / uploadState.width * 100) + '%',
              height: (region.rect.h / uploadState.height * 100) + '%',
            }"
            @click.stop="toggleRegion({x: region.rect.x, y: region.rect.y, w: region.rect.w, h: region.rect.h})">
            <span class="region-label">{{ region.label }}</span>
          </div>
        </div>
        <div v-if="ocrLoading" class="loading-overlay"><p class="loading-text">🔍 AI 正在识别敏感信息...</p></div>
      </div>

      <div class="control-panel">
        <div v-if="!isProcessed && !ocrLoading && textRegions.length === 0 && objectRegions.length === 0">
          <button class="btn btn-primary" @click="runOCR" :disabled="ocrLoading">🔍 开始识别</button>
        </div>

        <div v-if="(textRegions.length > 0 || objectRegions.length > 0) && !isProcessed" class="regions-list">
          <p class="panel-title">检测到 {{ textRegions.length }} 处文本<span v-if="objectRegions.length"> + {{ objectRegions.length }} 个目标</span></p>
          <div class="method-select">
            <p class="section-title">脱敏方式</p>
            <label v-for="opt in methodOptions" :key="opt.value" class="method-option">
              <input type="radio" v-model="method" :value="opt.value" />
              <span>{{ opt.label }}</span>
              <span class="method-desc">{{ opt.desc }}</span>
            </label>
          </div>
          <div class="intensity-slider">
            <p class="section-title">脱敏强度: {{ Math.round(intensity * 100) }}%</p>
            <input type="range" v-model.number="intensity" min="0.1" max="1.0" step="0.05" />
          </div>
          <p class="selected-count">已选 {{ selectedRegions.length }} 个脱敏区域<span v-if="selectedRegions.length === 0" class="hint-text">（点击图片上的框选择）</span></p>
          <button class="btn btn-warn" @click="runDesensitize" :disabled="selectedRegions.length === 0">🔒 应用脱敏 ({{ selectedRegions.length }} 处)</button>
        </div>

        <div v-if="isProcessed" class="result-panel">
          <p class="success-msg">✅ 脱敏完成</p>
          <p class="result-info">共处理 {{ selectedRegions.length }} 处敏感信息</p>
          <button class="btn btn-primary" @click="downloadImage">💾 下载图片</button>
          <button class="btn btn-secondary" @click="startOver">🔄 重新处理</button>
          <div class="check-link">
            <span>还不够放心？</span>
            <router-link to="/check" class="link">👉 去检测脱敏强度</router-link>
          </div>
        </div>

        <div v-if="ocrError" class="error-msg">⚠️ {{ ocrError }}</div>
      </div>
    </div>

    <div class="footer-note">
      <p>🔒 图片仅在浏览器或内存中处理，<strong>不会存储到服务器</strong></p>
    </div>
  </div>
</template>

<style scoped>
.page { max-width: 1200px; margin: 0 auto; padding: 16px; }
.hero { text-align: center; padding: 24px 0; }
.hero-title { font-size: 28px; font-weight: 700; color: #e0e0f0; }
.hero-sub { color: #8888aa; font-size: 14px; margin-top: 8px; }
.steps { display: flex; align-items: center; justify-content: center; gap: 0; margin: 16px 0 24px; }
.step { display: flex; flex-direction: column; align-items: center; gap: 4px; }
.step-num { width: 36px; height: 36px; border-radius: 50%; background: #2a2a4a; color: #8888aa; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 16px; }
.step.active .step-num { background: #6c63ff; color: #fff; }
.step.done .step-num { background: #22c55e; color: #fff; }
.step-label { font-size: 12px; color: #8888aa; }
.step-line { width: 60px; height: 2px; background: #2a2a4a; margin-bottom: 20px; display: inline-block; }
.step-line.done { background: #22c55e; }
.upload-zone { border: 2px dashed #4a4a6a; border-radius: 16px; padding: 48px 24px; text-align: center; cursor: pointer; transition: all 0.2s; }
.upload-zone:hover { border-color: #6c63ff; background: rgba(108,99,255,0.05); }
.upload-icon { font-size: 48px; }
.upload-text { color: #c0c0e0; font-size: 16px; margin-top: 12px; }
.upload-hint { color: #6666aa; font-size: 12px; margin-top: 6px; }
.mode-selector { margin-top: 16px; background: #1a1a2e; border-radius: 12px; padding: 16px; }
.mode-label { font-weight: 600; font-size: 14px; margin-bottom: 8px; }
.mode-option { display: flex; align-items: center; gap: 8px; padding: 6px 0; color: #b0b0d0; font-size: 13px; cursor: pointer; }
.workspace { display: flex; gap: 16px; margin-top: 16px; }
.image-panel { flex: 1; position: relative; background: #111122; border-radius: 12px; overflow: hidden; min-height: 300px; }
.preview-canvas, .preview-image { width: 100%; display: block; }
.overlay { position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; }
.region-box { position: absolute; border: 2px solid #ffcc00; background: rgba(255,204,0,0.08); border-radius: 4px; cursor: pointer; pointer-events: auto; transition: all 0.15s; }
.region-box.risk-high { border-color: #ff4444; background: rgba(255,68,68,0.12); }
.region-box.risk-medium { border-color: #ffaa00; background: rgba(255,170,0,0.10); }
.region-box.selected { border-color: #6c63ff; background: rgba(108,99,255,0.20); border-width: 3px; box-shadow: 0 0 8px rgba(108,99,255,0.4); }
.region-box.object-region { border-color: #00ccff; background: rgba(0,204,255,0.08); }
.region-label { font-size: 10px; color: #fff; background: rgba(0,0,0,0.7); padding: 1px 4px; border-radius: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%; display: block; }
.control-panel { width: 280px; flex-shrink: 0; background: #1a1a2e; border-radius: 12px; padding: 16px; }
.panel-title { font-size: 16px; font-weight: 600; margin-bottom: 12px; }
.section-title { font-size: 13px; font-weight: 600; color: #aaaacc; margin: 12px 0 6px; }
.method-option { display: flex; flex-direction: column; padding: 8px 0; border-bottom: 1px solid #2a2a4a; gap: 2px; cursor: pointer; }
.method-desc { font-size: 11px; color: #6666aa; }
.selected-count { font-size: 13px; color: #b0b0d0; margin: 12px 0; }
.hint-text { color: #6666aa; font-size: 11px; }
.btn { display: block; width: 100%; padding: 12px; border-radius: 8px; border: none; font-size: 15px; font-weight: 600; cursor: pointer; margin: 8px 0; transition: all 0.15s; }
.btn-primary { background: #6c63ff; color: #fff; }
.btn-primary:hover { background: #5a52e0; }
.btn-warn { background: #ff6b35; color: #fff; }
.btn-warn:hover { background: #e55a2b; }
.btn-secondary { background: #2a2a4a; color: #c0c0e0; }
.btn:disabled { opacity: 0.4; cursor: not-allowed; }
.result-panel { text-align: center; }
.success-msg { font-size: 20px; font-weight: 700; color: #22c55e; }
.result-info { color: #8888aa; font-size: 13px; margin: 8px 0; }
.check-link { margin-top: 16px; font-size: 13px; color: #8888aa; }
.link { color: #6c63ff; margin-left: 4px; text-decoration: none; }
.loading-overlay { position: absolute; inset: 0; background: rgba(15,15,26,0.8); display: flex; align-items: center; justify-content: center; }
.loading-text { color: #e0e0f0; font-size: 16px; }
.error-msg { color: #ff4444; font-size: 13px; background: rgba(255,68,68,0.1); padding: 10px; border-radius: 8px; margin-top: 8px; }
.footer-note { text-align: center; padding: 24px; color: #6666aa; font-size: 12px; }
.intensity-slider input { width: 100%; accent-color: #6c63ff; margin: 4px 0; }
/* 帮助面板 */
.help-card { background: linear-gradient(135deg, #1a1a3e, #1a1a2e); border: 1px solid #2a2a4a; border-radius: 12px; margin-bottom: 16px; overflow: hidden; }
.help-header { display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; cursor: pointer; font-weight: 600; color: #c0c0e0; }
.help-close { background: none; border: none; color: #6666aa; font-size: 16px; cursor: pointer; }
.help-body { padding: 0 16px 14px; font-size: 13px; line-height: 2; color: #aaaacc; }
.help-body strong { color: #6c63ff; margin-right: 4px; }
.help-methods { display: flex; gap: 8px; flex-wrap: wrap; margin: 8px 0 12px 20px; }
.help-tag { background: rgba(255,170,0,0.1); border: 1px solid #2a2a4a; border-radius: 6px; padding: 3px 10px; font-size: 12px; color: #b0b0d0; }
</style>
