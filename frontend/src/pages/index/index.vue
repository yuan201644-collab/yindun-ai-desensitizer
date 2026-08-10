<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from 'vue'
import { useImageUpload } from '../../composables/useImageUpload'
import { useOCR } from '../../composables/useOCR'
import { useDesensitize } from '../../composables/useDesensitize'
import { applyDesensitize, drawImageToCanvas, canvasToBlob } from '../../utils/canvas'
import { SCENARIO_TEMPLATES, getTemplate } from '../../utils/scenarioTemplates'
import { recognizeLocal, detectNameColumn } from '../../utils/localOCR'
import { assessComplexity, type ComplexityResult } from '../../utils/imageComplexity'
import { setCheckImages } from '../../utils/checkTransfer'
import { getOcrEstimateMs, recordOcrDuration } from '../../utils/ocrStats'

const { state: uploadState, handleFile, reset: resetUpload } = useImageUpload()
const { loading: ocrLoading, textRegions, objectRegions, error: ocrError, detect: ocrDetect } = useOCR()
const { selectedRegions, method, intensity, isProcessed, methodOptions, addRegion, removeRegion, clearRegions, markProcessed, resetProcessed } = useDesensitize()

const canvasRef = ref<HTMLCanvasElement | null>(null)
const originalImage = ref('')
const processedImage = ref('')
const processingMode = ref<'local' | 'cloud'>('cloud')
const activeTab = ref<'detect' | 'desensitize' | 'result'>('detect')
const showHelp = ref(true)
const activeTemplate = ref('general')
const activeTemplateObj = computed(() => getTemplate(activeTemplate.value))
const detectEmpty = ref(false)
const complexity = ref<ComplexityResult | null>(null)
// 后端 OCR 加载计时与预估（预估来自历史真实耗时，非臆测）
const loadingElapsed = ref(0)
const loadingEstimate = ref<number | null>(null)
let loadingTimer: number | null = null
let ocrStartMs = 0

const loadingTimeText = computed(() => {
  const el = loadingElapsed.value
  if (loadingEstimate.value) {
    const remain = Math.max(0, Math.ceil((loadingEstimate.value - el * 1000) / 1000))
    return `已用时 ${el}s · 预计还需 ~${remain}s`
  }
  return `首次识别稍慢 · 已用时 ${el}s`
})

function resetDetection() {
  textRegions.value = []
  objectRegions.value = []
  ocrError.value = ''
  detectEmpty.value = false
}

function applyFile(file: File) {
  handleFile(file)
  activeTab.value = 'detect'
  clearRegions()
  resetDetection()
  // 分流引导：评估图片复杂度（表格/密集 → 推荐精准增强）
  complexity.value = null
  assessComplexity(file).then(c => { complexity.value = c }).catch(() => { complexity.value = null })
}

function onFileSelected(e: Event) {
  const target = e.target as HTMLInputElement
  if (target.files?.[0]) applyFile(target.files[0])
}

// P2 修复：拖拽上传（与点击上传走同一入口）
function onDrop(e: DragEvent) {
  const file = e.dataTransfer?.files?.[0]
  if (file) applyFile(file)
}

async function runOCR() {
  if (!uploadState.value.file || uploadState.value.status !== 'ready') return
  ocrError.value = ''
  if (processingMode.value === 'cloud') {
    // 计时 + 预估（预估用历史真实耗时平均）
    ocrStartMs = Date.now()
    loadingElapsed.value = 0
    loadingEstimate.value = getOcrEstimateMs()
    if (loadingTimer) clearInterval(loadingTimer)
    loadingTimer = window.setInterval(() => { loadingElapsed.value = Math.floor((Date.now() - ocrStartMs) / 1000) }, 500)
    try {
      await ocrDetect(uploadState.value.file, 'full')
    } finally {
      if (loadingTimer) { clearInterval(loadingTimer); loadingTimer = null }
      recordOcrDuration(Date.now() - ocrStartMs)
    }
  } else {
    try {
      textRegions.value = await recognizeLocal(uploadState.value.file)
      objectRegions.value = []
    } catch (e: any) {
      ocrError.value = '本地 OCR 失败：' + (e.message || '请检查网络或切换精准增强模式')
    }
  }
  // 仅当无错误时才提示"未检测到"（有错误时显示具体错误，不误导）
  if (!ocrError.value) detectEmpty.value = textRegions.value.length === 0 && objectRegions.value.length === 0
  applyTemplateAutoSelect()
  activeTab.value = 'desensitize'
}

/** 按当前场景模板自动选区（模板带 preferTypes 时只选偏好类型；通用则按风险全选） */
function applyTemplateAutoSelect() {
  clearRegions()
  const t = activeTemplateObj.value
  textRegions.value.forEach((r: any) => {
    const type = r.sensitive?.type
    const inPrefer = t.preferTypes?.length ? t.preferTypes!.includes(type) : false
    const byRisk = r.sensitive && r.sensitive.risk_level !== 'low'
    if (inPrefer || (!t.preferTypes?.length && byRisk)) {
      addRegion({ x: r.rect.x, y: r.rect.y, w: r.rect.w, h: r.rect.h })
    }
  })
  objectRegions.value.forEach((r: any) => {
    addRegion({ x: r.rect.x, y: r.rect.y, w: r.rect.w, h: r.rect.h })
  })
}

function onTemplateChange() {
  const t = getTemplate(activeTemplate.value)
  if (t.defaultMethod) method.value = t.defaultMethod
  if (t.defaultIntensity) intensity.value = t.defaultIntensity
  if (textRegions.value.length || objectRegions.value.length) applyTemplateAutoSelect()
}

// P1 修复：切换脱敏方法时，同步到所有已选区域（避免"改了方法实际还是旧算法"）
watch(method, (m) => {
  selectedRegions.value.forEach(r => { r.method = m })
})

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
  resetUpload(); clearRegions(); resetDetection(); originalImage.value = ''; processedImage.value = ''; activeTab.value = 'detect'; complexity.value = null
}

// P3 修复：脱敏后可返回选区调整（回到原图预览，保留选区）
function backToSelect() {
  resetProcessed()
  activeTab.value = 'desensitize'
}

// 跳转检测强度前，把原图/脱敏图写入中转，检测页自动带入（无需重新上传）
function prepareCheck() {
  if (originalImage.value && processedImage.value) {
    setCheckImages(originalImage.value, processedImage.value)
  }
}

// ---------- 按类别一键全选 ----------
interface RegionRect { x: number; y: number; w: number; h: number }
interface CategoryGroup { key: string; label: string; regions: RegionRect[]; total: number; selectedCount: number }

const allRegions = computed<RegionRect[]>(() => [
  ...textRegions.value.map((r: any) => ({ x: r.rect.x, y: r.rect.y, w: r.rect.w, h: r.rect.h })),
  ...objectRegions.value.map((r: any) => ({ x: r.rect.x, y: r.rect.y, w: r.rect.w, h: r.rect.h })),
])

const allSelected = computed(() => allRegions.value.length > 0 && allRegions.value.every(r => isRegionSelected(r)))

/** 相同文字出现 >=N 次 → 创建该图片专属的"重复文字分类"（如名单里的学院名/性别列） */
const RECURRING_MIN = 3

/** 按敏感类别/目标分组 + 重复文字创建图片专属分类，统计各组的选中数 */
const categoryGroups = computed<CategoryGroup[]>(() => {
  const map = new Map<string, CategoryGroup>()
  const push = (label: string, rect: RegionRect) => {
    const key = label || '未识别'
    if (!map.has(key)) map.set(key, { key, label: key, regions: [], total: 0, selectedCount: 0 })
    const g = map.get(key)!
    g.regions.push(rect); g.total++
    if (isRegionSelected(rect)) g.selectedCount++
  }
  // 第一遍：敏感类型入类别；非敏感文本统计出现次数
  const textCounts = new Map<string, number>()
  textRegions.value.forEach((r: any) => {
    const s = r.sensitive
    const rect = { x: r.rect.x, y: r.rect.y, w: r.rect.w, h: r.rect.h }
    if (s) {
      push(s.object_label || s.type, rect)
    } else if (r.text) {
      textCounts.set(r.text, (textCounts.get(r.text) || 0) + 1)
    }
  })
  objectRegions.value.forEach((r: any) =>
    push(r.label || '目标', { x: r.rect.x, y: r.rect.y, w: r.rect.w, h: r.rect.h }))
  // 第二遍：出现 >=N 次的相同文字 → 图片专属分类（📌 标记）
  textRegions.value.forEach((r: any) => {
    const s = r.sensitive
    if (!s && r.text && (textCounts.get(r.text) || 0) >= RECURRING_MIN) {
      push(`📌 ${r.text}`, { x: r.rect.x, y: r.rect.y, w: r.rect.w, h: r.rect.h })
    }
  })
  // 第三遍：姓名列检测——同一列 2-3 字中文、多为不同文字 → "👤 姓名"分类
  const nameCol = detectNameColumn(textRegions.value)
  if (nameCol) {
    nameCol.forEach(r => push('👤 姓名', { x: r.rect.x, y: r.rect.y, w: r.rect.w, h: r.rect.h }))
  }
  return Array.from(map.values())
})

/** 一键全选/取消某类别 */
function toggleCategory(group: CategoryGroup) {
  const allOn = group.regions.every(r => isRegionSelected(r))
  if (allOn) {
    for (let i = selectedRegions.value.length - 1; i >= 0; i--) {
      const r = selectedRegions.value[i]
      if (group.regions.some(gr => gr.x === r.x && gr.y === r.y)) removeRegion(i)
    }
  } else {
    group.regions.forEach(r => { if (!isRegionSelected(r)) addRegion(r) })
  }
}

/** 全选 / 全不选 */
function toggleAll() {
  clearRegions()
  if (!allSelected.value) allRegions.value.forEach(r => addRegion(r))
}

const fileInputRef = ref<HTMLInputElement | null>(null)
function triggerUpload() { fileInputRef.value?.click() }

onUnmounted(() => { resetUpload() })
</script>

<template>
  <div class="page">
    <div class="hero">
      <h1 class="hero-title fade-up">🛡️ 「隐盾」图片智能脱敏</h1>
      <p class="hero-sub fade-up" style="animation-delay:0.08s">上传图片 → 自动识别敏感信息 → 一键脱敏 → 安全分享</p>
    </div>

    <!-- 使用说明 -->
    <div class="help-card fade-in" v-if="showHelp">
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
    <div class="steps fade-in">
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
      <div class="upload-zone scale-in" @click="triggerUpload" @dragover.prevent @drop.prevent="onDrop">
        <span class="upload-icon">📤</span>
        <p class="upload-text">点击上传或拖拽图片到此处</p>
        <p class="upload-hint">支持 PNG / JPG / WebP，最大 20MB</p>
      </div>
      <div class="mode-selector">
        <p class="mode-label">识别模式：</p>
        <label class="mode-option"><input type="radio" v-model="processingMode" value="cloud" /> 精准增强（PaddleOCR · 高精度）</label>
        <label class="mode-option"><input type="radio" v-model="processingMode" value="local" /> 本地处理（Tesseract WASM · 图片不出设备）</label>
      </div>
      <div v-if="uploadState.status === 'error'" class="error-msg">⚠️ {{ uploadState.errorMessage }}</div>
    </div>

    <!-- 文件输入框：放在上传区外，保证进入工作区（更换图片）时始终存在 -->
    <input ref="fileInputRef" type="file" accept="image/png,image/jpeg,image/webp,image/bmp" style="display:none" @change="onFileSelected" />

    <!-- 工作区 -->
    <div class="workspace" v-if="uploadState.status === 'ready'">
      <div class="image-panel fade-in">
        <canvas v-show="isProcessed" ref="canvasRef" class="preview-canvas" />
        <img v-show="!isProcessed" :src="uploadState.previewUrl" class="preview-image" />
        <div v-if="!isProcessed && (textRegions.length > 0 || objectRegions.length > 0)" class="overlay">
          <div v-for="(region, i) in textRegions" :key="'t'+i" class="region-box"
            :class="{
              'risk-high': region.sensitive?.risk_level === 'high',
              'risk-medium': region.sensitive?.risk_level === 'medium',
              'risk-low': region.sensitive?.risk_level === 'low',
              selected: isRegionSelected({x: region.rect.x, y: region.rect.y, w: region.rect.w, h: region.rect.h}),
              'region-selected-anim': isRegionSelected({x: region.rect.x, y: region.rect.y, w: region.rect.w, h: region.rect.h}),
            }"
            :style="{
              left: (region.rect.x / uploadState.width * 100) + '%',
              top: (region.rect.y / uploadState.height * 100) + '%',
              width: (region.rect.w / uploadState.width * 100) + '%',
              height: (region.rect.h / uploadState.height * 100) + '%',
            }"
            @click.stop="toggleRegion({x: region.rect.x, y: region.rect.y, w: region.rect.w, h: region.rect.h})">
            <span class="region-label">{{ region.sensitive?.object_label || region.sensitive?.type || region.text }}</span>
          </div>
          <div v-for="(region, i) in objectRegions" :key="'o'+i" class="region-box object-region"
            :class="{ selected: isRegionSelected({x: region.rect.x, y: region.rect.y, w: region.rect.w, h: region.rect.h}), 'region-selected-anim': isRegionSelected({x: region.rect.x, y: region.rect.y, w: region.rect.w, h: region.rect.h}) }"
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
        <div v-if="ocrLoading" class="loading-overlay fade-in">
          <div class="scan-frame"><div class="scan-line"></div></div>
          <div class="loading-content">
            <p class="loading-text">{{ processingMode === 'local' ? '🔍 本地识别中（首次需下载语言包，图片不出设备）...' : '🔍 AI 正在识别敏感信息...' }}</p>
            <p v-if="processingMode === 'cloud'" class="loading-time">{{ loadingTimeText }}</p>
          </div>
        </div>
      </div>

      <div class="control-panel fade-in">
        <div v-if="complexity && !isProcessed" class="complexity-banner fade-in" :class="complexity.level">
          <span class="cb-text">{{ complexity.reason }}</span>
          <button v-if="complexity.level !== 'simple' && processingMode === 'local'" class="cb-btn" @click="processingMode = 'cloud'">改用精准增强</button>
          <span v-else-if="complexity.level === 'simple'" class="cb-ok">✓ 两种模式都可用</span>
        </div>
        <div class="image-actions" v-if="!isProcessed">
          <button class="btn btn-small" @click="triggerUpload">🔄 更换图片</button>
          <button class="btn btn-small btn-danger" @click="startOver">🗑️ 删除图片</button>
        </div>

        <div v-if="!isProcessed && !ocrLoading && textRegions.length === 0 && objectRegions.length === 0">
          <button v-if="!detectEmpty" class="btn btn-primary" @click="runOCR" :disabled="ocrLoading">🔍 开始识别</button>
          <div v-else class="info-msg">😕 未检测到敏感信息，可更换图片、切换识别模式或换一张更清晰的图</div>
        </div>

        <div v-if="(textRegions.length > 0 || objectRegions.length > 0) && !isProcessed" class="regions-list">
          <p class="panel-title">检测到 {{ textRegions.length }} 处文本<span v-if="objectRegions.length"> + {{ objectRegions.length }} 个目标</span></p>
          <div class="category-select" v-if="categoryGroups.length">
            <p class="section-title">⚡ 按类别全选</p>
            <div class="category-chips">
              <span v-for="g in categoryGroups" :key="g.key" class="category-chip chip-pop"
                :class="{ all: g.total > 0 && g.selectedCount === g.total, partial: g.selectedCount > 0 && g.selectedCount < g.total }"
                @click="toggleCategory(g)">{{ g.label }} {{ g.selectedCount }}/{{ g.total }}</span>
            </div>
            <div class="select-all-row">
              <span class="select-all" @click="toggleAll">{{ allSelected ? '✖ 取消全选' : '✔ 全选' }}</span>
            </div>
          </div>
          <div class="template-select">
            <p class="section-title">🎯 场景模板</p>
            <div class="template-list">
              <span v-for="t in SCENARIO_TEMPLATES" :key="t.id" class="template-chip chip-pop" :class="{ active: activeTemplate === t.id }" :title="t.desc" @click="activeTemplate = t.id; onTemplateChange()">{{ t.icon }} {{ t.name }}</span>
            </div>
            <p class="template-desc">{{ activeTemplateObj.desc }}</p>
          </div>
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

        <div v-if="isProcessed" class="result-panel scale-in">
          <p class="success-msg">✅ 脱敏完成</p>
          <p class="result-info">共处理 {{ selectedRegions.length }} 处敏感信息</p>
          <button class="btn btn-primary" @click="downloadImage">💾 下载图片</button>
          <button class="btn btn-secondary" @click="backToSelect">↩️ 返回选区调整</button>
          <button class="btn btn-secondary" @click="startOver">🔄 重新处理</button>
          <div class="check-link">
            <span>还不够放心？</span>
            <router-link to="/check" class="link" @click="prepareCheck">👉 去检测脱敏强度（自动带入图片）</router-link>
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
.template-list { display: flex; gap: 6px; flex-wrap: wrap; }
.template-chip { background: #2a2a4a; color: #aaaacc; font-size: 12px; padding: 5px 12px; border-radius: 16px; cursor: pointer; border: 1px solid transparent; transition: all 0.15s; }
.template-chip.active { background: rgba(108,99,255,0.2); color: #6c63ff; border-color: #6c63ff; font-weight: 600; }
.template-desc { font-size: 11px; color: #6666aa; margin: 6px 0 2px; line-height: 1.5; }
.complexity-banner { display: flex; flex-direction: column; gap: 6px; border-radius: 10px; padding: 10px 12px; margin-bottom: 10px; font-size: 12px; line-height: 1.5; }
.complexity-banner.simple { background: rgba(34,197,94,0.12); border: 1px solid rgba(34,197,94,0.4); color: #4ade80; }
.complexity-banner.medium { background: rgba(255,170,0,0.1); border: 1px solid rgba(255,170,0,0.4); color: #ffc94d; }
.complexity-banner.complex { background: rgba(255,107,53,0.12); border: 1px solid rgba(255,107,53,0.4); color: #ffab91; }
.cb-text { word-break: break-all; }
.cb-btn { align-self: flex-start; background: #ff6b35; color: #fff; border: none; border-radius: 6px; padding: 5px 12px; font-size: 12px; font-weight: 600; cursor: pointer; }
.cb-ok { color: #4ade80; font-size: 11px; }
.image-actions { display: flex; gap: 8px; margin-bottom: 8px; }
.btn-small { flex: 1; padding: 8px 0; font-size: 13px; margin: 0; }
.btn-danger { background: #3a1a1a; color: #ff6b6b; }
.btn-danger:hover { background: #4a2020; }
.category-select { margin-bottom: 4px; }
.category-chips { display: flex; gap: 6px; flex-wrap: wrap; }
.category-chip { background: #2a2a4a; color: #aaaacc; font-size: 12px; padding: 5px 10px; border-radius: 14px; cursor: pointer; border: 1px solid transparent; transition: all 0.15s; }
.category-chip:hover { border-color: #6c63ff; }
.category-chip.all { background: rgba(108,99,255,0.22); color: #6c63ff; border-color: #6c63ff; font-weight: 600; }
.category-chip.partial { border-color: #ffaa00; color: #ffaa00; }
.select-all-row { margin-top: 6px; text-align: right; }
.select-all { font-size: 12px; color: #6c63ff; cursor: pointer; }
.info-msg { color: #6c63ff; font-size: 13px; background: rgba(108,99,255,0.1); padding: 10px; border-radius: 8px; margin-top: 8px; }

/* P3 修复：移动端响应式 */
@media (max-width: 768px) {
  .workspace { flex-direction: column; }
  .control-panel { width: 100%; }
  .image-panel { min-height: 220px; }
  .steps .step-line { width: 30px; }
}
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
