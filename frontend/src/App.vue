<script setup>
import { computed, onMounted, ref } from 'vue'
import Icon from './components/Icon.vue'
import { api } from './api'
import { useTheme } from './theme'

const { resolved, toggleTheme } = useTheme()

// 后端就绪状态：顶部胶囊灯 + 文案都来自真实的 /api/health
const health = ref(null)
const healthError = ref('')

onMounted(async () => {
  try {
    health.value = await api.health()
  } catch (error) {
    healthError.value = error.message
  }
})

const statusClass = computed(() => {
  if (health.value?.ready) return 'ok'
  if (health.value || healthError.value) return 'bad'
  return ''
})

const statusText = computed(() => {
  if (health.value?.ready) return '模型就绪'
  if (health.value) return '部分组件未就绪'
  if (healthError.value) return '后端未连接'
  return '连接中'
})

const navItems = [
  { to: '/library', title: '资料库', icon: 'film' },
  { to: '/analyze', title: '情感分析', icon: 'spark' },
  { to: '/search', title: '相似检索', icon: 'search' },
  { to: '/challenge', title: '模型挑战', icon: 'duel' },
  { to: '/lab', title: '实验台', icon: 'chart' },
]
</script>

<template>
  <div class="app">
    <!-- 环境光：四团缓慢漂移的色斑，是玻璃材质的“背光” -->
    <div class="ambient" aria-hidden="true">
      <span class="blob b1"></span>
      <span class="blob b2"></span>
      <span class="blob b3"></span>
      <span class="blob b4"></span>
    </div>

    <div class="topbar-wrap">
      <header class="topbar glass">
        <RouterLink to="/library" class="brand">
          <span class="brand-mark"><Icon name="film" :size="19" /></span>
          <span class="brand-text">
            <b>影评侦探</b>
            <span>Reel Detective</span>
          </span>
        </RouterLink>

        <nav class="nav">
          <RouterLink
            v-for="item in navItems"
            :key="item.to"
            :to="item.to"
            class="navlink"
            active-class="active"
          >
            <Icon :name="item.icon" :size="15" />
            {{ item.title }}
          </RouterLink>
        </nav>

        <div class="topbar-tools">
          <span class="status" :class="statusClass" :title="healthError || ''">
            <span class="dot"></span>
            {{ statusText }}
          </span>

          <button
            class="theme-switch"
            type="button"
            :aria-label="resolved === 'dark' ? '切换到白天模式' : '切换到夜间模式'"
            :title="resolved === 'dark' ? '切换到白天模式' : '切换到夜间模式'"
            @click="toggleTheme"
          >
            <span class="ghost">
              <Icon :name="resolved === 'dark' ? 'sun' : 'moon'" :size="12" />
            </span>
            <span class="knob">
              <Icon :name="resolved === 'dark' ? 'moon' : 'sun'" :size="14" />
            </span>
          </button>
        </div>
      </header>
    </div>

    <main class="page">
      <RouterView />
    </main>

    <footer class="footer">
      <span>影评侦探 · 自然语言处理与应用课程设计</span>
      <span>数据与模型来自 Hugging Face · 本地 CPU 推理 · MIT</span>
    </footer>
  </div>
</template>
