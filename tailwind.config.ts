import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#0B1220",
        card: "#111827",
        border: "#1F2937",
        foreground: "#F9FAFB",
        new: "#22C55E",
        add: "#4ADE80",
        trim: "#F59E0B",
        exit: "#EF4444",
      },
    },
  },
  plugins: [],
};

export default config;
