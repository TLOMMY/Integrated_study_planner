<script setup>
/**
 * 升级徽章：六边形徽章弹出 → 光带扫过一次。实心金色、墨色数字（不用渐变），减少动态效果时直接显示。
 * 成就解锁可以用同一个外形，通过默认插槽替换中间的内容。
 */
defineProps({
  level: { type: Number, required: true },
  play: { type: Boolean, default: true },
  size: { type: Number, default: 96 },
})
const uid = `lb-${Math.random().toString(36).slice(2, 8)}`
const HEX = 'M52 4l44 25v58L52 112 8 87V29z'
</script>

<template>
  <svg class="level-badge" :class="play && 'is-playing'" :width="size" :height="size * 116 / 104" viewBox="0 0 104 116" role="img" :aria-label="`等级 ${level}`">
    <defs>
      <linearGradient :id="`${uid}-g`" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" class="stop-a" />
        <stop offset="1" class="stop-b" />
      </linearGradient>
      <clipPath :id="`${uid}-c`"><path :d="HEX" /></clipPath>
    </defs>
    <g class="hex">
      <path :fill="`url(#${uid}-g)`" :d="HEX" />
      <g :clip-path="`url(#${uid}-c)`"><rect class="shine" x="30" y="-10" width="18" height="140" transform="rotate(20 52 58)" /></g>
      <slot>
        <text class="caption" x="52" y="44" text-anchor="middle">LEVEL</text>
        <text class="value" x="52" y="78" text-anchor="middle">{{ level }}</text>
      </slot>
    </g>
  </svg>
</template>

<style scoped>
.stop-a { stop-color: rgb(var(--c-gold)); }
.stop-b { stop-color: rgb(var(--c-gold)); }
.hex { transform-box: fill-box; transform-origin: center; }
.caption { font-size: 11px; font-weight: 700; fill: rgb(var(--c-ink)); opacity: .75; letter-spacing: .08em; }
.value { font-size: 30px; font-weight: 900; fill: rgb(var(--c-ink)); font-variant-numeric: tabular-nums; }
.shine { fill: rgb(var(--c-gold-light)); opacity: 0; }
.is-playing .hex { animation: lb-pop .6s cubic-bezier(.3, 1.6, .5, 1) both; }
.is-playing .shine { animation: lb-shine .9s .45s ease-in-out both; }
@keyframes lb-pop { 0% { transform: scale(.4) rotate(-12deg); opacity: 0; } 100% { transform: scale(1) rotate(0); } }
@keyframes lb-shine { 0% { opacity: .55; transform: translateX(-90px); } 100% { opacity: 0; transform: translateX(90px); } }
@media (prefers-reduced-motion: reduce) {
  .is-playing .hex, .is-playing .shine { animation: none; }
}
</style>
