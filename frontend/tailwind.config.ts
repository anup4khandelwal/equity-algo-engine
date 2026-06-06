import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0b0e14",
        panel: "#141a24",
        border: "#222b39",
        muted: "#8a97a8",
        accent: "#3b82f6",
        up: "#22c55e",
        down: "#ef4444",
      },
    },
  },
  plugins: [],
};

export default config;
