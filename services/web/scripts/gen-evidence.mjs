// Builds public/evidence.json for the Evidence view from two committed files:
//   data/raw/MANIFEST.md          (source table: Document, Pages, Retrieved, sha256)
//   eval/results/score_table.md   (per-question results and per-category totals)
// plus services/web/evidence/blind_summary.txt (one optional line; empty means "show nothing").
//
// Run by `npm run build` and, per request, by the dev server (vite.config.ts). The output is
// committed so the Docker build (context services/web, no access to the repo root) can serve it;
// CI regenerates it and fails if the committed copy differs. Values are copied as text, never
// recomputed. Exits non-zero if a source file exists but its table cannot be parsed.
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = path.resolve(webRoot, "../..");
export const SOURCES = {
  manifest: path.join(repoRoot, "data/raw/MANIFEST.md"),
  scores: path.join(repoRoot, "eval/results/score_table.md"),
  blind: path.join(webRoot, "evidence/blind_summary.txt"),
};
export const OUTPUT = path.join(webRoot, "public/evidence.json");

const cells = (line) =>
  line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((c) => c.trim().replace(/^`(.*)`$/, "$1"));

/** Rows of the first Markdown table whose header starts with `firstHeader`, as objects keyed by header. */
function table(md, firstHeader, file) {
  const lines = md.split("\n");
  const start = lines.findIndex((l) => l.trim().startsWith("|") && cells(l)[0] === firstHeader);
  if (start < 0) throw new Error(`${file}: no table with header "${firstHeader}"`);
  const head = cells(lines[start]);
  const rows = [];
  for (const l of lines.slice(start + 2)) {
    if (!l.trim().startsWith("|")) break;
    const c = cells(l);
    rows.push(Object.fromEntries(head.map((h, i) => [h, c[i] ?? ""])));
  }
  if (!rows.length) throw new Error(`${file}: table "${firstHeader}" has no rows`);
  return rows;
}

function need(row, key, file) {
  const v = row[key];
  if (v === undefined || v === "") throw new Error(`${file}: missing "${key}" in a row`);
  return v;
}

export function buildEvidence() {
  const m = readFileSync(SOURCES.manifest, "utf8");
  const sources = table(m, "Local file", "MANIFEST.md").map((r) => {
    const retrieved = need(r, "Retrieved (IST)", "MANIFEST.md");
    if (!/^\d{4}-\d{2}-\d{2}/.test(retrieved)) throw new Error(`MANIFEST.md: unexpected date "${retrieved}"`);
    const sha256 = need(r, "sha256", "MANIFEST.md");
    if (!/^[0-9a-f]{64}$/.test(sha256)) throw new Error(`MANIFEST.md: unexpected sha256 "${sha256}"`);
    return {
      file: need(r, "Local file", "MANIFEST.md"),
      document: need(r, "Document", "MANIFEST.md"),
      pages: need(r, "Pages", "MANIFEST.md"),
      retrieved: retrieved.slice(0, 10),
      sha256,
    };
  });

  const s = readFileSync(SOURCES.scores, "utf8");
  const questions = table(s, "id", "score_table.md").map((r) => ({
    id: need(r, "id", "score_table.md"),
    category: need(r, "category", "score_table.md"),
    result: need(r, "result", "score_table.md"),
  }));
  const categories = table(s, "category", "score_table.md").map((r) => ({
    category: need(r, "category", "score_table.md"),
    passed: need(r, "passed", "score_table.md"),
    scored: need(r, "scored", "score_table.md"),
    pending: r.pending ?? "",
  }));
  const total = s.match(/^Total:\s*(\d+)\s*\/\s*(\d+)\s+scored/m);
  if (!total) throw new Error('score_table.md: no "Total: N / M scored" line');

  const blind = existsSync(SOURCES.blind) ? readFileSync(SOURCES.blind, "utf8").trim() : "";

  return {
    sources,
    evaluation: { questions, categories, passed_total: total[1], scored_total: total[2] },
    blind_summary: blind || null,
  };
}

export function writeEvidence() {
  const body = JSON.stringify(buildEvidence(), null, 2) + "\n";
  writeFileSync(OUTPUT, body);
  return body;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const present = existsSync(SOURCES.manifest) && existsSync(SOURCES.scores);
  if (!present) {
    // Docker build: the context is services/web only, so use the committed public/evidence.json.
    if (!existsSync(OUTPUT)) {
      console.error("gen-evidence: source files not found and public/evidence.json is missing");
      process.exit(1);
    }
    console.log("gen-evidence: source files not in build context; using committed public/evidence.json");
  } else {
    try {
      writeEvidence();
      console.log("gen-evidence: wrote public/evidence.json");
    } catch (e) {
      console.error(`gen-evidence: ${e.message}`);
      process.exit(1);
    }
  }
}
