<script setup>
import { computed, onMounted, ref } from 'vue'
import { api, formatScore } from '../api'

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
          class="stat"
          style="cursor: pointer"
          :style="selectedId === pair.id ? 'border-color:#4f46e5;background:#f8f9ff' : ''"
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
              · 分数变化 {{ item.delta_score > 0 ? '+' : '' }}{{ formatScore(item.delta_score) }}
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
