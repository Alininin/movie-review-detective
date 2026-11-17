<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api'

const query = ref('')
const loading = ref(false)
const error = ref('')
const result = ref(null)
const presets = ref([])
const expanded = ref(new Set())

const MAX_CHARS = 5000

async function loadPresets() {
  try {
    const payload = await api.presetQueries()
    presets.value = payload.queries || []
  } catch (e) {
    presets.value = []
  }
}

function usePreset(text) {
  query.value = text
  runSearch()
}

async function runSearch() {
  if (loading.value) return
  error.value = ''
  result.value = null

  if (!query.value.trim()) {
    error.value = '查询为空，请填写英文查询语句。'
    return
  }
  if (query.value.length > MAX_CHARS) {
    error.value = `查询超过 ${MAX_CHARS} 字符上限，请截短。`
    return
  }

  loading.value = true
  try {
    result.value = await api.search(query.value, 5)
    expanded.value = new Set()
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

function toggle(id) {
  const next = new Set(expanded.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  expanded.value = next
}

onMounted(loadPresets)
</script>

<template>
  <div>
    <div class="page-head">
      <h2>相似影评搜索</h2>
      <p>
        用 MiniLM 把查询编码成向量，与检索库中 500 条影评的预生成向量计算余弦相似度，返回 Top-5。
        向量已离线生成并保存，查询时只编码你输入的这句话。
      </p>
    </div>

    <div class="panel">
      <h3>输入查询<span class="hint">英文</span></h3>

      <div v-if="presets.length" class="toolbar" style="margin-bottom: 10px">
        <span class="small muted">预设查询（人工检查用的 5 条）：</span>
        <button v-for="item in presets" :key="item.id" class="chip" @click="usePreset(item.text)">
          {{ item.id }} · {{ item.topic }}
        </button>
      </div>

      <textarea
        v-model="query"
        rows="3"
        placeholder="例如：The actors were excellent, but the story was boring."
      ></textarea>

      <div class="toolbar" style="margin-top: 10px">
        <span class="counter">{{ query.length }} / {{ MAX_CHARS }} 字符</span>
        <div class="grow"></div>
        <button class="primary" :disabled="loading" @click="runSearch">
          <span v-if="loading" class="spinner"></span>
          {{ loading ? '检索中…' : '检索 Top-5' }}
        </button>
      </div>

      <div v-if="error" class="alert error" style="margin-top: 12px">{{ error }}</div>
    </div>

    <div v-if="result" class="panel">
      <h3>
        检索结果
        <span class="hint">检索库 {{ result.pool_size }} 条 · 返回 {{ result.results.length }} 条</span>
      </h3>

      <div class="alert info">{{ result.note }}</div>

      <div
        v-for="item in result.results"
        :key="item.sample_id"
        class="stat"
        style="margin-bottom: 10px"
      >
        <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap">
          <span class="badge info">#{{ item.rank }}</span>
          <span class="mono">{{ item.sample_id }}</span>
          <span class="badge" :class="item.dataset_label === 1 ? 'pos' : 'neg'">
            数据集原始标签：{{ item.dataset_label === 1 ? '正面' : '负面' }}
          </span>
          <span class="small muted">{{ item.word_len }} 词</span>
          <div class="grow"></div>
          <span class="small muted">余弦相似度</span>
          <span class="mono" style="font-weight: 600">{{ item.similarity.toFixed(4) }}</span>
        </div>

        <div class="bar" style="margin: 8px 0 10px">
          <span :style="{ width: `${Math.max(2, Math.round(item.similarity * 100))}%` }"></span>
        </div>

        <div class="review-text" :class="{ expanded: expanded.has(item.sample_id) }">
          {{ item.text }}
        </div>
        <button class="link-button" @click="toggle(item.sample_id)">
          {{ expanded.has(item.sample_id) ? '收起全文' : '查看完整影评' }}
        </button>
      </div>

      <p class="small muted">{{ result.label_note }}</p>
    </div>
  </div>
</template>
