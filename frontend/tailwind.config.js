/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        cream: {
          DEFAULT: '#F7F0E6',
          deep: '#EDE3D4',
        },
        brown: {
          900: '#2C1A0E',
          800: '#3A2214',
          700: '#4A2C14',
          400: '#8C6246',
        },
        saffron: {
          DEFAULT: '#C94B1F',
          soft: '#F0835A',
        },
        gold: {
          DEFAULT: '#C9952B',
        },
        white: {
          DEFAULT: '#FDFAF6',
        },
        // Dark theme
        void: {
          950: '#0D0B13',
          900: '#121018',
          800: '#1C1824',
          700: '#252032',
          600: '#322A40',
        },
        warm: {
          100: '#E8DFD4',
          200: '#F0EAE0',
          300: '#F5EFE6',
        },
      },
      fontFamily: {
        display: ['Fraunces', 'Georgia', 'serif'],
        body: ['Newsreader', 'Georgia', 'serif'],
        label: ['"Spline Sans Mono"', 'monospace'],
      },
      animation: {
        'fade-in': 'fadeIn 240ms ease-out',
        'slide-up': 'slideUp 240ms ease-out',
        'slide-down': 'slideDown 180ms ease-out',
        'pulse-soft': 'pulseSoft 2s ease-in-out infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0', transform: 'translateY(6px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideDown: {
          '0%': { opacity: '1', transform: 'translateY(0)' },
          '100%': { opacity: '0', transform: 'translateY(8px)' },
        },
        pulseSoft: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.5' },
        },
      },
    },
  },
  plugins: [],
}
