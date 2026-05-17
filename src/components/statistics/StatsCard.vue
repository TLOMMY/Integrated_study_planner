<template>
  <div
    :class="[
      color === 'blue'
        ? 'bg-blue-50/50 border-blue-50'
        : 'bg-indigo-50/50 border-indigo-50',
      'rounded-2xl p-4 border',
    ]"
  >
    <p
      :class="[
        color === 'blue' ? 'text-blue-400' : 'text-indigo-400',
        'text-[10px] font-bold uppercase mb-1',
      ]"
    >
      {{ title }}
    </p>

    <div class="flex items-baseline gap-1">
      <span
        :class="[
          color === 'blue' ? 'text-blue-900' : 'text-indigo-900',
          'text-2xl font-bold',
        ]"
      >
        {{ value }}
      </span>

      <span
        :class="[
          color === 'blue'
            ? 'text-blue-900/50'
            : 'text-indigo-900/50',
          'text-xs font-bold italic',
        ]"
      >
        {{ unit }}
      </span>
    </div>

    <template v-if="trend">
      <p
        class="text-[10px] text-green-500 font-bold mt-2 flex items-center gap-1"
      >
        <Icon :icon="icon" width="12" />
        {{ trend }}
      </p>
    </template>

    <template v-else>
      <div class="flex gap-1 mt-2">
        <span class="w-3 h-1 bg-indigo-200 rounded-full"></span>
        <span class="w-3 h-1 bg-indigo-200 rounded-full"></span>
        <span
          class="w-3 h-1 bg-indigo-600 rounded-full animate-pulse"
        ></span>
      </div>
    </template>
  </div>
</template>

<script setup>
import { Icon } from '@iconify/vue'

defineProps({
  title: String,
  value: String,
  unit: String,
  color: String,
  trend: String,
  icon: String,
})
</script>