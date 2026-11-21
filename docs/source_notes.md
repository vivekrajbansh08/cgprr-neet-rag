# Source notes: MCC NEET-UG 2025 allotment results and seat matrices

Source: Medical Counselling Committee (MCC), Government of India, mcc.nic.in

MCC's material is not redistributed in this repository; scripts/fetch_sources.sh downloads it from mcc.nic.in and verifies each file's sha256.

These notes describe the raw files listed in `data/raw/MANIFEST.md`: how their tables are laid
out, how the parser reads them, and the conventions the project follows when turning rows into
closing ranks. Every observation was checked against `pdftotext -layout` output (poppler).

Pointers use the form `r2 p780 l17-19`: file (r1, r2, r3 for the Round 1-3 allotment results),
PDF page, and line number within that page's `pdftotext -layout` text. Rows are cited by pointer
plus, where needed, quota, institute, course and allotted category. Candidate-category values,
remark text from individual rows and closing-rank values are not reproduced here. Figures in
examples are invented unless a file is named as their source.

## 1. Files and their table layouts

### Allotment results

| File | Pages | Title on page 1 | Table starts | Footer |
|---|---|---|---|---|
| `r1_allotment_final.pdf` | 1107 | "NEET-UG Counselling Seats Allotment -2025 Round 1" | p3 | none |
| `r2_allotment_final.pdf` | 3237 | "NEET-UG Counselling Seats Allotment -2025 Round 2" | p3 | "Page No. N   17-09-2025 10:38:30 AM" |
| `r3_allotment_final.pdf` | 1930 | "Revised NEET-UG Counselling Seats Allotment -2025 Round 3" | p2 | "Page No. N   23-10-2025 12:13:37 PM" |

Page counts are from `data/raw/MANIFEST.md`.

The first pages hold two legends: quota abbreviations (28 quotas, code and description) and
allotted-category abbreviations (BC, BC PwD, EW, EW PwD, GN, GN PwD, SC, SC PwD, ST, ST PwD). They
also carry a note about candidates whose category or quota changed within the same institute. The
table itself prints quota and category in words, not codes.

The header row is printed once, on the first table page only:

- Round 1 (8 columns), r1 p3 l3-4:
  `SNo | Rank | Allotted Quota | Allotted Institute | Course | Alloted Category | Candidate Category | Remarks`
- Round 2 (13 columns in two blocks), r2 p3 l2-6:
  `SNo | Rank |`, then a Round 1 block `Allotted Quota | Allotted Institute | Course | Remarks |`,
  then a Round 2 block `Allotted Quota | Allotted Institute | Course | Alloted Category | candidate Category | option No. | Remarks`
- Round 3 (16 columns in three blocks, no SNo), r3 p2 l2-5:
  `Rank |`, then Round 1 and Round 2 blocks `Allotted Quota | Allotted Institute | Course | Remarks |`,
  then a Round 3 block `Allotted Quota | Allotted Institute | Course | Alloted Category | candidate Category | option No. | Remarks`

In Round 2 and Round 3 the earlier-round blocks show where the candidate stood before the round:
seat, course and a reporting remark. Only the right-most block is the allotment made in that
round. Earlier-round blocks use a short institute name ("AIIMS, New Delhi"); the current-round
block uses name plus address.

### Seat matrices (Round 1, MBBS and BDS)

There are two layouts.

- Long layout, one row per institute, quota, course and category:
  `StateName | InstituteType | Institute | Quota | Branch | Category | TotalSeats`. Used by
  `seat_matrix_r1_aiq_except_cu.pdf`, `seat_matrix_r1_aiims_bhu_jipmer.pdf` and
  `seat_matrix_r1_central_universities.pdf`. Branch is printed as "MBBS (MBBS)" or "BDS (BDS)".
  Category is a two-letter code plus NO or PH, for example "OP NO" or "BC PH" (OP = Open,
  BC = OBC, EW = EWS, PH = PwD).
- Wide layout, one row per institute, course and quota, one column per category:
  `Institute Type | Institute | Program | Quota | Open | Open PwD | General-EWS | General-EWS PwD | OBC | OBC PwD | SC | SC PwD | ST | ST PwD | TotalSeats`.
  Used by `seat_matrix_r1_deemed.pdf` and `seat_matrix_r1_esic_ip.pdf`.

The seat matrix gives each institute a 6-digit code in parentheses, for example "(123456)". The
allotment results carry no institute code.

## 2. How rows wrap, and how they are counted

- One row is one candidate. A row starts on a line whose first token (indent of at most 2
  characters) is `SNo Rank` (Round 1 and 2) or `Rank` (Round 3). Cells that do not fit wrap onto
  following lines within their own column: quota ("Deemed/Paid Seats" / "Quota"), institute and
  address (up to 10 lines in Round 2 and 3), remarks ("Did not opt" / "for" / "Upgradation."), and
  PwD ("OBC" / "PwD").
- Rows never break across pages. The first row of every page is preceded by a form feed (`\f`). A
  row-start pattern that does not allow for it misses exactly one row per page.
- Narrow columns wrap mid-word: "Deemed/Pa" / "id Seats" / "Quota" (r2 p780 l17-19). Adjacent
  cells sometimes touch with one space or with no space at all, for example
  "Internal -PuducherryJIPMER PUDUCHERRY" (r1 p772 l28). Splitting on runs of two or more spaces
  therefore does not separate cells reliably.
- Occasionally a cell sits one line above the rest of its row: at r2 p2833 l37 the quota is on the
  rank line while institute, course, categories and remarks start on the next line.
- A whitespace-gutter column detector gives the wrong column count on most pages, because of
  centred multi-line cells and touching cells. The parser anchors on fixed vocabularies instead
  (see the docstrings in `libs/mccparse`).

Row counts. A row is counted at each row-start line as defined above, with the form feed stripped
and rank matched as `\d+(\.\d+)?`. The counts below come from running the parser
(`scripts/oracle_closing_rank.py`, `libs/mccparse`) on the files in `data/raw/MANIFEST.md`.

| Round | Rows (candidates) | Check | Allotments made in this round |
|---|---|---|---|
| 1 | 26,608 | SNo runs 1..26608 with no gap; ranks strictly increasing | 26,608 (every row is "Allotted") |
| 2 | 35,551 | SNo runs 1..35551 with no gap; ranks strictly increasing | 15,321 = 12,901 fresh + 2,420 upgraded |
| 3 | 39,479 | no SNo; ranks strictly increasing | 9,143 = 5,529 fresh + 3,614 upgraded |

Every row falls in exactly one class (allotted in this round, or one of the no-allotment classes
in 5.3). The parser raises an error on any row it cannot classify.

Reconciliation that does not depend on the parser:

- Allotment counts equal a plain `grep` of "Fresh Allotted" and "Upgraded" lines in each file.
- Round 1 allotments per cell equal the seat-matrix seats for each cell sampled.

## 3. Personal-data check (every column)

| Column | Present in | Identifies a person? |
|---|---|---|
| SNo | Round 1, 2 | No (row number) |
| Rank (NEET AIR) | all | Not directly, but see the note below |
| Allotted Quota / Institute / Course | all | No |
| Remarks in earlier-round blocks (Reported / Not Reported / Seat Surrendered) | Round 2, 3 | No |
| Alloted Category | all | No |
| Candidate Category (including PwD status) | all | Not by itself; sensitive (disability, caste) when linked to a rank |
| option No. (choice number) | Round 2, 3 | No |
| Remarks (including "NRI Priority : n", "CW Rank : n") | all | No |
| Seat-matrix columns (state, institute type, institute, quota, branch, category, seats) | seat matrices | No |

No column holds a name, roll number, application number or date of birth, in any of the 10 files.

An AIR belongs to exactly one candidate, and top ranks are often published with names elsewhere.
A row-level record (AIR, candidate category, PwD status and college) is therefore
quasi-identifying. Row-level allotments stay in the local database and are never committed. The
oracle scripts keep rows in memory only and print aggregates plus a page and line pointer.

## 4. What "closing rank" means here

Closing rank for (round N, quota, institute, course, allotted category) is the highest
(numerically largest) AIR among rows that received an allotment in round N in that cell.

- Allotted in round N: in Round 1, every row. In Round 2 and 3, rows whose right-most block is
  filled, that is, remarks "Fresh Allotted in 2nd/3nd Round" or "Upgraded", with or without an
  "( NRI Priority ... )" or "( CW Rank ... )" suffix.
- Not counted: rows that keep an earlier seat ("Did not opt for Upgradation.", "No Upgradation"),
  rows not allotted ("Not Allotted."), and rows that did not fill choices. An earlier-round seat
  already counts toward the round in which it was allotted.
- Grouped by allotted category (Open, OBC, EWS, SC, ST, each with or without PwD), not by
  candidate category. An OBC candidate on an Open seat counts toward Open.
- Rank is a decimal, not an integer (see 5.1).
- Per round, not cumulative. Later rounds only re-allot vacated or newly added seats, so a later
  round's closing rank can be lower than an earlier round's. Invented example: a cell closes at
  9,000 in Round 1 from 60 allotments, at 6,500 in Round 2 from 1 allotment, and at 8,200 in
  Round 3 from 2 allotments. Each figure describes only its own round.
- Every answer and predictor output names the round and the number of allotments behind each
  closing rank (hard rule g). A closing rank from one allotment is weak evidence.
- Institute identity. The allotment PDFs have no institute code. Rows are matched on the
  normalised institute string (case- and whitespace-insensitive, because wraps split words, as in
  "TA MIL NADU"). If a name matches more than one institute, the rows are not pooled (see 5.7).
- A cell with no allotment in a round has no closing rank for that round. It is not zero and is
  not carried over from another round. A cell filled entirely in Round 1, with no Round 2 or 3
  allotment, has a Round 1 closing rank only.

## 5. Edge cases in the data

### 5.1 Fractional rank
Ranks can carry a fractional part, for example 12345.5 sitting between 12345 and 12346. One such
rank appears at r1 p287 l53 (and again at r2 p640 l37 and r3 p328 l1). Integer parsing would
truncate it to a duplicate of its neighbour. Rank is stored as numeric, the original text is
kept, and a test pins the case.

### 5.2 Seat surrender
"Seat Surrendered" occurs only in the earlier-round Remarks column of Round 2 and 3, never as a
current-round allotment. Pointers: r2 p19 l27-28 and r3 p12 l75-77, both with an earlier-round
seat and nothing allotted in the current round. The remark wraps as "Seat" / "Surrendered" and can
touch the next cell (r2 p780 l18).

### 5.3 Remark vocabulary and the no-allotment rows
Current-round remarks with no allotment (row counts from the parser, as in section 2):

| First line of remark | Round 2 | Round 3 | Full text when wrapped |
|---|---|---|---|
| "Did not opt" (Round 2) / "Did not opt for" (Round 3) | 8,081 | 13,308 | "Did not opt for Upgradation." |
| "Did not fill up" | 4,507 | 11,168 | "Did not fill up fresh choices." |
| "No" | 3,968 | 3,754 | "No Upgradation" |
| "Not Allotted." | 3,674 | 2,106 | (not wrapped) |

With the allotted rows in section 2, these add up to the row totals (35,551 and 39,479).

Current-round remarks with an allotment: "Allotted" (Round 1), "Fresh Allotted in 2nd Round"
(Round 2), "Fresh Allotted in 3nd Round" (Round 3, sic), "Upgraded" (Round 2 and 3). Each can
carry an "( NRI Priority : n )" or "( CW Rank : n )" suffix. Earlier-round remarks are
"Reported", "Not Reported" and "Seat Surrendered".

Pointers to examples of the no-allotment classes: r2 p19 l29-31, r2 p5 l40-41, r2 p4 l19-20,
r2 p18 l38-39.

The parser matches "no allotment" against this fixed vocabulary. A looser pattern ("six dashes
then any word") drops 7 real Round 3 allotments whose first line ends in dashes followed by the
next cell's "All India" (for example r3 p645 l37-38). The parser also raises an error if a
no-allotment row mentions "Fresh Allotted" or "Upgraded".

### 5.4 Reported / Not Reported
Earlier-round blocks carry a reporting status: "Reported", "Not Reported" (wrapped as "Not" /
"Reported") or "Seat Surrendered". A candidate who did not report can still receive a fresh
allotment later (r3 p48 l4-5). Reporting status does not change the current round's closing rank.

### 5.5 PwD sub-categories
- Allotted categories are Open, OBC, EWS, SC and ST, each optionally PwD. All 10 occur.
- The "PwD" suffix wraps to the next line, left-aligned under its own cell. At r1 p1107 l16-17
  the allotted-category cell shows "OBC" on the first line and "PwD" alone on the next. No Round 1
  row has "Open PwD" on its first line; every one is wrapped.
- Candidate category is spelled differently by round. Round 1 uses "General PwD" (163 rows).
  Round 2 and 3 never use it; the token "GNYes" appears instead (105 and 49 rows). Counts are from
  the parser, as in section 2.
- PwD closing ranks can be very high AIRs and often rest on a single allotment (for example
  r2 p3122 l4). Answers do not present such a figure as typical.

### 5.6 Quotas: deemed, central universities, CW, NRI, institution-specific
- 28 quota names appear in the legend, and Round 1 uses all of them.
- "Open Seat Quota" and "All India" are different quotas. AIIMS, JIPMER, BHU and AMU seats are
  allotted under "Open Seat Quota" (for example r1 p130 l50); other All India Quota government
  seats are "All India". A question that just says "AIQ" is ambiguous between the two.
- Deemed/Paid Seats Quota wraps mid-word ("Deemed/Pa" / "id Seats" / "Quota", r2 p780) or as
  "Deemed/" / "Paid" / "Seats" / "Quota" (Round 3).
- Central-university quotas: Delhi University Quota, IP University Quota, Aligarh Muslim
  University (AMU) Quota, Jamia Internal Quota, Muslim / Muslim OBC / Muslim ST / Muslim Women
  Quota, (AMU) Self finance, Non-Resident Indian(AMU)Quota / (Jamia)Quota, Internal -Puducherry UT
  Domicile, Foreign Country Quota.
- CW quota (Children/Widows of Armed Forces personnel) is allotted in CW-rank order, printed in
  Remarks as "( CW Rank : n )" (for example r1 p164 l18-19). The AIR is still printed, but
  allotment order follows CW rank, so a closing AIR for a CW cell is computable but is not the
  admission criterion.
- NRI rows carry a priority, "( NRI Priority : 1 )" or "( ... : 2 )" (for example r1 p465 l26-27).
  Priority 1 and 2 candidates are allotted in separate tiers, so one closing AIR across them mixes
  tiers.

### 5.7 Institutes with name variants and near-duplicates
- Two seat-matrix institutes can have almost the same name. `seat_matrix_r1_aiq_except_cu.pdf`
  p35 lists two Government Medical College, Anantnag entries with different codes and spellings
  (l24 and l41), each with its own allotments in Round 1. They are separate entries and are never
  merged by fuzzy name.
- One substring can match several institutes. "Kasturba Medical College, Manipal" matches both the
  Mangalore and the Manipal campus strings; "JIPMER" matches JIPMER Puducherry and JIPMER Karaikal;
  "Lady Hardinge Medical College" matches the medical college and its college of nursing. Pooling
  them gives a wrong closing rank, so the oracle refuses ambiguous institute strings (exit 2).
- The same institute can be printed differently per file: a space before a comma in one round and
  not in another, a word split across lines ("TA MIL NADU"), or a short name in earlier-round
  blocks. Whitespace is normalised before matching.
- Some institutes are not in the Round 1 seat matrix. ESIC Medical College & Hospital, Andheri,
  Mumbai first appears in Round 2 (r2 p371 l38-44), matching the archive entry "Newly Added Seats
  Round 2". Some of these strings have no pincode.
- "(Female Seat only )" is part of some institute strings (for example r1 p12 l36-37). It is an
  eligibility restriction, not part of the name.

### 5.8 Other quirks
- The Round 3 remark reads "Fresh Allotted in 3nd Round" (sic) on every fresh row.
- The Round 3 PDF title says "Revised"; it is the final result, issued after the provisional
  results.
- On 18 September 2025 MCC issued a notice withdrawing the Round 2 result for revision, and a
  clarification the same day stating that the result remains unchanged as declared. The Round 2
  file used here is therefore the standing result; its footer timestamp is 17-09-2025 10:38:30 AM.
  Both notices are listed in `data/raw/MANIFEST.md`.
- The seat matrix codes categories differently from the results ("OP NO", "BC PH" against "Open",
  "OBC PwD") and prints some quotas differently (for example "Employees State Insurance
  Scheme(ESI)" split over two lines in the ESIC matrix). The mapping lives in code, with tests.

## 6. Project conventions

1. Derived data. No table derived from MCC files is committed; `data/derived/` is gitignored
   except its README and `.gitkeep`. Every user-facing view of MCC data carries the credit
   "Source: Medical Counselling Committee (MCC), Government of India, mcc.nic.in".
2. Citing real rows in documentation. Committed docs cite rows by pointer (file, page, line) plus
   only quota, institute, course and allotted category. They contain no candidate-category values
   and no remark text from a row.
3. Per-round closing rank, as defined in section 4. Every figure carries its round and allotment
   count (hard rule g).
4. CW and NRI cells.
   - The predictor excludes them. A row is CW or NRI if its quota is a CW quota ("... (CW) DU
     Quota", "... (CW) IP Quota", "B.Sc Nursing ... CW Quota") or an NRI quota ("Non-Resident
     Indian", "...(AMU)Quota", "...(Jamia)Quota"), or if its remark carries "CW Rank" or "NRI
     Priority". The remark test matters: Round 2 and 3 also have rows in the Deemed/Paid Seats
     Quota with an NRI-priority remark (11 in Round 2, 10 in Round 3, counted by the parser as in
     section 2). Without the remark test they would leak into deemed closing ranks.
   - RAG answers may show CW and NRI closing ranks, but only with the caveat that these seats are
     allotted by CW rank or NRI priority, not by AIR, so the AIR figure is not the admission
     cut-off.
5. GNYes. This candidate-category token appears only in Round 2 and 3. It is stored and displayed
   verbatim and is never interpreted, mapped or merged with another category. Closing ranks group
   by allotted category, which never contains it.
6. State comes from the seat matrix. An institute's state is the StateName column of the Round 1
   long-layout seat matrices (AIQ except central universities, AIIMS/BHU/JIPMER, central
   universities), never address text in the allotment PDFs. Because allotment strings carry no
   institute code, `scripts/oracle_seat_matrix.py` matches them to seat-matrix entries:
   - both strings are normalised (lower case, no whitespace);
   - the longest common prefix must cover the institute name plus the first 8 characters of the
     next comma-separated part (the city), so a generic prefix such as
     "governmentmedicalcollege," is not enough;
   - equally good matches in different states are an error, never a guess.

   Coverage, as reported by `scripts/oracle_seat_matrix.py` on the files in
   `data/raw/MANIFEST.md`: 33 states; all 474 Round 1 MBBS/BDS institutes outside the
   deemed, NRI, minority and ESI quotas map to a state. As a cross-check, 473 of the 474 agree with
   the state named in their address (the remaining one names no state), with no disagreements.
   Known gaps, reported and never guessed:
   - B.Sc Nursing colleges: the nursing seat matrix is not among the source files.
   - Deemed and ESIC-IP institutes: the wide-layout matrices have no StateName column.
   - Institutes first added in Round 2 or 3 (for example ESIC Andheri): not in the Round 1 seat
     matrix.

   With a state filter, the predictor lists such institutes as "no seat-matrix state" rather than
   placing them.

   Counts in the database (Postgres, schema `neet`, queried as `neet_reader` on 2026-11-21 after
   ingest of the files in `data/raw/MANIFEST.md`): of 600 institutes, 474 have a seat-matrix state
   (447 from `seat_matrix_r1_aiq_except_cu.pdf`, 23 from `seat_matrix_r1_aiims_bhu_jipmer.pdf`, 4
   from `seat_matrix_r1_central_universities.pdf`) and 126 have none:

   | Institutes with no state | Count | Why |
   |---|---|---|
   | Only Deemed/Paid Seats Quota MBBS/BDS cells | 88 | the deemed seat matrix has no StateName column |
   | MBBS/BDS cells in at least one other quota | 29 | for example ESIC IP; their seat matrix layout carries no state |
   | No MBBS/BDS cells (nursing only) | 9 | the nursing seat matrix is not among the source files |

   Queries:

   ```sql
   SELECT coalesce(state_source, 'null'), (state IS NULL), count(*)
   FROM neet.institute GROUP BY 1, 2;

   -- split of the institutes with no state, by their closing_rank rows
   WITH s AS (
     SELECT i.id,
            count(cr.institute_id) FILTER (WHERE cr.course IN ('MBBS', 'BDS')) AS mbbs_bds,
            count(cr.institute_id) FILTER (WHERE cr.course IN ('MBBS', 'BDS')
                                             AND cr.quota NOT ILIKE '%deemed%') AS non_deemed
     FROM neet.institute i
     LEFT JOIN neet.closing_rank cr ON cr.institute_id = i.id
     WHERE i.state IS NULL
     GROUP BY i.id
   )
   SELECT CASE WHEN mbbs_bds = 0 THEN 'no MBBS/BDS rows'
               WHEN non_deemed = 0 THEN 'Deemed/Paid only'
               ELSE 'other quota' END AS reason,
          count(*)
   FROM s GROUP BY 1;
   ```

## 7. Parser independence

Ingest and the oracle share one parser. The pdftotext and regex parsing lives in one workspace
package, `libs/mccparse` (`neet_mccparse`), imported by both `jobs/ingest` and the
`scripts/oracle_*.py` command-line tools.

With one shared parser, a parsing bug shows up identically in the database and in the oracle, so
agreement between them says nothing about parsing. Comparing the database with the oracle, or
with the golden questions whose values the oracle derived, shows only that loading, the SQL views
and the closing-rank definition are correct. It does not show that the PDFs were read correctly.

Parsing correctness rests on evidence that does not depend on the parser:

| | Evidence | Independent of the parser because |
|---|---|---|
| a | Seat-matrix reconciliation. Round 1 allotments per cell against seats in MCC's seat-matrix PDFs, over all matched cells; allotments above seats must be zero or explained. | It uses a different MCC document with its own layout. A parser that drops, duplicates or mis-assigns rows breaks the counts. |
| b | Keyword-count reconciliation. Database counts of "Fresh Allotted" and "Upgraded" allotments against a plain grep of the pdftotext output; row counts against gap-free SNo runs (Round 1 and 2) and strictly increasing ranks. | A grep has no column logic. It catches rows the parser skips or misclassifies (the 7 Round 3 rows in section 5.3 were caught this way). |
| c | Manual checks. `SPOTCHECK.md` in `eval/golden/`: a person opens the PDF at file, page and SNo and reads the cell. | No software is involved. |
| d | PDF re-extraction of cited lines. For a random sample of closing-rank cells, pdftotext is re-run on the stored file and page to confirm the stored rank appears on the stored line. | It checks each stored provenance pointer against the source, not against the parser's output. |

Checks (a), (b) and (d) are re-run after every parser change (`uv run python -m neet_ingest.report`),
and (c) is repeated whenever a golden value is amended. If stronger guarantees are needed, a
second parser (for example pdfplumber word boxes) can be added for cross-checking only.
