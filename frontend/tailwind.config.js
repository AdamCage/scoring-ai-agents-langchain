/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#F2F3F7",
        ink: "#000000",
        muted: "#6E6E73",
        line: "#E4E5EA",
        yellow: "#FFCC00",
        yhover: "#F0C000",
        ok: "#11803A",
        wait: "#C45C00",
        bad: "#E31227",
      },
      borderRadius: {
        tile: "24px",
      },
      fontFamily: {
        sans: ['"Golos Text"', "YS Text", "Arial", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "monospace"],
      },
      boxShadow: {
        tile: "0 8px 24px rgba(0,0,0,0.04)",
      },
    },
  },
  plugins: [],
};
