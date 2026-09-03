/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        stone: {
          bg: "#EDEAE3",
          card: "#F5F3EE",
          line: "#D9D4C7",
        },
        ink: {
          DEFAULT: "#1C2541",
          soft: "#4A5270",
        },
        brass: {
          DEFAULT: "#B08D57",
          dark: "#8E7043",
          soft: "#E4D9C3",
        },
        sage: "#6B8F71",
        rust: "#B1502F",
      },
      fontFamily: {
        serif: ["'Source Serif 4'", "Georgia", "serif"],
        sans: ["'Inter'", "system-ui", "sans-serif"],
      },
      maxWidth: {
        prose: "70ch",
      },
    },
  },
  plugins: [],
}

