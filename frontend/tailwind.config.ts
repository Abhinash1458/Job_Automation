import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "var(--ink)",
        panel: "var(--panel)",
        elevated: "var(--elevated)",
        border: "var(--border)",
        "border-soft": "var(--border-soft)",
        text: "var(--text)",
        muted: "var(--muted)",
        faint: "var(--faint)",
        brand: { DEFAULT: "var(--brand)", strong: "var(--brand-strong)" },
        "brand-2": "var(--brand-2)",
        weak: "var(--weak)",
        good: "var(--good)",
        fair: "var(--fair)",
        strong: "var(--strong)",
        danger: "var(--danger)",
      },
      fontFamily: {
        display: ["var(--font-display)", "system-ui", "sans-serif"],
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      borderRadius: {
        xl: "14px",
        "2xl": "20px",
      },
      boxShadow: {
        card: "0 1px 0 0 rgba(255,255,255,.03) inset, 0 8px 24px -12px rgba(0,0,0,.5)",
        lift: "0 1px 0 0 rgba(255,255,255,.05) inset, 0 16px 40px -16px rgba(0,0,0,.6)",
        glow: "0 0 0 1px rgba(124,135,255,.35), 0 8px 30px -6px rgba(124,135,255,.35)",
      },
    },
  },
  plugins: [],
};
export default config;
