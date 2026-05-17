<template>
  <span class="typing-cursor" />
</template>

<style scoped>
.typing-cursor {
  display: inline-block;
  width: 2px;
  height: 1em;
  background: #3b82f6;
  margin-left: 2px;
  animation: blink 1s infinite;
  vertical-align: middle;
}

@keyframes blink {
  0%,
  50% {
    opacity: 1;
  }

  51%,
  100% {
    opacity: 0;
  }
}
</style>