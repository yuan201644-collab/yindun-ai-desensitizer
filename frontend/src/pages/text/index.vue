<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { DEFAULT_PATTERNS, applyMask } from '../../utils/sensitivePatterns'
import { SCENARIO_TEMPLATES, getTemplate, filterPatternsByTemplate } from '../../utils/scenarioTemplates'

const inputText = ref('')
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

interface SpanResult { start: number; end: number; type: string; category: string; riskLevel: string; matchText: string; maskChar: string }
const spans = ref<SpanResult[]>([])
const highRiskCount = computed(() => spans.value.filter(s => s.riskLevel === 'high').length)

function detectLocally() {
  spans.value = []
  const text = inputText.value
  if (!text.trim()) return
  const patterns = filterPatternsByTemplate(DEFAULT_PATTERNS, activeTemplateObj.value)
  for (const pattern of patterns) {
    const regex = new RegExp(pattern.pattern.source, pattern.pattern.flags)
    let match: RegExpExecArray | null
    while ((match = regex.exec(text)) !== null) {
      const isOverlapping = spans.value.some(s => match!.index < s.end && match!.index + match![0].length > s.start)
      if (!isOverlapping) {
        spans.value.push({ start: match.index, end: match.index + match[0].length, type: pattern.type, category: pattern.category, riskLevel: pattern.riskLevel, matchText: match[0], maskChar: pattern.maskChar })
      }
    }
  }
  spans.value.sort((a, b) => a.start - b.start)
  applyLocalMask()
}

function applyLocalMask() {
  let result = inputText.value
  const sorted = [...spans.value].sort((a, b) => b.start - a.start)
  for (const span of sorted) {
    const mp = DEFAULT_PATTERNS.find(p => p.type === span.type)
    const masked = applyMask(span.matchText, mp?.keepFirst ?? 0, mp?.keepLast ?? 0, mp?.maskChar ?? '*')
    result = result.slice(0, span.start) + masked + result.slice(span.end)
  }
  maskedText.value = result
}

async function runDesensitize() {
  processing.value = true; error.value = ''
  try { detectLocally(); isProcessed.value = true } catch (e: any) { error.value = e.message || '处理失败' } finally { processing.value = false }
}

async function copyMaskedText() {
  try { await navigator.clipboard.writeText(maskedText.value); alert('已复制到剪贴板') } catch { /* ignore */ }
}

function reset() { maskedText.value = ''; spans.value = []; isProcessed.value = false; error.value = '' }

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
    html += `<mark style="background:${color}33;border-bottom:2px solid ${color};color:#fff;padding:2px 4px;border-radius:3px" title="${span.type}">${escapeHTML(span.matchText)}</mark>`
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
