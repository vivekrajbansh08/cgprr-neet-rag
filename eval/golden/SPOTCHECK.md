# Spot-check: confirm three draft answers by eye

For three answerable questions in `questions.yaml`, this gives the exact file, page and row
so you can open the PDF and check the number yourself. Files are in `data/raw/mcc/2025/`; fetch
and verify them with `scripts/fetch_sources.sh`.

- **Page** is the PDF page number your viewer shows (1-based; same as `pdfinfo`).
- **Line** is the line within that page's `pdftotext -layout` output. A PDF viewer does not show
  it, so search the page for the rank (Ctrl/Cmd-F) instead.
- Rows are given as pointers (SNo/rank) plus only the fields that define the cell: quota,
  institute, course and **Alloted Category**. Check those four fields on the row, and that the rank
  is the one stated. The oracle found no larger rank in the same cell anywhere in the file. To
  re-derive it: `uv run python scripts/oracle_closing_rank.py ...` with the arguments shown.

## ans-01: AIIMS New Delhi, Open Seat Quota, MBBS, Open, Round 1 → **48**

- File: `r1_allotment_final.pdf` (sha256 `95c607c2…69a8f0`)
- Page **4**, line 47: the row with **SNo 48, Rank 48**.
- Fields to confirm: Allotted Quota "Open Seat Quota"; Allotted Institute "AIIMS, New Delhi" (with
  its Ansari Nagar address); Course "MBBS"; Alloted Category "Open".
- Closing rank groups by the **Alloted Category** column, not the Candidate Category column next
  to it.
- Independent check: `seat_matrix_r1_aiims_bhu_jipmer.pdf` lists AIIMS New Delhi, Open Seat Quota,
  MBBS, **OP NO 48** seats, and the oracle finds exactly 48 Round 1 Open allotments in this cell.
  The next AIIMS New Delhi rows after rank 48 (page 5: ranks 52, 53, 61) are other allotted
  categories.
- Re-derive: `--round 1 --quota "Open Seat Quota" --institute "AIIMS, New Delhi" --course MBBS --category Open`

## ans-04: Madras Medical College, All India, MBBS, SC, Round 1 → **6518**

- File: `r1_allotment_final.pdf`
- Page **178**, line 15: the row with **SNo 4594, Rank 6518**.
- Fields to confirm: Allotted Quota "All India"; Allotted Institute "MADRAS MEDICAL COLLEGE,
  CHENNAI" (EVR Periyar Salai address, wraps to a second line); Course "MBBS"; Alloted Category "SC".
- Independent check: `seat_matrix_r1_aiq_except_cu.pdf` lists Madras Medical College, All
  India, MBBS, **SC NO 6** seats, and the oracle finds 6 Round 1 SC allotments in this cell. This
  row is the last of the 6.
- Re-derive: `--round 1 --quota "All India" --institute "MADRAS MEDICAL COLLEGE" --course MBBS --category SC`

## ans-05: ESIC Medical College, Gulbarga, ESI quota, MBBS, Open, Round 2 → **36944**

- File: `r2_allotment_final.pdf` (sha256 `a4575f18…0980eb`)
- Page **1281**, line 30: the row with **SNo 14021, Rank 36944**.
- In Round 2 each row has two blocks. This row's Round 1 block is all "-" (no Round 1 seat). The
  **right-hand Round 2 block** holds the allotment.
- Fields to confirm in the Round 2 block: Allotted Quota "Employees State Insurance Scheme(ESI)",
  printed over four lines as "Employees" / "State" / "Insurance" / "Scheme(ESI)"; Allotted
  Institute "ESIC Medical College, Gulbarga", wrapped; Course "MBBS"; Alloted Category "Open".
- 17 Round 2 allotments in this cell; this is the highest rank among them.
- Re-derive: `--round 2 --quota "Employees State Insurance Scheme(ESI)" --institute "ESIC Medical College, Gulbarga" --course MBBS --category Open`
