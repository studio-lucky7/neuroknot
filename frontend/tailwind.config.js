/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{js,jsx,ts,tsx}'],
  presets: [require('nativewind/preset')],
  theme: {
    extend: {
      colors: {
        // NeuroKnots 브랜드 팔레트
        brand: {
          gold: '#FFB800',
          cream: '#FDF4E7',
          border: '#F0E5D8',
          ink: '#3D2B1F',
          muted: '#8C7B6E',
          faint: '#C2B7A8',
        },
      },
    },
  },
  plugins: [],
};
