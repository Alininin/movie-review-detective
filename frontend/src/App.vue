<script setup>
import { onMounted, ref } from 'vue'
import { api } from './api'

// 后端就绪状态：用于在页面上明确提示「模型未就绪」
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
  { to: '/analyze', title: '情感分析', sub: '双模型 · CSV 批量' },
  { to: '/search', title: '相似影评搜索', sub: 'MiniLM 向量 · Top-5' },
  { to: '/challenge', title: '模型挑战', sub: '否定 · 转折 · 改写' },
  { to: '/lab', title: '实验与历史', sub: '指标 · 案例 · 历史' },
]
</script>

<template>
  <div class="layout">
    <aside class="sidebar">
      <div class="brand">
        <h1>影评侦探</h1>
        <p>基于 Hugging Face 的情感分析与相似影评检索</p>
      </div>
      <RouterLink
        v-for="item in navItems"
        :key="item.to"
        :to="item.to"
        class="nav-item"
        active-class="active"
      >
        {{ item.title }}
        <span class="sub">{{ item.sub }}</span>
      </RouterLink>

      <div class="sidebar-foot">
        <div v-if="health && health.ready">模型已就绪</div>
        <div v-else-if="health">部分组件未就绪，详见各页面提示</div>
        <div v-else-if="healthError">后端未连接</div>
        <div>CPU 推理 · 仅本地运行</div>
      </div>
    </aside>

    <main class="main">
      <RouterView />
    </main>
  </div>
</template>
