<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { api } from '../api'

const stats = ref(null)
const statsError = ref('')

const filters = ref({ split: 'all', label: 'all', keyword: '' })
const page = ref(1)
const pageSize = 10
const list = ref({ items: [], total: 0, pages: 1 })
const listLoading = ref(false)
const listError = ref('')
const expanded = ref(new Set())

const chartEl = ref(null)
let chart = null

const totals = computed(() => stats.value?.totals ?? {})
const labelCounts = computed(() => stats.value?.label_counts ?? {})
const trainLength = computed(() => stats.value?.length?.train?.word ?? null)

function renderChart() {
  if (!chartEl.value || !stats.value) return
  if (!chart) chart = echarts.init(chartEl.value)
  const histogram = stats.value.histogram.train
  chart.setOption({
    grid: { left: 46, right: 16, top: 28, bottom: 34 },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    xAxis: {
      type: 'category',
      data: histogram.bin_labels,
      axisLabel: { fontSize: 10, rotate: 38, color: '#6b7280' },
      axisLine: { lineStyle: { color: '#e5e7eb' } },
    },
    yAxis: {
      type: 'value',
      name: '样本数',
      nameTextStyle: { fontSize: 10, color: '#9ca3af' },
      splitLine: { lineStyle: { color: '#f3f4f6' } },
      axisLabel: { fontSize: 10, color: '#6b7280' },
    },
    series: [
      {
        type: 'bar',
        data: histogram.counts,
        itemStyle: { color: '#6366f1', borderRadius: [3, 3, 0, 0] },
        barMaxWidth: 26,
      },
    ],
  })
}

function handleResize() {
  chart?.resize()
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
      page: page.value,
      page_size: pageSize,
    })
    expanded.value = new Set()
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

function goPage(target) {
  if (target < 1 || target > list.value.pages || target === page.value) return
  page.value = target
  loadList()
}

function toggleExpand(sampleId) {
  const next = new Set(expanded.value)
  if (next.has(sampleId)) next.delete(sampleId)
  else next.add(sampleId)
  expanded.value = next
}

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

watch(page, () => loadList())
</script>

<template>
  <div>
    <div class="page-head">
      <h2>影评资料库</h2>
      <p>
        IMDB 影评抽样结果：训练集 1000 条、官方测试集 200 条、检索库 500 条。
        统计数字与 <span class="mono">data/stats.json</span> 同源，页面只做展示。
      </p>
    </div>

    <div v-if="statsError" class="alert error">{{ statsError }}</div>

    <template v-if="stats">
      <div class="grid grid-3" style="margin-bottom: 16px">
        <div class="stat">
          <div class="label">影评样本总数</div>
          <div class="value">{{ totals.reviews }}<small>条</small></div>
        </div>
        <div class="stat">
          <div class="label">训练集 / 测试集</div>
          <div class="value">{{ totals.train }}<small>/ {{ totals.test }}</small></div>
        </div>
        <div class="stat">
          <div class="label">检索库</div>
          <div class="value">{{ totals.retrieval_pool }}<small>条</small></div>
        </div>
        <div class="stat">
          <div class="label">训练集平均长度</div>
          <div class="value">{{ trainLength ? trainLength.mean : '—' }}<small>词</small></div>
        </div>
      </div>

      <div class="grid grid-2">
        <div class="panel">
          <h3>长度分布<span class="hint">训练集，按词统计</span></h3>
          <div ref="chartEl" class="chart"></div>
          <p class="small muted" style="margin: 6px 0 0">
            长度口径：{{ stats.length_unit.definition }}。
            中位数 {{ trainLength?.median }} 词，最长 {{ trainLength?.max }} 词。
          </p>
        </div>

        <div class="panel">
          <h3>类别与数据来源<span class="hint">固定随机种子 {{ stats.seed }}</span></h3>
          <table>
            <thead>
              <tr>
                <th>集合</th>
                <th>负面</th>
                <th>正面</th>
                <th>合计</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="key in ['train', 'test', 'retrieval_pool']" :key="key">
                <td>{{ { train: '训练集', test: '测试集', retrieval_pool: '检索库' }[key] }}</td>
                <td>{{ labelCounts[key]?.negative ?? 0 }}</td>
                <td>{{ labelCounts[key]?.positive ?? 0 }}</td>
                <td>{{ (labelCounts[key]?.negative ?? 0) + (labelCounts[key]?.positive ?? 0) }}</td>
              </tr>
            </tbody>
          </table>
          <dl class="kv" style="margin-top: 12px">
            <dt>数据来源</dt>
            <dd class="mono">{{ stats.dataset.id }}</dd>
            <dt>抽样规则</dt>
            <dd class="small">{{ stats.sampling_rule }}</dd>
            <dt>检索库来源</dt>
            <dd class="small">{{ stats.retrieval_pool_rule }}</dd>
          </dl>
        </div>
      </div>
    </template>

    <div class="panel">
      <h3>浏览与筛选<span class="hint">共 {{ list.total }} 条符合条件</span></h3>

      <div class="toolbar" style="margin-bottom: 14px">
        <select v-model="filters.split" style="width: 130px" @change="applyFilters">
          <option value="all">全部集合</option>
          <option value="train">训练集</option>
          <option value="test">测试集</option>
        </select>
        <select v-model="filters.label" style="width: 130px" @change="applyFilters">
          <option value="all">全部情感</option>
          <option value="0">负面</option>
          <option value="1">正面</option>
        </select>
        <input
          v-model="filters.keyword"
          type="text"
          class="grow"
          placeholder="按关键词搜索影评原文（英文）"
          @keyup.enter="applyFilters"
        />
        <button @click="applyFilters">筛选</button>
      </div>

      <div v-if="listError" class="alert error">{{ listError }}</div>
      <div v-if="listLoading" class="empty"><span class="spinner dark"></span>正在读取影评……</div>

      <table v-else-if="list.items.length">
        <thead>
          <tr>
            <th style="width: 130px">样本 ID</th>
            <th style="width: 70px">集合</th>
            <th style="width: 70px">标签</th>
            <th style="width: 70px">词数</th>
            <th>影评原文</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in list.items" :key="item.sample_id">
            <td class="mono">{{ item.sample_id }}</td>
            <td>{{ item.split === 'train' ? '训练' : '测试' }}</td>
            <td>
              <span class="badge" :class="item.label === 1 ? 'pos' : 'neg'">
                {{ item.label_cn }}
              </span>
            </td>
            <td>{{ item.word_len }}</td>
            <td>
              <div class="review-text" :class="{ expanded: expanded.has(item.sample_id) }">
                {{ item.text }}
              </div>
              <button class="link-button" @click="toggleExpand(item.sample_id)">
                {{ expanded.has(item.sample_id) ? '收起' : '展开全文' }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>

      <div v-else-if="!listLoading" class="empty">没有符合条件的影评，试试换个筛选条件。</div>

      <div class="pager">
        <span>第 {{ list.page }} / {{ list.pages }} 页</span>
        <button :disabled="page <= 1" @click="goPage(page - 1)">上一页</button>
        <button :disabled="page >= list.pages" @click="goPage(page + 1)">下一页</button>
      </div>
    </div>
  </div>
</template>
