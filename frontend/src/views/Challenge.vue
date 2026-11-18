<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api, formatScore } from '../api'
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

// 词级差异：纯文本对齐，用来指出「改动到底发生在哪个词上」
const diff = computed(() => {
  if (!result.value) return null
  const raw = diffWords(result.value.original, result.value.rewritten)
  return {
    left: renderDiffHtml(raw.left),
    right: renderDiffHtml(raw.right),
    changed:
      raw.left.some((part) => part.kind === 'del') ||
      raw.right.some((part) => part.kind === 'add'),
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

onMounted(async () => {
  await loadPresets()
  // 支持可分享链接：#/challenge?pair=N1 直接载入某一对预置样本并比较
  const shared = route.query.pair
  if (typeof shared === 'string') {
    const pair = pairs.value.find((item) => item.id.toLowerCase() === shared.toLowerCase())
    if (pair) {
      selectPair(pair)
      await compare()
    }
  }
})

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
    error.value = '原句与改写句都不能为空。'
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

onMounted(loadPresets)
</script>

<template>
  <div>
    <div class="page-head">
      <h2>模型挑战</h2>
      <p>
        6 对英文句子，覆盖否定、转折与保持含义的改写三类。看两个模型在「情感应当翻转」和
        「只是换说法」两种情形下是否给出了合理的预测。
      </p>
    </div>

    <div v-if="presetsError" class="alert error">{{ presetsError }}</div>

    <div class="panel">
      <h3>预置样本<span class="hint">点击载入到下方输入框</span></h3>
      <div class="grid grid-2">
        <div
          v-for="pair in pairs"
          :key="pair.id"
          class="stat preset-card"
          :class="{ selected: selectedId === pair.id }"
          @click="selectPair(pair)"
        >
          <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px">
            <span class="badge info">{{ pair.id }}</span>
            <span class="badge neutral">{{ categoryLabel(pair.category) }}</span>
            <span class="badge" :class="pair.expected_change === 'flip' ? 'warn' : 'neutral'">
              {{ pair.expected_change === 'flip' ? '应翻转' : '应保持' }}
            </span>
          </div>
          <div class="small" style="margin-bottom: 3px">原句：{{ pair.original }}</div>
          <div class="small muted">改写：{{ pair.rewritten }}</div>
        </div>
      </div>
    </div>

    <div class="panel">
      <h3>句子对比较<span class="hint">也可以现场输入新的句子对</span></h3>

      <div class="grid grid-2">
        <div>
          <label class="small muted">原句（英文）</label>
          <textarea v-model="original" rows="3" placeholder="The movie was good."></textarea>
        </div>
        <div>
          <label class="small muted">改写句（英文）</label>
          <textarea v-model="rewritten" rows="3" placeholder="The movie was not good."></textarea>
        </div>
      </div>

      <div class="toolbar" style="margin-top: 10px">
        <button class="primary" :disabled="loading" @click="compare">
          <span v-if="loading" class="spinner"></span>
          {{ loading ? '两个模型推理中…' : '比较两个模型' }}
        </button>
        <button :disabled="loading" @click="resetInputs">清空</button>
      </div>

      <div v-if="error" class="alert error" style="margin-top: 12px">{{ error }}</div>
    </div>

    <div v-if="result" class="panel">
      <h3>
        比较结果
        <span class="hint">{{ result.match_note }}</span>
      </h3>

      <div v-if="currentPreset" class="alert info">
        <strong>人工判断：</strong>
        原句「{{ currentPreset.human_label_original === 'positive' ? '正面' : '负面' }}」→
        改写句「{{ currentPreset.human_label_rewritten === 'positive' ? '正面' : '负面' }}」。
        {{ currentPreset.human_note }}（关注点：{{ currentPreset.focus }}）
      </div>

      <div v-if="diff" class="diverge-item" style="margin-bottom: 14px">
        <div class="head">
          <span class="badge info">句子差异</span>
          <span class="small muted">
            按词对齐：<span class="diff-del">红色删除线</span>是原句独有，
            <span class="diff-add">绿色</span>是改写句新增
          </span>
        </div>
        <div class="grid grid-2">
          <div>
            <div class="small muted" style="margin-bottom: 2px">原句</div>
            <p class="small" style="margin: 0; line-height: 1.9" v-html="diff.left"></p>
          </div>
          <div>
            <div class="small muted" style="margin-bottom: 2px">改写句</div>
            <p class="small" style="margin: 0; line-height: 1.9" v-html="diff.right"></p>
          </div>
        </div>
        <p v-if="!diff.changed" class="small muted" style="margin: 8px 0 0">
          两个句子在词面上完全一致，模型输出若有差异只能来自上下文编码而非词表变化。
        </p>
      </div>

      <div class="grid grid-2">
        <div v-for="(item, key) in result.comparison" :key="key" class="stat">
          <div class="label">{{ item.model }}</div>

          <table style="margin-top: 8px">
            <thead>
              <tr>
                <th>句子</th>
                <th style="width: 90px">预测</th>
                <th style="width: 90px">分类分数</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td class="small">原句</td>
                <td>
                  <span class="badge" :class="item.original.label === 1 ? 'pos' : 'neg'">
                    {{ item.original.label_cn }}
                  </span>
                </td>
                <td class="mono">{{ formatScore(item.original.score) }}</td>
              </tr>
              <tr>
                <td class="small">改写句</td>
                <td>
                  <span class="badge" :class="item.rewritten.label === 1 ? 'pos' : 'neg'">
                    {{ item.rewritten.label_cn }}
                  </span>
                </td>
                <td class="mono">{{ formatScore(item.rewritten.score) }}</td>
              </tr>
            </tbody>
          </table>

          <p class="small" style="margin: 10px 0 0">
            <span class="badge" :class="item.changed ? 'warn' : 'neutral'">
              {{ item.changed ? '预测发生翻转' : '预测保持不变' }}
            </span>
            <span class="muted">
              · 正面分数变化 {{ item.delta_score > 0 ? '+' : '' }}{{ formatScore(item.delta_score) }}
            </span>
          </p>
          <p class="small" style="margin: 4px 0 0">
            判断：<strong>{{ item.judgement }}</strong>
          </p>
        </div>
      </div>

      <p class="small muted" style="margin-top: 12px">{{ result.score_note }}</p>
    </div>
  </div>
</template>
