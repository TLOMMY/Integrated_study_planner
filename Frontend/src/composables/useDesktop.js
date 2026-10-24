import { onBeforeUnmount, ref } from 'vue'

/** 与 Tailwind 的 lg 断点一致：≥1024px 使用桌面布局（侧边栏 + 多栏）。 */
export const DESKTOP_QUERY = '(min-width: 1024px)'

const query = typeof window !== 'undefined' ? window.matchMedia(DESKTOP_QUERY) : null
const isDesktop = ref(Boolean(query?.matches))
let listeners = 0
const sync = (event) => (isDesktop.value = event.matches)

/** 需要在 JS 里区分布局时使用（如课表格子行高）；纯样式差异优先用 lg: 前缀。 */
export function useDesktop() {
  if (query && listeners++ === 0) query.addEventListener('change', sync)
  onBeforeUnmount(() => {
    if (query && --listeners === 0) query.removeEventListener('change', sync)
  })
  return isDesktop
}
