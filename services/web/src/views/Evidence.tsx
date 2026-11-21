import { useEffect, useState } from "react";
import { Markdown } from "@/lib/markdown";
import { evidence } from "@/lib/api";

function useDoc(name: "manifest.md" | "score_table.md") {
  const [doc, setDoc] = useState<{ text?: string; error?: string }>({});
  useEffect(() => {
    evidence(name)
      .then((text) => setDoc({ text }))
      .catch((e: Error) => setDoc({ error: e.message }));
  }, [name]);
  return doc;
}

/** Drop the file's own top-level heading; the view supplies its own. */
const body = (md: string) => md.replace(/^#\s+.*\n/, "");

export function EvidenceView() {
  const manifest = useDoc("manifest.md");
  const scores = useDoc("score_table.md");
  return (
    <div>
      <h1 className="font-serif text-[28px] leading-tight text-foreground sm:text-[34px]">Evidence</h1>
      <p className="mt-3 border-l-2 border-primary pl-3 text-[15px] text-foreground" data-testid="local-line">
        Runs on this machine. No question or answer leaves it.
      </p>

      <section className="mt-10" aria-labelledby="ev-scores">
        <h2 id="ev-scores" className="label-caps border-b border-border pb-2">
          Evaluation score table · eval/results/score_table.md
        </h2>
        {scores.error && <p className="mt-3 text-sm text-text-2">{scores.error}</p>}
        {scores.text && <Markdown source={body(scores.text)} />}
      </section>

      <section className="mt-12" aria-labelledby="ev-sources">
        <h2 id="ev-sources" className="label-caps border-b border-border pb-2">
          Data sources and sha256 · data/raw/MANIFEST.md
        </h2>
        {manifest.error && <p className="mt-3 text-sm text-text-2">{manifest.error}</p>}
        {manifest.text && <Markdown source={body(manifest.text)} />}
      </section>
    </div>
  );
}
