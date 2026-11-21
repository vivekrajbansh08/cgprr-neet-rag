import { useEffect, useState, type ReactNode } from "react";
import { RecordTable } from "@/components/record-table";
import { evidence, shortSha, type Evidence, type EvidenceQuestion, type EvidenceSource } from "@/lib/api";

/** Plain words for the score table's category keys. Labels only; no value is changed. */
const CATEGORY_NAMES: Record<string, string> = {
  answerable: "Answerable",
  out_of_index: "Out of index",
  injection: "Injection",
  unsafe_advice: "Unsafe advice",
  predictor: "Predictor",
};
const categoryName = (key: string) => CATEGORY_NAMES[key] ?? key.replace(/_/g, " ");

function Fingerprint({ source, onCopied }: { source: EvidenceSource; onCopied: (msg: string) => void }) {
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(source.sha256);
      onCopied(`Full sha256 for ${source.document} copied.`);
    } catch {
      onCopied("Copying is not available here. The full sha256 is in the tooltip.");
    }
  };
  return (
    <button
      type="button"
      onClick={copy}
      title={source.sha256}
      aria-label={`Copy full sha256 fingerprint of ${source.document}`}
      className="rounded-sm font-mono text-foreground underline decoration-border underline-offset-4 hover:decoration-primary"
    >
      {shortSha(source.sha256)}
    </button>
  );
}

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section className="mt-10" aria-labelledby={id}>
      <h2 id={id} className="label-caps border-b border-border pb-2">
        {title}
      </h2>
      <div className="mt-4">{children}</div>
    </section>
  );
}

export function EvidenceView() {
  const [data, setData] = useState<Evidence | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState("");

  useEffect(() => {
    evidence()
      .then(setData)
      .catch((e: Error) => setError(e.message));
  }, []);

  return (
    <div>
      <h1 className="font-serif text-[28px] leading-tight text-foreground sm:text-[34px]">Evidence</h1>
      {error && <p className="mt-3 text-sm text-text-2">{error}</p>}

      <Section id="ev-sources" title="Where the numbers come from">
        <p className="text-[15px] text-foreground">
          MCC NEET-UG 2025 All India Quota results, Rounds 1 to 3, and the Round 1 seat matrices, from
          mcc.nic.in/archive-ug.
        </p>
        {data && (
          <div className="mt-4">
            <RecordTable<EvidenceSource>
              label="Source documents"
              rows={data.sources}
              rowKey={(r) => r.sha256}
              columns={[
                { label: "Document", cell: (r) => r.document },
                { label: "Pages", cell: (r) => r.pages, className: "tabular-nums" },
                { label: "Retrieved", cell: (r) => r.retrieved, className: "tabular-nums whitespace-nowrap" },
                { label: "Fingerprint", cell: (r) => <Fingerprint source={r} onCopied={setCopied} /> },
              ]}
            />
            <p className="mt-2 text-xs text-label" role="status" aria-live="polite">
              {copied || "Fingerprint: first 12 characters of the file's sha256. Select one to copy the full value."}
            </p>
          </div>
        )}
      </Section>

      <Section id="ev-checks" title="How answers are checked">
        <ul className="space-y-1.5 text-[15px] text-foreground">
          <li>Figures come from the database, not the model.</li>
          <li>Every figure must match a cited row, or the answer is withheld.</li>
          <li>Institutes with ambiguous names are never merged.</li>
        </ul>
      </Section>

      <Section id="ev-eval" title="Evaluation">
        {data && (
          <>
            <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-1 text-[15px]" aria-label="Passed questions by category">
              {data.evaluation.categories.map((c) => (
                <div key={c.category} className="contents">
                  <dt className="text-text-2">{categoryName(c.category)}</dt>
                  <dd className="tabular-nums text-foreground">
                    {c.passed} of {c.scored} passed
                  </dd>
                </div>
              ))}
            </dl>
            <p className="mt-4 text-[15px] text-foreground">
              {data.evaluation.scored_total} questions written and locked before the system was built; the same set
              was also used during development, so this is not a held-out score.
            </p>
            {/* Blind-question summary: one line from evidence/blind_summary.txt. Nothing is shown when it is empty. */}
            {data.blind_summary && (
              <p className="mt-2 text-[15px] text-foreground" data-testid="blind-summary">
                {data.blind_summary}
              </p>
            )}
            <div className="mt-4">
              <RecordTable<EvidenceQuestion>
                label="Results by question"
                rows={data.evaluation.questions}
                rowKey={(r) => r.id}
                columns={[
                  { label: "Id", cell: (r) => <span className="font-mono">{r.id}</span> },
                  { label: "Category", cell: (r) => categoryName(r.category) },
                  { label: "Result", cell: (r) => r.result },
                ]}
              />
            </div>
            <p className="mt-2 text-xs text-label">eval/results/score_table.md</p>
          </>
        )}
      </Section>

      <Section id="ev-privacy" title="Privacy">
        <p className="border-l-2 border-primary pl-3 text-[15px] text-foreground" data-testid="local-line">
          Runs on this machine. No question or answer leaves it.
        </p>
        <p className="mt-2 text-[15px] text-foreground">The services read the database through a read-only role.</p>
      </Section>
    </div>
  );
}
