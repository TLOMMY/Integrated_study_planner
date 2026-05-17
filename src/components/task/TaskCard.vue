<script setup>
defineProps({
  task: Object,
})

const emit = defineEmits(['toggle'])
</script>

<template>
  <div class="task-card">
    <div>
      <h3>{{ task.title }}</h3>

      <p>{{ task.time }}</p>
    </div>

    <button @click="emit('toggle', task.id)">
      {{ task.finished ? '已完成' : '完成' }}
    </button>
  </div>
</template>

<style scoped>
.task-card {
  background: white;

  padding: 16px;

  border-radius: 16px;

  margin-bottom: 12px;

  display: flex;
  justify-content: space-between;
}
</style>