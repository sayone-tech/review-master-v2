/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "../templates/**/*.html",
    "../apps/**/templates/**/*.html",
    "./src/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        "yellow":        "#FACC15",
        "yellow-hover":  "#EAB308",
        "yellow-tint":   "#FEFCE8",
        "black":         "#0A0A0A",
        "ink":           "#18181B",
        "text":          "#27272A",
        "muted":         "#52525B",
        "subtle":        "#71717A",
        "faint":         "#A1A1AA",
        "line":          "#E4E4E7",
        "line-soft":     "#F4F4F5",
        "bg":            "#FAFAFA",
        "green":         "#16A34A",
        "green-tint":    "#DCFCE7",
        "red":           "#DC2626",
        "red-tint":      "#FEE2E2",
        "amber":         "#D97706",
        "amber-tint":    "#FEF3C7",
        "blue":          "#2563EB",
        "blue-tint":     "#DBEAFE",
      },
      fontFamily: {
        sans: ["Geist", "-apple-system", "BlinkMacSystemFont", "'Segoe UI'", "system-ui", "sans-serif"],
        mono: ["'Geist Mono'", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      spacing: {
        "sidebar":      "240px",
        "sidebar-rail": "64px",
      },
      borderRadius: {
        "sm":           "6px",
        "md":           "8px",
        "menu":         "10px",
        "card":         "12px",
        "modal":        "14px",
        "logo":         "7px",
        "confirm-icon": "12px",
      },
    },
  },
  plugins: [],
};
