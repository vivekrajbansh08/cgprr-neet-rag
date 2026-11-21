import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, type Plugin } from "vite";
import { writeEvidence } from "./scripts/gen-evidence.mjs";

// /evidence.json is regenerated from data/raw/MANIFEST.md, eval/results/score_table.md and
// evidence/blind_summary.txt on every request in dev. `npm run build` runs the same script once and
// Vite copies public/evidence.json into dist, where nginx serves it as a static file.
function evidence(): Plugin {
  return {
    name: "neet-evidence",
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        if ((req.url ?? "").split("?")[0] !== "/evidence.json") return next();
        if (req.method !== "GET" && req.method !== "HEAD") {
          res.statusCode = 405;
          return res.end();
        }
        try {
          const body = writeEvidence();
          res.setHeader("Content-Type", "application/json; charset=utf-8");
          res.setHeader("Cache-Control", "no-store");
          res.end(body);
        } catch (e) {
          res.statusCode = 500;
          res.end(e instanceof Error ? e.message : "evidence build failed");
        }
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), tailwindcss(), evidence()],
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: {
      "/api/answer": {
        target: "http://127.0.0.1:8002",
        rewrite: (p) => p.replace(/^\/api\/answer/, ""),
      },
      "/api/predictor": {
        target: "http://127.0.0.1:8003",
        rewrite: (p) => p.replace(/^\/api\/predictor/, ""),
      },
    },
  },
  preview: { host: "127.0.0.1" },
});
