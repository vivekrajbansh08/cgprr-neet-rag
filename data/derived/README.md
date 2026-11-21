# data/derived

Source: Medical Counselling Committee (MCC), Government of India, mcc.nic.in

This directory holds local build output derived from MCC's published PDFs, for example closing rank per round, quota, institute, course and allotted category. Only this README and `.gitkeep` are tracked; everything else is gitignored.

MCC's material is not redistributed in this repository; scripts/fetch_sources.sh downloads it from mcc.nic.in and verifies each file's sha256. Derived tables are rebuilt locally from those files:

```bash
scripts/fetch_sources.sh      # download the sha256-pinned MCC PDFs into data/raw/mcc/2025/
make ingest                   # parse them into Postgres; derived tables are built from there
```

Every derived file states how it was produced (script and input sha256 values) in a header or sidecar file.
