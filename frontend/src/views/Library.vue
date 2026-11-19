<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { api } from '../api'
import Icon from '../components/Icon.vue'
import { useTheme } from '../theme'

const { resolved } = useTheme()

const stats = ref(null)
const statsError = ref('')

const filters = ref({ split: 'all', label: 'all', keyword: '' })
// 长度区间：由柱状图点击产生（真实分箱，不是示意图）
const wordRange = ref(null)
const page = ref(1)
const pageSize = 8
const list = ref({ items: [], total: 0, pages: 1 })
const listLoading = ref(false)
const listError = ref('')
const openIds = ref(new Set())

const chartEl = ref(null)
let chart = null

const totals = computed(() => stats.value?.totals ?? {})
const labelCounts = computed(() => stats.value?.label_counts ?? {})
const trainLength = computed(() => stats.value?.length?.train?.word ?? null)

function themeColor(name, fallback) {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return value || fallback
}

function renderChart() {
  if (!chartEl.value || !stats.value) return
  if (!chart) {
    chart = echarts.init(chartEl.value)
    chart.on('click', (params) => {
      const histogram = stats.value?.histogram?.train
      if (!histogram || params.dataIndex == null) return
      const min = histogram.bin_edges[params.dataIndex]
      const max = histogram.bin_edges[params.dataIndex + 1]
      const current = wordRange.value
      wordRange.value =
        current && current.min === min && current.max === max
          ? null
          : { min, max, label: histogram.bin_labels[params.dataIndex] }
      page.value = 1
      loadList()
      renderChart()
    })
  }

  const histogram = stats.value.histogram.train
  const selected = wordRange.value
  const accent = themeColor('--accent', '#ff9d6b')
  const muted = themeColor('--muted', '#8d97a6')
  const border = themeColor('--border-strong', 'rgba(255,255,255,.2)')
  const panel = themeColor('--bg-soft', '#0d1017')

  chart.setOption(
    {
      grid: { left: 8, right: 8, top: 18, bottom: 26, containLabel: true },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow', shadowStyle: { color: 'rgba(127,127,127,0.08)' } },
        backgroundColor: panel,
        borderColor: border,
        textStyle: { color: themeColor('--text', '#fff'), fontSize: 12 },
        padding: [8, 11],
        formatter: (items) => {
          const item = items[0]
          const min = histogram.bin_edges[item.dataIndex]
          const max = histogram.bin_edges[item.dataIndex + 1]
          return `${min}–${max} 词 · ${item.value} 条`
        },
      },
      xAxis: {
        type: 'category',
        data: histogram.bin_labels,
        axisLabel: { fontSize: 9.5, rotate: 40, color: muted, margin: 10 },
        axisLine: { lineStyle: { color: border } },
        axisTick: { show: false },
      },
      yAxis: {
        type: 'value',
        splitLine: { lineStyle: { color: border, opacity: 0.35 } },
        axisLabel: { fontSize: 9.5, color: muted },
      },
      series: [
        {
          type: 'bar',
          data: histogram.counts.map((value, index) => {
            const min = histogram.bin_edges[index]
            const max = histogram.bin_edges[index + 1]
            const isSelected = selected && selected.min === min && selected.max === max
            return {
              value,
              itemStyle: {
                borderRadius: [4, 4, 0, 0],
                color: isSelected
                  ? accent
                  : new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                      { offset: 0, color: accent },
                      { offset: 1, color: 'rgba(127,127,127,0.08)' },
                    ]),
                opacity: isSelected ? 1 : 0.75,
              },
            }
          }),
          barMaxWidth: 22,
          cursor: 'pointer',
        },
      ],
    },
    true
  )
}

async function loadStats() {
  try {
    stats.value = await api.datasetStats()
    statsError.value = ''
    await nextTick()
    renderChart()
  } catch (error) {
    statsError.value = error.message
  }
}

async function loadList() {
  listLoading.value = true
  listError.value = ''
  try {
    list.value = await api.reviews({
      split: filters.value.split,
      label: filters.value.label,
      keyword: filters.value.keyword.trim(),
      min_words: wordRange.value ? wordRange.value.min : 0,
      max_words: wordRange.value ? wordRange.value.max : 0,
      page: page.value,
      page_size: pageSize,
    })
    openIds.value = new Set()
  } catch (error) {
    listError.value = error.message
  } finally {
    listLoading.value = false
  }
}

function applyFilters() {
  page.value = 1
  loadList()
}

function clearRange() {
  wordRange.value = null
  page.value = 1
  loadList()
  renderChart()
}

function goPage(target) {
  if (target < 1 || target > list.value.pages || target === page.value) return
  page.value = target
  loadList()
}

function toggleOpen(sampleId) {
  const next = new Set(openIds.value)
  if (next.has(sampleId)) next.delete(sampleId)
  else next.add(sampleId)
  openIds.value = next
}

function handleResize() {
  chart?.resize()
}

watch(resolved, () => renderChart())

onMounted(async () => {
  await loadStats()
  await loadList()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  chart?.dispose()
  chart = null
})
</script>

<template>
  <div>
    <header class="hero">
      <div>
        <div class="kicker">01 · 数据集</div>
        <h1 class="title">影评资料库</h1>
        <p class="lede">IMDB 影评的抽样结果与逐条原文。所有数字与 data/stats.json 同源，页面只负责展示。</p>
      </div>
      <div class="hero-side">
        <span class="tag accent">种子 42</span>
        <span class="tag neutral">{{ totals.reviews || '—' }} 条样本</span>
      </div>
    </header>

    <div v-if="statsError" class="alert error">{{ statsError }}</div>

    <template v-if="stats">
      <section class="tiles">
        <div class="tile glass">
          <div class="tile-label">样本总数</div>
          <div class="tile-value">{{ totals.reviews }}<em>条</em></div>
          <div class="tile-foot">训练 + 测试，去重后</div>
        </div>
        <div class="tile glass">
          <div class="tile-label">训练 / 测试</div>
          <div class="tile-value">{{ totals.train }}<em>/ {{ totals.test }}</em></div>
          <div class="tile-foot">正负各半，固定种子</div>
        </div>
        <div class="tile glass">
          <div class="tile-label">检索库</div>
          <div class="tile-value">{{ totals.retrieval_pool }}<em>条</em></div>
          <div class="tile-foot">已预生成向量</div>
        </div>
        <div class="tile glass">
          <div class="tile-label">训练集平均长度</div>
          <div class="tile-value">{{ trainLength?.mean ?? '—' }}<em>词</em></div>
          <div class="tile-foot">中位数 {{ trainLength?.median }} · 最长 {{ trainLength?.max }}</div>
        </div>
      </section>

      <div class="duo">
        <section class="card glass">
          <div class="card-head">
            <h2 class="card-title">长度分布</h2>
            <span class="hint">训练集 · 点柱子可筛选</span>
            <span class="spacer"></span>
            <button v-if="wordRange" class="chip on" @click="clearRange">
              {{ wordRange.min }}–{{ wordRange.max }} 词 <Icon name="close" :size="12" />
            </button>
          </div>
          <div ref="chartEl" class="chart"></div>
          <details class="note-box">
            <summary>长度是怎么统计的</summary>
            <div class="note-body">{{ stats.length_unit.definition }}</div>
          </details>
        </section>

        <section class="card glass">
          <div class="card-head">
            <h2 class="card-title">类别构成</h2>
            <span class="hint">正负平衡</span>
          </div>
          <table class="plain">
            <thead>
              <tr>
                <th>集合</th>
                <th>负面</th>
                <th>正面</th>
                <th style="width: 90px">比例</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="key in ['train', 'test', 'retrieval_pool']" :key="key">
                <td>{{ { train: '训练集', test: '测试集', retrieval_pool: '检索库' }[key] }}</td>
                <td class="mono">{{ labelCounts[key]?.negative ?? 0 }}</td>
                <td class="mono">{{ labelCounts[key]?.positive ?? 0 }}</td>
                <td>
                  <div class="split">
                    <i
                      class="neg"
                      :style="{
                        width: `${((labelCounts[key]?.negative ?? 0) / ((labelCounts[key]?.negative ?? 0) + (labelCounts[key]?.positive ?? 0) || 1)) * 100}%`,
                      }"
                    ></i>
                    <i class="pos" style="flex: 1"></i>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
          <details class="note-box">
            <summary>数据来源与抽样规则</summary>
            <div class="note-body">
              <p style="margin: 0 0 6px">数据集：<span class="mono">{{ stats.dataset.id }}</span></p>
              <p style="margin: 0 0 6px">{{ stats.sampling_rule }}</p>
              <p style="margin: 0">{{ stats.retrieval_pool_rule }}</p>
            </div>
          </details>
        </section>
      </div>
    </template>

    <section class="card glass">
      <div class="card-head">
        <h2 class="card-title">浏览影评</h2>
        <span class="hint">{{ list.total }} 条符合条件</span>
      </div>

      <div class="row" style="margin-bottom: 16px">
        <select v-model="filters.split" class="field" style="width: 132px" @change="applyFilters">
          <option value="all">全部集合</option>
          <option value="train">训练集</option>
          <option value="test">测试集</option>
        </select>
        <select v-model="filters.label" class="field" style="width: 118px" @change="applyFilters">
          <option value="all">全部情感</option>
          <option value="0">负面</option>
          <option value="1">正面</option>
        </select>
        <input
          v-model="filters.keyword"
          class="field grow"
          type="text"
          placeholder="搜索影评原文（英文）"
          @keyup.enter="applyFilters"
        />
        <button class="btn" @click="applyFilters"><Icon name="filter" :size="15" />筛选</button>
      </div>

      <div v-if="listError" class="alert error">{{ listError }}</div>

      <div v-if="listLoading" class="list">
        <div class="skeleton" v-for="n in 4" :key="n"></div>
      </div>

      <div v-else-if="list.items.length" class="list">
        <article v-for="item in list.items" :key="item.sample_id" class="item">
          <div class="item-head">
            <span class="tag" :class="item.label === 1 ? 'pos' : 'neg'">
              {{ item.label_cn }}
            </span>
            <span class="mono muted">{{ item.sample_id }}</span>
            <span class="tag neutral">{{ item.split === 'train' ? '训练集' : '测试集' }}</span>
            <span class="small muted">{{ item.word_len }} 词</span>
          </div>
          <p class="review-text" :class="{ open: openIds.has(item.sample_id) }">{{ item.text }}</p>
          <button class="btn btn-quiet" style="margin-top: 6px" @click="toggleOpen(item.sample_id)">
            {{ openIds.has(item.sample_id) ? '收起' : '展开全文' }}
            <Icon name="arrowRight" :size="13" />
          </button>
        </article>
      </div>

      <div v-else class="empty">没有符合条件的影评，换个筛选条件试试。</div>

      <div class="pager">
        <span class="pages">第 {{ list.page }} / {{ list.pages }} 页</span>
        <button class="btn icon-btn" :disabled="page <= 1" @click="goPage(page - 1)">
          <Icon name="arrowLeft" :size="15" />
        </button>
        <button class="btn icon-btn" :disabled="page >= list.pages" @click="goPage(page + 1)">
          <Icon name="arrowRight" :size="15" />
        </button>
      </div>
    </section>
  </div>
</template>
