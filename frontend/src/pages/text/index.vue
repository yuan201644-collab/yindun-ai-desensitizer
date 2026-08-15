<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { DEFAULT_PATTERNS, applyMask, matchCustomWords, type RegExpExecWithIndices } from '../../utils/sensitivePatterns'
import { SCENARIO_TEMPLATES, getTemplate, filterPatternsByTemplate } from '../../utils/scenarioTemplates'
import { enhanceContext } from '../../utils/contextEnhance'
import { buildPlaceholderMask, restorePlaceholders } from '../../utils/placeholderMask'

const inputText = ref('')
// 自定义敏感词（换行/逗号分隔），不受场景模板 activeTypes 过滤影响，用户显式指定的词恒生效
const customWordsText = ref('')
const maskedText = ref('')
const isProcessed = ref(false)
const processing = ref(false)
const error = ref('')
const previewMode = ref<'masked' | 'highlighted'>('highlighted')
const activeTemplate = ref('general')
const activeTemplateObj = computed(() => getTemplate(activeTemplate.value))

// P3 修复：切换场景模板时，若有文本则重新检测（避免保留旧模板的检测结果）
watch(activeTemplate, () => {
  if (inputText.value.trim()) detectLocally()
})

interface SpanResult { start: number; end: number; type: string; category: string; riskLevel: 'high' | 'medium' | 'low'; matchText: string; maskChar: string; contextConfirmed?: boolean }
const spans = ref<SpanResult[]>([])
const highRiskCount = computed(() => spans.value.filter(s => s.riskLevel === 'high').length)

// ⭐ 占位符模式（AI 对话前置）：敏感值 → 【类型N】，事后可还原
const placeholderMode = ref(false)
const placeholderMapping = ref<Record<string, string>>({})
const restoreInput = ref('')
const restoredText = ref('')

function detectLocally() {
  spans.value = []
  const text = inputText.value
  if (!text.trim()) return
  const patterns = filterPatternsByTemplate(DEFAULT_PATTERNS, activeTemplateObj.value)
  for (const pattern of patterns) {
    // 加 d 标志以读取捕获组位置（group 模式时 span 指向值部分，标签保留）
    const flags = pattern.pattern.flags.includes('d') ? pattern.pattern.flags : pattern.pattern.flags + 'd'
    const regex = new RegExp(pattern.pattern.source, flags)
    let match: RegExpExecWithIndices | null
    while ((match = regex.exec(text) as RegExpExecWithIndices | null) !== null) {
      const gi = pattern.group ?? 0
      const matched = match[gi] ?? match[0]
      let start = match.index
      let end = match.index + match[0].length
      if (match.indices?.[gi]) {
        start = match.indices[gi][0]
        end = match.indices[gi][1]
      }
      const isOverlapping = spans.value.some(s => start < s.end && end > s.start)
      if (!isOverlapping) {
        spans.value.push({ start, end, type: pattern.type, category: pattern.category, riskLevel: pattern.riskLevel, matchText: matched, maskChar: pattern.maskChar })
      }
    }
  }
  // 自定义敏感词：解析（换行/逗号分隔）后调用 matchCustomWords，
  // 命中加入 spans（type='自定义'、high 风险、█ 全掩码），恒生效、不受模板 activeTypes 过滤影响
  const customWords = customWordsText.value.split(/[\n,，、]+/).map(w => w.trim()).filter(Boolean)
  for (const cm of matchCustomWords(text, customWords)) {
    const isOverlapping = spans.value.some(s => cm.start < s.end && cm.end > s.start)
    if (!isOverlapping) {
      spans.value.push({ start: cm.start, end: cm.end, type: cm.type, category: 'custom', riskLevel: 'high', matchText: cm.text, maskChar: '█' })
    }
  }
  // 上下文关键词增强：同类别关键词语义确认+风险升级；补漏捕捉"姓名：张三/微信号/QQ"等结构隐私
  spans.value = enhanceContext(text, spans.value)
  applyLocalMask()
}

function applyLocalMask() {
  refreshMaskedText()
}

/** ⭐ 按当前模式刷新脱敏结果（普通掩码 / 占位符） */
function refreshMaskedText() {
  if (placeholderMode.value) {
    const { masked, mapping } = buildPlaceholderMask(inputText.value, spans.value)
    maskedText.value = masked
    placeholderMapping.value = mapping
    return
  }
  let result = inputText.value
  const sorted = [...spans.value].sort((a, b) => b.start - a.start)
  for (const span of sorted) {
    const mp = DEFAULT_PATTERNS.find(p => p.type === span.type)
    const maskChar = span.maskChar || mp?.maskChar || '*'
    const masked = mp
      ? applyMask(span.matchText, mp.keepFirst, mp.keepLast, maskChar)
      : maskChar.repeat(span.matchText.length) // 自定义词在模式库中找不到 mp → 全掩码（保留 0 前 0 后）
    result = result.slice(0, span.start) + masked + result.slice(span.end)
  }
  maskedText.value = result
  placeholderMapping.value = {}
}

watch(placeholderMode, () => {
  if (!isProcessed.value || !inputText.value.trim()) return
  refreshMaskedText()
})

async function runDesensitize() {
  processing.value = true; error.value = ''
  try { detectLocally(); isProcessed.value = true } catch (e: any) { error.value = e.message || '处理失败' } finally { processing.value = false }
}

async function copyMaskedText() {
  try { await navigator.clipboard.writeText(maskedText.value); alert('已复制到剪贴板') } catch { /* ignore */ }
}

/** ⭐ 复制占位符映射表（JSON） */
async function copyPlaceholderMapping() {
  try {
    await navigator.clipboard.writeText(JSON.stringify(placeholderMapping.value))
    alert('已复制映射表（保存好，还原时用）')
  } catch { /* ignore */ }
}

/** ⭐ 还原：把 AI 回复中的占位符替换回原文 */
function doRestore() {
  restoredText.value = restorePlaceholders(restoreInput.value, placeholderMapping.value)
}

async function copyRestored() {
  try { await navigator.clipboard.writeText(restoredText.value); alert('已复制还原文本') } catch { /* ignore */ }
}

function reset() {
  maskedText.value = ''; spans.value = []; isProcessed.value = false; error.value = ''
  placeholderMapping.value = {}; restoreInput.value = ''; restoredText.value = ''
}

const sampleTexts = [
  '张三，身份证号110101199001011234，手机13800138000，住北京市朝阳区某某路100号。',
  '订单号SF1234567890123，收货人李四，电话13912345678，地址广东省深圳市南山区科技园。',
  '银行卡号6222021234567890123，开户行中国工商银行，户名王五。',
  '【快递单】收件人：王小明，电话13812345678，地址：浙江省杭州市西湖区文三路100号，单号：YT1234567890123，包裹内件：文件。',
]
function useSample(index: number) { inputText.value = sampleTexts[index]; detectLocally() }

const highlightedHTML = computed(() => {
  if (!inputText.value || spans.value.length === 0) return inputText.value
  let html = ''; let lastEnd = 0
  for (const span of [...spans.value].sort((a, b) => a.start - b.start)) {
    html += escapeHTML(inputText.value.slice(lastEnd, span.start))
    const color = span.riskLevel === 'high' ? '#ff4444' : span.riskLevel === 'medium' ? '#ffaa00' : '#ffcc00'
    html += `<mark style="background:${color}33;border-bottom:2px solid ${color};color:#fff;padding:2px 4px;border-radius:3px" title="${span.type}${span.contextConfirmed ? '（上下文确认）' : ''}">${escapeHTML(span.matchText)}</mark>`
    lastEnd = span.end
  }
  html += escapeHTML(inputText.value.slice(lastEnd))
  return html
})

function escapeHTML(str: string): string { return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;') }
</script>

<template>
  <div class="page">
    <div class="hero"><h1 class="hero-title fade-up">📝 文本智能脱敏</h1><p class="hero-sub fade-up" style="animation-delay:0.08s">粘贴文本，AI 自动识别并脱敏敏感信息</p></div>
    <div class="help-card fade-in">
      <div class="help-header"><span>📖 使用说明</span></div>
      <div class="help-body">
        <p>粘贴聊天记录、订单信息或文档 → 自动 <span style="color:#ff4444">红色</span>=高风险 <span style="color:#ffaa00">黄色</span>=中风险 → 一键打码 → 复制使用</p>
        <p style="margin-top:6px;color:#8888aa;font-size:11px;">💡 支持：身份证 / 手机号 / 银行卡 / 邮箱 / 地址 / 车牌 / 快递单号 / 微信号 / QQ号</p>
        <p style="margin-top:6px;color:#6c63ff;font-size:11px;">🔍 上下文增强：识别"姓名：张三""微信号：abc12345"等结构化隐私，且"电话/邮箱/单号"等上下文会提升风险等级</p>
        <p style="color:#22c55e;font-size:11px;">🔒 文本脱敏全部在浏览器本地完成，不上传服务器</p>
      </div>
    </div>
    <div class="input-section" v-if="!isProcessed">
      <div class="template-select">
        <p class="template-label">🎯 场景模板：</p>
        <div class="template-list">
          <span v-for="t in SCENARIO_TEMPLATES" :key="t.id" class="template-chip chip-pop" :class="{ active: activeTemplate === t.id }" :title="t.desc" @click="activeTemplate = t.id">{{ t.icon }} {{ t.name }}</span>
        </div>
        <p class="template-desc">{{ activeTemplateObj.desc }}</p>
      </div>
      <textarea v-model="inputText" class="text-input" placeholder="在此粘贴聊天记录、订单信息、文档片段..." rows="10"></textarea>
      <div class="custom-words-box">
        <p class="custom-words-label">✏️ 自定义敏感词（恒生效，不受场景模板影响）：</p>
        <textarea v-model="customWordsText" class="text-input custom-words-input" placeholder="输入自定义敏感词，换行或逗号分隔，如：雷霆项目，机密代号，王小明" rows="2"></textarea>
      </div>
      <div class="samples"><span class="samples-label">📋 快速粘贴示例：</span>
        <div class="sample-list"><span v-for="(s, i) in sampleTexts" :key="i" class="sample-item chip-pop" @click="useSample(i)">示例{{ i+1 }}</span></div>
        <p class="sample-tip">💡 示例1适「证件照/通用」· 示例2/4适「快递单」· 示例3适「通用」</p>
      </div>
      <div class="action-row"><span class="char-count">{{ inputText.length }} 字</span><button class="btn btn-primary" @click="runDesensitize" :disabled="!inputText.trim()||processing">{{ processing?'处理中...':'🔒 一键脱敏' }}</button></div>
      <div v-if="error" class="error">{{ error }}</div>
    </div>
    <div class="result-section reveal" v-if="isProcessed">
      <div class="stats">
        <div class="stat-card high"><span class="stat-num">{{ highRiskCount }}</span><span class="stat-label">高风险</span></div>
        <div class="stat-card medium"><span class="stat-num">{{ spans.filter(s=>s.riskLevel==='medium').length }}</span><span class="stat-label">中风险</span></div>
        <div class="stat-card low"><span class="stat-num">{{ spans.filter(s=>s.riskLevel==='low').length }}</span><span class="stat-label">低风险</span></div>
      </div>
      <div class="preview-tabs">
        <span class="tab" :class="{active:previewMode==='highlighted'}" @click="previewMode='highlighted'">高亮标注</span>
        <span class="tab" :class="{active:previewMode==='masked'}" @click="previewMode='masked'">脱敏预览</span>
      </div>
      <div v-if="previewMode==='highlighted'" class="text-display" v-html="highlightedHTML"></div>
      <div v-if="previewMode==='masked'" class="text-display masked-text">{{ maskedText }}</div>
      <label class="placeholder-toggle">
        <input type="checkbox" v-model="placeholderMode">
        🧠 占位符模式（AI 对话：敏感值换【类型N】，拿到 AI 回复后可一键还原）
      </label>
      <div v-if="placeholderMode" class="placeholder-panel">
        <p class="pp-title">🔑 占位符映射表（<strong>复制保存</strong>，还原时用）：</p>
        <pre class="pp-mapping">{{ JSON.stringify(placeholderMapping, null, 2) }}</pre>
        <button class="btn btn-secondary" @click="copyPlaceholderMapping">📋 复制映射表</button>
        <p class="pp-title" style="margin-top:12px">🔄 还原 AI 回复：</p>
        <textarea v-model="restoreInput" class="text-input restore-input" placeholder="粘贴 AI 返回的文本（含【手机1】等占位符）" rows="3"></textarea>
        <div class="action-row">
          <button class="btn btn-primary" @click="doRestore" :disabled="!restoreInput.trim() || Object.keys(placeholderMapping).length === 0">🔄 还原占位符</button>
          <button v-if="restoredText" class="btn btn-secondary" @click="copyRestored">📋 复制还原文本</button>
        </div>
        <div v-if="restoredText" class="text-display masked-text restore-result">{{ restoredText }}</div>
      </div>
      <div class="action-row"><button class="btn btn-secondary" @click="reset">🔄 重新处理</button><button class="btn btn-primary" @click="copyMaskedText">📋 复制脱敏文本</button></div>
    </div>
    <div class="footer-note"><p>🔒 文本脱敏在浏览器本地完成，<strong>不会上传到服务器</strong></p></div>
  </div>
</template>

<style scoped>
.page { max-width: 800px; margin: 0 auto; padding: 16px; }
.hero { text-align: center; padding: 24px 0; }
.hero-title { font-size: 28px; font-weight: 700; color: #e0e0f0; }
.hero-sub { color: #8888aa; font-size: 14px; margin-top: 8px; }
.template-select { background: #1a1a2e; border: 1px solid #2a2a4a; border-radius: 12px; padding: 12px 16px; margin-bottom: 12px; }
.template-label { font-size: 13px; font-weight: 600; color: #aaaacc; margin-bottom: 8px; }
.template-list { display: flex; gap: 8px; flex-wrap: wrap; }
.template-chip { background: #2a2a4a; color: #aaaacc; font-size: 13px; padding: 6px 14px; border-radius: 20px; cursor: pointer; border: 1px solid transparent; transition: all 0.15s; }
.template-chip.active { background: rgba(108,99,255,0.2); color: #6c63ff; border-color: #6c63ff; font-weight: 600; }
.template-desc { font-size: 11px; color: #6666aa; margin-top: 8px; }
.text-input { width: 100%; background: #111122; border: 1px solid #2a2a4a; border-radius: 12px; padding: 16px; color: #e0e0f0; font-size: 14px; line-height: 1.8; min-height: 200px; resize: vertical; box-sizing: border-box; }
.custom-words-box { margin-top: 12px; }
.placeholder-toggle { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #6c63ff; margin: 10px 0; cursor: pointer; user-select: none; }
.placeholder-panel { background: #14142a; border: 1px solid #2a2a4a; border-radius: 12px; padding: 12px 14px; margin: 10px 0; }
.pp-title { font-size: 12px; color: #aaaacc; margin-bottom: 6px; }
.pp-mapping { background: #0d0d1a; border: 1px solid #2a2a4a; border-radius: 8px; padding: 10px; font-size: 11px; color: #22c55e; overflow-x: auto; max-height: 160px; overflow-y: auto; }
.restore-input { min-height: 60px; }
.restore-result { margin-top: 10px; }
.custom-words-label { font-size: 12px; color: #8888aa; margin-bottom: 6px; }
.custom-words-input { min-height: 64px; }
.samples { margin: 12px 0; } .samples-label { font-size: 12px; color: #6666aa; }
.sample-tip { font-size: 11px; color: #8888aa; margin-top: 6px; }
.sample-list { display: flex; gap: 8px; margin-top: 6px; }
.sample-item { background: #2a2a4a; color: #aaaacc; font-size: 12px; padding: 4px 12px; border-radius: 6px; cursor: pointer; }
.stats { display: flex; gap: 12px; margin-bottom: 16px; }
.stat-card { flex: 1; text-align: center; padding: 12px; border-radius: 10px; background: #1a1a2e; }
.stat-card.high { border-left: 3px solid #ff4444; } .stat-card.medium { border-left: 3px solid #ffaa00; } .stat-card.low { border-left: 3px solid #ffcc00; }
.stat-num { font-size: 28px; font-weight: 700; display: block; } .stat-label { font-size: 12px; color: #8888aa; }
.preview-tabs { display: flex; margin-bottom: 12px; }
.tab { flex: 1; text-align: center; padding: 10px; background: #1a1a2e; color: #8888aa; font-size: 14px; cursor: pointer; border-bottom: 2px solid transparent; }
.tab:first-child { border-radius: 8px 0 0 0; } .tab:last-child { border-radius: 0 8px 0 0; }
.tab.active { color: #6c63ff; border-bottom-color: #6c63ff; background: #222238; }
.text-display { background: #111122; border: 1px solid #2a2a4a; border-radius: 0 0 12px 12px; padding: 16px; min-height: 100px; font-size: 14px; line-height: 1.8; color: #e0e0f0; word-break: break-all; }
.masked-text { font-family: monospace; }
.action-row { display: flex; gap: 8px; margin-top: 16px; } .action-row .btn { flex: 1; }
.char-count { color: #6666aa; font-size: 12px; align-self: center; }
.btn { padding: 12px; border-radius: 8px; border: none; font-size: 15px; font-weight: 600; cursor: pointer; }
.btn-primary { background: #6c63ff; color: #fff; } .btn-secondary { background: #2a2a4a; color: #c0c0e0; }
.btn:disabled { opacity: 0.4; cursor: not-allowed; }
.error { color: #ff4444; font-size: 13px; margin-top: 8px; }
.footer-note { text-align: center; padding: 24px; color: #6666aa; font-size: 12px; }
.help-card { background: linear-gradient(135deg, #1a1a3e, #1a1a2e); border: 1px solid #2a2a4a; border-radius: 12px; margin-bottom: 16px; overflow: hidden; }
.help-header { padding: 12px 16px; font-weight: 600; color: #c0c0e0; }
.help-body { padding: 0 16px 14px; font-size: 13px; line-height: 1.8; color: #aaaacc; }
</style>
