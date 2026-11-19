<script setup>
// 极简线性图标：统一 24×24 视框、当前色描边，不引入图标库。
import { computed } from 'vue'

const props = defineProps({
  name: { type: String, required: true },
  size: { type: [Number, String], default: 18 },
  stroke: { type: [Number, String], default: 1.6 },
})

const ICONS = {
  sun: [
    'M12 7.5a4.5 4.5 0 1 0 0 9 4.5 4.5 0 0 0 0-9Z',
    'M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M18.7 5.3l-1.4 1.4M6.7 17.3l-1.4 1.4',
  ],
  moon: ['M20.5 14.2A8.6 8.6 0 0 1 9.8 3.5a7.2 7.2 0 1 0 10.7 10.7Z'],
  film: [
    'M3.5 5.5h17v13h-17z',
    'M8 5.5v13M16 5.5v13M3.5 9.5H8M16 9.5h4.5M3.5 14.5H8M16 14.5h4.5',
  ],
  spark: [
    'M12 3v3.5M12 17.5V21M3 12h3.5M17.5 12H21M5.6 5.6l2.5 2.5M15.9 15.9l2.5 2.5M18.4 5.6l-2.5 2.5M8.1 15.9l-2.5 2.5',
  ],
  search: ['M11 4.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13Z', 'M16 16l4.5 4.5'],
  duel: ['M4 20 20 4', 'M14 4h6v6', 'M20 20 4 4', 'M10 20H4v-6'],
  chart: ['M4 19.5V4.5M4 19.5h16', 'M8 16l3.5-4.5 3 3L20 8'],
  history: ['M12 7v5l3.5 2', 'M3.5 12a8.5 8.5 0 1 0 2.6-6.1', 'M3.5 4.5V9H8'],
  arrowRight: ['M4.5 12h15', 'M13.5 6l6 6-6 6'],
  arrowLeft: ['M19.5 12h-15', 'M10.5 6l-6 6 6 6'],
  check: ['M5 12.5l4.5 4.5L19 7.5'],
  close: ['M6 6l12 12M18 6 6 18'],
  info: ['M12 4.5a7.5 7.5 0 1 0 0 15 7.5 7.5 0 0 0 0-15Z', 'M12 11v5.5M12 7.8h.01'],
  upload: ['M12 15.5V4.5', 'M8 8.5l4-4 4 4', 'M4.5 16v2.5a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2V16'],
  download: ['M12 4.5v11', 'M8 11.5l4 4 4-4', 'M4.5 16v2.5a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2V16'],
  copy: ['M9.5 9.5h8.5a1.5 1.5 0 0 1 1.5 1.5v8.5a1.5 1.5 0 0 1-1.5 1.5H9.5A1.5 1.5 0 0 1 8 19.5V11A1.5 1.5 0 0 1 9.5 9.5Z', 'M15.5 9.5V5a1.5 1.5 0 0 0-1.5-1.5H5A1.5 1.5 0 0 0 3.5 5v9A1.5 1.5 0 0 0 5 15.5h3'],
  minus: ['M5 12h14'],
  plus: ['M12 5v14M5 12h14'],
  filter: ['M4 6h16', 'M7 12h10', 'M10 18h4'],
}

const paths = computed(() => ICONS[props.name] || [])
</script>

<template>
  <svg
    class="icon"
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    :stroke-width="stroke"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path v-for="(d, index) in paths" :key="index" :d="d" />
  </svg>
</template>
