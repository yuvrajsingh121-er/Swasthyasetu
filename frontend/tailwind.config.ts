import type { Config } from "tailwindcss";
const config: Config = { content: ["./app/**/*.{js,ts,jsx,tsx}"], theme: { extend: { colors: { forest: "#146a5a", ink: "#193c3a", cream: "#fbf7ef" } } }, plugins: [] };
export default config;
