<script setup>
// 数字滚动：从 0 跑到目标值，带缓出。
// 只做一件小事，但让「1200 条」「0.81」这类关键数字有落地的感觉。
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  value: { type: Number, default: 0 },
  decimals: { type: Number, default: 0 },
  duration: { type: Number, default: 900 },
})

const display = ref(0)
let frame = null

const reduceMotion =
  typeof window.matchMedia === 'function' &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches

function run(from, to) {
  if (reduceMotion || from === to) {
    display.value = to
    return
  }
  cancelAnimationFrame(frame)
  const started = performance.now()
  const step = (now) => {
    const progress = Math.min(1, (now - started) / props.duration)
    const eased = 1 - Math.pow(1 - progress, 3)
    display.value = from + (to - from) * eased
    if (progress < 1) frame = requestAnimationFrame(step)
  }
  frame = requestAnimationFrame(step)
}

onMounted(() => run(0, props.value ?? 0))
watch(
  () => props.value,
  (next, previous) => run(previous ?? 0, next ?? 0)
)
onBeforeUnmount(() => cancelAnimationFrame(frame))
</script>

<template>
  <span class="countup">{{ display.toFixed(decimals) }}</span>
</template>
