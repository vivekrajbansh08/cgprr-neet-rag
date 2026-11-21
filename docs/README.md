# docs

- `source_notes.md`: the MCC source files, how their tables are parsed, the per-round closing-rank
  definition (section 4), and the project's data conventions.
- `eval_log.md`: dated log of changes made after evaluation runs and checks of raw answers,
  and how the eval runner scores answers.
- `benchmark.md`: measured latency and tokens-per-second on the Apple M5 from `jobs/bench`, plus
  labelled estimates for an RTX 6000 Ada (VRAM, decode speed, running cost).
- `design_note.md`: problem, architecture, hard rules and their enforcement, model choice, eval
  method and results, data privacy, cost, limitations. `design_note.pdf` is the same note
  rendered to two A4 pages (`node services/web/scripts/render-design-note.mjs`).
- `screenshots/`: local self-check images of the web UI. Gitignored and never committed, because
  they show MCC figures.
