/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        cx: {
          void: '#f4f6f9',
          deep: '#eef1f6',
          surface: '#e8ecf2',
          panel: 'rgba(255,255,255,0.72)',
          raised: '#ffffff',
          line: 'rgba(100,116,139,0.12)',
          border: 'rgba(100,116,139,0.15)',
          borderStrong: 'rgba(100,116,139,0.28)',
          fg: '#1a2332',
          fgMuted: '#475569',
          fgDim: '#64748b',
          accent: '#0891b2',
          accent2: '#7c6bc4',
          success: '#059669',
          warn: '#d97706',
          danger: '#dc2626',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        display: ['Outfit', 'Inter', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      fontSize: {
        '2xs': ['0.625rem', { lineHeight: '0.875rem', letterSpacing: '0.2em' }],
      },
      boxShadow: {
        glass: '0 1px 2px rgba(15,23,42,0.04), 0 8px 32px rgba(15,23,42,0.06), inset 0 1px 0 rgba(255,255,255,0.9)',
        dock: '-8px 0 24px rgba(15,23,42,0.06)',
        'inner-soft': 'inset 0 2px 4px rgba(15,23,42,0.04)',
      },
      backdropBlur: {
        xs: '2px',
      },
    },
  },
  plugins: [],
}
