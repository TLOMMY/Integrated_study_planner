<script setup>
/**
 * 打卡火苗：火苗从火星长大并回弹 → 进度环闭合 → 天数从 from 翻到 days → 火星散开。
 * 颜色取主题变量（flame-glow → flame-deep，火芯 gold-light），换主题自动跟随；系统"减少动态效果"时直接显示最后一帧。
 * play 从 false 变 true（或 key 变化）时重播。
 */
import { computed } from 'vue'

const props = defineProps({
  days: { type: Number, default: 1 },
  from: { type: Number, default: null },
  play: { type: Boolean, default: true },
  size: { type: Number, default: 132 },
  // 外面已经写了天数时可以不显示
  showDays: { type: Boolean, default: true },
})
const previous = computed(() => (props.from ?? Math.max(0, props.days - 1)))
const uid = `sf-${Math.random().toString(36).slice(2, 8)}`
// 火星的飞散方向（相对火苗顶部，px）
const SPARKS = [[-30, -14, 3], [28, -18, 2.5], [-38, 16, 2], [36, 12, 3], [2, -34, 2]]
</script>

<template>
  <div class="streak-flame" :class="play && 'is-playing'" :style="{ '--size': `${size}px` }">
    <svg :width="size" :height="size" viewBox="0 0 132 132" aria-hidden="true">
      <defs>
        <linearGradient :id="uid" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" class="stop-glow" />
          <stop offset="1" class="stop-flame" />
        </linearGradient>
      </defs>
      <circle class="track" cx="66" cy="66" r="54" />
      <circle class="arc" cx="66" cy="66" r="54" />
      <g class="body">
        <path :fill="`url(#${uid})`" d="M66 30c4 10 18 18 18 38a18 18 0 0 1-36 0c0-8 4-14 9-18 0 7 3 11 7 12-2-12 0-22 2-32z" />
        <path class="core" d="M66 70c3 4 8 7 8 14a8 8 0 0 1-16 0c0-6 4-9 8-14z" />
      </g>
      <circle v-for="([dx, dy, r], i) in SPARKS" :key="i" class="spark" cx="66" cy="42" :r="r" :style="{ '--dx': `${dx}px`, '--dy': `${dy}px`, animationDelay: `${1 + (i % 2) * 0.08}s` }" />
    </svg>
    <p v-if="showDays" class="days num" :aria-label="`连续打卡 ${days} 天`">
      <span class="roll"><span>{{ previous }}</span><span>{{ days }}</span></span>
      <small>天</small>
    </p>
  </div>
</template>

<style scoped>
.streak-flame { display: grid; justify-items: center; gap: 6px; }
.track { fill: none; stroke: rgb(var(--c-ink-line)); stroke-width: 7; }
.arc { fill: none; stroke: rgb(var(--c-flame)); stroke-width: 7; stroke-linecap: round; stroke-dasharray: 339.3; stroke-dashoffset: 0; transform: rotate(-90deg); transform-origin: 66px 66px; }
.stop-glow { stop-color: rgb(var(--c-flame-glow)); }
.stop-flame { stop-color: rgb(var(--c-flame-deep)); }
.body { transform-box: fill-box; transform-origin: 50% 100%; }
.core { fill: rgb(var(--c-gold-light)); }
.spark { fill: rgb(var(--c-flame-glow)); opacity: 0; transform-box: fill-box; transform-origin: center; }
.days { display: flex; align-items: baseline; gap: 4px; font-size: 34px; font-weight: 900; line-height: 1.2; color: rgb(var(--c-ink)); }
.days small { font-size: 14px; font-weight: 700; color: rgb(var(--c-ink-mute)); }
/* 静止时显示新数字；播放时从旧数字翻上来 */
.roll { display: inline-block; height: 1.2em; overflow: hidden; vertical-align: bottom; }
.roll span { display: block; line-height: 1.2em; transform: translateY(-1.2em); }

.is-playing .arc { animation: sf-arc 1s cubic-bezier(.3, .7, .2, 1) both; }
.is-playing .body { animation: sf-grow .9s .15s cubic-bezier(.3, 1.6, .5, 1) both, sf-flick 1.6s 1.1s ease-in-out 2; }
.is-playing .spark { animation: sf-spark .8s ease-out both; }
.is-playing .roll span { animation: sf-roll .45s 1s cubic-bezier(.3, 1.4, .5, 1) both; }
@keyframes sf-arc { from { stroke-dashoffset: 339.3; } }
@keyframes sf-grow { 0% { transform: scale(.12); opacity: 0; } 55% { transform: scale(1.14); opacity: 1; } 78% { transform: scale(.95); } 100% { transform: scale(1); } }
@keyframes sf-flick { 50% { transform: scale(1.04, .96) skewX(-2deg); } }
@keyframes sf-spark { 0% { opacity: 0; transform: translate(0, 0) scale(.4); } 25% { opacity: 1; } 100% { opacity: 0; transform: translate(var(--dx), var(--dy)) scale(1); } }
@keyframes sf-roll { from { transform: translateY(0); } }
@media (prefers-reduced-motion: reduce) {
  .is-playing .arc, .is-playing .body, .is-playing .spark, .is-playing .roll span { animation: none; }
}
</style>
