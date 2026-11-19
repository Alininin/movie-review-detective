<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api, formatMs, formatScore } from '../api'
import Icon from '../components/Icon.vue'

const MAX_CHARS = 5000
const route = useRoute()

const text = ref('')
const loading = ref(false)
const error = ref('')
const result = ref(null)

const explainResult = ref(null)
const explainLoading = ref(false)
const explainError = ref('')
const shareCopied = ref(false)

const batchFile = ref(null)
const batchLoading = ref(false)
const batchError = ref('')
const batchResult = ref(null)

const charCount = computed(() => text.value.length)
const overLimit = computed(() => charCount.value > MAX_CHARS)

const explainTerms = computed(() => explainResult.value?.terms ?? [])
const maxContribution = computed(() =>
  Math.max(1e-9, ...explainTerms.value.map((term) => Math.abs(term.contribution)))
)

const samples = [
  'The actors were excellent, but the story was boring.',
  'I really enjoyed this film. The pacing was perfect and the ending was unforgettable.',
  'A complete waste of time. The dialogue was flat and the plot made no sense.',
]

function contributionWidth(term) {
  return `${Math.max(4, Math.round((Math.abs(term.contribution) / maxContribution.value) * 50))}%`
}

function fillSample(sample) {
  text.value = sample
  result.value = null
  explainResult.value = null
  error.value = ''
}

async function analyze() {
  if (loading.value) return
  error.value = ''
  result.value = null
  explainResult.value = null
  explainError.value = ''

  if (!text.value.trim()) {
    error.value = '先写一段英文影评再分析。'
    return
  }
  if (overLimit.value) {
    error.value = `超过 ${MAX_CHARS} 字符上限（当前 ${charCount.value}）。`
    return
  }

  loading.value = true
  explainLoading.value = true
  try {
    // 两个请求都打真实后端：预测是模型输出，解释是同一个线性模型的系数贡献
    const [prediction, explanation] = await Promise.allSettled([
      api.predict(text.value),
      api.explain(text.value, 12),
    ])
    if (prediction.status === 'fulfilled') result.value = prediction.value
    else error.value = prediction.reason?.message || '分析失败'
    if (explanation.status === 'fulfilled') explainResult.value = explanation.value
    else explainError.value = explanation.reason?.message || '词贡献计算失败'
  } finally {
    loading.value = false
    explainLoading.value = false
  }
}

function onFileChange(event) {
  batchFile.value = event.target.files?.[0] || null
  batchResult.value = null
  batchError.value = ''
}

async function uploadBatch() {
  if (batchLoading.value) return
  batchError.value = ''
  batchResult.value = null
  if (!batchFile.value) {
    batchError.value = '先选一个 CSV 文件。'
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

onMounted(() => {
  const shared = route.query.text
  if (typeof shared === 'string' && shared.trim()) {
    text.value = shared.slice(0, MAX_CHARS)
    analyze()
  }
})
</script>

<template>
  <div>
    <header class="hero">
      <div>
        <div class="kicker">02 · 情感分析</div>
        <h1 class="title">两个模型，一起看一段影评</h1>
        <p class="lede">自训的 TF-IDF + 逻辑回归 与 现成的 DistilBERT，各自给出判断、分数与耗时。</p>
      </div>
      <div class="hero-side">
        <button class="btn" :disabled="!text.trim()" @click="copyShareLink">
          <Icon :name="shareCopied ? 'check' : 'copy'" :size="15" />
          {{ shareCopied ? '已复制' : '分享这段' }}
        </button>
      </div>
    </header>

    <section class="card glass">
      <div class="row" style="margin-bottom: 12px">
        <span class="hint">试试：</span>
        <button v-for="(sample, index) in samples" :key="index" class="chip" @click="fillSample(sample)">
          示例 {{ index + 1 }}
        </button>
      </div>

      <textarea
        v-model="text"
        class="field"
        rows="5"
        :maxlength="MAX_CHARS + 200"
        placeholder="Paste an English movie review..."
      ></textarea>

      <div class="row" style="margin-top: 14px">
        <span class="mono muted" :style="overLimit ? 'color:var(--neg)' : ''">
          {{ charCount }} / {{ MAX_CHARS }}
        </span>
        <span class="grow"></span>
        <button class="btn btn-primary" :disabled="loading" @click="analyze">
          <Icon name="spark" :size="15" />
          {{ loading ? '推理中…' : '开始分析' }}
        </button>
      </div>

      <div v-if="overLimit" class="alert warn" style="margin-top: 14px">超过 {{ MAX_CHARS }} 字符上限。</div>
      <div v-if="error" class="alert error" style="margin-top: 14px">{{ error }}</div>
    </section>

    <template v-if="result">
      <section class="card glass">
        <div class="card-head">
          <h2 class="card-title">判断</h2>
          <span class="tag" :class="result.agreement ? 'pos' : 'accent'">
            {{ result.agreement ? '两模型一致' : '两模型分歧' }}
          </span>
          <span class="spacer"></span>
          <span class="hint">合计 {{ formatMs(result.total_ms) }}</span>
        </div>

        <div class="model-grid">
          <div v-for="model in modelEntries(result)" :key="model.key" class="model-card">
            <div class="row" style="justify-content: space-between">
              <span class="model-name">{{ model.model }}</span>
              <span class="mono muted">{{ formatMs(model.elapsed_ms) }}</span>
            </div>

            <div class="verdict" :style="{ color: model.label === 1 ? 'var(--pos)' : 'var(--neg)' }">
              {{ model.label_cn }}
              <small>{{ model.label_name }}</small>
            </div>

            <div class="meter" :class="model.label === 1 ? 'pos' : 'neg'">
              <i :style="{ width: `${Math.round(model.score * 100)}%` }"></i>
            </div>

            <div class="kvline" style="margin-top: 10px">
              <span>分数 {{ formatScore(model.scores.negative) }} <span class="muted">负</span></span>
              <span class="muted">·</span>
              <span>{{ formatScore(model.scores.positive) }} <span class="muted">正</span></span>
              <span class="tip" :data-tip="result.score_note" style="margin-left: auto">
                <Icon name="info" :size="14" />
              </span>
            </div>

            <div v-if="model.key === 'distilbert'" class="kvline" style="margin-top: 8px">
              <span class="tag" :class="model.truncated ? 'accent' : 'neutral'">
                {{ model.truncated ? '已截断' : '未截断' }}
              </span>
              <span>{{ model.input_tokens }} token / 上限 {{ model.max_length }}</span>
            </div>
            <div v-else class="kvline" style="margin-top: 8px">
              <span class="tag neutral">全文参与</span>
              <span>不截断</span>
            </div>
          </div>
        </div>
      </section>

      <section class="card glass">
        <div class="card-head">
          <h2 class="card-title">为什么这么判</h2>
          <span class="hint">TF-IDF + 逻辑回归的线性贡献</span>
          <span class="spacer"></span>
          <span class="tip" :data-tip="explainResult?.note || '词贡献来自模型系数，不是事后解释'">
            <Icon name="info" :size="15" />
          </span>
        </div>

        <div v-if="explainLoading" class="empty">正在计算…</div>
        <div v-else-if="explainError" class="alert warn">{{ explainError }}</div>

        <template v-else-if="explainResult">
          <div v-if="explainResult.empty_note" class="alert warn">{{ explainResult.empty_note }}</div>

          <template v-else>
            <div class="term-cloud" style="margin-bottom: 16px">
              <span
                v-for="term in explainTerms"
                :key="term.token"
                class="term"
                :class="term.direction === 'positive' ? 'up' : 'down'"
              >
                {{ term.token }}
              </span>
            </div>

            <div
              v-for="term in explainTerms.slice(0, 6)"
              :key="'row-' + term.token"
              class="contrib"
            >
              <span class="mono" style="color: var(--text-soft)">{{ term.token }}</span>
              <span class="axis">
                <i
                  :class="term.direction === 'positive' ? 'up' : 'down'"
                  :style="{ width: contributionWidth(term) }"
                ></i>
              </span>
              <span class="mono" :style="{ color: term.direction === 'positive' ? 'var(--pos)' : 'var(--neg)', textAlign: 'right' }">
                {{ term.contribution > 0 ? '+' : '' }}{{ term.contribution.toFixed(3) }}
              </span>
            </div>

            <details class="note-box">
              <summary>这些数字怎么读</summary>
              <div class="note-body">
                <p style="margin: 0 0 6px">{{ explainResult.note }}</p>
                <p style="margin: 0">
                  命中词表 {{ explainResult.known_tokens }} 个 · 输入 {{ explainResult.input_tokens }} 词 ·
                  截距 {{ explainResult.intercept }}
                </p>
              </div>
            </details>
          </template>
        </template>
      </section>
    </template>

    <section class="card glass">
      <div class="card-head">
        <h2 class="card-title">批量分析</h2>
        <span class="hint">CSV 一列 text，1~20 行</span>
      </div>

      <div class="row">
        <input
          class="field grow"
          type="file"
          accept=".csv,text/csv"
          :disabled="batchLoading"
          @change="onFileChange"
        />
        <button class="btn btn-primary" :disabled="batchLoading || !batchFile" @click="uploadBatch">
          <Icon name="upload" :size="15" />
          {{ batchLoading ? '分析中…' : '上传分析' }}
        </button>
        <button v-if="batchResult" class="btn" @click="downloadBatchCsv">
          <Icon name="download" :size="15" />下载结果
        </button>
      </div>

      <div v-if="batchError" class="alert error" style="margin-top: 12px">{{ batchError }}</div>

      <template v-if="batchResult">
        <div class="row" style="margin: 14px 0 10px">
          <span class="tag neutral">共 {{ batchResult.summary.submitted_rows }} 行</span>
          <span class="tag pos">分析 {{ batchResult.summary.analyzed_rows }}</span>
          <span v-if="batchResult.summary.skipped_rows" class="tag neg">
            跳过 {{ batchResult.summary.skipped_rows }}
          </span>
          <span class="hint">一致 {{ batchResult.summary.agree_rows }} · {{ formatMs(batchResult.summary.total_ms) }}</span>
        </div>

        <table class="plain">
          <thead>
            <tr>
              <th style="width: 48px">#</th>
              <th>影评</th>
              <th style="width: 92px">TF-IDF</th>
              <th style="width: 92px">DistilBERT</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in batchResult.rows" :key="row.row">
              <td class="mono muted">{{ row.row }}</td>
              <td><div class="review-text" style="max-height: 54px">{{ row.text }}</div></td>
              <td><span class="tag" :class="row.tfidf_label === 1 ? 'pos' : 'neg'">{{ row.tfidf_label_cn }}</span></td>
              <td><span class="tag" :class="row.distilbert_label === 1 ? 'pos' : 'neg'">{{ row.distilbert_label_cn }}</span></td>
            </tr>
          </tbody>
        </table>
      </template>
    </section>
  </div>
</template>
