<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api, formatScore } from '../api'
import Icon from '../components/Icon.vue'
import { diffWords, renderDiffHtml } from '../text'

const route = useRoute()

const pairs = ref([])
const categories = ref([])
const presetsError = ref('')

const original = ref('')
const rewritten = ref('')
const loading = ref(false)
const error = ref('')
const result = ref(null)
const selectedId = ref(null)

const categoryLabel = (key) => categories.value.find((item) => item.key === key)?.label || key
const currentPreset = computed(() => pairs.value.find((pair) => pair.id === selectedId.value) || null)

// 词级差异：纯文本对齐，只是指出「改动发生在哪个词上」
const diff = computed(() => {
  if (!result.value) return null
  const raw = diffWords(result.value.original, result.value.rewritten)
  return {
    left: renderDiffHtml(raw.left),
    right: renderDiffHtml(raw.right),
    changed:
      raw.left.some((part) => part.kind === 'del') || raw.right.some((part) => part.kind === 'add'),
  }
})

async function loadPresets() {
  try {
    const payload = await api.challengePresets()
    pairs.value = payload.pairs || []
    categories.value = payload.categories || []
  } catch (e) {
    presetsError.value = e.message
  }
}

function selectPair(pair) {
  selectedId.value = pair.id
  original.value = pair.original
  rewritten.value = pair.rewritten
  result.value = null
  error.value = ''
}

function resetInputs() {
  selectedId.value = null
  original.value = ''
  rewritten.value = ''
  result.value = null
  error.value = ''
}

async function compare() {
  if (loading.value) return
  error.value = ''
  result.value = null

  if (!original.value.trim() || !rewritten.value.trim()) {
    error.value = '原句与改写句都要填。'
    return
  }

  loading.value = true
  try {
    result.value = await api.challenge(original.value, rewritten.value)
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadPresets()
  const shared = route.query.pair
  if (typeof shared === 'string') {
    const pair = pairs.value.find((item) => item.id.toLowerCase() === shared.toLowerCase())
    if (pair) {
      selectPair(pair)
      await compare()
    }
  }
})
</script>

<template>
  <div>
    <header class="hero">
      <div>
        <div class="kicker">04 · 模型挑战</div>
        <h1 class="title">改一个词，看模型会不会被骗</h1>
        <p class="lede">否定、转折、同义改写各两对。前四对情感应当翻转，后两对只是换个说法。</p>
      </div>
      <div class="hero-side">
        <button v-if="selectedId" class="btn" @click="resetInputs">
          <Icon name="close" :size="14" />清空
        </button>
      </div>
    </header>

    <div v-if="presetsError" class="alert error">{{ presetsError }}</div>

    <section class="card glass">
      <div class="card-head">
        <h2 class="card-title">选一对</h2>
        <span class="hint">点一下载入</span>
      </div>
      <div class="term-cloud">
        <button
          v-for="pair in pairs"
          :key="pair.id"
          class="chip"
          :class="{ on: selectedId === pair.id }"
          @click="selectPair(pair)"
        >
          <span class="mono">{{ pair.id }}</span>
          {{ categoryLabel(pair.category) }}
          <span class="muted">·</span>
          {{ pair.expected_change === 'flip' ? '应翻转' : '应保持' }}
        </button>
      </div>
    </section>

    <section class="card glass">
      <div class="card-head">
        <h2 class="card-title">句子对</h2>
        <span class="hint">也可以自己写</span>
      </div>

      <div class="pair-grid">
        <div>
          <label class="hint">原句</label>
          <textarea v-model="original" class="field" rows="3" placeholder="The movie was good."></textarea>
        </div>
        <div>
          <label class="hint">改写句</label>
          <textarea v-model="rewritten" class="field" rows="3" placeholder="The movie was not good."></textarea>
        </div>
      </div>

      <div class="row" style="margin-top: 14px">
        <button class="btn btn-primary" :disabled="loading" @click="compare">
          <Icon name="duel" :size="15" />
          {{ loading ? '推理中…' : '比较两个模型' }}
        </button>
      </div>

      <div v-if="error" class="alert error" style="margin-top: 14px">{{ error }}</div>
    </section>

    <template v-if="result">
      <section class="card glass">
        <div class="card-head">
          <h2 class="card-title">差异</h2>
          <span class="hint">按词对齐</span>
          <span class="spacer"></span>
          <span class="small muted">
            <span class="diff-del">删除线</span> = 原句独有 ·
            <span class="diff-add">高亮</span> = 改写新增
          </span>
        </div>

        <div v-if="diff" class="pair-grid">
          <div class="model-card">
            <div class="hint" style="margin-bottom: 6px">原句</div>
            <p class="small" style="margin: 0; line-height: 1.9" v-html="diff.left"></p>
          </div>
          <div class="model-card">
            <div class="hint" style="margin-bottom: 6px">改写句</div>
            <p class="small" style="margin: 0; line-height: 1.9" v-html="diff.right"></p>
          </div>
        </div>
      </section>

      <section class="card glass">
        <div class="card-head">
          <h2 class="card-title">预测变化</h2>
          <span class="spacer"></span>
          <span class="hint">{{ result.match_note }}</span>
        </div>

        <div v-if="currentPreset" class="row" style="margin-bottom: 14px">
          <span class="tag accent">人工判断</span>
          <span class="small muted">
            原句 {{ currentPreset.human_label_original === 'positive' ? '正面' : '负面' }} →
            改写 {{ currentPreset.human_label_rewritten === 'positive' ? '正面' : '负面' }} ·
            {{ currentPreset.focus }}
          </span>
        </div>

        <div class="model-grid">
          <div v-for="(item, key) in result.comparison" :key="key" class="model-card">
            <div class="row" style="justify-content: space-between">
              <span class="model-name">{{ item.model }}</span>
              <span class="tag" :class="item.changed ? 'accent' : 'neutral'">
                {{ item.changed ? '翻转' : '保持' }}
              </span>
            </div>

            <div class="row" style="margin-top: 12px; gap: 8px">
              <span class="tag" :class="item.original.label === 1 ? 'pos' : 'neg'">
                {{ item.original.label_cn }}
              </span>
              <Icon name="arrowRight" :size="14" />
              <span class="tag" :class="item.rewritten.label === 1 ? 'pos' : 'neg'">
                {{ item.rewritten.label_cn }}
              </span>
              <span class="mono muted" style="margin-left: auto">
                {{ formatScore(item.original.score) }} → {{ formatScore(item.rewritten.score) }}
              </span>
            </div>

            <div class="kvline" style="margin-top: 10px">
              <span>正面分数变化 {{ item.delta_score > 0 ? '+' : '' }}{{ formatScore(item.delta_score) }}</span>
            </div>
            <div class="small" style="margin-top: 6px; color: var(--text-soft)">{{ item.judgement }}</div>
          </div>
        </div>

        <details class="note-box">
          <summary>怎么判断「合理」</summary>
          <div class="note-body">{{ result.score_note }}</div>
        </details>
      </section>
    </template>
  </div>
</template>
