/**
 * 颜色全部来自 CSS 变量（取值见 src/themes/index.js，运行时由 useTheme 写入 <style id="theme-vars">），
 * 变量存的是 "R G B" 三个通道，所以 bg-primary/40 这类透明度写法照常可用。
 */
const v = (name) => `rgb(var(--c-${name}) / <alpha-value>)`

/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js}'],
  theme: {
    extend: {
      colors: {
        primary: { DEFAULT: v('primary'), dark: v('primary-dark'), light: v('primary-light'), soft: v('primary-soft') },
        background: v('background'),
        surface: v('surface'),
        ink: { DEFAULT: v('ink'), soft: v('ink-soft'), mute: v('ink-mute'), line: v('ink-line') },
        flame: { DEFAULT: v('flame'), light: v('flame-light'), glow: v('flame-glow') },
        xp: { DEFAULT: v('xp'), light: v('xp-light') },
        success: { DEFAULT: v('success'), light: v('success-light') },
        danger: { DEFAULT: v('danger'), light: v('danger-light'), soft: v('danger-soft') },
        // 反色块（Toast 等）：bg-inverse text-inverse-ink；深色主题下不会变成"白底白字"
        inverse: { DEFAULT: v('inverse'), ink: v('inverse-ink'), accent: v('inverse-accent') },
        // 弹窗遮罩：bg-scrim/45
        scrim: v('scrim'),
        // 渐变中间色：from-primary via-hero to-xp
        hero: v('hero'),
        // 专注页沉浸背景：from-deep-from via-deep-via to-deep-to；白色按钮上的文字 text-deep-ink
        deep: { from: v('deep-from'), via: v('deep-via'), to: v('deep-to'), ink: v('deep-ink') },
        // 分类配色：bg-chart-1 … bg-chart-7
        chart: Object.fromEntries([1, 2, 3, 4, 5, 6, 7].map((i) => [i, v(`chart-${i}`)])),
        // 色块上的文字：bg-primary 上用 text-on-primary，bg-success 上用 text-on-success……（不要写 text-white）
        on: { primary: v('on-primary'), success: v('on-success'), flame: v('on-flame'), danger: v('on-danger'), xp: v('on-xp') },
      },
      // 内容层：玻璃主题下 bg-surface 按文档的"内容层标准材质"半透明（--surface-alpha），普通主题为 1，与原来一致
      backgroundColor: {
        surface: 'rgb(var(--c-surface) / calc(<alpha-value> * var(--surface-alpha, 1)))',
      },
      // 语义色当文字用：强调色在浅色内容层上对比度不够时，主题可以单独压深"文字版"（--c-*-text）
      textColor: {
        primary: { DEFAULT: v('primary-text'), dark: v('primary-dark'), light: v('primary-light'), soft: v('primary-soft') },
        success: { DEFAULT: v('success-text'), light: v('success-light') },
        flame: { DEFAULT: v('flame-text'), light: v('flame-light') },
        danger: { DEFAULT: v('danger-text'), light: v('danger-light'), soft: v('danger-soft') },
      },
      fontFamily: {
        sans: ['"PingFang SC"', '"HarmonyOS Sans SC"', '"Microsoft YaHei"', 'system-ui', 'sans-serif'],
        num: ['"DIN Alternate"', '"SF Pro Rounded"', 'ui-rounded', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        soft: 'var(--shadow-soft)',
        lift: 'var(--shadow-lift)',
        // 玻璃主题下的导航层玻璃（普通主题不会用到）
        glass: 'var(--glass-shadow)',
      },
      keyframes: {
        pop: { '0%': { transform: 'scale(.6)', opacity: 0 }, '70%': { transform: 'scale(1.08)' }, '100%': { transform: 'scale(1)', opacity: 1 } },
        rise: { '0%': { transform: 'translateY(12px)', opacity: 0 }, '100%': { transform: 'translateY(0)', opacity: 1 } },
        flicker: { '0%,100%': { transform: 'scale(1) rotate(-2deg)' }, '50%': { transform: 'scale(1.12) rotate(3deg)' } },
        check: { '0%': { transform: 'scale(.4)' }, '60%': { transform: 'scale(1.25)' }, '100%': { transform: 'scale(1)' } },
        confetti: { '0%': { transform: 'translateY(-10%) rotate(0)', opacity: 1 }, '100%': { transform: 'translateY(520px) rotate(540deg)', opacity: 0 } },
        shimmer: { '0%': { backgroundPosition: '-200% 0' }, '100%': { backgroundPosition: '200% 0' } },
      },
      animation: {
        pop: 'pop .45s cubic-bezier(.2,.9,.3,1.3) both',
        rise: 'rise .35s ease-out both',
        flicker: 'flicker 1.6s ease-in-out infinite',
        check: 'check .35s ease-out both',
        confetti: 'confetti 2.4s ease-in forwards',
        shimmer: 'shimmer 1.4s linear infinite',
      },
    },
  },
  plugins: [],
}
