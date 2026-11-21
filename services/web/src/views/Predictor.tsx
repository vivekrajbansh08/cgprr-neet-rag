import { Info, MinusCircle } from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";
import { Fade } from "@/components/Fade";
import StarBorder from "@/components/StarBorder";
import { InstituteName } from "@/components/institute";
import { Notice, RoundAllotments, SourceLine } from "@/components/record";
import { RecordTable, SourceCell } from "@/components/record-table";
import { Button } from "@/components/ui/button";
import { ApiError, type FormOptions, type PredictResponse, formOptions, predict } from "@/lib/api";

const field = "h-9 w-full rounded-md border border-input bg-background px-3 text-sm text-foreground focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-primary";
const lab = "label-caps mb-1.5 block";

/** AIR must be a whole number from 1 to 10,000,000 (the predictor API's limit). */
function rankProblem(raw: string): string | null {
  const v = raw.trim();
  if (!v) return "Enter your All India Rank.";
  if (!/^\d+$/.test(v)) return "Use digits only, with no commas, spaces or decimals.";
  const n = Number(v);
  if (n < 1) return "The rank must be 1 or more.";
  if (n > 10_000_000) return "The rank must be 10,000,000 or less.";
  return null;
}

type Form = { rank: string; category: string; pwd: boolean; quota: string; course: string; round: string; state: string };

export function PredictorView() {
  const [opts, setOpts] = useState<FormOptions | null>(null);
  const [optsError, setOptsError] = useState<string | null>(null);
  const [form, setForm] = useState<Form>({ rank: "", category: "", pwd: false, quota: "", course: "", round: "", state: "" });
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState<{ data: PredictResponse; seq: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  // The message appears after the first submit (not on blur, so the layout never shifts under a click).
  const [rankTouched, setRankTouched] = useState(false);
  const rankError = rankProblem(form.rank);
  const showRankError = rankTouched && rankError !== null;

  useEffect(() => {
    formOptions()
      .then((o) => {
        setOpts(o);
        setForm((f) => ({
          ...f,
          category: f.category || o.categories[0] || "",
          quota: f.quota || o.quotas[0] || "",
          course: f.course || o.courses[0] || "",
          round: f.round || String(o.rounds[0] ?? ""),
        }));
      })
      .catch((e) => setOptsError(e instanceof ApiError ? e.message : "Could not load the form options."));
  }, []);

  const set = <K extends keyof Form>(k: K, v: Form[K]) => setForm((f) => ({ ...f, [k]: v }));

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (rankError) {
      setRankTouched(true);
      document.getElementById("p-rank")?.focus();
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const data = await predict({
        rank: Number(form.rank.trim()),
        category: form.category,
        pwd: form.pwd,
        quota: form.quota,
        course: form.course,
        round: Number(form.round),
        state: form.state || null,
      });
      setRes((r) => ({ data, seq: (r?.seq ?? 0) + 1 }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <h1 className="font-serif text-[28px] leading-tight text-foreground sm:text-[34px]">Predictor</h1>
      <p className="mt-2 text-sm text-text-2">
        Where did ranks like yours close in 2025? Options are read from the closing-rank records, then explained.
      </p>

      {optsError && (
        <div className="mt-6">
          <Notice tone="outline" title="The predictor service did not reply" icon={<MinusCircle aria-hidden="true" className="size-4 text-label" />}>
            {optsError}
          </Notice>
        </div>
      )}

      <form onSubmit={submit} className="mt-7 grid grid-cols-1 gap-4 rounded-lg border border-border bg-surface p-5 sm:grid-cols-2 lg:grid-cols-3" aria-busy={busy}>
        <div>
          <label htmlFor="p-rank" className={lab}>All India Rank (AIR)</label>
          <input
            id="p-rank"
            required
            inputMode="numeric"
            autoComplete="off"
            value={form.rank}
            onChange={(e) => set("rank", e.target.value)}
            aria-invalid={showRankError}
            aria-describedby={showRankError ? "p-rank-msg" : undefined}
            placeholder="e.g. 3000"
            className={field}
          />
          {showRankError && (
            <p id="p-rank-msg" role="alert" className="mt-1.5 flex items-start gap-1.5 text-xs text-foreground" data-testid="rank-error">
              <MinusCircle aria-hidden="true" className="mt-px size-3.5 shrink-0 text-label" />
              {rankError}
            </p>
          )}
        </div>
        <Select id="p-category" label="Category" value={form.category} onChange={(v) => set("category", v)} options={opts?.categories ?? []} />
        <div>
          <span className={lab} id="p-pwd-label">Persons with disability</span>
          <label htmlFor="p-pwd" className="flex h-9 items-center gap-2 text-sm text-foreground">
            <input id="p-pwd" type="checkbox" checked={form.pwd} onChange={(e) => set("pwd", e.target.checked)} className="size-4 accent-primary" aria-describedby="p-pwd-label" />
            PwD candidate
          </label>
        </div>
        <Select id="p-quota" label="Quota" value={form.quota} onChange={(v) => set("quota", v)} options={opts?.quotas ?? []} />
        <Select id="p-course" label="Course" value={form.course} onChange={(v) => set("course", v)} options={opts?.courses ?? []} />
        <Select id="p-round" label="Round" value={form.round} onChange={(v) => set("round", v)} options={(opts?.rounds ?? []).map(String)} format={(r) => `Round ${r}`} />
        <Select id="p-state" label="State (optional)" value={form.state} onChange={(v) => set("state", v)} options={opts?.states ?? []} empty="Any state" />
        <div className="flex items-end sm:col-span-2 lg:col-span-2 lg:justify-end">
          <Button type="submit" disabled={busy || !opts}>
            {busy ? "Checking…" : "Show options"}
          </Button>
        </div>
      </form>

      <div className="mt-8" aria-live="polite">
        {busy && (
          <StarBorder as="div" role="status" theme="light" radius={10} glow={0.15} duration={3} hover="none" clickPulse={false} className="w-full justify-start px-5 py-4 text-sm font-normal text-text-2">
            Reading the closing-rank records…
          </StarBorder>
        )}
        {!busy && error && (
          <Notice tone="outline" title="The predictor service did not reply" icon={<MinusCircle aria-hidden="true" className="size-4 text-label" />}>
            {error}
          </Notice>
        )}
        {!busy && !error && res && (
          <Fade key={res.seq} trigger="mount" duration={450} initialOpacity={0} blur={false}>
            <Results data={res.data} />
          </Fade>
        )}
      </div>
    </div>
  );
}

function Select({ id, label, value, onChange, options, empty, format }: { id: string; label: string; value: string; onChange: (v: string) => void; options: string[]; empty?: string; format?: (v: string) => string }) {
  return (
    <div>
      <label htmlFor={id} className={lab}>{label}</label>
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)} className={field}>
        {empty !== undefined && <option value="">{empty}</option>}
        {options.map((o) => (
          <option key={o} value={o}>{format ? format(o) : o}</option>
        ))}
      </select>
    </div>
  );
}

function Results({ data }: { data: PredictResponse }) {
  const stateChosen = !!data.inputs?.state;
  return (
    <section aria-label="Predictor results" className="space-y-5">
      <p className="flex items-start gap-2 border-l-2 border-primary py-0.5 pl-3 text-sm text-foreground" data-testid="predictor-note">
        <Info aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-label" />
        {data.note}
      </p>

      <dl className="flex flex-wrap gap-x-8 gap-y-2 text-sm">
        <div>
          <dt className="label-caps">Options</dt>
          <dd className="font-serif text-2xl text-foreground">{data.option_count}</dd>
        </div>
        <div>
          <dt className="label-caps">Institutes in scope</dt>
          <dd className="font-serif text-2xl text-foreground">{data.institutes_in_scope}</dd>
        </div>
        {stateChosen && (
          <div>
            <dt className="label-caps">Not placed (no state recorded)</dt>
            <dd className="font-serif text-2xl text-foreground">{data.unplaced_no_state}</dd>
          </div>
        )}
        <div>
          <dt className="label-caps">Categories considered</dt>
          <dd className="pt-1.5 text-foreground">{data.eligible_categories.join(", ")}</dd>
        </div>
      </dl>

      {data.options.length === 0 && (
        <Notice tone="outline" title="No options in these records" icon={<MinusCircle aria-hidden="true" className="size-4 text-label" />}>
          {data.empty_message && <p>{data.empty_message}</p>}
          {data.best_in_scope && (
            <div className="mt-3 border-t border-border pt-3" data-testid="best-in-scope">
              <p className="label-caps mb-1">Best closing rank in scope</p>
              <p className="text-foreground">
                <InstituteName full={data.best_in_scope.institute} /> · {data.best_in_scope.category} ·{" "}
                <span className="font-serif text-lg font-semibold">{data.best_in_scope.closing_rank}</span>{" "}
                <span className="text-text-2">
                  (<RoundAllotments round={data.best_in_scope.round} allotments={data.best_in_scope.allotments} />)
                </span>
              </p>
              <SourceLine className="mt-1" file={data.best_in_scope.file} page={data.best_in_scope.page} line={data.best_in_scope.line} sha={data.best_in_scope.source_sha256} />
            </div>
          )}
        </Notice>
      )}

      {data.options.length > 0 && (
        <ol className="divide-y divide-border border-y border-border" data-testid="options">
          {data.options.map((o, i) => (
            <li key={`${o.institute_id}-${i}`} className="py-5">
              <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                <h2 className="text-[15px] font-semibold text-foreground">
                  <span className="mr-2 font-mono text-xs font-normal text-label">{i + 1}.</span>
                  <InstituteName full={o.institute} withAddress />
                </h2>
                {o.state && <span className="text-xs text-label">{o.state}</span>}
              </div>
              <div className="mt-3">
                <RecordTable
                  label={`Closing ranks for ${o.institute}`}
                  rows={o.cells}
                  rowKey={(c, j) => `${c.round}-${c.quota}-${c.category}-${j}`}
                  columns={[
                    { label: "Round", cell: (c) => c.round },
                    { label: "Quota", cell: (c) => c.quota, className: "text-text-2" },
                    { label: "Category", cell: (c) => c.category, className: "text-text-2" },
                    { label: "Closing rank", cell: (c) => c.closing_rank, className: "font-medium" },
                    { label: "Allotments", cell: (c) => c.allotments },
                    { label: "Source (file p/l)", cell: (c) => <SourceCell file={c.file} page={c.page} line={c.line} sha={c.source_sha256} /> },
                  ]}
                />
              </div>
              {o.explanation && <p className="mt-3 text-sm leading-relaxed text-text-2">{o.explanation}</p>}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
