import { CircleCheck } from "lucide-react";
import type { ReactNode } from "react";
import { shortSha } from "@/lib/api";
import { cn } from "@/lib/utils";

/** "Round 1 · from 48 allotments" — every closing rank names its round and allotment count. */
export function RoundAllotments({ round, allotments }: { round: number; allotments: number }) {
  return (
    <>
      Round {round} · from {allotments} {allotments === 1 ? "allotment" : "allotments"}
    </>
  );
}

export function SourceLine({
  file,
  page,
  line,
  sha,
  className,
}: {
  file: string;
  page: number;
  line: number;
  sha: string;
  className?: string;
}) {
  return (
    <p className={cn("text-xs text-label", className)}>
      <span className="font-mono text-text-2">{file}</span>, page {page}, line {line}
      <span aria-hidden="true"> · </span>
      <span className="sr-only">, </span>sha256 <span className="font-mono" title={sha}>{shortSha(sha)}</span>
    </p>
  );
}

export function CheckedMark() {
  return (
    <p className="inline-flex items-center gap-1.5 text-[13px] font-medium text-foreground">
      <CircleCheck aria-hidden="true" className="size-4 text-primary" strokeWidth={2} />
      Checked against source
    </p>
  );
}

export function Notice({ tone, title, children, icon }: { tone: "outline" | "muted"; title?: string; children: ReactNode; icon?: ReactNode }) {
  return (
    <div
      className={cn(
        "rounded-lg px-5 py-4",
        tone === "outline" ? "border border-border bg-background" : "bg-muted",
      )}
    >
      {title && (
        <p className="mb-1.5 flex items-center gap-2 text-sm font-semibold text-foreground">
          {icon}
          {title}
        </p>
      )}
      <div className="text-sm leading-relaxed text-text-2">{children}</div>
    </div>
  );
}
