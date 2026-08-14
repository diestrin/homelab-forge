import type { Config } from "tailwindcss";

export default {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        forge: {
          void: "var(--forge-void)",
          slate: "var(--forge-slate)",
          steel: "var(--forge-steel)",
          ember: "var(--forge-ember)",
          copper: "var(--forge-copper)",
          spark: "var(--forge-spark)",
          ash: "var(--forge-ash)",
          smoke: "var(--forge-smoke)",
        },
      },
      fontFamily: {
        display: ["var(--font-instrument-serif)", "Georgia", "serif"],
        sans: ["var(--font-dm-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-jetbrains-mono)", "ui-monospace", "monospace"],
      },
      animation: {
        "fade-up": "fade-up 0.6s ease-out forwards",
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
} satisfies Config;
