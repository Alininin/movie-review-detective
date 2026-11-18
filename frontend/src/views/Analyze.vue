<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api, formatMs, formatScore } from '../api'

const MAX_CHARS = 5000
const route = useRoute()

const text = ref('')
const loading = ref(false)
const error = ref('')
const result = ref(null)

// 词贡献解释：与预测结果同时请求，失败不影响主结果展示
const explainResult = ref(null)
const explainLoading = ref(false)
const explainError = ref('')
const shareCopied = ref(false)

const batchFile = ref(null)
const batchLoading = ref(false)
const batchError = ref('')
const batchResult = ref(null)
const fileInput = ref(null)

const charCount = computed(() => text.value.length)
const overLimit = computed(() => charCount.value > MAX_CHARS)

const explainTerms = computed(() => explainResult.value?.terms ?? [])
const maxContribution = computed(() =>
  Math.max(1e-9, ...explainTerms.value.map((term) => Math.abs(term.contribution)))
)

function contributionWidth(term) {
  // 以中轴为 0，最长的贡献占满半幅
  return `${Math.max(2, Math.round((Math.abs(term.contribution) / maxContribution.value) * 50))}%`
}

const sampleTexts = [
  'The actors were excellent, but the story was boring.',
  'I really enjoyed this film. The pacing was perfect and the ending was unforgettable.',
  'A complete waste of time. The dialogue was flat and the plot made no sense.',
]

function fillSample(sample) {
  text.value = sample
  result.value = null
  explainResult.value = null
  error.value = ''
}

async function analyze() {
  // 防重复提交：请求进行中按钮不可点
  if (loading.value) return
  error.value = ''
  result.value = null
  explainResult.value = null
  explainError.value = ''

  if (!text.value.trim()) {
    error.value = '输入为空，请先填写英文影评文本。'
    return
  }
  if (overLimit.value) {
    error.value = `输入超过 ${MAX_CHARS} 字符上限（当前 ${charCount.value} 个字符），请截短后再试。`
    return
  }

  loading.value = true
  explainLoading.value = true
  try {
    // 两个请求都打到真实后端：预测是模型输出，解释是同一个线性模型的系数贡献
    const [prediction, explanation] = await Promise.allSettled([
      api.predict(text.value),
      api.explain(text.value, 12),
    ])
    if (prediction.status === 'fulfilled') {
      result.value = prediction.value
    } else {
      error.value = prediction.reason?.message || '分析失败'
    }
    if (explanation.status === 'fulfilled') {
      explainResult.value = explanation.value
    } else {
      explainError.value = explanation.reason?.message || '词贡献计算失败'
    }
  } finally {
    loading.value = false
    explainLoading.value = false
  }
}

function onFileChange(event) {
  const file = event.target.files?.[0] || null
  batchFile.value = file
  batchResult.value = null
  batchError.value = ''
}

async function uploadBatch() {
  if (batchLoading.value) return
  batchError.value = ''
  batchResult.value = null
  if (!batchFile.value) {
    batchError.value = '请先选择一个 CSV 文件。'
    return
  }
  batchLoading.value = true
  try {
    batchResult.value = await api.batch(batchFile.value)
  } catch (e) {
    batchError.value = e.message
  } finally {
    batchLoading.value = false
  }
}

function downloadBatchCsv() {
  if (!batchResult.value) return
  const header = ['row', 'text', 'tfidf_label_name', 'tfidf_score', 'distilbert_label_name', 'distilbert_score', 'agree']
  const escape = (value) => {
    const str = String(value ?? '')
    return /[",\n]/.test(str) ? `"${str.replace(/"/g, '""')}"` : str
  }
  const lines = [header.join(',')]
  for (const row of batchResult.value.rows) {
    lines.push([
      row.row,
      row.text,
      row.tfidf_label_name,
      row.tfidf_score,
      row.distilbert_label_name,
      row.distilbert_score,
      row.agree ? 'yes' : 'no',
    ].map(escape).join(','))
  }
  const blob = new Blob(['\uFEFF' + lines.join('\n')], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = 'batch_sentiment_result.csv'
  anchor.click()
  URL.revokeObjectURL(url)
}

function modelEntries(payload) {
  if (!payload) return []
  return Object.entries(payload.models).map(([key, value]) => ({ key, ...value }))
}

onMounted(() => {
  // 支持可分享链接：#/analyze?text=... 只把输入带过来，结果仍然由后端实时计算
  const shared = route.query.text
  if (typeof shared === 'string' && shared.trim()) {
    text.value = shared.slice(0, MAX_CHARS)
    analyze()
  }
})

// 复制当前输入的分享链接（不含任何结果，避免看起来像「预置答案」）
async function copyShareLink() {
  const url = `${location.origin}${location.pathname}#/analyze?text=${encodeURIComponent(text.value)}`
  try {
    await navigator.clipboard.writeText(url)
    shareCopied.value = true
    setTimeout(() => (shareCopied.value = false), 2000)
  } catch (e) {
    shareCopied.value = false
  }
}
</script>

<template>
  <div>
    <div class="page-head">
      <h2>情感分析</h2>
      <p>
        输入英文影评，后端同时调用 TF-IDF + 逻辑回归与 DistilBERT 两个模型，
        返回标签、分类分数与各自耗时。结果由后端实时计算，页面不保存任何预置答案。
      </p>
    </div>

    <div class="panel">
      <h3>单条分析<span class="hint">网页文本上限 {{ MAX_CHARS }} 字符</span></h3>

      <div class="toolbar" style="margin-bottom: 8px">
        <span class="small muted">示例影评（英文）：</span>
        <button v-for="(sample, index) in sampleTexts" :key="index" class="chip" @click="fillSample(sample)">
          示例 {{ index + 1 }}
        </button>
      </div>

      <textarea
        v-model="text"
        rows="6"
        :maxlength="MAX_CHARS + 200"
        placeholder="例如：The actors were excellent, but the story was boring."
      ></textarea>

      <div class="toolbar" style="margin-top: 10px">
        <span class="counter" :class="{ over: overLimit }">{{ charCount }} / {{ MAX_CHARS }} 字符</span>
        <div class="grow"></div>
        <button class="primary" :disabled="loading" @click="analyze">
          <span v-if="loading" class="spinner"></span>
          {{ loading ? '模型推理中…' : '开始分析' }}
        </button>
        <button :disabled="!text.trim()" @click="copyShareLink">
          {{ shareCopied ? '已复制' : '复制可分享链接' }}
        </button>
      </div>

      <div v-if="overLimit" class="alert warn" style="margin-top: 12px">
        输入超过 {{ MAX_CHARS }} 字符上限，请截短后再提交。
      </div>
      <div v-if="error" class="alert error" style="margin-top: 12px">{{ error }}</div>
      <div v-if="loading" class="alert info" style="margin-top: 12px">
        CPU 推理需要一点时间，请等待返回；请求进行中按钮已禁用，避免重复提交。
      </div>
    </div>

    <div v-if="result" class="panel">
      <h3>
        分析结果
        <span class="hint">
          总耗时 {{ formatMs(result.total_ms) }} ·
          <span class="badge" :class="result.agreement ? 'info' : 'warn'">
            {{ result.agreement ? '两个模型结论一致' : '两个模型结论不一致' }}
          </span>
        </span>
      </h3>

      <div class="grid grid-2">
        <div v-for="model in modelEntries(result)" :key="model.key" class="stat ticket">
          <div class="label">{{ model.model }}</div>
          <div style="display: flex; align-items: baseline; gap: 10px; margin: 4px 0 10px">
            <span class="badge" :class="model.label === 1 ? 'pos' : 'neg'" style="font-size: 13px">
              {{ model.label_cn }}（{{ model.label_name }}）
            </span>
            <span class="muted small">耗时 {{ formatMs(model.elapsed_ms) }}</span>
          </div>

          <div class="small muted" style="margin-bottom: 4px">
            分类分数 {{ formatScore(model.scores.negative) }}（负面） ·
            {{ formatScore(model.scores.positive) }}（正面）
          </div>
          <div class="bar" :class="model.label === 1 ? 'pos' : 'neg'">
            <span :style="{ width: `${Math.round(model.score * 100)}%` }"></span>
          </div>

          <p class="small muted" style="margin: 8px 0 0">
            {{ model.model_id }}
            <template v-if="model.key === 'distilbert'">
              · 截断上限 {{ model.max_length }} token
              <template v-if="model.input_tokens">
                · 本条 {{ model.input_tokens }} token
                <span v-if="model.truncated" class="badge warn">已截断</span>
              </template>
            </template>
            <template v-else>· 不截断（全文参与 TF-IDF 计算）</template>
          </p>
        </div>
      </div>

      <p class="small muted" style="margin: 12px 0 0">{{ result.score_note }}</p>
    </div>

    <div v-if="result" class="panel">
      <h3>
        模型依据 · 词贡献
        <span class="hint">TF-IDF + 逻辑回归的线性贡献，数值来自训练好的模型</span>
      </h3>

      <div v-if="explainLoading" class="empty">
        <span class="spinner dark"></span>正在计算词贡献……
      </div>

      <div v-else-if="explainError" class="alert warn">{{ explainError }}</div>

      <template v-else-if="explainResult">
        <div v-if="explainResult.empty_note" class="alert warn">
          {{ explainResult.empty_note }}
          （已知词 {{ explainResult.known_tokens }} 个 / 输入 {{ explainResult.input_tokens }} 个词）
        </div>

        <template v-else>
          <div class="term-cloud" style="margin-bottom: 16px">
            <span
              v-for="term in explainTerms"
              :key="term.token"
              class="term"
              :class="term.direction === 'positive' ? 'push-pos' : 'push-neg'"
            >
              <span class="token">{{ term.token }}</span>
            </span>
          </div>

          <div
            v-for="term in explainTerms.slice(0, 6)"
            :key="'row-' + term.token"
            class="contrib-row"
          >
            <span class="mono" style="color: var(--cream-dim)">{{ term.token }}</span>
            <span class="contrib-axis">
              <span class="mid"></span>
              <span
                class="fill"
                :class="term.direction === 'positive' ? 'pos' : 'neg'"
                :style="{ width: contributionWidth(term) }"
              ></span>
            </span>
            <span
              class="mono"
              style="text-align: right"
              :style="{ color: term.direction === 'positive' ? 'var(--pos)' : 'var(--neg)' }"
            >
              {{ term.contribution > 0 ? '+' : '' }}{{ term.contribution.toFixed(3) }}
            </span>
          </div>

          <p class="small muted" style="margin: 12px 0 0">{{ explainResult.note }}</p>
          <p class="small muted" style="margin: 4px 0 0">
            落在训练集词表里的词 / n-gram 共 {{ explainResult.known_tokens }} 个，输入共
            {{ explainResult.input_tokens }} 个词；截距项 {{ explainResult.intercept }}。
          </p>
        </template>
      </template>
    </div>

    <div class="panel">
      <h3>CSV 批量分析<span class="hint">字段统一为 text，每次 1~20 条</span></h3>

      <div class="alert info">
        CSV 第一行必须是表头，且包含一列名为 <code>text</code>。逐行顺序执行，页面会显示等待状态。
      </div>

      <div class="toolbar">
        <input ref="fileInput" type="file" accept=".csv,text/csv" :disabled="batchLoading" @change="onFileChange" />
        <button class="primary" :disabled="batchLoading || !batchFile" @click="uploadBatch">
          <span v-if="batchLoading" class="spinner"></span>
          {{ batchLoading ? '批量分析中…' : '上传并分析' }}
        </button>
        <button v-if="batchResult" @click="downloadBatchCsv">下载结果 CSV</button>
      </div>

      <div v-if="batchError" class="alert error" style="margin-top: 12px">{{ batchError }}</div>

      <template v-if="batchResult">
        <div class="alert" :class="batchResult.skipped.length ? 'warn' : 'info'" style="margin-top: 12px">
          共 {{ batchResult.summary.submitted_rows }} 行，成功分析
          {{ batchResult.summary.analyzed_rows }} 行，跳过 {{ batchResult.summary.skipped_rows }} 行；
          两模型一致 {{ batchResult.summary.agree_rows }} 行，不一致 {{ batchResult.summary.disagree_rows }} 行；
          总耗时 {{ formatMs(batchResult.summary.total_ms) }}。
        </div>
        <p v-for="(skip, index) in batchResult.skipped" :key="index" class="small muted">
          第 {{ skip.row }} 行已跳过：{{ skip.reason }}
        </p>

        <table style="margin-top: 10px">
          <thead>
            <tr>
              <th style="width: 56px">行号</th>
              <th>影评原文</th>
              <th style="width: 110px">TF-IDF</th>
              <th style="width: 100px">分数</th>
              <th style="width: 110px">DistilBERT</th>
              <th style="width: 100px">分数</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in batchResult.rows" :key="row.row">
              <td>{{ row.row }}</td>
              <td><div class="review-text">{{ row.text }}</div></td>
              <td><span class="badge" :class="row.tfidf_label === 1 ? 'pos' : 'neg'">{{ row.tfidf_label_cn }}</span></td>
              <td class="mono">{{ formatScore(row.tfidf_score) }}</td>
              <td><span class="badge" :class="row.distilbert_label === 1 ? 'pos' : 'neg'">{{ row.distilbert_label_cn }}</span></td>
              <td class="mono">{{ formatScore(row.distilbert_score) }}</td>
            </tr>
          </tbody>
        </table>
        <p class="small muted">{{ batchResult.score_note }}</p>
      </template>
    </div>
  </div>
</template>
