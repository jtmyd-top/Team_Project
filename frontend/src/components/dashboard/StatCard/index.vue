<template>
  <div
    class="db-card stat-card"
    :class="{ 'stat-card--clickable': href }"
    @click="handleClick"
  >
    <div class="stat-card__icon" :class="`stat-card__icon--${color}`">
      <i :class="icon"></i>
    </div>
    <div class="stat-card__info">
      <div class="stat-card__value" ref="valueRef">{{ displayValue }}</div>
      <div class="stat-card__label">{{ label }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { CountUp } from 'countup.js'

const props = defineProps({
  value: { type: Number, default: 0 },
  label: { type: String, default: '' },
  icon: { type: String, default: 'fas fa-chart-bar' },
  color: { type: String, default: 'cyan' },
  suffix: { type: String, default: '' },
  decimals: { type: Number, default: 0 },
  href: { type: String, default: '' },
})

const valueRef = ref(null)
const displayValue = ref(props.value)
let countUp = null

function handleClick() {
  if (props.href) {
    window.open(props.href, '_blank')
  }
}

onMounted(() => {
  if (valueRef.value) {
    countUp = new CountUp(valueRef.value, props.value, {
      duration: 1.5,
      suffix: props.suffix,
      decimalPlaces: props.decimals,
    })
    if (!countUp.error) countUp.start()
  }
})

watch(() => props.value, (newVal) => {
  if (countUp && !countUp.error) {
    countUp.update(newVal)
  } else {
    displayValue.value = newVal
  }
})
</script>
