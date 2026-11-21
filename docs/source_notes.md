# Source notes: MCC NEET-UG 2025 allotment results and seat matrices

> **Source: Medical Counselling Committee (MCC), Government of India, mcc.nic.in**
>
> MCC's copyright policy allows reproduction only "after taking proper permission" (quoted in
> `data/raw/MANIFEST.md`). This repo therefore commits neither MCC's files nor tables derived
> from them. Everything is rebuilt locally (`scripts/fetch_sources.sh`, then ingest); see
> project rule d and `data/derived/README.md`. Rows below are cited by pointer
> (file, page, line, SNo/rank), never copied.

Evidence-based notes on the raw files listed in `data/raw/MANIFEST.md`. Every claim below was
checked against `pdftotext -layout` output (poppler). "p" = PDF page, "l" = line number within
that page's `pdftotext -layout` text. Quotes are verbatim, with runs of spaces shortened.

## 1. Files and their table layouts

### Allotment results

| File | Pages | Title on page 1 | Table starts | Footer |
|---|---|---|---|---|
| `r1_allotment_final.pdf` | 1107 | "NEET-UG Counselling Seats Allotment -2025 Round 1" | p3 | none |
| `r2_allotment_final.pdf` | 3237 | "NEET-UG Counselling Seats Allotment -2025 Round 2" | p3 | "Page No. N   17-09-2025 10:38:30 AM" |
| `r3_allotment_final.pdf` | 1930 | "Revised NEET-UG Counselling Seats Allotment -2025 Round 3" | p2 | "Page No. N   23-10-2025 12:13:37 PM" |

Pages 1–2 hold two legends: "Quota Abbrevation" (28 quotas: code + description) and "Allotted
Category Abbrevations" (BC, BC PwD, EW, EW PwD, GN, GN PwD, SC, SC PwD, ST, ST PwD). They also
carry a note about candidates whose category or quota changed within the same institute. The
table itself prints quota and category in words, not codes.

**Exact column headers** (header row printed once, on the first table page only):

- Round 1 (8 columns), r1 p3 l3–4:
  `SNo | Rank | Allotted Quota | Allotted Institute | Course | Alloted Category | Candidate Category | Remarks`
- Round 2 (13 columns, two blocks), r2 p3 l2–6:
  `SNo | Rank |` **Round 1:** `Allotted Quota | Allotted Institute | Course | Remarks |`
  **Round 2:** `Allotted Quota | Allotted Institute | Course | Alloted Category | candidate Category | option No. | Remarks`
- Round 3 (16 columns, three blocks, **no SNo**), r3 p2 l2–5:
  `Rank |` **Round 1:** `Allotted Quota | Allotted Institute | Course | Remarks |`
  **Round 2:** `Allotted Quota | Allotted Institute | Course | Remarks |`
  **Round 3:** `Allotted Quota | Allotted Institute | Course | Alloted Category | candidate Category | option No. | Remarks`

In R2 and R3 the earlier-round blocks show where the candidate stood before this round: seat,
course and a reporting remark. Only the right-most block is the allotment made in this round.
The earlier-round blocks use a short institute name ("AIIMS, New Delhi"). The current-round block
uses name + address ("AIIMS, New Delhi ,AIIMS ANSARI NAGAR EAST AUROBINDO MARG NEW DELHI 110029,
Delhi (NCT), 110029").

### Seat matrices (Round 1, MBBS & BDS)

Two layouts:

- **Long** (one row per institute × quota × course × category):
  `StateName | InstituteType | Institute | Quota | Branch | Category | TotalSeats`. Used by
  `seat_matrix_r1_aiq_except_cu.pdf` (2617 rows, 8860 seats), `seat_matrix_r1_aiims_bhu_jipmer.pdf`
  (215 rows, 2600 seats) and `seat_matrix_r1_central_universities.pdf` (115 rows, 1272 seats).
  Branch is printed as "MBBS (MBBS)" / "BDS (BDS)". Category is a two-letter code plus NO/PH, e.g.
  "OP NO", "BC PH", "EW NO". OP = Open, BC = OBC, EW = EWS, PH = PwD.
- **Wide** (one row per institute × course × quota, one column per category):
  `Institute Type | Institute | Program | Quota | Open | Open PwD | General-EWS | General-EWS PwD | OBC | OBC PwD | SC | SC PwD | ST | ST PwD | TotalSeats`.
  Used by `seat_matrix_r1_deemed.pdf` (153 rows, 13939 seats) and `seat_matrix_r1_esic_ip.pdf`
  (11 rows, 474 seats).

The seat matrix gives each institute a **6-digit code in parentheses**, e.g. "(200631)". The
allotment results carry no institute code. The seat-matrix row counts above come from a regex
over the layout text (branch + category + number at line end, or 11 numbers at line end for the
wide layout). They are a profile, not yet a validated parse.

## 2. How rows wrap, and how they were counted

- One row = one candidate. Each row starts on a line whose first token (indent ≤ 2 characters)
  is `SNo Rank` (R1, R2) or `Rank` (R3). Cells that do not fit wrap onto following lines
  **within their own column**: quota ("Deemed/Paid Seats" / "Quota"), institute + address (up to
  10 lines in R2/R3), remarks ("Did not opt" / "for" / "Upgradation."), and PwD ("OBC" / "PwD").
- **Rows never break across pages.** The first row of every page is preceded by a form feed
  (`\f`). A row-start regex that does not allow for this misses exactly one row per page; the
  first attempt hit this (1104 SNo gaps in R1).
- Narrow columns wrap **mid-word**: "Deemed/Pa" / "id Seats" / "Quota" (r2 p780 l17–19). Adjacent
  cells sometimes touch with one space, or with **no space at all**:
  "Internal -PuducherryJIPMER PUDUCHERRY" (r1 p772 l28), "ResidentMedical Sciences" (r3 p1675),
  "QuotaPillaiyarkuppam" (r3 p1823). Splitting on runs of 2+ spaces is therefore not enough to
  separate cells.
- Occasionally a cell sits one line **above** the rest of its row: r2 p2833 l37 has "Jain
  Minority" on the rank line, while institute, course, categories and remarks start on the next line.
- A whitespace-gutter column detector gave the wrong column count on most pages (centred
  multi-line cells and touching cells). The oracle anchors on fixed vocabularies instead
  (`scripts/oracle_parse.py` docstring).

**Row counts.** Method: count row-start lines as defined above (form feed stripped; rank pattern
`\d+(\.\d+)?`).

| Round | Rows (candidates) | Check | Allotments made in this round |
|---|---|---|---|
| 1 | 26,608 | SNo runs 1..26608 with no gap; ranks strictly increasing | 26,608 (every row is "Allotted") |
| 2 | 35,551 | SNo runs 1..35551 with no gap; ranks strictly increasing | 15,321 = 12,901 "Fresh Allotted in 2nd Round…" + 2,420 "Upgraded…" |
| 3 | 39,479 | no SNo; ranks strictly increasing (39,478 consecutive pairs) | 9,143 = 5,529 "Fresh Allotted in 3nd Round…" + 3,614 "Upgraded…" |

Rows with no allotment in this round: R2: "Did not opt for Upgradation." 8,081; "Did not fill
up fresh choices." 4,507; "No Upgradation" 3,968; "Not Allotted." 3,674 (sum + allotted = 35,551).
R3: 13,308 / 11,168 / 3,754 / 2,106 respectively (sum + allotted = 39,479). Every row falls in
exactly one class; the oracle raises an error on any row it cannot classify.

Independent reconciliation:
- Allotment counts equal a plain `grep` of "Fresh Allotted" and "Upgraded" lines in each file.
- Round 1 allotments per cell equal the seat-matrix seats for every cell sampled. AIIMS New Delhi,
  Open Seat Quota, MBBS: OP NO 48 / BC NO 33 / SC NO 18 seats vs 48 / 33 / 18 allotments. Madras
  Medical College, All India, MBBS: OP NO 14 / BC NO 10 / SC NO 6 vs 14 / 10 / 6.

## 3. Personal-data check (every column)

| Column | Present in | Identifies a person? |
|---|---|---|
| SNo | R1, R2 | No (row number) |
| Rank (NEET AIR) | all | Not directly, but see note |
| Allotted Quota / Institute / Course | all | No |
| Remarks (earlier-round blocks: Reported / Not Reported / Seat Surrendered) | R2, R3 | No |
| Alloted Category | all | No |
| Candidate Category (incl. PwD status) | all | No by itself; sensitive (disability, caste) when linked to a rank |
| option No. (choice number) | R2, R3 | No |
| Remarks (incl. "NRI Priority : n", "CW Rank : n") | all | No |
| Seat-matrix columns (state, institute type, institute, quota, branch, category, seats) | seat matrices | No |

**No column holds a name, roll number, application number or date of birth.** None was found in
any of the 10 files.

Note: an AIR belongs to exactly one candidate, and top ranks are often publicised with names
elsewhere. A row-level record (AIR + candidate category + PwD status + college) is therefore
quasi-identifying. Row-level allotments, including AIR and candidate category, stay in the local
DB and are never committed. Derived aggregates are not committed either (MCC copyright, project rules
rule d). The oracle keeps rows in memory only and prints aggregates plus a page/line pointer.

## 4. What "closing rank" means here

**Closing rank (round N, quota, institute, course, allotted category)** = the highest (numerically
largest) AIR among rows that received an allotment **in round N** in that cell.

- *Allotted in round N*: R1, every row. R2/R3, rows whose right-most block is filled, i.e. remarks
  "Fresh Allotted in 2nd/3nd Round" or "Upgraded", with or without an "( NRI Priority … )" or
  "( CW Rank … )" suffix.
- *Not* counted: rows that keep an earlier seat ("Did not opt for Upgradation.", "No
  Upgradation"), rows not allotted ("Not Allotted."), and rows that did not fill choices. Their
  earlier-round seat already counted toward that earlier round.
- Grouped by **allotted** category (Open, OBC, EWS, SC, ST, each with or without PwD), not by
  candidate category. Example: an OBC candidate on an Open seat counts toward Open.
- Rank is a decimal, not an integer (see 5.1).
- **Per round, not cumulative.** Later rounds only re-allot vacated or newly added seats, so a
  later round's closing rank can be *lower* than an earlier round's:
  - Lady Hardinge Medical College, Delhi University Quota, MBBS, Open: R1 5577 (70 allotments),
    R2 3108 (1), R3 4860 (1).
  - Kasturba Medical College, Manipal Univ., Manipal, Deemed/Paid Seats Quota, MBBS, Open: R1 40008
    (212), R2 43835 (57), R3 31834 (5).

  Hard rule (project rule g): every answer and predictor output names the round and the number
  of allotments behind each closing rank. A closing rank from one allotment is weak evidence.
- **Institute identity.** Allotment PDFs have no institute code. Match on the normalised institute
  string (case- and whitespace-insensitive, because wraps split words: "TA MIL NADU"). If a name
  matches more than one institute, do not pool the rows (see 5.6). Ingest should map each
  allotment institute to the seat-matrix code.
- A cell with no allotment in a round has **no** closing rank for that round. It is not zero and
  not carried over. Example: AIIMS New Delhi, Open Seat Quota, MBBS, Open has R1 48 and no R2 or R3
  allotment.

## 5. Edge cases seen in the real data

Quotes below are pointers, not copies: file, page, line and SNo/rank, plus only the fields needed
to make the point (quota, institute, course, allotted category). Candidate-category values and
remark text from individual rows are not reproduced. Remark *vocabulary* is listed separately in
5.3, with counts only.

### 5.1 Fractional rank
Pointer: `r1 p287 l53`, SNo 7265, rank **13767.5**. All India, Govt Medical College Shivpuri, MBBS,
allotted EWS. The same rank also appears at r2 p640 l37 and r3 p328 l1, between ranks 13767 and
13768. Integer rank parsing truncates it to a duplicate 13767. Store rank as numeric, keep the
original text, and test this case.

### 5.2 Seat surrender
Pointers: `r2 p19 l27–28` (SNo 288, rank 290) and `r3 p12 l75–77` (rank 290). Both have an
earlier-round seat of Open Seat Quota, AIIMS Bhubaneswar, MBBS, and nothing allotted in the current
round.

"Seat Surrendered" occurs only in the earlier-round Remarks column (264 lines in R2, 726 in R3).
It wraps as "Seat" / "Surrendered" and can touch the next cell (r2 p780 l18, where "Surrendered"
abuts the next block's quota text). It never appears as a current-round allotment.

### 5.3 Remark vocabulary (counts only) and the no-allotment rows
Current-round remarks with **no allotment** (row counts; R2 / R3):

| First line of remark | R2 | R3 | Full text when wrapped |
|---|---|---|---|
| "Did not opt" (R2) / "Did not opt for" (R3) | 8,081 | 13,308 | "Did not opt for Upgradation." |
| "Did not fill up" | 4,507 | 11,168 | "Did not fill up fresh choices." |
| "No" | 3,968 | 3,754 | "No Upgradation" |
| "Not Allotted." | 3,674 | 2,106 | — |

Current-round remarks **with an allotment**: "Allotted" (R1), "Fresh Allotted in 2nd Round" (R2),
"Fresh Allotted in 3nd Round" (R3, sic), "Upgraded" (R2, R3). Each can carry an "( NRI Priority :
n )" or "( CW Rank : n )" suffix. Earlier-round remarks (R2, R3): "Reported", "Not Reported",
"Seat Surrendered".

Pointers to examples of the no-allotment classes: r2 p19 l29–31 (SNo 289, rank 291), r2 p5 l40–41
(SNo 49, rank 49), r2 p4 l19–20 (SNo 23, rank 23), r2 p18 l38–39 (SNo 273, rank 274).

R2 prints "Did not opt" on the first line; R3 prints "Did not opt for" (r3 p2 l5). A pattern for
"no allotment" must use this fixed vocabulary. A looser pattern ("six dashes then any word")
silently dropped 7 real R3 allotments, whose first line ends in dashes followed by the next
cell's "All India" (e.g. r3 p645 l37–38, rank 32738). The oracle now also errors if a "no
allotment" row mentions "Fresh Allotted" or "Upgraded".

### 5.4 Reported / Not Reported
Earlier-round blocks carry a reporting status ("Reported", "Not Reported", wrapped as "Not" /
"Reported", or "Seat Surrendered"). Pointer `r2 p11 l20–22` (SNo 148, rank 148): earlier seat Open
Seat Quota, AIIMS-Bhopal, MBBS; current-round allotment IP University Quota, Atal Bihari Vajpayee
Institute of Medical Sciences & Dr RML, MBBS, allotted Open. A candidate who did not report can
still get a fresh allotment later: pointer `r3 p48 l4–5` (rank 1277), whose Round 3 allotment is
All India, Madurai Medical College, MBBS, allotted Open. Reporting status does not change the
current round's closing rank.

### 5.5 PwD sub-categories
- Allotted categories: Open, OBC, EWS, SC, ST, each optionally "PwD". Every one of the 10 occurs.
- The "PwD" suffix wraps to the next line, left-aligned under its own cell. Pointer `r1 p1107
  l16–17` (SNo 26604): B.Sc Nursing All India, College of Nursing BHU Varanasi, B.Sc. Nursing,
  allotted **OBC PwD**. The first line shows "OBC" in the allotted-category cell; "PwD" sits alone
  on the next line under it. No R1 row has "Open PwD" on its first line; all 260 are wrapped.
- **Candidate category is spelled differently by round:** R1 uses "General PwD" (163 rows). R2 and
  R3 never use "General PwD"; instead the token "GNYes" appears (105 and 49 rows). Counts only, no
  row pointer.
- PwD closing ranks run to very high AIRs: AIIMS New Delhi, Open Seat Quota, MBBS, allotted ST
  PwD, R2 closing rank 785618 (pointer `r2 p3122 l4`, SNo 34309, a single allotment). The answer
  layer should not present such a figure as typical.

### 5.6 Quotas: deemed, central universities, CW, NRI, institution-specific
- 28 quota names appear in the legend; R1 uses all 28. Most rows: Deemed/Paid Seats Quota
  (12,367), All India (8,791), Open Seat Quota (2,697), Non-Resident Indian (548), Delhi
  University Quota (545), Employees State Insurance Scheme(ESI) (451).
- **"Open Seat Quota" vs "All India".** AIIMS, JIPMER, BHU and AMU seats are allotted under "Open
  Seat Quota". Other AIQ government seats are "All India". `r1 p130 l50` shows Jawaharlal Nehru
  Medical College, AMU under Open Seat Quota. Questions that just say "AIQ" are ambiguous between
  the two.
- **Deemed/Paid Seats Quota** wraps mid-word ("Deemed/Pa" / "id Seats" / "Quota", r2 p780) or as
  "Deemed/" / "Paid" / "Seats" / "Quota" (R3).
- **Central-university quotas**: Delhi University Quota, IP University Quota, Aligarh Muslim
  University (AMU) Quota, Jamia Internal Quota, Muslim / Muslim OBC / Muslim ST / Muslim Women
  Quota, (AMU) Self finance, Non-Resident Indian(AMU)Quota / (Jamia)Quota, Internal -Puducherry UT
  Domicile, Foreign Country Quota.
- **CW quota (Children/Widows of Armed Forces personnel)** is allotted in CW-rank order, printed
  in Remarks as "( CW Rank : n )". Pointer `r1 p164 l18–19` (SNo 4231, rank 5650): Delhi NCR
  Children/Widows of Personnel of the Armed Forces (CW) DU Quota, University College of Medical
  Sciences, MBBS, allotted OBC. The AIR is still printed, but allotment order is CW rank. A "closing
  AIR" for a CW cell is computable, but it is not the admission criterion.
- **NRI** rows carry a priority, "( NRI Priority : 1 )" or "( … : 2 )". Pointer `r1 p465 l26–27`
  (SNo 11504, rank 54284): Non-Resident Indian, Kasturba Medical College, Manipal Univ., Manipal,
  MBBS, allotted Open. Priority 1 and 2 candidates are allotted in separate tiers, so one closing AIR
  across them mixes tiers.

### 5.7 Institutes with name variants and near-duplicates
- **Two seat-matrix institutes with almost the same name.** `seat_matrix_r1_aiq_except_cu.pdf p35`:
  "Government Medical College, Anantnag, verinag Road Dialgam Anantnag 192210 (200631)" (l24) and
  "GOVERNMENT MEDICAL COLLEGE, ANANTNAG J&K, VERINAG ROAD DIALGAM ANANTNAG (200684)" (l41). Each
  has 15 All India MBBS seats, and R1 has 15 allotments under each string (first at r1 p189 l24
  and r1 p245 l11). These are separate entries; do not merge them by fuzzy name.
- **One substring, several institutes.** "Kasturba Medical College, Manipal" matches both
  "Kasturba Medical College, Manipal Univ., Mangalore, …" and "…, Manipal Univ., Manipal, …".
  "JIPMER" matches "JIPMER PUDUCHERRY" and "JIPMER KARAIKAL". "Lady Hardinge Medical College"
  matches the medical college and "College of Nursing LHMC". Pooling them gives a wrong closing rank
  (Kasturba Deemed Open R1: 52466 pooled vs 40008 Manipal alone). The oracle refuses ambiguous
  institute strings (exit 2).
- **Same institute, different string per file.** R1 "AIIMS, New Delhi,AIIMS ANSARI NAGAR …" vs R2
  "AIIMS, New Delhi , AIIMS ANSARI NAGAR …" (space before comma). R2 also splits a word across lines
  ("TA MIL NADU"). In earlier-round blocks the same institute appears under a short name ("AIIMS,
  New Delhi", "GOVERNMENT MEDICAL COLLEGE ,MEDAK"). Normalise whitespace before matching.
- **Institutes not in the Round 1 seat matrix.** ESIC Medical College & Hospital, Andheri, Mumbai
  first appears in R2 (`r2 p371 l38–44`) and never in R1. This matches the archive entry "Newly
  Added Seats Round 2". Some such R2/R3 strings have no pincode ("…, Andheri(East), Mumbai").
- **"(Female Seat only )"** is part of some institute strings: `r1 p12 l36–37` "Lady Hardinge Medical
  College, New Delhi, … 110001 (Female Seat only )". It is an eligibility restriction, not part
  of the name.

### 5.8 Other quirks
- The R3 remark reads "Fresh Allotted in **3nd** Round" (sic) on all 5,529 fresh rows.
- The R3 PDF title says "Revised"; it is the final result after "Revised Provisional Result-II".
- The R2 result was withdrawn and then restored the same day (see MANIFEST notes). The standing
  file was generated "17-09-2025 10:38:30 AM" per its footer.
- The seat matrix codes categories differently from the results ("OP NO", "BC PH" vs "Open", "OBC
  PwD") and prints quotas differently ("All India" in the AIQ matrix, "Employees State Insurance
  Scheme(ESI)" split over two lines in the ESIC matrix). A mapping table is needed; keep it in code
  with tests.

## 6. Decisions (approved 2026-11-20)

1. **Copyright.** No derived table is committed. `data/derived/` is gitignored except its README.
   Every user-facing view of MCC data carries the credit "Source: Medical Counselling Committee
   (MCC), Government of India, mcc.nic.in".
2. **Real rows.** Committed docs cite rows by pointer (file, page, line, SNo/rank) plus only quota,
   institute, course and allotted category. No candidate-category values, no remark text from a
   row.
3. **Per-round closing rank.** As section 4. Every figure carries its round and allotment count
   (project rule g).
4. **CW and NRI cells.**
   - *Predictor:* excludes them entirely. A row is CW/NRI if its quota is a CW quota ("… (CW) DU
     Quota", "… (CW) IP Quota", "B.Sc Nursing … CW Quota") or an NRI quota ("Non-Resident
     Indian", "…(AMU)Quota", "…(Jamia)Quota"), **or** its remark carries "CW Rank" or "NRI
     Priority". The remark test matters: R2 and R3 also have rows in the **Deemed/Paid Seats
     Quota** with an NRI-priority remark (11 in R2, 10 in R3). Without it they would leak into
     deemed closing ranks.
   - *RAG answers* may show CW/NRI closing ranks, but only with the caveat that these seats are
     allotted by CW rank / NRI priority, not by AIR, so the AIR figure is not the admission cut-off.
5. **GNYes.** A candidate-category token seen only in R2 (105 rows) and R3 (49 rows). It is stored
   and displayed verbatim and never interpreted, mapped or merged with any other category.
   (Closing ranks group by *allotted* category, which never contains it.)
6. **State comes from the seat matrix.** An institute's state is the **StateName** column of the
   Round 1 long-layout seat matrices (AIQ except CU, AIIMS/BHU/JIPMER, central universities),
   never address text in the allotment PDFs. Allotment strings carry no institute code, so
   `scripts/oracle_seat_matrix.py` matches them to seat-matrix entries:
   - normalise both strings (lower case, no whitespace);
   - the longest common prefix must cover the institute name plus the first 8 characters of the
     next comma-separated part (the city), so a generic prefix like "governmentmedicalcollege," is
     not enough;
   - equally good matches in different states are an error, never a guess.

   Coverage: 33 states; all 474 R1 MBBS/BDS institutes outside the deemed/NRI/minority/ESI quotas
   map to a state. As a cross-check, 473 of 474 agree with the state named in their address
   (the 474th names no state), with 0 disagreements. Known gaps, reported and never guessed:
   - B.Sc Nursing colleges: the nursing seat matrix was not downloaded.
   - Deemed and ESIC-IP institutes: the wide-layout matrices have no StateName column.
   - Institutes first added in R2/R3 (e.g. ESIC Andheri): not in the Round 1 seat matrix.

   With a state filter, the predictor lists such institutes as "no seat-matrix state" rather than
   placing them.

## 7. Parser independence (decision 2026-11-21)

**Decision:** ingest reuses the oracle parser. The pdftotext + regex parsing that was written as
an independent oracle now lives in one workspace package, `libs/mccparse` (`neet_mccparse`). Both
`jobs/ingest` and the `scripts/oracle_*.py` CLIs import it.

**What this costs.** The original plan was for ingest to use a *different* parser, so that two
implementations agreeing would be evidence. With one shared parser, a parsing bug shows up
identically in the database and in the oracle. A test comparing them would pass, and that
agreement proves nothing about parsing. Comparing the DB against the oracle (or against the
golden questions, whose values the oracle derived) only shows that **loading, SQL views and the
closing-rank definition** are correct. It does not show that the PDFs were read correctly.

**Why it is acceptable.** Parsing correctness rests on evidence that does not depend on the parser:

| | Evidence | Independent of the parser because |
|---|---|---|
| a | **Seat-matrix reconciliation.** Round 1 allotments per cell vs seats in MCC's seat-matrix PDFs, over all matched cells; allotments > seats must be 0 or explained. | A different MCC document, with its own layout. A parser that drops, duplicates or mis-assigns rows breaks the counts. |
| b | **Keyword-count reconciliation.** DB counts of "Fresh Allotted" / "Upgraded" allotments vs a plain grep of the pdftotext output; row counts vs gap-free SNo runs (R1, R2) and strictly increasing ranks. | A grep has no column logic. It catches rows the parser silently skips or misclassifies (the 7 dropped Round 3 rows in section 5.3 were caught this way). |
| c | **Human eye checks.** `SPOTCHECK.md` in the golden folder: a person opens the PDF at file/page/SNo and reads the cell. | No software in the loop. |
| d | **PDF re-extraction of cited lines.** For a random sample of closing-rank cells, re-run pdftotext on the stored file/page and confirm the stored rank appears on the stored line. | Checks every stored provenance pointer against the source, not against the parser's own output. |

Re-run (a), (b) and (d) after every parser change (`uv run python -m neet_ingest.report`), and
repeat (c) whenever a golden value is amended. If a future change needs stronger guarantees,
reintroduce a second parser (e.g. pdfplumber word boxes) for cross-checking only.

