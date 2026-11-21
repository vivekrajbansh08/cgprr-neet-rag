import { ArrowUp, CornerDownRight, HelpCircle, Info, MinusCircle } from "lucide-react";
import { type FormEvent, useRef, useState } from "react";
import BlurText from "@/components/BlurText";
import { Fade } from "@/components/Fade";
import StarBorder from "@/components/StarBorder";
import { InstituteName } from "@/components/institute";
import { CheckedMark, Notice, RoundAllotments, SourceLine } from "@/components/record";
import { RecordTable, SourceCell } from "@/components/record-table";
import { Button } from "@/components/ui/button";
import { ApiError, type AskResponse, type ClarifyOption, GUARANTEE_SENTENCE, ask } from "@/lib/api";

const EXAMPLES = [
  "In NEET-UG 2025 MCC counselling, what was the Round 1 closing rank for MBBS at AIIMS New Delhi under the Open Seat Quota, Open category?",
  "What was the Round 1 closing rank for MBBS at Kasturba Medical College, Open category?",
  "My AIR is 9000. Was that within the Round 1 All India Open closing rank for MBBS at Madras Medical College?",
];

type State =
  | { kind: "idle" }
  | { kind: "checking"; question: string }
  | { kind: "done"; question: string; res: AskResponse; seq: number }
  | { kind: "error"; question: string; message: string };

/** Missing fields (older answer service) are treated as [] / false. */
const clarifyOptions = (res: AskResponse): ClarifyOption[] => res.clarify_options ?? [];

/** When guarantee_note is set, the service prepends the fixed sentence; show it once, on its own line. */
function splitGuarantee(res: AskResponse): { note: boolean; body: string } {
  const text = res.answer ?? "";
  const note = res.guarantee_note ?? false;
  if (!note) return { note, body: text };
  const t = text.trimStart();
  return { note, body: t.startsWith(GUARANTEE_SENTENCE) ? t.slice(GUARANTEE_SENTENCE.length).trim() : text };
}

export function AskView() {
  const [q, setQ] = useState("");
  const [state, setState] = useState<State>({ kind: "idle" });
  const seq = useRef(0);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  async function run(question: string, institute_id?: number) {
    const text = question.trim();
    if (!text) return;
    setQ(text);
    setState({ kind: "checking", question: text });
    try {
      const res = await ask(text, institute_id);
      setState({ kind: "done", question: text, res, seq: ++seq.current });
    } catch (e) {
      setState({ kind: "error", question: text, message: e instanceof ApiError ? e.message : "Something went wrong." });
    }
  }

  const submit = (e: FormEvent) => {
    e.preventDefault();
    void run(q);
  };
  const busy = state.kind === "checking";

  return (
    <div>
      <h1 className="font-serif text-[28px] leading-tight text-foreground sm:text-[34px]">
        <BlurText text="What would you like to check?" animateBy="words" trigger="load" delay={60} className="font-serif" />
      </h1>
      <p className="mt-2 text-sm text-text-2">
        Answers come from MCC's NEET-UG 2025 counselling records. Every figure is checked against its source row.
      </p>

      <form onSubmit={submit} className="mt-7" aria-busy={busy}>
        <label htmlFor="question" className="sr-only">
          Your question
        </label>
        <div className="flex items-end gap-2 rounded-xl border border-input bg-background p-2 pl-4 focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-primary" data-testid="ask-box">
          <textarea
            id="question"
            ref={inputRef}
            rows={2}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void run(q);
              }
            }}
            placeholder="Ask about a closing rank, a round, a quota…"
            className="min-h-11 flex-1 resize-none bg-transparent py-1.5 text-[15px] leading-relaxed text-foreground outline-none focus-visible:outline-none"
          />
          <Button type="submit" size="icon" aria-label="Send question" disabled={busy || !q.trim()} className="rounded-lg">
            <ArrowUp strokeWidth={2.25} />
          </Button>
        </div>
      </form>

      {state.kind === "idle" && (
        <ul className="mt-6 space-y-1" aria-label="Example questions">
          {EXAMPLES.map((ex) => (
            <li key={ex}>
              <button
                type="button"
                onClick={() => void run(ex)}
                className="flex w-full items-start gap-2.5 rounded-md px-2 py-2 text-left text-sm leading-snug text-text-2 hover:bg-muted hover:text-foreground"
              >
                <CornerDownRight aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-label" />
                {ex}
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-8" aria-live="polite">
        {state.kind === "checking" && (
          <StarBorder
            as="div"
            role="status"
            theme="light"
            radius={10}
            thickness={1}
            glow={0.15}
            duration={3}
            hover="none"
            clickPulse={false}
            className="w-full justify-start px-5 py-4 text-sm font-normal text-text-2"
          >
            Checking against the sources…
          </StarBorder>
        )}
        {state.kind === "error" && (
          <Notice tone="outline" title="The answer service did not reply" icon={<MinusCircle aria-hidden="true" className="size-4 text-label" />}>
            {state.message}
          </Notice>
        )}
        {state.kind === "done" && (
          <Fade key={state.seq} trigger="mount" duration={450} initialOpacity={0} blur={false}>
            <Result question={state.question} res={state.res} onPick={(id) => void run(state.question, id)} />
          </Fade>
        )}
      </div>
    </div>
  );
}

function Result({ question, res, onPick }: { question: string; res: AskResponse; onPick: (id: number) => void }) {
  const { note, body } = splitGuarantee(res);
  const cits = res.citations ?? [];
  const one = cits.length === 1 ? cits[0] : null;

  return (
    <section aria-label="Answer" className="space-y-5">
      <p className="text-xs text-label">
        <span className="label-caps mr-2">Question</span>
        {question}
      </p>

      {note && (
        <p className="flex items-start gap-2 border-l-2 border-primary py-0.5 pl-3 text-sm text-foreground" data-testid="guarantee-note">
          <Info aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-label" />
          {GUARANTEE_SENTENCE}
        </p>
      )}

      {res.status === "refused" && (
        <Notice tone="outline" title="Not in the sources" icon={<MinusCircle aria-hidden="true" className="size-4 text-label" />}>
          <p className="whitespace-pre-line">{body}</p>
        </Notice>
      )}

      {res.status === "clarify" && (
        <Notice tone="muted" title={clarifyOptions(res).length ? "Which one do you mean?" : "Please narrow the question"} icon={<HelpCircle aria-hidden="true" className="size-4 text-text-2" />}>
          <p className="whitespace-pre-line">{body}</p>
          {clarifyOptions(res).length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2" role="group" aria-label="Pick a campus">
              {clarifyOptions(res).map((o) => (
                <Button key={o.institute_id} variant="outline" size="sm" className="h-auto min-h-8 whitespace-normal py-1.5 text-left" onClick={() => onPick(o.institute_id)}>
                  {o.label}
                </Button>
              ))}
            </div>
          )}
        </Notice>
      )}

      {res.status === "answered" && (
        <>
          {one && (
            <div className="rounded-lg border border-border bg-surface px-5 py-5 sm:px-6" data-testid="record">
              <p className="label-caps">
                Closing rank · <InstituteName full={one.institute} /> · {one.course}
              </p>
              <p className="mt-0.5 text-xs text-label">
                {one.quota} · {one.allotted_category}
                {one.is_cw_nri ? " · CW/NRI" : ""}
              </p>
              <div className="mt-3 flex flex-wrap items-baseline gap-x-4 gap-y-1">
                <span className="font-serif text-5xl leading-none font-semibold text-foreground sm:text-6xl">{one.rank_text}</span>
                <span className="text-sm text-text-2">
                  <RoundAllotments round={one.round} allotments={one.allotments} />
                </span>
              </div>
              <div className="mt-4 flex flex-col gap-1.5 border-t border-border pt-3 sm:flex-row sm:items-center sm:justify-between">
                <CheckedMark />
                <SourceLine file={one.file} page={one.page} line={one.line} sha={one.source_sha256} />
              </div>
            </div>
          )}
          {!one && cits.length > 0 && <CheckedMark />}

          <div className="text-[15px] leading-relaxed whitespace-pre-line text-foreground">{body}</div>

          {cits.length > 0 && (
            <div>
              <h2 className="label-caps mb-2">Sources</h2>
              <RecordTable
                label="Sources"
                rows={cits}
                rowKey={(c) => c.sid + c.cell_id}
                columns={[
                  { label: "Ref", cell: (c) => c.sid, className: "font-mono text-label" },
                  { label: "Institute, course", cell: (c) => <><InstituteName full={c.institute} />, {c.course}</> },
                  { label: "Round", cell: (c) => c.round },
                  { label: "Quota", cell: (c) => c.quota, className: "text-text-2" },
                  { label: "Category", cell: (c) => `${c.allotted_category}${c.is_cw_nri ? " (CW/NRI)" : ""}`, className: "text-text-2" },
                  { label: "Closing rank", cell: (c) => c.rank_text, className: "font-medium" },
                  { label: "Allotments", cell: (c) => c.allotments },
                  { label: "Source (file p/l)", cell: (c) => <SourceCell file={c.file} page={c.page} line={c.line} sha={c.source_sha256} /> },
                ]}
              />
            </div>
          )}
        </>
      )}
    </section>
  );
}
