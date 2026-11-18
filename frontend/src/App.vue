<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from './api'

// 后端就绪状态：顶部状态灯 + 页脚说明都来自真实的 /api/health
const health = ref(null)
const healthError = ref('')

onMounted(async () => {
  try {
    health.value = await api.health()
  } catch (error) {
    // /api/health 在未就绪时返回 503，这里仍要展示细节
    healthError.value = error.message
  }
})

const navItems = [
  { to: '/library', title: '影评资料库', sub: '样本统计 · 分页筛选' },
  { to: '/analyze', title: '情感分析', sub: '双模型 · 词贡献 · CSV 批量' },
  { to: '/search', title: '相似影评搜索', sub: 'MiniLM 向量 · Top-5' },
  { to: '/challenge', title: '模型挑战', sub: '否定 · 转折 · 改写' },
  { to: '/lab', title: '实验与历史', sub: '指标 · 分歧 · 历史' },
]

const statusClass = computed(() => {
  if (health.value?.ready) return 'ok'
  if (health.value || healthError.value) return 'bad'
  return ''
})

const statusText = computed(() => {
  if (health.value?.ready) return '模型已就绪 · CPU 推理'
  if (health.value) return '部分组件未就绪'
  if (healthError.value) return '后端未连接'
  return '正在连接后端…'
})
</script>

<template>
  <div class="shell">
    <header class="masthead">
      <div class="masthead-inner">
        <div class="brand">
          <div class="title-row">
            <h1>影评侦探</h1>
            <span class="reel">REEL 01 / 2026</span>
          </div>
          <p>基于 Hugging Face 的情感分析与相似影评检索</p>
        </div>

        <nav class="nav">
          <RouterLink
            v-for="(item, index) in navItems"
            :key="item.to"
            :to="item.to"
            class="nav-item"
            active-class="active"
          >
            <span class="idx">{{ String(index + 1).padStart(2, '0') }}</span>
            {{ item.title }}
          </RouterLink>
        </nav>

        <div class="status-pill" :class="statusClass">
          <span class="dot"></span>
          {{ statusText }}
        </div>
      </div>
    </header>

    <main class="main">
      <RouterView />
    </main>

    <footer class="credits">
      <strong>影评侦探</strong> · 自然语言处理与应用课程设计 · 数据与模型来自 Hugging Face 公开资源 ·
      本地 CPU 推理 · MIT License
    </footer>
  </div>
</template>
