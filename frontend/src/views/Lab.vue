<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api, formatMs, formatScore } from '../api'
import Icon from '../components/Icon.vue'
import { renderMarkdown } from '../markdown'
import { useTheme } from '../theme'

const { resolved } = useTheme()

const data = ref(null)
const error = ref('')
const loading = ref(true)

const history = ref({ items: [], total: 0 })
const historyError = ref('')
const historyLoading = ref(false)

const divergence = ref({
  items: [],
  total: 0,
  test_total: 0,
  all_total: 0,
  tfidf_wins: 0,
  distilbert_wins: 0,
})
const divergenceLoading = ref(false)
const divergenceError = ref('')
const divergenceOffset = ref(0)
const divergenceLimit = 4
const divergenceWinner = ref('all')

const tab = ref('metrics')

const TABS = [
  { key: 'metrics', label: '指标' },
  { key: 'matrix', label: '混淆矩阵' },
  { key: 'retrieval', label: '检索质量' },
  { key: 'divergence', label: '分歧样本' },
  { key: 'cases', label: '错误案例' },
  { key: 'history', label: '历史' },
]

// 支持可分享链接：#/lab?tab=divergence 直接打开某个标签页
const route = useRoute()
const initialTab = route.query.tab
if (typeof initialTab === 'string' && TABS.some((item) => item.key === initialTab)) {
  tab.value = initialTab
}

const metrics = computed(() => data.value?.metrics ?? null)
const retrieval = computed(() => data.value?.retrieval ?? null)
const errorCasesHtml = computed(() => renderMarkdown(data.value?.error_cases_markdown || ''))
const matrixUrl = computed(
  () => data.value?.artifacts?.confusion_matrix_url || '/api/experiments/confusion-matrix.png'
)

const modelRows = computed(() => {
  if (!metrics.value) return []
  return Object.entries(metrics.value.models).map(([key, value]) => ({ key, ...value }))
})

async function loadExperiments() {
  loading.value = true
  error.value = ''
  try {
    data.value = await api.experiments(resolved.value)
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function loadHistory() {
  historyLoading.value = true
  historyError.value = ''
  try {
    history.value = await api.history(20, 0)
  } catch (e) {
    historyError.value = e.message
  } finally {
    historyLoading.value = false
  }
}

async function removeHistory(id) {
  try {
    await api.deleteHistory(id)
    await loadHistory()
  } catch (e) {
    historyError.value = e.message
  }
}

async function loadDivergence() {
  divergenceLoading.value = true
  divergenceError.value = ''
  try {
    divergence.value = await api.divergence(divergenceLimit, divergenceOffset.value, divergenceWinner.value)
  } catch (e) {
    divergenceError.value = e.message
  } finally {
    divergenceLoading.value = false
  }
}

function setWinner(winner) {
  divergenceWinner.value = winner
  divergenceOffset.value = 0
  loadDivergence()
}

function pageDivergence(delta) {
  const next = divergenceOffset.value + delta * divergenceLimit
  if (next < 0 || next >= divergence.value.total) return
  divergenceOffset.value = next
  loadDivergence()
}

onMounted(async () => {
  await loadExperiments()
  await loadHistory()
  await loadDivergence()
})

// 切换明暗主题时，混淆矩阵换用对应的配色版本
watch(resolved, () => loadExperiments())
</script>

<template>
  <div>
    <header class="hero">
      <div>
        <div class="kicker">05 · 实验台</div>
        <h1 class="title">数字都在这里</h1>
        <p class="lede">指标与案例由离线脚本生成，网页只读取；历史记录存在 SQLite，重启后仍在。</p>
      </div>
      <div class="hero-side">
        <span v-if="metrics" class="tag neutral">{{ metrics.evaluated_on.samples }} 条测试集</span>
      </div>
    </header>

    <div v-if="error" class="alert error">{{ error }}</div>

    <div class="tabs">
      <button
        v-for="item in TABS"
        :key="item.key"
        class="tab"
        :class="{ on: tab === item.key }"
        @click="tab = item.key"
      >
        {{ item.label }}
      </button>
    </div>

    <!-- 指标 -->
    <section v-if="tab === 'metrics'" class="card glass">
      <div v-if="loading" class="empty">正在读取实验结果…</div>
      <template v-else-if="metrics">
        <table class="plain">
          <thead>
            <tr>
              <th>模型</th>
              <th>Accuracy</th>
              <th>Macro-F1</th>
              <th>加载</th>
              <th>推理</th>
              <th>每条</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in modelRows" :key="row.key">
              <td>
                <div style="font-weight: 600">{{ row.display_name }}</div>
                <div class="mono muted" style="margin-top: 3px">{{ row.model_id }}</div>
              </td>
              <td class="mono" style="font-weight: 600">{{ formatScore(row.accuracy) }}</td>
              <td class="mono">{{ formatScore(row.macro_f1) }}</td>
              <td class="mono muted">{{ row.timing.model_load_seconds }} s</td>
              <td class="mono muted">{{ row.timing.inference_total_seconds }} s</td>
              <td class="mono">{{ formatMs(row.timing.per_item_ms) }}</td>
            </tr>
          </tbody>
        </table>

        <div style="margin-top: 20px; display: grid; gap: 10px">
          <div class="hint">准确率对比</div>
          <div v-for="row in modelRows" :key="'bar-' + row.key" class="contrib">
            <span class="mono" style="color: var(--text-soft); font-size: 11px">{{ row.display_name }}</span>
            <span class="axis">
              <i class="accent" :style="{ width: (row.accuracy * 100).toFixed(1) + '%' }"></i>
            </span>
            <span class="mono" style="text-align: right">{{ formatScore(row.accuracy) }}</span>
          </div>
        </div>

        <div class="row" style="margin-top: 14px">
          <span class="tag accent">一致率 {{ formatScore(metrics.agreement_rate) }}</span>
          <span class="tag neutral">批大小 {{ metrics.run_config.batch_size }}</span>
          <span class="tag neutral">max_length 256 · 均值 {{ Math.round(metrics.run_config.distilbert.token_count.mean) }} token</span>
        </div>

        <details class="note-box">
          <summary>运行环境与截断情况</summary>
          <div class="note-body">
            <p style="margin: 0 0 6px">{{ metrics.run_config.cpu.processor_identifier }} · Python {{ metrics.run_config.cpu.python }}</p>
            <p style="margin: 0 0 6px">{{ metrics.run_config.distilbert.truncation }}；测试集均值 {{ metrics.run_config.distilbert.token_count.mean }} token，最大 {{ metrics.run_config.distilbert.token_count.max }}，其中 {{ metrics.run_config.distilbert.token_count.truncated_samples }} 条被截断。</p>
            <p style="margin: 0">分类分数不是判断正确的概率；相似度不是准确率。</p>
          </div>
        </details>
      </template>
    </section>

    <!-- 混淆矩阵 -->
    <section v-if="tab === 'matrix'" class="card glass">
      <div class="card-head">
        <h2 class="card-title">测试集混淆矩阵</h2>
        <span class="hint">行 = 真实标签，列 = 预测标签</span>
      </div>
      <div v-if="loading" class="empty">正在加载…</div>
      <img v-else :src="matrixUrl" alt="混淆矩阵" style="width: 100%; border-radius: var(--r-md)" />
      <details class="note-box">
        <summary>图从哪来</summary>
        <div class="note-body">
          由 <span class="mono">scripts/04_evaluate.py</span> 生成。白底版给报告，深色版给界面，
          地址带文件版本号，重新生成后不会读到缓存。
        </div>
      </details>
    </section>

    <!-- 检索质量 -->
    <section v-if="tab === 'retrieval'" class="card glass">
      <div v-if="!retrieval" class="empty">还没有检索人工判断。</div>
      <template v-else>
        <div class="card-head">
          <h2 class="card-title">5 条查询 × Top-5</h2>
          <span class="spacer"></span>
          <span class="tag accent">平均 P@5 = {{ formatScore(retrieval.mean_precision_at_5) }}</span>
        </div>

        <table class="plain">
          <thead>
            <tr>
              <th style="width: 56px">查询</th>
              <th style="width: 96px">主题</th>
              <th>Top-5 判断</th>
              <th style="width: 72px">P@5</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="query in retrieval.queries" :key="query.query_id">
              <td class="mono">{{ query.query_id }}</td>
              <td>{{ query.topic }}</td>
              <td>
                <span
                  v-for="item in query.items"
                  :key="item.rank"
                  class="tag"
                  :class="item.relevant ? 'pos' : 'neutral'"
                  style="margin-right: 5px"
                  :title="item.reason"
                >
                  #{{ item.rank }}
                </span>
              </td>
              <td class="mono">{{ formatScore(query.precision_at_5) }}</td>
            </tr>
          </tbody>
        </table>

        <details class="note-box">
          <summary>相关性怎么判的</summary>
          <div class="note-body">{{ retrieval.scope_note }} {{ retrieval.judging_rule }}</div>
        </details>
      </template>
    </section>

    <!-- 分歧样本 -->
    <section v-if="tab === 'divergence'" class="card glass">
      <div class="card-head">
        <h2 class="card-title">两模型不同意的地方</h2>
        <span class="hint">200 条测试集里有 {{ divergence.all_total }} 条</span>
      </div>

      <div class="row" style="margin-bottom: 14px">
        <button class="chip" :class="{ on: divergenceWinner === 'all' }" @click="setWinner('all')">
          全部 {{ divergence.all_total }}
        </button>
        <button
          class="chip"
          :class="{ on: divergenceWinner === 'distilbert' }"
          @click="setWinner('distilbert')"
        >
          DistilBERT 对 {{ divergence.distilbert_wins }}
        </button>
        <button class="chip" :class="{ on: divergenceWinner === 'tfidf' }" @click="setWinner('tfidf')">
          TF-IDF 对 {{ divergence.tfidf_wins }}
        </button>
        <span class="grow"></span>
        <button class="btn icon-btn" :disabled="divergenceOffset <= 0 || divergenceLoading" @click="pageDivergence(-1)">
          <Icon name="arrowLeft" :size="15" />
        </button>
        <button
          class="btn icon-btn"
          :disabled="divergenceOffset + divergenceLimit >= divergence.total || divergenceLoading"
          @click="pageDivergence(1)"
        >
          <Icon name="arrowRight" :size="15" />
        </button>
      </div>

      <div v-if="divergenceError" class="alert error">{{ divergenceError }}</div>
      <div v-if="divergenceLoading" class="list">
        <div class="skeleton" v-for="n in 3" :key="n"></div>
      </div>

      <div v-else class="list">
        <article v-for="item in divergence.items" :key="item.sample_id" class="item">
          <div class="item-head">
            <span class="mono muted">{{ item.sample_id }}</span>
            <span class="tag" :class="item.true_label === 1 ? 'pos' : 'neg'">
              真实 {{ item.true_label_cn }}
            </span>
            <span class="spacer"></span>
            <span class="tag" :class="item.tfidf_correct ? 'pos' : 'neg'">
              TF-IDF {{ item.tfidf_label_cn }} {{ item.tfidf_correct ? '对' : '错' }}
            </span>
            <span class="tag" :class="item.distilbert_correct ? 'pos' : 'neg'">
              DistilBERT {{ item.distilbert_label_cn }} {{ item.distilbert_correct ? '对' : '错' }}
            </span>
          </div>
          <p class="review-text" style="max-height: 76px">{{ item.text }}</p>
        </article>
      </div>

      <details class="note-box">
        <summary>这些样本怎么来的</summary>
        <div class="note-body">{{ divergence.note }}</div>
      </details>
    </section>

    <!-- 错误案例 -->
    <section v-if="tab === 'cases'" class="card glass">
      <div class="card-head">
        <h2 class="card-title">错误案例分析</h2>
        <span class="hint">人工撰写 · 7 条</span>
      </div>
      <div v-if="errorCasesHtml" class="markdown" v-html="errorCasesHtml"></div>
      <div v-else class="empty">还没有案例分析文件。</div>
    </section>

    <!-- 历史 -->
    <section v-if="tab === 'history'" class="card glass">
      <div class="card-head">
        <h2 class="card-title">分析历史</h2>
        <span class="hint">SQLite · 共 {{ history.total }} 条</span>
        <span class="spacer"></span>
        <button class="btn icon-btn" :disabled="historyLoading" @click="loadHistory">
          <Icon name="history" :size="15" />
        </button>
      </div>

      <div v-if="historyError" class="alert error">{{ historyError }}</div>

      <div v-if="historyLoading" class="list">
        <div class="skeleton" v-for="n in 3" :key="n"></div>
      </div>

      <div v-else-if="history.items.length" class="list">
        <article v-for="item in history.items" :key="item.id" class="item">
          <div class="item-head">
            <span class="mono muted">#{{ item.id }}</span>
            <span class="tag" :class="item.tfidf_label_name === 'positive' ? 'pos' : 'neg'">
              TF-IDF {{ item.tfidf_label_name === 'positive' ? '正面' : '负面' }}
            </span>
            <span class="tag" :class="item.hf_label_name === 'positive' ? 'pos' : 'neg'">
              DistilBERT {{ item.hf_label_name === 'positive' ? '正面' : '负面' }}
            </span>
            <span class="small muted">{{ item.created_at }}</span>
            <span class="spacer"></span>
            <button class="btn icon-btn" title="删除这条" @click="removeHistory(item.id)">
              <Icon name="close" :size="14" />
            </button>
          </div>
          <p class="review-text" style="max-height: 54px">{{ item.text }}</p>
        </article>
      </div>

      <div v-else class="empty">还没有历史记录，去「情感分析」跑一条。</div>
    </section>
  </div>
</template>
