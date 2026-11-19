<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api'
import Icon from '../components/Icon.vue'
import { highlightSegments } from '../text'

const MAX_CHARS = 5000
const route = useRoute()

const query = ref('')
const loading = ref(false)
const error = ref('')
const result = ref(null)
const presets = ref([])
const openIds = ref(new Set())

const CIRCUMFERENCE = 2 * Math.PI * 26

// 命中高亮只是词面对齐，用来解释「为什么它排得靠前」，与余弦相似度是两套口径
const highlighted = computed(() => {
  if (!result.value) return []
  return result.value.results.map((item) => ({
    ...item,
    ...highlightSegments(item.text, result.value.query),
  }))
})

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
    error.value = '写一句英文查询再检索。'
    return
  }
  if (query.value.length > MAX_CHARS) {
    error.value = `查询超过 ${MAX_CHARS} 字符。`
    return
  }

  loading.value = true
  try {
    result.value = await api.search(query.value, 5)
    openIds.value = new Set()
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

function toggle(id) {
  const next = new Set(openIds.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  openIds.value = next
}

function ringOffset(similarity) {
  return (CIRCUMFERENCE * (1 - Math.max(0, Math.min(1, similarity)))).toFixed(2)
}

onMounted(() => {
  loadPresets()
  const shared = route.query.q
  if (typeof shared === 'string' && shared.trim()) {
    query.value = shared
    runSearch()
  }
})
</script>

<template>
  <div>
    <header class="hero">
      <div>
        <div class="kicker">03 · 相似检索</div>
        <h1 class="title">找到观点相近的影评</h1>
        <p class="lede">MiniLM 把你的话变成 384 维向量，在 500 条影评里找最近的那五条。</p>
      </div>
      <div class="hero-side">
        <span class="tag neutral">余弦相似度 · 非准确率</span>
      </div>
    </header>

    <section class="card glass">
      <textarea
        v-model="query"
        class="field"
        rows="2"
        :maxlength="MAX_CHARS + 200"
        placeholder="Describe what you want to find, e.g. the acting was great but the plot was slow"
      ></textarea>

      <div class="row" style="margin-top: 12px">
        <span v-if="presets.length" class="hint">预设：</span>
        <button
          v-for="item in presets"
          :key="item.id"
          class="chip"
          @click="usePreset(item.text)"
        >
          {{ item.id }} {{ item.topic }}
        </button>
        <span class="grow"></span>
        <button class="btn btn-primary" :disabled="loading" @click="runSearch">
          <Icon name="search" :size="15" />
          {{ loading ? '检索中…' : '检索' }}
        </button>
      </div>

      <div v-if="error" class="alert error" style="margin-top: 14px">{{ error }}</div>
    </section>

    <section v-if="result" class="card glass">
      <div class="card-head">
        <h2 class="card-title">Top 5</h2>
        <span class="hint">检索库 {{ result.pool_size }} 条</span>
        <span class="spacer"></span>
        <span class="tag neutral">按相似度降序</span>
      </div>

      <div class="list">
        <article v-for="item in highlighted" :key="item.sample_id" class="item">
          <div class="row" style="align-items: flex-start; gap: 14px">
            <div class="ring">
              <svg width="62" height="62" viewBox="0 0 62 62">
                <circle class="track" cx="31" cy="31" r="26" fill="none" stroke-width="5" />
                <circle
                  class="value"
                  cx="31"
                  cy="31"
                  r="26"
                  fill="none"
                  stroke-width="5"
                  :stroke-dasharray="CIRCUMFERENCE.toFixed(2)"
                  :stroke-dashoffset="ringOffset(item.similarity)"
                />
              </svg>
              <span class="num">{{ item.similarity.toFixed(2) }}</span>
            </div>

            <div style="flex: 1; min-width: 0">
              <div class="item-head" style="margin-bottom: 6px">
                <span class="mono muted">#{{ item.rank }}</span>
                <span class="mono muted">{{ item.sample_id }}</span>
                <span class="tag" :class="item.dataset_label === 1 ? 'pos' : 'neg'">
                  原始标签 {{ item.dataset_label === 1 ? '正面' : '负面' }}
                </span>
                <span class="small muted">{{ item.word_len }} 词</span>
              </div>

              <p class="review-text" :class="{ open: openIds.has(item.sample_id) }">
                <template v-for="(segment, index) in item.segments" :key="index">
                  <span v-if="segment.hit" class="hit">{{ segment.text }}</span>
                  <template v-else>{{ segment.text }}</template>
                </template>
              </p>

              <div class="row" style="margin-top: 8px; gap: 12px">
                <button class="btn btn-quiet" @click="toggle(item.sample_id)">
                  {{ openIds.has(item.sample_id) ? '收起' : '展开全文' }}
                  <Icon name="arrowRight" :size="13" />
                </button>
                <span v-if="item.hits.length" class="small muted">
                  词面重合 {{ item.hits.length }}：{{ item.hits.join('、') }}
                </span>
                <span v-else class="small muted">没有词面重合，靠语义被召回</span>
              </div>
            </div>
          </div>
        </article>
      </div>

      <details class="note-box">
        <summary>两个口径别混用</summary>
        <div class="note-body">
          <p style="margin: 0 0 6px">{{ result.label_note }}</p>
          <p style="margin: 0">{{ result.note }} 高亮只统计词面重合，排序仍由后端余弦相似度决定。</p>
        </div>
      </details>
    </section>

    <div v-else-if="loading" class="card glass">
      <div class="skeleton" v-for="n in 3" :key="n"></div>
    </div>
  </div>
</template>
