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
    if (/^<(svg|div|p class)/.test(line.trim())) {
      // Raw inline HTML block (used for the SVG diagram and the subtitle): copied as is up to the
      // first blank line.
      const buf = [];
      while (i < lines.length && lines[i].trim()) buf.push(lines[i++]);
      html.push(buf.join("\n"));
      continue;
    }
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

const font = (rel) => readFileSync(path.join(here, "../node_modules", rel)).toString("base64");
const fonts = `
@font-face { font-family: "NoteSans"; src: url(data:font/woff2;base64,${font("@fontsource-variable/inter/files/inter-latin-wght-normal.woff2")}) format("woff2"); font-weight: 100 900; }
@font-face { font-family: "NoteSerif"; src: url(data:font/woff2;base64,${font("@fontsource/source-serif-4/files/source-serif-4-latin-400-normal.woff2")}) format("woff2"); font-weight: 400; }
@font-face { font-family: "NoteSerif"; src: url(data:font/woff2;base64,${font("@fontsource/source-serif-4/files/source-serif-4-latin-600-normal.woff2")}) format("woff2"); font-weight: 600; }
`;
const css = `${fonts}
@page { size: A4; margin: 18mm 20mm; }
body { font-family: "NoteSans", sans-serif; font-size: 9.4pt; line-height: 1.45; color: #212224;
  background: #ffffff; margin: 0; }
h1 { font-family: "NoteSerif", serif; font-weight: 600; font-size: 19pt; color: #142644; margin: 0 0 2pt; }
.subtitle { font-size: 8.8pt; color: #212224; margin: 0 0 10pt; }
h2 { font-family: "NoteSerif", serif; font-weight: 600; font-size: 11.5pt; color: #142644; margin: 10pt 0 3pt; }
h3 { font-family: "NoteSerif", serif; font-weight: 600; font-size: 10pt; color: #142644; margin: 7pt 0 2pt; }
p { margin: 0 0 5pt; }
ul { margin: 0 0 5pt; padding-left: 14pt; } li { margin: 0 0 2pt; }
code, pre { font-family: Menlo, monospace; font-size: 8.4pt; color: #212224; }
pre { margin: 0 0 5pt; white-space: pre-wrap; font-size: 7.6pt; }
table { border-collapse: collapse; margin: 3pt 0 7pt; width: 100%; font-size: 8.8pt; }
th { text-align: left; font-weight: 600; color: #212224; border-bottom: 0.75pt solid #ECEDEF; padding: 3pt 5pt 3pt 0; }
td { border-bottom: 0.75pt solid #ECEDEF; padding: 3pt 5pt 3pt 0; vertical-align: top; }
svg { display: block; margin: 4pt 0 8pt; max-width: 100%; }
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
