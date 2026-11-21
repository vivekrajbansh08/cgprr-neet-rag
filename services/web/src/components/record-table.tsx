import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export type Column<T> = { label: string; cell: (row: T) => ReactNode; className?: string };

/**
 * A table on wide containers; on narrow ones (phones, a narrow column) each row becomes a stack of
 * label/value pairs, so no column, and no figure, is ever clipped or scrolled out of view.
 */
export function RecordTable<T>({ columns, rows, rowKey, label }: { columns: Column<T>[]; rows: T[]; rowKey: (row: T, i: number) => string; label: string }) {
  return (
    <div className="@container">
      <div className="hidden rounded-md border border-border @2xl:block">
        <table className="w-full border-collapse text-[13px]" aria-label={label}>
          <thead className="bg-surface">
            <tr>
              {columns.map((c) => (
                <th key={c.label} scope="col" className="label-caps border-b border-border px-3 py-2 text-left align-bottom font-medium">
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={rowKey(r, i)} className="border-b border-border last:border-b-0 hover:bg-muted">
                {columns.map((c) => (
                  <td key={c.label} className={cn("px-3 py-2.5 align-top text-foreground", c.className)}>
                    {c.cell(r)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ul className="divide-y divide-border rounded-md border border-border @2xl:hidden" aria-label={label}>
        {rows.map((r, i) => (
          <li key={rowKey(r, i)} className="px-4 py-3">
            <dl className="grid grid-cols-[minmax(6.5rem,auto)_1fr] gap-x-4 gap-y-1.5 text-[13px]">
              {columns.map((c) => (
                <div key={c.label} className="contents">
                  <dt className="label-caps pt-px">{c.label}</dt>
                  <dd className={cn("min-w-0 break-words text-foreground", c.className)}>{c.cell(r)}</dd>
                </div>
              ))}
            </dl>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** "r1_allotment_final.pdf / p4/l47 · 95c607c2dbd7" */
export function SourceCell({ file, page, line, sha }: { file: string; page: number; line: number; sha: string }) {
  return (
    <span className="text-label">
      <span className="block font-mono break-all text-text-2">{file}</span>
      <span className="whitespace-nowrap">
        p{page}/l{line} · <span className="font-mono" title={sha}>{sha.slice(0, 12)}</span>
      </span>
    </span>
  );
}
