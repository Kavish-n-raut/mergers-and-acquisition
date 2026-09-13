import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
  },
  build: {
    chunkSizeWarningLimit: 700,
    rollupOptions: {
      output: {
        // Split large third-party libraries into their own long-cached chunks
        // so they aren't bundled into (or duplicated across) page chunks.
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined;
          if (id.includes("maplibre-gl")) return "maplibre";
          if (id.includes("leaflet")) return "leaflet";
          if (id.includes("recharts") || id.includes("d3-") || id.includes("victory-vendor")) return "recharts";
          if (id.includes("react-router") || id.includes("@remix-run")) return "router";
          if (id.includes("/react/") || id.includes("/react-dom/") || id.includes("/scheduler/")) return "react";
          return "vendor";
        },
      },
    },
  },
});
