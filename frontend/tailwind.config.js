/** tailwind.config.js */
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        court: {
          bg: '#0f172a',
          surface: '#1e293b',
          border: '#334155',
          accent: '#3b82f6',
          gold: '#f59e0b',
        },
      },
    },
  },
  plugins: [],
}
