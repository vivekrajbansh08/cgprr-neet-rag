# data/derived — local build output, never committed

Source: Medical Counselling Committee (MCC), Government of India, mcc.nic.in

This directory holds tables derived from MCC's published PDFs, for example closing rank per
round × quota × institute × course × allotted category. **Nothing here is committed** (only this
README and `.gitkeep`; everything else is gitignored).

Why: MCC's copyright policy (https://mcc.nic.in/copyright-policy/, quoted in
`data/raw/MANIFEST.md`) allows reproduction only "after taking proper permission" from MCC. This
repo does not hold that permission, so it redistributes neither MCC's files nor tables derived
from them. Everyone rebuilds them locally from MCC's own files:

```bash
scripts/fetch_sources.sh          # download the sha256-pinned MCC PDFs into data/raw/mcc/2025/
uv run python -m neet_ingest      # parse into Postgres; derived tables are built from there
```

Every derived file must state how it was produced (script + input sha256s) in a header or
sidecar (see the project rules).
