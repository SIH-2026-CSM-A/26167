/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        isro: {
          blue: "#0B3C5D",
          gold: "#D9B310",
          dark: "#081B2A",
        },
      },
    },
  },
  plugins: [],
};
