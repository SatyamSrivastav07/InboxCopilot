/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#172033',
        canvas: '#f5f7fb',
      },
      boxShadow: {
        card: '0 1px 2px rgba(15, 23, 42, 0.05), 0 12px 30px rgba(15, 23, 42, 0.05)',
      },
    },
  },
  plugins: [],
}

