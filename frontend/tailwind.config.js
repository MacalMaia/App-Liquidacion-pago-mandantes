/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          orange: {
            DEFAULT: "#FF6600",
            50:  "#FFEFE5",
            100: "#FFD1B2",
            200: "#FFB27F",
            300: "#FF944D",
            400: "#FF761A",
            500: "#FF6600",
            600: "#CC5200",
            700: "#993D00",
          },
          purple: {
            DEFAULT: "#554FF1",
            50:  "#EEEDFE",
            100: "#CCCAFB",
            200: "#AAA7F8",
            300: "#8884F5",
            400: "#6661F2",
            500: "#554FF1",
            600: "#3730C1",
            700: "#2A2491",
          },
          gray: {
            50:  "#E6E6E6",
            100: "#B3B3B3",
            200: "#828282",
            300: "#666666",
            400: "#333333",
            500: "#1A1A1A",
          },
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
