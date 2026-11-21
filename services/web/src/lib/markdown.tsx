// A small, safe Markdown renderer for the two evidence files (headings, paragraphs, lists,
// tables, **bold**, `code`, [links](url)). Builds React elements; never uses innerHTML.
import type { ReactNode } from "react";
import { RecordTable } from "@/components/record-table";

function inline(text: string, key = 0): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /(`[^`]+`|\*\*[^*]+\*\*|\[[^\]]+\]\([^)]+\)|https?:\/\/[^\s)|]+)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const t = m[0];
    const k = `${key}-${i++}`;
    if (t.startsWith("`")) {
      out.push(
        <code key={k} className="font-mono text-[0.9em] break-all text-foreground">
          {t.slice(1, -1)}
        </code>,
      );
    } else if (t.startsWith("**")) {
      out.push(
        <strong key={k} className="font-semibold text-foreground">
          {inline(t.slice(2, -2), i)}
        </strong>,
      );
    } else {
      const lm = t.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
      const href = lm ? lm[2].trim() : t;
      // Only http(s) and in-page links become anchors; any other scheme is shown as plain text.
      if (!/^(https?:\/\/|#)/i.test(href)) {
        out.push(lm ? lm[1] : t);
        last = m.index + t.length;
        continue;
      }
      out.push(
        <a key={k} href={href} rel="noreferrer noopener" target="_blank" className="break-all text-primary underline underline-offset-2">
          {lm ? lm[1] : t}
        </a>,
      );
    }
    last = m.index + t.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

const cells = (row: string) =>
  row
    .trim()
    .replace(/^\||\|$/g, "")
    .split("|")
    .map((c) => c.trim());

export function Markdown({ source }: { source: string }) {
  const lines = source.replace(/\r\n/g, "\n").split("\n");
  const blocks: ReactNode[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) {
      i++;
      continue;
    }
    const h = line.match(/^(#{1,4})\s+(.*)$/);
    if (h) {
      const level = h[1].length;
      const cls =
        level === 1
          ? "font-serif text-2xl text-foreground mt-2 mb-3"
          : level === 2
            ? "font-serif text-xl text-foreground mt-8 mb-3"
            : "text-sm font-semibold text-foreground mt-6 mb-2";
      const Tag = (level === 1 ? "h2" : level === 2 ? "h3" : "h4") as "h2";
      blocks.push(
        <Tag key={i} className={cls}>
          {inline(h[2], i)}
        </Tag>,
      );
      i++;
      continue;
    }
    if (line.trim().startsWith("|")) {
      const rows: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith("|")) rows.push(lines[i++]);
      const head = cells(rows[0]);
      const body = rows.slice(rows[1] && /^\s*\|?\s*:?-+/.test(rows[1]) ? 2 : 1).map(cells);
      blocks.push(
        <div key={i} className="my-4">
          <RecordTable
            label={head.join(", ")}
            rows={body}
            rowKey={(_, ri) => String(ri)}
            columns={head.map((h, j) => ({ label: h.replace(/`/g, ""), cell: (r: string[]) => inline(r[j] ?? "", j) }))}
          />
        </div>,
      );
      continue;
    }
    if (/^\s*([-*]|\d+\.)\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*([-*]|\d+\.)\s+/.test(lines[i])) {
        let item = lines[i++].replace(/^\s*([-*]|\d+\.)\s+/, "");
        while (i < lines.length && /^\s{2,}\S/.test(lines[i]) && !/^\s*([-*]|\d+\.)\s+/.test(lines[i])) item += " " + lines[i++].trim();
        items.push(item);
      }
      blocks.push(
        <ul key={i} className="my-3 list-disc space-y-1 pl-5 text-sm leading-relaxed text-text-2">
          {items.map((it, j) => (
            <li key={j}>{inline(it, j)}</li>
          ))}
        </ul>,
      );
      continue;
    }
    const para: string[] = [];
    while (i < lines.length && lines[i].trim() && !/^(#{1,4}\s|\s*\||\s*([-*]|\d+\.)\s)/.test(lines[i])) para.push(lines[i++].trim().replace(/^>\s?/, ""));
    blocks.push(
      <p key={i} className="my-3 text-sm leading-relaxed text-text-2">
        {inline(para.join(" "), i)}
      </p>,
    );
  }
  return <div>{blocks}</div>;
}
