import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        /* Ink & Silver with semantic accents. */
        luma: {
          charcoal: "rgb(var(--luma-charcoal-rgb) / <alpha-value>)",
          coal: "rgb(var(--luma-coal-rgb) / <alpha-value>)",
          ivory: "rgb(var(--luma-ivory-rgb) / <alpha-value>)",
          ember: "rgb(var(--luma-ember-rgb) / <alpha-value>)",
          smoke: "rgb(var(--luma-smoke-rgb) / <alpha-value>)",
          smokeline: "rgb(var(--luma-smokeline-rgb) / <alpha-value>)",
          sage: "rgb(var(--luma-sage-rgb) / <alpha-value>)",
          coral: "rgb(var(--luma-coral-rgb) / <alpha-value>)",
          gold: "rgb(var(--luma-gold-rgb) / <alpha-value>)",
          transfer: "rgb(var(--luma-transfer-rgb) / <alpha-value>)",
        },
        obsidian: {
          bg: "rgb(var(--obsidian-bg-rgb) / <alpha-value>)",
          panel: "rgb(var(--obsidian-panel-rgb) / <alpha-value>)",
          card: "rgb(var(--obsidian-card-rgb) / <alpha-value>)",
          hover: "rgb(var(--obsidian-hover-rgb) / <alpha-value>)",
          border: "rgb(var(--obsidian-border-rgb) / <alpha-value>)",
          borderStrong: "rgb(var(--obsidian-border-strong-rgb) / <alpha-value>)",
        },
        slateText: {
          primary: "rgb(var(--slate-primary-rgb) / <alpha-value>)",
          secondary: "rgb(var(--slate-secondary-rgb) / <alpha-value>)",
          muted: "rgb(var(--slate-muted-rgb) / <alpha-value>)",
        },
        amberGold: "rgb(var(--amber-gold-rgb) / <alpha-value>)",
        mintRise: "rgb(var(--mint-rise-rgb) / <alpha-value>)",
        coralFall: "rgb(var(--coral-fall-rgb) / <alpha-value>)",
        cyanHub: "rgb(var(--cyan-hub-rgb) / <alpha-value>)",
        purpleLock: "rgb(var(--purple-lock-rgb) / <alpha-value>)",
      },
      fontFamily: {
        sans: [
          "var(--font-geist-sans)",
          "Inter",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
        mono: ["var(--font-geist-mono)", "ui-monospace", "monospace"],
      },
      borderWidth: {
        hairline: "1px",
      },
      borderRadius: {
        xl: "var(--ai7-radius-control)",
        "2xl": "var(--ai7-radius-panel)",
        "3xl": "var(--ai7-radius-panel)",
        badge: "var(--ai7-radius-badge)",
        luma: "var(--ai7-radius-panel)",
        "luma-lg": "28px",
      },
      boxShadow: {
        "luma-glass": "0 8px 32px rgba(0, 0, 0, 0.35)",
        "luma-ember": "0 0 60px rgba(240, 138, 75, 0.22)",
      },
      keyframes: {
        fadeIn: {
          from: { opacity: "0", transform: "translateY(4px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        fadeIn: "fadeIn 0.22s cubic-bezier(0.16, 1, 0.3, 1) both",
      },
      spacing: {
        "8.5": "2.125rem",
      },
    },
  },
  plugins: [],
};
export default config;
