/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,jsx,ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        bg:         '#1a1a1a',
        sidebar:    '#111111',
        card:       '#1e1e1e',
        border:     '#2a2a2a',
        orange:     '#e8742a',
        'orange-dark': '#c85c14',
        'text-pri': '#eeeeee',
        'text-sec': '#999999',
        'text-hint':'#555555',
        success:    '#4ade80',
        danger:     '#f87171',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      borderRadius: {
        DEFAULT: '6px',
        lg: '10px',
        xl: '14px',
      },
      animation: {
        'pulse-dot':  'pulse-dot 2s ease-in-out infinite',
        'float-up':   'float-up 0.4s ease-out forwards',
        'blink-eyes': 'blink-eyes 0.15s ease-in-out',
        'breathe':    'breathe 4s ease-in-out infinite',
      },
      keyframes: {
        'pulse-dot': {
          '0%, 100%': { opacity: 1 },
          '50%':      { opacity: 0.3 },
        },
        'float-up': {
          from: { opacity: 0, transform: 'translateY(8px)' },
          to:   { opacity: 1, transform: 'translateY(0)' },
        },
        'blink-eyes': {
          '0%, 100%': { scaleY: 1 },
          '50%':      { scaleY: 0.05 },
        },
        breathe: {
          '0%, 100%': { transform: 'scale(1)' },
          '50%':      { transform: 'scale(1.025)' },
        },
      },
    },
  },
  plugins: [],
}
