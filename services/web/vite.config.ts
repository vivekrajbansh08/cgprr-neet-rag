import { readFile } from "node:fs/promises";
import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, type Plugin } from "vite";

const repoRoot = path.resolve(__dirname, "../..");

// Read-only evidence files, read from the repo at request time (dev only; nginx mounts them in prod).
const EVIDENCE: Record<string, string> = {
  "/evidence/manifest.md": path.join(repoRoot, "data/raw/MANIFEST.md"),
  "/evidence/score_table.md": path.join(repoRoot, "eval/results/score_table.md"),
};

function evidence(): Plugin {
  return {
    name: "neet-evidence",
    configureServer(server) {
      server.middlewares.use(async (req, res, next) => {
        const url = (req.url ?? "").split("?")[0];
        const file = EVIDENCE[url];
        if (!file) return next();
        if (req.method !== "GET" && req.method !== "HEAD") {
          res.statusCode = 405;
          return res.end();
        }
        try {
          const body = await readFile(file, "utf8");
          res.setHeader("Content-Type", "text/markdown; charset=utf-8");
          res.setHeader("Cache-Control", "no-store");
          res.end(body);
        } catch {
          res.statusCode = 404;
          res.end("not found");
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
