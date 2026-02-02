import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Kickstat Dark Theme
        bg: {
          DEFAULT: "#08080d",
          2: "#0e0e15",
          3: "#13131d",
          4: "#191926",
        },
        border: {
          DEFAULT: "#1a1a2a",
          2: "#272740",
        },
        text: {
          1: "#eaeaf2",
          2: "#8888a4",
          3: "#4e4e68",
          4: "#2e2e42",
        },
        green: {
          DEFAULT: "#00e87b",
          dark: "rgba(0,232,123,.12)",
          darker: "rgba(0,232,123,.06)",
        },
        red: {
          DEFAULT: "#ff4466",
          dark: "rgba(255,68,102,.1)",
        },
        amber: {
          DEFAULT: "#ffaa00",
          dark: "rgba(255,170,0,.1)",
        },
        cyan: {
          DEFAULT: "#00d4ff",
          dark: "rgba(0,212,255,.1)",
        },
        blue: {
          DEFAULT: "#4488ff",
        },
        // Legacy colors for compatibility
        primary: {
          50: "#eff6ff",
          100: "#dbeafe",
          200: "#bfdbfe",
          300: "#93c5fd",
          400: "#60a5fa",
          500: "#3b82f6",
          600: "#2563eb",
          700: "#1d4ed8",
          800: "#1e40af",
          900: "#1e3a8a",
        },
        success: "#10b981",
        warning: "#f59e0b",
        danger: "#ef4444",
      },
      fontFamily: {
        sans: ["Outfit", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      animation: {
        "fade-up": "fadeUp 0.6s ease forwards",
        pulse: "pulse 2s infinite",
        "card-in": "cardIn 0.3s ease backwards",
      },
      keyframes: {
        fadeUp: {
          from: { opacity: "0", transform: "translateY(18px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        cardIn: {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
