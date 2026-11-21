// Render docs/design_note.md to docs/design_note.pdf (A4) with the bundled Playwright Chromium.
// Supports the Markdown the note uses: headings, paragraphs, bullet lists, tables, inline code,
// emphasis and links. Usage (from services/web): node scripts/render-design-note.mjs
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "../../..");
const src = path.join(root, "docs/design_note.md");
const out = path.join(root, "docs/design_note.pdf");

const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const inline = (s) =>
  esc(s)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*])\*([^*]+)\*/g, "$1<em>$2</em>")
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, "$1");

function toHtml(md) {
  const lines = md.replace(/\r/g, "").split("\n");
  const html = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }
    const h = line.match(/^(#{1,4})\s+(.*)$/);
    if (h) { html.push(`<h${h[1].length}>${inline(h[2])}</h${h[1].length}>`); i++; continue; }
    if (line.startsWith("```")) {
      const buf = []; i++;
      while (i < lines.length && !lines[i].startsWith("```")) buf.push(lines[i++]);
      i++; html.push(`<pre>${esc(buf.join("\n"))}</pre>`); continue;
    }
    if (/^\|/.test(line)) {
      const rows = [];
      while (i < lines.length && /^\|/.test(lines[i])) rows.push(lines[i++]);
      const cells = (r) => r.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
      const body = rows.filter((r) => !/^\|\s*:?-{2,}/.test(r));
      const [head, ...rest] = body;
      html.push(
        `<table><thead><tr>${cells(head).map((c) => `<th>${inline(c)}</th>`).join("")}</tr></thead><tbody>` +
          rest.map((r) => `<tr>${cells(r).map((c) => `<td>${inline(c)}</td>`).join("")}</tr>`).join("") +
          "</tbody></table>",
      );
      continue;
    }
    if (/^\s*[-*]\s+/.test(line)) {
      const items = [];
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
        let item = lines[i++].replace(/^\s*[-*]\s+/, "");
        while (i < lines.length && /^\s{2,}\S/.test(lines[i]) && !/^\s*[-*]\s+/.test(lines[i])) item += " " + lines[i++].trim();
        items.push(`<li>${inline(item)}</li>`);
      }
      html.push(`<ul>${items.join("")}</ul>`);
      continue;
    }
    const buf = [];
    while (i < lines.length && lines[i].trim() && !/^(#|\||```|\s*[-*]\s+)/.test(lines[i])) buf.push(lines[i++].trim());
    html.push(`<p>${inline(buf.join(" "))}</p>`);
  }
  return html.join("\n");
}

const css = `
@page { size: A4; margin: 16mm 17mm; }
body { font-family: "Inter", -apple-system, "Helvetica Neue", Arial, sans-serif; font-size: 9.6pt;
  line-height: 1.42; color: #212224; background: #ffffff; margin: 0; }
h1 { font-size: 15pt; color: #142644; margin: 0 0 4pt; padding-bottom: 4pt; border-bottom: 0.75pt solid #142644; }
h2 { font-size: 11pt; color: #142644; margin: 9pt 0 3pt; }
h3 { font-size: 10pt; color: #142644; margin: 7pt 0 2pt; }
p { margin: 0 0 5pt; }
ul { margin: 0 0 5pt; padding-left: 14pt; } li { margin: 0 0 1.5pt; }
code, pre { font-family: "SF Mono", Menlo, monospace; font-size: 8.4pt; color: #212224; }
pre { margin: 0 0 5pt; white-space: pre-wrap; font-size: 7.6pt; }
table { border-collapse: collapse; margin: 2pt 0 6pt; width: 100%; font-size: 8.8pt; }
th { text-align: left; color: #212224; border-bottom: 0.75pt solid #142644; padding: 2pt 4pt; }
td { border-bottom: 0.5pt solid #142644; padding: 2pt 4pt; vertical-align: top; }
strong { font-weight: 600; }
`;

const md = readFileSync(src, "utf8");
const page = `<!doctype html><html><head><meta charset="utf-8"><title>Design note</title><style>${css}</style></head><body>${toHtml(md)}</body></html>`;
const browser = await chromium.launch();
const ctx = await browser.newContext();
const p = await ctx.newPage();
await p.route("**/*", (route) => (route.request().url().startsWith("data:") || route.request().url() === "about:blank" ? route.continue() : route.abort()));
await p.setContent(page, { waitUntil: "load" });
const pdf = await p.pdf({ format: "A4", printBackground: true, preferCSSPageSize: true });
writeFileSync(out, pdf);
await browser.close();
console.log(`wrote ${path.relative(root, out)} (${pdf.length} bytes)`);
