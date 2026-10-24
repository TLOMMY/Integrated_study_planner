/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js}'],
  theme: {
    extend: {
      colors: {
        primary: { DEFAULT: '#4F6EF7', dark: '#3B57E0', light: '#EEF1FE', soft: '#C7D2FE' },
        background: '#F5F7FB',
        surface: '#FFFFFF',
        ink: { DEFAULT: '#0F172A', soft: '#475569', mute: '#94A3B8', line: '#E2E8F0' },
        flame: { DEFAULT: '#FF8A00', light: '#FFF4E5' },
        xp: { DEFAULT: '#8B5CF6', light: '#F3EEFF' },
        success: { DEFAULT: '#10B981', light: '#ECFDF5' },
        danger: { DEFAULT: '#EF4444', light: '#FEF2F2' },
      },
      fontFamily: {
        sans: ['"PingFang SC"', '"HarmonyOS Sans SC"', '"Microsoft YaHei"', 'system-ui', 'sans-serif'],
        num: ['"DIN Alternate"', '"SF Pro Rounded"', 'ui-rounded', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        soft: '0 6px 24px -10px rgba(15, 23, 42, 0.18)',
        lift: '0 18px 40px -16px rgba(79, 110, 247, 0.45)',
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
