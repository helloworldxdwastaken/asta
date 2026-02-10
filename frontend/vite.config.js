import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";
export default defineConfig({
    plugins: [react()],
    resolve: {
        alias: { "@": path.resolve(__dirname, "./src") },
    },
    server: {
        port: 5173,
        proxy: {
            "/api": {
                // Default backend port 8010 (configurable via VITE_API_URL)
                target: process.env.VITE_API_URL || "http://localhost:8010",
                changeOrigin: true,
            },
        },
    },
});
