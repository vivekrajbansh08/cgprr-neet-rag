import { ArrowUp, ChevronRight, CornerDownRight, HelpCircle, Info, MinusCircle, X } from "lucide-react";
import { type FormEvent, useEffect, useLayoutEffect, useRef, useState } from "react";
import BlurText from "@/components/BlurText";
import { Fade } from "@/components/Fade";
import StarBorder from "@/components/StarBorder";
import { InstituteName } from "@/components/institute";
import { CheckedMark, Notice, RoundAllotments, SourceLine } from "@/components/record";
import { RecordTable, SourceCell } from "@/components/record-table";
import { Button } from "@/components/ui/button";
import { ApiError, type AskResponse, type Citation, type ClarifyOption, GUARANTEE_SENTENCE, ask } from "@/lib/api";
import { namePart } from "@/lib/names";
import { cn } from "@/lib/utils";

const EXAMPLES = [
  "In NEET-UG 2025 MCC counselling, what was the Round 1 closing rank for MBBS at AIIMS New Delhi under the Open Seat Quota, Open category?",
  "What was the Round 1 closing rank for MBBS at Kasturba Medical College, Open category?",
  "My AIR is 9000. Was that within the Round 1 All India Open closing rank for MBBS at Madras Medical College?",
];

/** Fixed lines the answer service wraps every reply in (neet_answer.compose LEAD / CREDIT). The UI
 *  hides them from the prose: the record card says where figures come from and the footer credits MCC. */
const LEAD_LINE = "NEET-UG 2025 MCC counselling, from the cited source rows:";
const CREDIT_LINE = "Source: Medical Counselling Committee (MCC), Government of India, mcc.nic.in.";

type Reply = { kind: "checking" } | { kind: "done"; res: AskResponse } | { kind: "error"; message: string };
type Turn = { id: number; question: string; reply: Reply };
/** Follow-up context: one institute, shown as a removable chip and sent as the pin. */
type Context = { id: number; name: string };

/** Missing fields (older answer service) are treated as [] / false. */
const clarifyOptions = (res: AskResponse): ClarifyOption[] => res.clarify_options ?? [];

/** Answer text without the fixed lead-in and credit lines; the guarantee sentence split out once. */
function prose(res: AskResponse): { note: boolean; body: string } {
  const text = (res.answer ?? "")
    .split("\n")
    .filter((l) => l.trim() !== LEAD_LINE && l.trim() !== CREDIT_LINE)
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
  const note = res.guarantee_note ?? false;
  if (!note) return { note, body: text };
  return { note, body: text.startsWith(GUARANTEE_SENTENCE) ? text.slice(GUARANTEE_SENTENCE.length).trim() : text };
}

/** Institute id inside a citation's cell_id, "cr:<round>:<institute_id>:<quota>:<course>:<category>". */
function cellInstitute(c: Citation): number | null {
  const id = Number(c.cell_id.split(":")[2]);
  return c.cell_id.startsWith("cr:") && Number.isInteger(id) && id > 0 ? id : null;
}

type Resolve = { status?: string; candidates?: [number, string][]; institute_id?: number; found?: boolean; pinned?: number };

/**
 * The single institute a reply is about, or null when it is about several, or undefined when the
 * reply does not say (context is then left as it was).
 * - answered: every citation's cell_id names the same institute id (the cells the figures came from).
 * - clarify (missing round/quota etc.): debug.resolve resolved to one institute, or was pinned.
 */
function replyInstitute(res: AskResponse, current: Context | null): Context | null | undefined {
  const cits = res.citations ?? [];
  if (res.status === "answered" && cits.length) {
    const ids = new Set(cits.map(cellInstitute));
    const [id] = [...ids];
    return ids.size === 1 && id !== null ? { id, name: namePart(cits[0].institute) } : null;
  }
  if (res.status === "clarify" && clarifyOptions(res).length === 0) {
    const r = ((res.debug ?? {}) as { resolve?: Resolve }).resolve;
    if (r?.status === "resolved" && r.candidates?.length) return { id: r.candidates[0][0], name: namePart(r.candidates[0][1]) };
    const pinned = r?.status === "pinned" && r.found ? r.institute_id : r?.pinned;
    if (pinned !== undefined && current?.id === pinned) return current;
  }
  return undefined;
}

const smooth = () => (window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth");

export function AskView() {
  const [q, setQ] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [context, setContext] = useState<Context | null>(null);
  const nextId = useRef(0);
  const epoch = useRef(0); // bumped by "New conversation" so a late reply is dropped
  const ctxGen = useRef(0); // bumped whenever the user changes the chip, so a late reply cannot re-set it
  const scrollTo = useRef<{ id: number; to: "bottom" | "question" } | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const busy = turns.some((t) => t.reply.kind === "checking");
  const empty = turns.length === 0;

  useLayoutEffect(() => {
    const s = scrollTo.current;
    if (!s) return;
    scrollTo.current = null;
    if (s.to === "bottom") window.scrollTo({ top: document.documentElement.scrollHeight, behavior: smooth() });
    else document.getElementById(`turn-${s.id}`)?.scrollIntoView({ block: "start", behavior: smooth() });
  }, [turns]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  async function run(question: string, pin: Context | null) {
    const text = question.trim();
    if (!text || busy) return;
    const id = ++nextId.current;
    const at = epoch.current;
    const gen = ctxGen.current;
    setQ("");
    scrollTo.current = { id, to: "bottom" };
    setTurns((ts) => [...ts, { id, question: text, reply: { kind: "checking" } }]);
    inputRef.current?.focus();
    let reply: Reply;
    try {
      const res = await ask(text, pin?.id);
      reply = { kind: "done", res };
      const next = replyInstitute(res, pin);
      if (next !== undefined && epoch.current === at && ctxGen.current === gen) setContext(next);
    } catch (e) {
      reply = { kind: "error", message: e instanceof ApiError ? e.message : "Something went wrong." };
    }
    if (epoch.current !== at) return;
    scrollTo.current = { id, to: "question" };
    setTurns((ts) => ts.map((t) => (t.id === id ? { ...t, reply } : t)));
    const active = document.activeElement;
    if (!active || active === document.body || active === inputRef.current) inputRef.current?.focus();
  }

  const submit = (e?: FormEvent) => {
    e?.preventDefault();
    void run(q, context);
  };

  const pick = (question: string, o: ClarifyOption) => {
    const ctx = { id: o.institute_id, name: namePart(o.label) };
    ctxGen.current++;
    setContext(ctx);
    void run(question, ctx);
  };

  const reset = () => {
    epoch.current++;
    ctxGen.current++;
    setTurns([]);
    setContext(null);
    setQ("");
    inputRef.current?.focus();
  };

  const composer = (
    <div className={cn(empty ? "mt-7" : "sticky bottom-0 z-[1] mt-6 border-t border-border bg-background pt-3 pb-4")}>
      {context && (
        <div className="mb-2 flex">
          <span className="inline-flex max-w-full items-center gap-1 rounded-full bg-muted py-0.5 pr-1 pl-3 text-[13px] text-foreground" data-testid="context-chip">
            <span className="truncate">About: {context.name}</span>
            <button
              type="button"
              onClick={() => {
                ctxGen.current++;
                setContext(null);
                inputRef.current?.focus();
              }}
              aria-label="Remove institute context"
              className="inline-flex size-6 shrink-0 items-center justify-center rounded-full text-text-2 hover:bg-input hover:text-foreground"
            >
              <X aria-hidden="true" className="size-3.5" />
            </button>
          </span>
        </div>
      )}
      <form onSubmit={submit} aria-busy={busy}>
        <label htmlFor="question" className="sr-only">
          Your question
        </label>
        <div className="flex items-end gap-2 rounded-xl border border-input bg-background p-2 pl-4 focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-primary" data-testid="ask-box">
          <textarea
            id="question"
            ref={inputRef}
            rows={empty ? 2 : 1}
            value={q}
            readOnly={busy}
            aria-disabled={busy || undefined}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                submit();
              }
            }}
            placeholder={empty ? "Ask about a closing rank, a round, a quota…" : "Ask a follow-up question…"}
            className={cn(
              "min-h-11 flex-1 resize-none bg-transparent py-1.5 text-[15px] leading-relaxed text-foreground outline-none focus-visible:outline-none",
              busy && "cursor-not-allowed text-text-2",
            )}
          />
          <Button
            type="submit"
            size={busy ? "default" : "icon"}
            aria-label={busy ? "Checking against the source rows" : "Send question"}
            disabled={busy || !q.trim()}
            className="rounded-lg"
          >
            {busy ? "Checking…" : <ArrowUp strokeWidth={2.25} />}
          </Button>
        </div>
      </form>
      <p className="mt-2 text-xs text-label">Conversation is not saved. Closing the tab clears it.</p>
    </div>
  );

  // One tree for both states, with the composer always the last child of the same root, so the
  // textarea is never remounted (it keeps focus across the first send and "New conversation").
  return (
    <div
      className={cn(
        "mx-auto flex min-h-[calc(100dvh-17rem)] w-full max-w-3xl flex-col md:min-h-[calc(100dvh-14rem)]",
        empty && "justify-center",
      )}
    >
      {empty ? (
        <div>
          <div className="text-center">
            <h1 className="font-serif text-[28px] leading-tight text-foreground sm:text-[34px]">
              <BlurText text="What would you like to check?" animateBy="words" trigger="load" delay={60} className="justify-center font-serif" />
            </h1>
            <p className="mt-2 text-sm text-text-2">
              Answers come from MCC's NEET-UG 2025 counselling records. Every figure is checked against its source row.
            </p>
          </div>
          <ul className="mt-6 space-y-1" aria-label="Example questions">
            {EXAMPLES.map((ex) => (
              <li key={ex}>
                <button
                  type="button"
                  onClick={() => void run(ex, context)}
                  className="flex w-full items-start gap-2.5 rounded-md px-2 py-2 text-left text-sm leading-snug text-text-2 hover:bg-muted hover:text-foreground"
                >
                  <CornerDownRight aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-label" />
                  {ex}
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <section aria-label="Conversation" className="flex flex-1 flex-col">
          <h1 className="sr-only">Ask</h1>
          <div className="flex justify-end">
            <Button variant="outline" size="sm" onClick={reset}>
              New conversation
            </Button>
          </div>
          <ol className="mt-4 flex-1 space-y-8">
            {turns.map((t) => (
              <li key={t.id} id={`turn-${t.id}`} className="scroll-mt-28 space-y-4" data-testid="turn">
                <div className="flex justify-end">
                  <p className="max-w-[85%] rounded-xl bg-muted px-4 py-2.5 text-sm leading-snug whitespace-pre-line text-foreground" data-testid="turn-question">
                    <span className="sr-only">You asked: </span>
                    {t.question}
                  </p>
                </div>
                <div aria-live="polite">
                  {t.reply.kind === "checking" && (
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
                      Checking against the source rows…
                    </StarBorder>
                  )}
                  {t.reply.kind === "error" && (
                    <Notice tone="outline" title="The answer service did not reply" icon={<MinusCircle aria-hidden="true" className="size-4 text-label" />}>
                      {t.reply.message}
                    </Notice>
                  )}
                  {t.reply.kind === "done" && (
                    <Fade trigger="mount" duration={450} initialOpacity={0} blur={false}>
                      <Result res={t.reply.res} busy={busy} onPick={(o) => pick(t.question, o)} />
                    </Fade>
                  )}
                </div>
              </li>
            ))}
          </ol>
        </section>
      )}
      {composer}
    </div>
  );
}

function RecordCard({ c, large }: { c: Citation; large: boolean }) {
  return (
    <div className={cn("rounded-lg border border-border bg-surface", large ? "px-5 py-5 sm:px-6" : "px-4 py-4")} data-testid="record">
      <p className="label-caps">
        Closing rank · <InstituteName full={c.institute} /> · {c.course}
      </p>
      <p className="mt-0.5 text-xs text-label">
        {c.quota} · {c.allotted_category}
        {c.is_cw_nri ? " · CW/NRI" : ""}
      </p>
      <div className="mt-3 flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <span className={cn("font-serif leading-none font-semibold text-foreground", large ? "text-5xl sm:text-6xl" : "text-4xl")}>{c.rank_text}</span>
        <span className="text-sm text-text-2">
          <RoundAllotments round={c.round} allotments={c.allotments} />
        </span>
      </div>
      <div className={cn("mt-4 flex flex-col gap-1.5 border-t border-border pt-3", large && "sm:flex-row sm:items-center sm:justify-between")}>
        <CheckedMark />
        <SourceLine file={c.file} page={c.page} line={c.line} sha={c.source_sha256} />
      </div>
    </div>
  );
}

function Result({ res, busy, onPick }: { res: AskResponse; busy: boolean; onPick: (o: ClarifyOption) => void }) {
  const { note, body } = prose(res);
  const cits = res.citations ?? [];

  return (
    <section aria-label="Answer" className="space-y-5">
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
                <Button
                  key={o.institute_id}
                  variant="outline"
                  size="sm"
                  disabled={busy}
                  className="h-auto min-h-8 whitespace-normal py-1.5 text-left"
                  onClick={() => onPick(o)}
                >
                  {o.label}
                </Button>
              ))}
            </div>
          )}
        </Notice>
      )}

      {res.status === "answered" && (
        <>
          {cits.length === 1 && <RecordCard c={cits[0]} large />}
          {cits.length > 1 && (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {cits.map((c) => (
                <RecordCard key={c.sid + c.cell_id} c={c} large={false} />
              ))}
            </div>
          )}

          {body && <div className="text-[15px] leading-relaxed whitespace-pre-line text-foreground">{body}</div>}

          {cits.length > 0 && (
            <details className="group" data-testid="source-rows">
              <summary className="label-caps inline-flex cursor-pointer list-none items-center gap-1.5 rounded-sm py-1 hover:text-foreground [&::-webkit-details-marker]:hidden">
                <ChevronRight aria-hidden="true" className="size-3.5 transition-transform group-open:rotate-90 motion-reduce:transition-none" />
                Source rows ({cits.length})
              </summary>
              <div className="mt-2">
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
            </details>
          )}
        </>
      )}
    </section>
  );
}
