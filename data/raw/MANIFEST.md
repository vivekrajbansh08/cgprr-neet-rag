# Raw source manifest

The PDFs under `data/raw/` are not committed. Each one is listed here so anyone can fetch the same
file and check it against its sha256. `scripts/fetch_sources.sh` re-downloads every file below to
the same path and verifies the sha256 (`--force` re-downloads even if present).

## NEET-UG 2025, All India Quota counselling (MCC, UG Medical)

Why 2025: on 2026-11-20 the UG page (https://mcc.nic.in/ug-medical-counselling/) still shows the
2026 cycle in progress ("Registration and choice filling for Special Stray Round is available
now"), so 2026 is not completed. 2025 is the most recent completed cycle: the archive
(https://mcc.nic.in/archive-ug/) lists Rounds 1, 2, 3, the Stray Vacancy round, the Special Stray
round (final result Dec 2025) and BDS/B.Sc Nursing Rounds 5 and 6 (Jan 2026).

**Listing page for every file:** https://mcc.nic.in/archive-ug/ (the PDFs themselves are served from
MCC's government CDN `cdnbbsr.s3waas.gov.in`, which the official page links to directly).
**Base URL:** `https://cdnbbsr.s3waas.gov.in/s3e0f7a4d0ef9b84b83b693bbf3feb8e6e/uploads/`

All files first retrieved 2026-11-20 between 19:51:32 and 19:51:44 IST (+05:30) with a scripted
`curl` (no captcha, WAF or 403). They were re-downloaded with `scripts/fetch_sources.sh --force`
at 20:11:38–20:11:40 IST the same day, and every sha256 was identical.

| Local file (`data/raw/mcc/2025/…`) | Link text on archive page | URL (after base) | Retrieved (IST) | Bytes | Pages | sha256 |
|---|---|---|---|---|---|---|
| `r1_allotment_final.pdf` | Final Result for Round-I of NEET UG Counselling 2025 | `2025/08/20250813289226788.pdf` | 2026-11-20 19:51:32 | 4123031 | 1107 | `95c607c2dbd784c1c0b0a386e9859a022dea36522fc6931727ed9cb67869a8f0` |
| `r2_allotment_final.pdf` | Final Result for Round 2 of UG Counselling 2025 | `2025/09/202509182057444522.pdf` | 2026-11-20 19:51:33 | 9808078 | 3237 | `a4575f18bf6cffe64f603203a16f4b59904046206002b30d10b2d39a2c0980eb` |
| `r3_allotment_final.pdf` | Final Allotment Result for Round 3 of UG Counselling 2025 | `2025/10/202510231856675154.pdf` | 2026-11-20 19:51:34 | 8917291 | 1930 | `6d670410f5100ab341a29e108b0f3c65ae5c0edfb515fdcf7cae4fa183d807c6` |
| `seat_matrix_r1_aiq_except_cu.pdf` | FINAL SEAT MATRIX FOR ALL INDIA QUOTA EXCEPT CENTRAL UNIVERSITY ROUND 1 UG 2025 (MBBS & BDS) | `2025/07/2025080440.pdf` | 2026-11-20 19:51:35 | 1095532 | 149 | `5d8f0b73bc58c907f898e7c43eb9ecb32336cb42ad365c47780b48cda3af9731` |
| `seat_matrix_r1_aiims_bhu_jipmer.pdf` | FINAL SEAT MATRIX FOR AIIMS/BHU/JIMPER ROUND 1 UG 2025 (MBBS & BDS) | `2025/07/2025072378.pdf` | 2026-11-20 19:51:36 | 498278 | 14 | `89567f15ee0e2c942b2805198662e534b85bd5ac4c8709f8a70d12e201e491ca` |
| `seat_matrix_r1_central_universities.pdf` | FINAL SEAT MATRIX FOR CENTRAL UNIVERSITIES (DU/IP/BHU/JAMIA/AMU) ROUND 1 UG 2025 (MBBS & BDS) | `2025/07/2025072341.pdf` | 2026-11-20 19:51:35 | 470136 | 9 | `04b3348087e12fb05b3e0009e44c3fc376f875ac0ce7749409e8b18593d2ed85` |
| `seat_matrix_r1_deemed.pdf` | FINAL SEAT MATRIX FOR DEEMED UNIVERSITIES ROUND 1 UG 2025 (MBBS & BDS) | `2025/07/2025072244.pdf` | 2026-11-20 19:51:36 | 466927 | 6 | `73e9d3d5307288dc6e61d94dd9453401217240dd9a226104a5c5f1c4975491e4` |
| `seat_matrix_r1_esic_ip.pdf` | FINAL SEAT MATRIX FOR ESIC IP ROUND 1 UG 2025 (MBBS & BDS) | `2025/07/2025072276.pdf` | 2026-11-20 19:51:36 | 430693 | 1 | `c7b806c540f79b4743fa8b17e144eee321d5b52539d8c2b5eb37ed063a28df13` |
| `notices/r2_result_revision_notice.pdf` | Notice for revision of result of UG Round II | `2025/09/202509181478352888.pdf` | 2026-11-20 19:51:43 | 341791 | 1 | `5c8a5d46078e086f6cc9d0c9cfa6463b2b01d87d7c7f5fd6ef91bd8b421bab5d` |
| `notices/r2_result_clarification_notice.pdf` | Notice for clarification regarding UG Round-2 Result, 2025 | `2025/09/20250918502693653.pdf` | 2026-11-20 19:51:44 | 343081 | 1 | `f2866434f3388fcc480cea000381756a5d10638d695b4a7cff76bd315ce7de93` |

Page counts are from `pdfinfo`. Bytes are from `stat`. sha256 is from `shasum -a 256`.

Notes on the files:
- The Round 2 result went through a withdraw-and-restore episode, so it is worth checking that the
  PDF above is the result that stands. The revision notice (Ref. U-11011/07/2025-MEC, 18.09.2025)
  said the Round 2 result "is being withdrawn for revision". The clarification notice the same day
  (Ref. U-11011/07/2025-MEC-(UG R2)) superseded it: "the result remains unchanged as declared on
  18.09.2025 at 11:40 AM". So the Round 2 PDF above is the standing result. Both notices are kept
  as evidence.
- The Round 3 PDF is titled "Revised NEET-UG Counselling Seats Allotment -2025 Round 3". The
  archive also lists "Revised Provisional Result-II for Round 3", which was not downloaded: it is
  provisional, and the final result supersedes it.
- The seat matrices are the Round 1 final seat matrices. Later rounds publish vacancy lists
  ("Clear Vacancy" / "Virtual Vacancy" Round 2 and 3, "Newly Added Seats Round 2") rather than a
  full seat matrix. Those were not downloaded in this step. The B.Sc Nursing Round 1 seat matrix
  (`2025/07/2025072473.pdf`) was not downloaded either, because the request was MBBS/BDS-focused.
- Not downloaded: Stray Vacancy round and Special Stray round results (`2025/11/2025111596488171.pdf`,
  `2025/12/202512231822103663.pdf`), and BDS/B.Sc Nursing Round 5 (`2026/01/202601031185987538.pdf`).
  They exist if later work needs them.

## Licence / terms found on the source page

On the listing page (https://mcc.nic.in/archive-ug/) itself there is no licence statement, only
the footer: "Content Owned and Managed by Medical Counselling Committee (MCC) Developed and hosted
by National Informatics Centre, Ministry of Electronics & Information Technology, Government of
India". The footer links to the site's policies, quoted below (retrieved 2026-11-20).

https://mcc.nic.in/copyright-policy/:
> "Material featured on this site may be reproduced free of charge after taking proper permission
> from Medical Counselling Committee (MCC). This is subject to the material being reproduced
> accurately and not being used in a derogatory manner or in a misleading context. Wherever the
> material is being published or issued to others, the source must be prominently acknowledged.
> However, the permission to reproduce this material does not extend to any material on this site,
> which is explicitly identified as being the copyright of Medical Counselling Committee (MCC) or
> third party. Authorization to reproduce such material must be obtained from the
> departments/copyright holders concerned."

https://mcc.nic.in/terms-and-conditions/:
> "Though all efforts have been made to ensure the accuracy of the content on this website, the
> same should not be construed as a statement of law or used for any legal purposes. In case of any
> ambiguity or doubts, users are advised to verify/check with the Medical Counselling Committee
> (MCC) and/or other source(s), and to obtain appropriate professional advice."

The PDFs carry no licence text of their own: a case-insensitive search of the full
`pdftotext` output of all 10 files for "copyright", "licence/license", "terms of use" and
"reproduc" finds nothing. Implication for this repo: the raw PDFs are not redistributed (gitignored).
Committing derived aggregates or quoted excerpts is "reproduction" in the policy's terms. That
needs a decision by the repo owner (see the report for this step).
