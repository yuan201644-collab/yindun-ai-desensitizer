<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useImageUpload } from '../../composables/useImageUpload'
import { useOCR } from '../../composables/useOCR'
import { useDesensitize } from '../../composables/useDesensitize'
import { applyDesensitize, drawImageToCanvas, canvasToBlob } from '../../utils/canvas'
import { SCENARIO_TEMPLATES, getTemplate } from '../../utils/scenarioTemplates'
import { recognizeLocal, detectNameColumn } from '../../utils/localOCR'
import { assessComplexity, type ComplexityResult } from '../../utils/imageComplexity'
import { setCheckImages, setCheckRegions } from '../../utils/checkTransfer'
import { getOcrEstimateMs, recordOcrDuration } from '../../utils/ocrStats'
import { hitTestRegions, createRegionCycle, selectableTextRegions, type Rect } from '../../utils/regionSelect'

const { state: uploadState, handleFile, reset: resetUpload } = useImageUpload()
const { loading: ocrLoading, textRegions, objectRegions, error: ocrError, detect: ocrDetect } = useOCR()
const { selectedRegions, method, intensity, isProcessed, methodOptions, addRegion, removeRegion, clearRegions, markProcessed, resetProcessed } = useDesensitize()
const irreversibleLevel = ref(1) // 不可逆保护等级 1-3（1/2/3 轮打散）

const router = useRouter()
const canvasRef = ref<HTMLCanvasElement | null>(null)
const originalImage = ref('')
const processedImage = ref('')
const processingMode = ref<'local' | 'cloud'>('cloud')
const activeTab = ref<'detect' | 'desensitize' | 'result'>('detect')
const showHelp = ref(true)
const activeTemplate = ref('general')
const activeTemplateObj = computed(() => getTemplate(activeTemplate.value))

// ⭐ 预览缩放与平移：transform scale(zoom) + translate(pan)，滚轮以光标为中心缩放，非画框时拖拽平移
const zoom = ref(1)
const zoomStep = 0.25
const pan = ref({ x: 0, y: 0 })
let panStart: { x: number; y: number; panX: number; panY: number } | null = null
const panning = ref(false)
/** 以某 client 坐标为缩放中心，调整 pan 使光标下的图片点保持不动（transform: translate(p) scale(z) 推导） */
function zoomAt(cx: number, cy: number, newZoom: number) {
  const wrap = document.querySelector<HTMLElement>('.preview-wrap')
  if (!wrap) { zoom.value = newZoom; return }
  const r = wrap.getBoundingClientRect()
  const k = newZoom / zoom.value
  pan.value.x += (cx - r.left) * (1 - k)
  pan.value.y += (cy - r.top) * (1 - k)
  zoom.value = newZoom
}
function zoomAtCenter(t: number) {
  const wrap = document.querySelector<HTMLElement>('.preview-wrap')
  if (!wrap) { zoom.value = t; return }
  const r = wrap.getBoundingClientRect()
  zoomAt(r.left + r.width / 2, r.top + r.height / 2, t)
}
function zoomIn() { zoomAtCenter(Math.min(3, +(zoom.value + zoomStep).toFixed(2))) }
function zoomOut() { zoomAtCenter(Math.max(0.5, +(zoom.value - zoomStep).toFixed(2))) }
function zoomReset() { zoom.value = 1; pan.value = { x: 0, y: 0 } }
function onWheelZoom(e: WheelEvent) {
  e.preventDefault()
  const target = Math.min(3, Math.max(0.5, +(zoom.value + (e.deltaY < 0 ? zoomStep : -zoomStep)).toFixed(2)))
  zoomAt(e.clientX, e.clientY, target)
}
const detectEmpty = ref(false)
const complexity = ref<ComplexityResult | null>(null)
// 手动画框：人工二次修正（OCR 漏检时手动补框）
const drawMode = ref(false)
const drawing = ref(false)
const drawBox = ref<{ x: number; y: number; w: number; h: number } | null>(null)
let drawStart: { x: number; y: number } | null = null
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

// ⭐ 识别全文：把多行 OCR 结果按阅读顺序（y→x）拼成整段，供一键复制。
//   同一行的多个字体块用空格连接，不同行换行（阈值按行高自适应，避免跨行误连）。
const fullText = computed(() => {
  // 按中心 Y 分桶成"近似行"，桶内按 X 排序（标签在左、值在右），桶间换行＝整段可复制文本
  const items = textRegions.value
    .map(r => ({ x: r.rect.x, h: r.rect.h, cy: r.rect.y + r.rect.h / 2, t: ((r.text || '') as string).trim() }))
    .filter(r => r.t)
    .sort((a, b) => (a.cy - b.cy) || (a.x - b.x))
  const buckets: typeof items[] = []
  for (const it of items) {
    const last = buckets[buckets.length - 1]
    if (last && Math.abs(it.cy - last.reduce((s, x) => s + x.cy, 0) / last.length) <= 12) last.push(it)
    else buckets.push([it])
  }
  return buckets
    .map(b => b.sort((a, b) => a.x - b.x).map(x => x.t).join(' '))
    .join('\n')
})

/** 📋 复制识别全文到剪贴板 */
async function copyFullText() {
  try {
    await navigator.clipboard.writeText(fullText.value)
    alert('已复制识别全文')
  } catch {
    alert('复制失败：浏览器未授予剪贴板权限，请手动全选复制')
  }
}

// ⭐ 段落聚合：把竖直相邻、x 区间重叠的多行识别成"一整段"，图片上可整段全选打码。
//   行距动态阈值 = 行高×PARAGRAPH_GAP_RATIO（下限 14px），兼容营业执照经营范围这类
//   字号低、行距松的多行段落；两行 x 有重叠才同段（多栏文字不同 x 不会误并）。
const PARAGRAPH_GAP_RATIO = 1.5
const PARAGRAPH_MIN_GAP = 14
interface Paragraph { rect: Rect; rects: Rect[]; sensitiveRects: Rect[] }
const paragraphs = computed<Paragraph[]>(() => {
  const rows = textRegions.value
    .map(r => ({ rect: r.rect as Rect, sensitive: (r as any).sensitive != null }))
    .slice()
    .sort((a, b) => a.rect.y - b.rect.y)
  const paras: Paragraph[] = []
  for (const r of rows) {
    const last = paras[paras.length - 1]
    if (last) {
      const lr = last.rect
      const gap = r.rect.y - (lr.y + lr.h)
      const gapLimit = Math.max(PARAGRAPH_MIN_GAP, Math.round((lr.h || 20) * PARAGRAPH_GAP_RATIO))
      const xOverlap = r.rect.x < lr.x + lr.w && r.rect.x + r.rect.w > lr.x
      if (gap >= -1 && gap <= gapLimit && xOverlap) {
        last.rects.push(r.rect)
        if (r.sensitive) last.sensitiveRects.push(r.rect)
        last.rect = {
          x: Math.min(last.rect.x, r.rect.x),
          y: last.rect.y,
          w: Math.max(last.rect.x + last.rect.w, r.rect.x + r.rect.w) - Math.min(last.rect.x, r.rect.x),
          h: r.rect.y + r.rect.h - last.rect.y,
        }
        continue
      }
    }
    paras.push({ rect: { ...r.rect }, rects: [r.rect], sensitiveRects: r.sensitive ? [r.rect] : [] })
  }
  return paras
})
// 诊断辅助：硬刷新后看控制台，确认有多少行并成了整段
watch(paragraphs, ps => {
  const multi = ps.filter(p => p.rects.length >= 2)
  console.log(`[段落] 共 ${ps.length} 行组、多行段 ${multi.length} 个 →`, multi.map(p => p.rects.length + '行'))
})

/** 点一段整选：把这一段的所有行全部加入打码选区（已全选则整段取消）。 */
function toggleParagraph(p: Paragraph) {
  const rects = p.rects
  if (!rects.length) return
  const all = rects.every(r => isRegionSelected(r))
  if (all) {
    selectedRegions.value = selectedRegions.value.filter(r => !rects.some(rr => r.x === rr.x && r.y === rr.y))
  } else {
    rects.forEach(r => addRegion(r))
  }
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
  // ⭐ YOLO 对象区域是"提示框"（如身份证/人像整框），不再自动打码——
  // 大框会整块覆盖标签+内容（用户反馈"全部打码"的根因）。
  // 保留：对象框显示、分组列表、手动点选打码；自动打码聚焦 OCR 识别的敏感文字。
  // objectRegions.value.forEach((r: any) => { addRegion({ x: r.rect.x, y: r.rect.y, w: r.rect.w, h: r.rect.h }) })
}

function onTemplateChange() {
  const t = getTemplate(activeTemplate.value)
  if (t.defaultMethod) method.value = t.defaultMethod
  if (t.defaultIntensity) intensity.value = t.defaultIntensity
  if (textRegions.value.length || objectRegions.value.length) applyTemplateAutoSelect()
}

// 首页惠民快捷场景入口：点卡片直接进入对应流程
function pickScenario(id: string) {
  if (id === 'llm') {
    router.push('/text')
  } else {
    activeTemplate.value = id
    onTemplateChange()
  }
}

// P1 修复：切换脱敏方法时，同步到所有已选区域（避免"改了方法实际还是旧算法"）
watch(method, (m) => {
  selectedRegions.value.forEach(r => { r.method = m })
})
// 换图时复位缩放平移
watch(() => uploadState.value.previewUrl, () => { zoom.value = 1; pan.value = { x: 0, y: 0 } })

async function runDesensitize() {
  if (!canvasRef.value || selectedRegions.value.length === 0) return
  await drawImageToCanvas(canvasRef.value, uploadState.value.file!)
  const ctx = canvasRef.value.getContext('2d')!
  originalImage.value = canvasRef.value.toDataURL('image/png').split(',')[1]
  selectedRegions.value.forEach((region) => {
    applyDesensitize(ctx, region, region.method || method.value, intensity.value, irreversibleLevel.value)
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

// ---------- 右侧"点选文字"打码 ----------
// 勾选右侧一条文字 = 把对应框加入打码选区（左侧同步变紫）；hover 在图中定位闪烁。
const hoverTextIdx = ref(-1)
/** 右侧已点选的文字条数（含图内任何已选框） */
const checkedTextCount = computed(() => selectedRegions.value.length)

function isRegionSelected(region: {x:number,y:number,w:number,h:number}): boolean {
  return selectedRegions.value.some(r => r.x === region.x && r.y === region.y)
}

// ---------- 重叠框循环选择 ----------
// 多个框重叠时浏览器命中测试只把点击交给最上层框（DOM 最后=通常最大），被覆盖的小框点不到。
// 按点击点收集所有覆盖框，同一位置连续点击用游标依次循环切换选择。
const overlapHint = ref(false)
let overlapHintTimer: ReturnType<typeof setTimeout> | null = null
const regionCycle = createRegionCycle()

function getOverlappingRegions(p: { x: number; y: number }): Rect[] {
  const all: Rect[] = []
  textRegions.value.forEach(r => all.push({ x: r.rect.x, y: r.rect.y, w: r.rect.w, h: r.rect.h }))
  objectRegions.value.forEach(r => all.push({ x: r.rect.x, y: r.rect.y, w: r.rect.w, h: r.rect.h }))
  return hitTestRegions(p, all)
}

function handleRegionClick(e: MouseEvent, region: Rect) {
  const p = panelCoords(e)
  const stack = getOverlappingRegions(p)
  if (stack.length <= 1) {
    regionCycle.reset()
    toggleRegion(region)
    return
  }
  if (overlapHintTimer) clearTimeout(overlapHintTimer)
  overlapHint.value = true
  overlapHintTimer = setTimeout(() => { overlapHint.value = false }, 2500)
  toggleRegion(regionCycle.next(stack, p))
}

// ---------- 手动画框 ----------
/** 把鼠标在预览区的 client 坐标映射为原图像素坐标（以 .preview-image 的显示区域为基准） */
function panelCoords(e: MouseEvent) {
  const img = document.querySelector<HTMLElement>('.preview-image')
  if (!img) return { x: 0, y: 0 }
  const r = img.getBoundingClientRect()
  return {
    x: (e.clientX - r.left) / r.width * uploadState.value.width,
    y: (e.clientY - r.top) / r.height * uploadState.value.height,
  }
}

function onPanelDown(e: MouseEvent) {
  if (e.button !== 0) return
  e.preventDefault()
  if (drawMode.value) {
    drawing.value = true
    drawStart = panelCoords(e)
    return
  }
  // 非画框模式：拖拽平移
  panning.value = true
  panStart = { x: e.clientX, y: e.clientY, panX: pan.value.x, panY: pan.value.y }
}

function onPanelMove(e: MouseEvent) {
  if (drawing.value && drawStart) {
    const cur = panelCoords(e)
    const x0 = drawStart.x, y0 = drawStart.y, x1 = cur.x, y1 = cur.y
    drawBox.value = {
      x: Math.min(x0, x1),
      y: Math.min(y0, y1),
      w: Math.abs(x1 - x0),
      h: Math.abs(y1 - y0),
    }
    return
  }
  if (panning.value && panStart) {
    pan.value.x = panStart.panX + (e.clientX - panStart.x)
    pan.value.y = panStart.panY + (e.clientY - panStart.y)
  }
}

function onPanelUp() {
  if (drawing.value) {
    if (drawBox.value && drawBox.value.w > 5 && drawBox.value.h > 5) {
      addRegion({
        x: Math.round(drawBox.value.x),
        y: Math.round(drawBox.value.y),
        w: Math.round(drawBox.value.w),
        h: Math.round(drawBox.value.h),
      })
    }
  }
  drawing.value = false
  drawBox.value = null
  drawStart = null
  panning.value = false
  panStart = null
}

function onPanelLeave() {
  // 鼠标移出面板取消进行中的拖拽，避免平移/画框卡住
  drawing.value = false
  drawBox.value = null
  drawStart = null
  panning.value = false
  panStart = null
}

// 手动框（仅存于 selectedRegions）需要单独渲染，否则不可见。
// 判据是「坐标近乎重合才豁免」（该条目已由 OCR 的 v-for 渲染），
// 不能用面积重叠——大框会覆盖多个 OCR 框，否则会被误剔除而不显示。
function rectsClose(a: Rect, b: Rect) {
  const w = Math.abs(a.w * 0.1) + 4
  const h = Math.abs(a.h * 0.1) + 4
  return Math.abs(a.x - b.x) <= 4 && Math.abs(a.y - b.y) <= 4 && Math.abs(a.w - b.w) <= w && Math.abs(a.h - b.h) <= h
}
const manualBoxes = computed<Rect[]>(() => {
  const ocr: Rect[] = [
    ...textRegions.value.map((r: any) => ({ x: r.rect.x, y: r.rect.y, w: r.rect.w, h: r.rect.h })),
    ...objectRegions.value.map((r: any) => ({ x: r.rect.x, y: r.rect.y, w: r.rect.w, h: r.rect.h })),
  ]
  return selectedRegions.value.filter(r => !ocr.some(b => rectsClose(r, b)))
})

// 删除图片：全部重置（回到上传）
function startOver() {
  resetUpload(); clearRegions(); resetDetection(); originalImage.value = ''; processedImage.value = ''; activeTab.value = 'detect'; complexity.value = null; zoomReset()
}

// 重新处理：保留当前图片，清空选区/检测，回到识别步骤（无需重新上传）
function reprocess() {
  clearRegions()
  resetDetection()
  resetProcessed()
  activeTab.value = 'detect'
}

// P3 修复：脱敏后可返回选区调整（回到原图预览，保留选区）
function backToSelect() {
  resetProcessed()
  activeTab.value = 'desensitize'
}

// 跳转检测强度前，把原图/脱敏图 + 脱敏区域写入中转，检测页自动带入（无需重新上传）
function prepareCheck() {
  if (originalImage.value && processedImage.value) {
    setCheckImages(originalImage.value, processedImage.value)
    setCheckRegions(selectedRegions.value.map(r => ({ x: r.x, y: r.y, w: r.w, h: r.h })))
  }
}

// ---------- 按类别一键全选 ----------
interface RegionRect { x: number; y: number; w: number; h: number }
interface CategoryGroup { key: string; label: string; regions: RegionRect[]; total: number; selectedCount: number }

// ⭐ 全选只覆盖"敏感内容"（OCR rect 已收缩到值）：非敏感行（出生/民族/性别等标签行）
// 与 YOLO 对象区域（提示框）不进全选——满足"只打码内容不打标签"；对象框可手动点选
const allRegions = computed<RegionRect[]>(() => selectableTextRegions(textRegions.value))

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
  // ⭐ 先记住目标动作再清空：clearRegions 后 allSelected 必为 false，
  //    若先清空再判断会恒真 → "取消全选"永远失效（修复）
  const shouldSelectAll = !allSelected.value
  clearRegions()
  if (shouldSelectAll) allRegions.value.forEach(r => addRegion(r))
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
      <div class="trust-badges fade-up" style="animation-delay:0.16s">
        <span class="trust-badge">🔒 图片不出设备 · 本地优先</span>
        <span class="trust-badge">🧪 脱敏强度可检测</span>
        <span class="trust-badge">🚫 不可逆算法 AI 还原不了</span>
        <span class="trust-badge">⚡ 免注册 · 免费 · 即用即走</span>
      </div>
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
      <!-- 场景入口：点场景直接进入对应流程 -->
      <div class="scenario-entry">
        <p class="scenario-label">🎯 选个场景，直接上传开干</p>
        <div class="scenario-grid">
          <div class="scenario-card" :class="{ active: activeTemplate === 'general' }" @click="pickScenario('general')">
            <span class="scenario-icon">🌐</span>
            <span class="scenario-name">通用脱敏</span>
            <span class="scenario-desc">识别所有敏感信息，自己把关</span>
            <span class="scenario-scope">{{ getTemplate('general').scopeLabel }}</span>
            <span class="scenario-example">{{ getTemplate('general').example }}</span>
          </div>
          <div class="scenario-card" :class="{ active: activeTemplate === 'chat' }" @click="pickScenario('chat')">
            <span class="scenario-icon">🗨️</span>
            <span class="scenario-name">聊天截图脱敏</span>
            <span class="scenario-desc">微信/QQ截图，挡手机号/地址</span>
            <span class="scenario-scope">{{ getTemplate('chat').scopeLabel }}</span>
            <span class="scenario-example">{{ getTemplate('chat').example }}</span>
          </div>
          <div class="scenario-card" :class="{ active: activeTemplate === 'idcard' }" @click="pickScenario('idcard')">
            <span class="scenario-icon">🪪</span>
            <span class="scenario-name">证件材料脱敏</span>
            <span class="scenario-desc">身份证/成绩单/简历，保留有效信息</span>
            <span class="scenario-scope">{{ getTemplate('idcard').scopeLabel }}</span>
            <span class="scenario-example">{{ getTemplate('idcard').example }}</span>
          </div>
          <div class="scenario-card" :class="{ active: activeTemplate === 'express' }" @click="pickScenario('express')">
            <span class="scenario-icon">📦</span>
            <span class="scenario-name">快递单脱敏</span>
            <span class="scenario-desc">晒单不泄露客户隐私，只打码关键信息</span>
            <span class="scenario-scope">{{ getTemplate('express').scopeLabel }}</span>
            <span class="scenario-example">{{ getTemplate('express').example }}</span>
          </div>
          <div class="scenario-card" @click="pickScenario('llm')">
            <span class="scenario-icon">🤖</span>
            <span class="scenario-name">AI 对话前置脱敏</span>
            <span class="scenario-desc">发给大模型前先过滤隐私</span>
            <span class="scenario-scope">文本掩码 · 占位符 · 事后还原</span>
            <span class="scenario-example">张三 → 【姓名1】</span>
          </div>
        </div>
      </div>
      <div class="upload-zone scale-in" @click="triggerUpload" @dragover.prevent @drop.prevent="onDrop">
        <span class="upload-icon">📤</span>
        <p class="upload-text">点击上传或拖拽图片到此处</p>
        <p class="upload-hint">支持 PNG / JPG / WebP，最大 20MB</p>
      </div>
      <div class="mode-selector">
        <p class="mode-label">识别模式：</p>
        <label class="mode-option"><input type="radio" v-model="processingMode" value="cloud" /> 精准增强（PaddleOCR · 高精度）</label>
        <label class="mode-option"><input type="radio" v-model="processingMode" value="local" /> 本地处理（Tesseract WASM · 图片不出设备）</label>
        <p class="trust-hint">{{ processingMode === 'local' ? '🔒 本地处理：图片在浏览器内识别，全程不出设备' : '🔒 精准增强：图片上传后端识别，处理完即用即弃，不留存' }}</p>
      </div>
      <div v-if="uploadState.status === 'error'" class="error-msg">⚠️ {{ uploadState.errorMessage }}</div>
    </div>

    <!-- 文件输入框：放在上传区外，保证进入工作区（更换图片）时始终存在 -->
    <input ref="fileInputRef" type="file" accept="image/png,image/jpeg,image/webp,image/bmp" style="display:none" @change="onFileSelected" />

    <!-- 工作区 -->
    <div class="workspace" v-if="uploadState.status === 'ready'">
      <div class="image-panel fade-in" :class="{ 'draw-cursor': drawMode }" @mousedown="onPanelDown" @mousemove="onPanelMove" @mouseup="onPanelUp" @mouseleave="onPanelLeave" @wheel.prevent="onWheelZoom">
        <!-- ⭐ 缩放容器：transform translate+scale，滚轮以光标为中心缩放，非画框拖拽平移 -->
        <div class="preview-wrap" :style="{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})` }">
          <canvas v-show="isProcessed" ref="canvasRef" class="preview-canvas" />
          <img v-show="!isProcessed" :src="uploadState.previewUrl" class="preview-image" />
          <div v-if="!isProcessed" class="overlay">
          <!-- ⭐ 段落整选框：一段多行文字合成一个虚线框，点一下整段全选打码。显示在单行框下层。 -->
          <div v-for="(p, pi) in paragraphs.filter(p => p.rects.length >= 2)" :key="'p'+pi"
            class="paragraph-box"
            :class="{ 'paragraph-selected': p.rects.length && p.rects.every(rr => isRegionSelected(rr)) }"
            :style="{
              left: (p.rect.x / uploadState.width * 100) + '%',
              top: (p.rect.y / uploadState.height * 100) + '%',
              width: (p.rect.w / uploadState.width * 100) + '%',
              height: (p.rect.h / uploadState.height * 100) + '%',
            }"
            @click.stop="toggleParagraph(p)">
            <span class="paragraph-label" :title="'整段 ' + p.rects.length + ' 行，点击整段全选并打码'">整段 · {{ p.rects.length }} 行</span>
          </div>
          <div v-for="(region, i) in textRegions" :key="'t'+i" class="region-box"
            :class="{
              'risk-high': region.sensitive?.risk_level === 'high',
              'risk-medium': region.sensitive?.risk_level === 'medium',
              'risk-low': region.sensitive?.risk_level === 'low',
              selected: isRegionSelected({x: region.rect.x, y: region.rect.y, w: region.rect.w, h: region.rect.h}),
              'region-selected-anim': isRegionSelected({x: region.rect.x, y: region.rect.y, w: region.rect.w, h: region.rect.h}),
              'hover-locate': i === hoverTextIdx,
            }"
            :style="{
              left: (region.rect.x / uploadState.width * 100) + '%',
              top: (region.rect.y / uploadState.height * 100) + '%',
              width: (region.rect.w / uploadState.width * 100) + '%',
              height: (region.rect.h / uploadState.height * 100) + '%',
            }"
            @click.stop="handleRegionClick($event, {x: region.rect.x, y: region.rect.y, w: region.rect.w, h: region.rect.h})">
            <span class="region-label region-no" :title="(region.sensitive?.object_label || region.sensitive?.type || '') + '：' + region.text">#{{ i }}</span>
          </div>
          <div v-for="(region, i) in objectRegions" :key="'o'+i" class="region-box object-region"
            :class="{ selected: isRegionSelected({x: region.rect.x, y: region.rect.y, w: region.rect.w, h: region.rect.h}), 'region-selected-anim': isRegionSelected({x: region.rect.x, y: region.rect.y, w: region.rect.w, h: region.rect.h}) }"
            :style="{
              left: (region.rect.x / uploadState.width * 100) + '%',
              top: (region.rect.y / uploadState.height * 100) + '%',
              width: (region.rect.w / uploadState.width * 100) + '%',
              height: (region.rect.h / uploadState.height * 100) + '%',
            }"
            @click.stop="handleRegionClick($event, {x: region.rect.x, y: region.rect.y, w: region.rect.w, h: region.rect.h})">
            <span class="region-label" :title="region.label">{{ region.label }}</span>
          </div>
          <!-- 手动画框：拖拽中的临时框（原图像素坐标） -->
          <div v-if="drawBox" class="region-box selected draw-box" :style="{
            left: drawBox.x / uploadState.width * 100 + '%',
            top: drawBox.y / uploadState.height * 100 + '%',
            width: drawBox.w / uploadState.width * 100 + '%',
            height: drawBox.h / uploadState.height * 100 + '%',
          }">
            <span class="region-label">新框</span>
          </div>
          <!-- 手动追加框（未与 OCR 框重叠、仅存在于 selectedRegions）：单独渲染否则不可见 -->
          <div v-for="(region, i) in manualBoxes" :key="'m'+i" class="region-box draw-box selected"
            :style="{
              left: region.x / uploadState.width * 100 + '%',
              top: region.y / uploadState.height * 100 + '%',
              width: region.w / uploadState.width * 100 + '%',
              height: region.h / uploadState.height * 100 + '%',
            }"
            @click.stop="toggleRegion({ x: region.x, y: region.y, w: region.w, h: region.h })">
            <span class="region-label">✏️ 手动</span>
          </div>
          </div>
        </div>
        <div class="box-legend">
          <span class="lg"><i class="sw sel"></i>已选</span>
          <span class="lg"><i class="sw hi"></i>高风险</span>
          <span class="lg"><i class="sw me"></i>中风险</span>
          <span class="lg"><i class="sw lo"></i>低风险</span>
          <span class="lg"><i class="sw obj"></i>对象框</span>
          <span class="lg"><i class="sw man"></i>手动框</span>
        </div>
        <div class="zoom-controls">
          <button class="zoom-btn" @click.stop="zoomOut" :disabled="zoom <= 0.5" title="缩小">−</button>
          <span class="zoom-pct">{{ Math.round(zoom * 100) }}%</span>
          <button class="zoom-btn" @click.stop="zoomIn" :disabled="zoom >= 3" title="放大">＋</button>
          <button class="zoom-btn" @click.stop="zoomReset" title="重置 100%">⟳</button>
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
          <div class="fulltext-card" v-if="fullText">
            <div class="fulltext-head">
              <span class="section-title fulltext-title">📄 识别全文（{{ fullText.replace(/\s+/g, '').length }} 字）</span>
              <button class="btn-copyfull" @click="copyFullText">📋 复制全部文字</button>
            </div>
            <pre class="fulltext-body">{{ fullText }}</pre>
          </div>
          <!-- ⭐ 点选文字打码：勾选右侧一条 → 图中对应框标紫，点"打码选中"统一打码；hover 定位 -->
          <div class="text-pick-card" v-if="textRegions.length">
            <div class="text-pick-head">
              <span class="section-title">🔤 点选文字打码</span>
              <span class="text-pick-count">{{ checkedTextCount }} 已选</span>
            </div>
            <div class="text-pick-list">
              <div v-for="(region, i) in textRegions" :key="'pick'+i" class="text-pick-row"
                :class="{ picked: isRegionSelected({x: region.rect.x, y: region.rect.y, w: region.rect.w, h: region.rect.h}) }"
                :title="region.text"
                @mouseenter="hoverTextIdx = i" @mouseleave="hoverTextIdx = -1">
                <input type="checkbox" class="text-pick-check"
                  :checked="isRegionSelected({x: region.rect.x, y: region.rect.y, w: region.rect.w, h: region.rect.h})"
                  @click.stop="toggleRegion({x: region.rect.x, y: region.rect.y, w: region.rect.w, h: region.rect.h})" />
                <span class="text-pick-no">#{{ i }}</span>
                <span class="text-pick-txt">{{ region.text }}</span>
                <span v-if="region.sensitive" class="text-pick-tag"
                  :class="'risk-' + (region.sensitive.risk_level || 'low')">{{ region.sensitive.object_label || region.sensitive.type }}</span>
              </div>
            </div>
            <button class="btn btn-maskpick" :disabled="selectedRegions.length === 0" @click="runDesensitize">✔ 打码选中（{{ selectedRegions.length }}）</button>
          </div>
          <div class="draw-control">
            <button class="btn btn-draw" :class="{ active: drawMode }" @click="drawMode = !drawMode">
              {{ drawMode ? '画框中：拖拽画新框' : '✏️ 手动画框' }}
            </button>
            <p v-if="drawMode" class="draw-hint">在图片上拖拽，松开即加入新脱敏框</p>
          </div>
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
          <div class="level-select" v-if="method === 'irreversible'">
            <p class="section-title">不可逆保护等级</p>
            <div class="template-list">
              <span v-for="lv in [1,2,3]" :key="lv" class="template-chip chip-pop" :class="{ active: irreversibleLevel === lv }" @click="irreversibleLevel = lv">等级{{ lv }}</span>
            </div>
          </div>
          <p class="selected-count">已选 {{ selectedRegions.length }} 个脱敏区域<span v-if="selectedRegions.length === 0" class="hint-text">（点击图片上的框选择）</span></p>
          <p v-if="overlapHint" class="overlap-hint">↻ 该处有多个重叠框，可再点同一位置切换选择</p>
          <button class="btn btn-warn" @click="runDesensitize" :disabled="selectedRegions.length === 0">🔒 应用脱敏 ({{ selectedRegions.length }} 处)</button>
        </div>

        <div v-if="isProcessed" class="result-panel scale-in">
          <p class="success-msg">✅ 脱敏完成</p>
          <p class="privacy-note">{{ processingMode === 'local' ? '🔒 本次处理全程在本机完成，图片未上传' : '🔒 原始图片已处理完毕，服务器不留存' }}</p>
          <p class="result-info">共处理 {{ selectedRegions.length }} 处敏感信息</p>
          <button class="btn btn-primary" @click="downloadImage">💾 下载图片</button>
          <button class="btn btn-secondary" @click="backToSelect">↩️ 返回选区调整</button>
          <button class="btn btn-secondary" @click="reprocess">🔄 重新处理（保留图片）</button>
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
.trust-badges { display: flex; justify-content: center; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
.trust-badge { font-size: 12px; color: #b0d0ff; background: rgba(70,120,255,0.12); border: 1px solid rgba(70,120,255,0.3); border-radius: 999px; padding: 5px 12px; }
.trust-hint { font-size: 11px; color: #22c55e; margin-top: 8px; }
.privacy-note { font-size: 11px; color: #22c55e; margin: 4px 0 10px; }
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
/* 场景入口卡片 */
.scenario-entry { margin-bottom: 16px; }
.scenario-label { font-weight: 600; font-size: 14px; margin-bottom: 10px; color: #c0c0e0; }
.scenario-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }
.scenario-card { display: flex; flex-direction: column; align-items: center; gap: 4px; background: #1a1a2e; border: 1px solid #2a2a4a; border-radius: 12px; padding: 14px 10px; cursor: pointer; text-align: center; transition: all 0.15s; }
.scenario-card:hover { border-color: #6c63ff; background: rgba(108,99,255,0.05); }
.scenario-card.active { border-color: #6c63ff; background: rgba(108,99,255,0.18); box-shadow: inset 0 0 0 1px #6c63ff; }
.scenario-icon { font-size: 22px; }
.scenario-name { font-size: 13px; font-weight: 600; color: #c0c0e0; }
.scenario-card.active .scenario-name { color: #6c63ff; }
.scenario-scope { font-size: 11px; color: #8888aa; line-height: 1.4; }
.scenario-example { font-size: 11px; color: #22c55e; font-family: monospace; line-height: 1.4; }
.scenario-desc { font-size: 11px; color: #6666aa; line-height: 1.4; }
.workspace { display: flex; gap: 16px; margin-top: 16px; }
.image-panel { flex: 1; position: relative; background: #111122; border-radius: 12px; overflow: auto; min-height: 300px; user-select: none; -webkit-user-select: none; cursor: grab; }
.image-panel:active:not(.draw-cursor) { cursor: grabbing; }
.image-panel.draw-cursor, .image-panel.draw-cursor * { cursor: crosshair !important; }
.preview-canvas, .preview-image { width: 100%; display: block; }
/* ⭐ 缩放容器：transform translate+scale，原点 0 0，overlay 相对 wrap 定位（识别框与文字精确对齐） */
.preview-wrap { position: relative; width: 100%; display: block; transform-origin: 0 0; will-change: transform; }
.overlay { position: absolute; inset: 0; pointer-events: none; }
.zoom-controls { position: absolute; top: 8px; left: 8px; z-index: 20; display: flex; align-items: center; gap: 4px; background: rgba(0,0,0,0.65); border-radius: 8px; padding: 4px 6px; pointer-events: auto; }
.zoom-btn { background: #2a2a4a; color: #e0e0f0; border: 1px solid #3a3a5a; border-radius: 6px; width: 24px; height: 24px; cursor: pointer; font-size: 14px; line-height: 1; }
.zoom-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.zoom-pct { color: #aaaacc; font-size: 12px; min-width: 40px; text-align: center; }
/* ⭐ 段落整选框：把一段多行文字合成虚线框，点击整段全选打码（在下层，不遮挡单行框） */
    .paragraph-box { position: absolute; border: 2px dashed rgba(108,99,255,0.85); background: rgba(108,99,255,0.06); border-radius: 6px; cursor: pointer; pointer-events: auto; transition: all 0.15s; }
    .paragraph-box:hover { background: rgba(108,99,255,0.14); border-color: #6c63ff; }
    .paragraph-selected { border-color: #22c55e !important; background: rgba(34,197,94,0.15); }
    .paragraph-label { position: absolute; top: -16px; left: 0; font-size: 10px; color: #cfcaff; background: rgba(18,18,40,0.94); padding: 1px 5px; border-radius: 3px; white-space: nowrap; line-height: 1.5; pointer-events: none; }
    .region-box { position: absolute; border: 2px solid #ffcc00; background: rgba(255,204,0,0.08); border-radius: 4px; cursor: pointer; pointer-events: auto; transition: all 0.15s; }
.region-box.risk-high { border-color: #ff4444; background: rgba(255,68,68,0.12); }
.region-box.risk-medium { border-color: #ffaa00; background: rgba(255,170,0,0.10); }
.region-box.selected { border-color: #6c63ff !important; background: rgba(108,99,255,0.22); border-width: 3px; box-shadow: 0 0 8px rgba(108,99,255,0.45); }
.region-box.object-region { border-color: #00ccff; background: rgba(0,204,255,0.08); }
/* 框色图例：解释未选(风险色红/橙/黄)、已选(紫)、对象框(蓝)、手动框(紫虚线) */
.box-legend { position: absolute; top: 8px; right: 8px; z-index: 20; display: flex; flex-wrap: wrap; gap: 6px 10px; max-width: 200px; justify-content: flex-end; background: rgba(0,0,0,0.6); border-radius: 8px; padding: 5px 8px; font-size: 11px; color: #ccc; pointer-events: none; }
.box-legend .lg { display: inline-flex; align-items: center; gap: 4px; white-space: nowrap; }
.box-legend .sw { width: 10px; height: 10px; border-radius: 2px; display: inline-block; border: 1px solid rgba(255,255,255,0.3); }
.box-legend .sw.sel { background: #6c63ff; border-color: #6c63ff; }
.box-legend .sw.hi { background: #ff4444; border-color: #ff4444; }
.box-legend .sw.me { background: #ffaa00; border-color: #ffaa00; }
.box-legend .sw.lo { background: #ffcc00; border-color: #ffcc00; }
.box-legend .sw.obj { background: #00ccff; border-color: #00ccff; }
.box-legend .sw.man { background: transparent; border: 1.5px dashed #6c63ff; }
/* 手动画框：半透明主题色 + 虚线边框（区别于已选实线框） */
.draw-box { border-style: dashed; border-color: #6c63ff; background: rgba(108,99,255,0.25); box-shadow: none; }
.region-label { font-size: 10px; color: #fff; background: rgba(0,0,0,0.7); padding: 1px 4px; border-radius: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%; display: block; }
/* 图中文字框编号徽章：仅显示 #i，昵称移入 title 悬浮提示，避免遮挡图片 */
.region-no { min-width: 20px; text-align: center; font-weight: 700; background: rgba(20,20,46,0.85); border: 1px solid rgba(108,99,255,0.4); }
/* 右侧"点选文字打码"：逐条可勾选，hover 图中定位，底部统一打码 */
.text-pick-card { margin-top: 10px; }
.text-pick-head { display: flex; align-items: center; justify-content: space-between; }
.text-pick-count { font-size: 11px; color: #8888bb; }
.text-pick-list { max-height: 220px; overflow-y: auto; border: 1px solid #2a2a4a; border-radius: 8px; margin-top: 6px; background: #141428; }
.text-pick-row { display: flex; align-items: center; gap: 6px; padding: 4px 8px; font-size: 12px; color: #c9c9e8; cursor: pointer; border-bottom: 1px solid #1e1e38; transition: background 0.12s; }
.text-pick-row:last-child { border-bottom: none; }
.text-pick-row:hover { background: rgba(108,99,255,0.14); }
.text-pick-row.picked { background: rgba(108,99,255,0.22); color: #fff; }
.text-pick-check { accent-color: #6c63ff; flex-shrink: 0; }
.text-pick-no { flex-shrink: 0; font-size: 10px; font-weight: 700; color: #cfcaff; background: rgba(108,99,255,0.16); border: 1px solid rgba(108,99,255,0.35); border-radius: 4px; padding: 0 4px; min-width: 18px; text-align: center; }
.text-pick-txt { flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.text-pick-tag { flex-shrink: 0; font-size: 10px; color: #fff; padding: 1px 5px; border-radius: 3px; }
.text-pick-tag.risk-high { background: #ff4444; }
.text-pick-tag.risk-medium { background: #ffaa00; color: #221; }
.text-pick-tag.risk-low { background: #ffcc00; color: #221; }
.btn-maskpick { width: 100%; margin-top: 8px; background: linear-gradient(135deg, #6c63ff, #8b7cff); border: none; color: #fff; border-radius: 8px; padding: 8px 0; font-size: 13px; font-weight: 600; cursor: pointer; transition: opacity 0.15s, transform 0.1s; }
.btn-maskpick:hover:not(:disabled) { transform: translateY(-1px); }
.btn-maskpick:disabled { opacity: 0.4; cursor: not-allowed; }
/* hover 定位：右侧悬停某条时，图中对应框亮起粗白虚线高亮 */
.region-box.hover-locate { border-color: #ffffff !important; border-width: 3px; box-shadow: 0 0 12px rgba(255,255,255,0.8); z-index: 15; }
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
/* 识别全文卡片：多行 OCR 拼成整段，一键复制 */
.fulltext-card { background: #12122a; border: 1px solid #2a2a4a; border-radius: 10px; padding: 10px 12px; margin-bottom: 10px; }
.fulltext-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 6px; }
.fulltext-title { margin: 0; }
.btn-copyfull { flex-shrink: 0; background: #6c63ff; color: #fff; border: none; border-radius: 6px; padding: 5px 10px; font-size: 11px; font-weight: 600; cursor: pointer; }
.btn-copyfull:hover { background: #5a52e0; }
.btn-copyfull:disabled { opacity: 0.45; cursor: not-allowed; }
.fulltext-body { margin: 0; max-height: 120px; overflow: auto; background: #0d0d1a; border: 1px solid #26263f; border-radius: 8px; padding: 8px 10px; font-size: 12px; line-height: 1.6; color: #c0c0e0; white-space: pre-wrap; word-break: break-word; }
/* 手动画框切换按钮 */
.draw-control { margin-bottom: 10px; }
.btn-draw { background: #2a2a4a; color: #c0c0e0; border: 1px solid #3a3a5a; margin: 0; }
.btn-draw.active { background: rgba(108,99,255,0.25); color: #6c63ff; border-color: #6c63ff; }
.draw-hint { font-size: 11px; color: #6c63ff; margin-top: 4px; }
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
  .scenario-grid { grid-template-columns: 1fr; }
}
.method-option { display: flex; flex-direction: column; padding: 8px 0; border-bottom: 1px solid #2a2a4a; gap: 2px; cursor: pointer; }
.method-desc { font-size: 11px; color: #6666aa; }
.selected-count { font-size: 13px; color: #b0b0d0; margin: 12px 0; }
.hint-text { color: #6666aa; font-size: 11px; }
.overlap-hint { font-size: 11px; color: #ffaa00; margin: 4px 0 8px; }
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
