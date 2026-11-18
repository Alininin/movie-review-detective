<script setup>
import { computed, onMounted, ref } from 'vue'
import { api, formatMs, formatScore } from '../api'
import { renderMarkdown } from '../markdown'

const data = ref(null)
const error = ref('')
const loading = ref(true)

const history = ref({ items: [], total: 0 })
const historyError = ref('')
const historyLoading = ref(false)

// 分歧样本浏览器：数据来自 experiments/predictions_test.csv（经 /api/divergence 读取）
const divergence = ref({ items: [], total: 0, test_total: 0, all_total: 0, tfidf_wins: 0, distilbert_wins: 0 })
const divergenceLoading = ref(false)
const divergenceError = ref('')
const divergenceOffset = ref(0)
const divergenceLimit = 5
const divergenceWinner = ref('all')

const metrics = computed(() => data.value?.metrics ?? null)
const retrieval = computed(() => data.value?.retrieval ?? null)
const errorCasesHtml = computed(() => renderMarkdown(data.value?.error_cases_markdown || ''))
// 图片地址由后端给出（带文件修改时间），重新生成混淆矩阵后不会显示缓存的旧图
const confusionMatrixUrl = computed(
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
    data.value = await api.experiments()
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

async function loadDivergence() {
  divergenceLoading.value = true
  divergenceError.value = ''
  try {
    divergence.value = await api.divergence(
      divergenceLimit,
      divergenceOffset.value,
      divergenceWinner.value
    )
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

async function removeHistory(id) {
  try {
    await api.deleteHistory(id)
    await loadHistory()
  } catch (e) {
    historyError.value = e.message
  }
}

onMounted(async () => {
  await loadExperiments()
  await loadHistory()
  await loadDivergence()
})
</script>

<template>
  <div>
    <div class="page-head">
      <h2>实验与历史</h2>
      <p>
        评测指标由离线脚本 <span class="mono">scripts/04_evaluate.py</span> 生成并保存在
        <span class="mono">experiments/</span>，页面只读取，不在网页请求里重新评测。
      </p>
    </div>

    <div v-if="error" class="alert error">{{ error }}</div>
    <div v-if="loading" class="empty"><span class="spinner dark"></span>正在读取实验结果……</div>

    <template v-if="metrics">
      <div class="panel">
        <h3>
          指标比较
          <span class="hint">
            测试集 {{ metrics.evaluated_on.samples }} 条 · 批大小 {{ metrics.run_config.batch_size }} ·
            {{ metrics.run_config.cpu.processor_identifier }}
          </span>
        </h3>
        <table>
          <thead>
            <tr>
              <th>模型</th>
              <th>Accuracy</th>
              <th>Macro-F1</th>
              <th>负面 P / R / F1</th>
              <th>正面 P / R / F1</th>
              <th>加载 (s)</th>
              <th>推理 (s)</th>
              <th>每条 (ms)</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in modelRows" :key="row.key">
              <td>
                {{ row.display_name }}
                <div class="small muted mono">{{ row.model_id }}</div>
              </td>
              <td class="mono"><strong>{{ formatScore(row.accuracy) }}</strong></td>
              <td class="mono">{{ formatScore(row.macro_f1) }}</td>
              <td class="mono small">
                {{ formatScore(row.per_class.negative.precision) }} /
                {{ formatScore(row.per_class.negative.recall) }} /
                {{ formatScore(row.per_class.negative.f1) }}
              </td>
              <td class="mono small">
                {{ formatScore(row.per_class.positive.precision) }} /
                {{ formatScore(row.per_class.positive.recall) }} /
                {{ formatScore(row.per_class.positive.f1) }}
              </td>
              <td class="mono">{{ row.timing.model_load_seconds }} s</td>
              <td class="mono">{{ row.timing.inference_total_seconds }} s</td>
              <td class="mono">{{ formatMs(row.timing.per_item_ms) }}</td>
            </tr>
          </tbody>
        </table>

        <p class="small muted" style="margin: 10px 0 0">
          两模型一致率 {{ formatScore(metrics.agreement_rate) }} ·
          截断设置：{{ metrics.run_config.distilbert.truncation }} ·
          测试集平均 {{ metrics.run_config.distilbert.token_count.mean }} token，
          最大 {{ metrics.run_config.distilbert.token_count.max }} token，
          其中 {{ metrics.run_config.distilbert.token_count.truncated_samples }} 条超过上限被截断。
        </p>
        <p class="small muted">分类分数不是判断正确的概率；相似度不是准确率。</p>
      </div>

      <div class="panel">
        <h3>混淆矩阵<span class="hint">行 = 真实标签，列 = 预测标签</span></h3>
        <img
          :src="confusionMatrixUrl"
          alt="混淆矩阵"
          style="max-width: 100%; border: 1px solid var(--line); border-radius: 4px; background: #0f0d0b"
        />
      </div>

      <div v-if="retrieval" class="panel">
        <h3>
          检索效果检查
          <span class="hint">
            平均 Precision@5 = {{ formatScore(retrieval.mean_precision_at_5) }} ·
            共 {{ retrieval.total_judgements }} 条人工判断
          </span>
        </h3>
        <table>
          <thead>
            <tr>
              <th style="width: 60px">查询</th>
              <th style="width: 110px">主题</th>
              <th>Top-5 判断</th>
              <th style="width: 100px">P@5</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="query in retrieval.queries" :key="query.query_id">
              <td>{{ query.query_id }}</td>
              <td>{{ query.topic }}</td>
              <td class="small">
                <span
                  v-for="item in query.items"
                  :key="item.rank"
                  class="badge"
                  :class="item.relevant ? 'pos' : 'neutral'"
                  style="margin-right: 4px"
                  :title="item.reason"
                >
                  #{{ item.rank }} {{ item.relevant ? '相关' : '不相关' }}
                </span>
              </td>
              <td class="mono">{{ formatScore(query.precision_at_5) }}</td>
            </tr>
          </tbody>
        </table>
        <p class="small muted" style="margin-bottom: 0">{{ retrieval.scope_note }}</p>
      </div>

      <div class="panel">
        <h3>
          分歧样本浏览器
          <span class="hint">
            测试集 {{ divergence.test_total || '—' }} 条中，两模型意见不一致 {{ divergence.all_total }} 条
          </span>
        </h3>

        <div class="toolbar" style="margin-bottom: 12px">
          <button :class="{ primary: divergenceWinner === 'all' }" @click="setWinner('all')">
            全部 {{ divergence.all_total }}
          </button>
          <button
            :class="{ primary: divergenceWinner === 'distilbert' }"
            @click="setWinner('distilbert')"
          >
            DistilBERT 对 / TF-IDF 错 {{ divergence.distilbert_wins }}
          </button>
          <button :class="{ primary: divergenceWinner === 'tfidf' }" @click="setWinner('tfidf')">
            TF-IDF 对 / DistilBERT 错 {{ divergence.tfidf_wins }}
          </button>
          <div class="grow"></div>
          <span class="small muted">每页 {{ divergenceLimit }} 条</span>
          <button :disabled="divergenceOffset <= 0 || divergenceLoading" @click="pageDivergence(-1)">
            上一页
          </button>
          <button
            :disabled="divergenceOffset + divergenceLimit >= divergence.total || divergenceLoading"
            @click="pageDivergence(1)"
          >
            下一页
          </button>
        </div>

        <div v-if="divergenceError" class="alert error">{{ divergenceError }}</div>
        <div v-if="divergenceLoading" class="empty">
          <span class="spinner dark"></span>正在读取分歧样本……
        </div>

        <template v-else>
          <div v-for="item in divergence.items" :key="item.sample_id" class="diverge-item">
            <div class="head">
              <span class="mono">{{ item.sample_id }}</span>
              <span class="badge" :class="item.true_label === 1 ? 'pos' : 'neg'">
                真实：{{ item.true_label_cn }}
              </span>
              <span class="small muted">{{ item.word_len }} 词</span>
              <div class="grow"></div>
              <span class="small muted">
                TF-IDF → {{ item.tfidf_label_cn }}（{{ formatScore(item.tfidf_score) }}）
              </span>
              <span class="badge" :class="item.tfidf_correct ? 'pos' : 'neg'">
                {{ item.tfidf_correct ? '对' : '错' }}
              </span>
              <span class="small muted">
                DistilBERT → {{ item.distilbert_label_cn }}（{{ formatScore(item.distilbert_score) }}）
              </span>
              <span class="badge" :class="item.distilbert_correct ? 'pos' : 'neg'">
                {{ item.distilbert_correct ? '对' : '错' }}
              </span>
            </div>
            <div class="review-text" style="max-height: 96px">{{ item.text }}</div>
          </div>
          <div v-if="!divergence.items.length" class="empty">没有符合条件的分歧样本。</div>
        </template>

        <p class="small muted" style="margin: 10px 0 0">{{ divergence.note }}</p>
      </div>

      <div class="panel">
        <h3>错误案例分析<span class="hint">experiments/error_cases.md</span></h3>
        <div v-if="errorCasesHtml" class="markdown" v-html="errorCasesHtml"></div>
        <div v-else class="empty">还没有案例分析文件。</div>
      </div>
    </template>

    <div class="panel">
      <h3>
        分析历史
        <span class="hint">保存在 SQLite，刷新与重启后仍在</span>
      </h3>

      <div class="toolbar" style="margin-bottom: 10px">
        <button :disabled="historyLoading" @click="loadHistory">
          <span v-if="historyLoading" class="spinner dark"></span>刷新历史
        </button>
        <span class="small muted">共 {{ history.total }} 条，显示最近 20 条</span>
      </div>

      <div v-if="historyError" class="alert error">{{ historyError }}</div>

      <table v-if="history.items.length">
        <thead>
          <tr>
            <th style="width: 56px">ID</th>
            <th>文本</th>
            <th style="width: 120px">TF-IDF</th>
            <th style="width: 120px">DistilBERT</th>
            <th style="width: 160px">时间</th>
            <th style="width: 70px">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in history.items" :key="item.id">
            <td>{{ item.id }}</td>
            <td><div class="review-text" style="max-height: 76px">{{ item.text }}</div></td>
            <td class="small">
              {{ item.tfidf_label_name === 'positive' ? '正面' : '负面' }}
              <div class="mono">分数 {{ formatScore(item.tfidf_score) }}</div>
            </td>
            <td class="small">
              {{ item.hf_label_name === 'positive' ? '正面' : '负面' }}
              <div class="mono">分数 {{ formatScore(item.hf_score) }}</div>
            </td>
            <td class="small mono">{{ item.created_at }}</td>
            <td><button class="danger" @click="removeHistory(item.id)">删除</button></td>
          </tr>
        </tbody>
      </table>
      <div v-else class="empty">还没有历史记录，先去「情感分析」页跑一条。</div>
    </div>
  </div>
</template>
