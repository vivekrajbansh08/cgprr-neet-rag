# Raw source manifest

Source: Medical Counselling Committee (MCC), Government of India, mcc.nic.in

MCC's material is not redistributed in this repository; scripts/fetch_sources.sh downloads it from mcc.nic.in and verifies each file's sha256.

The files are the NEET-UG 2025 All India Quota counselling results for Rounds 1 to 3, the Round 1 final seat matrices for MBBS and BDS, and two notices about the Round 2 result. 2025 is the most recent completed counselling cycle. All of them are listed on https://mcc.nic.in/archive-ug/ and served from MCC's government CDN, which that page links to directly.

The table below is read by `scripts/fetch_sources.sh` and by the ingest job, which refuses any file whose sha256 does not match. Paths are relative to `data/raw/mcc/2025/`; URLs are relative to the base URL.

**Base URL:** `https://cdnbbsr.s3waas.gov.in/s3e0f7a4d0ef9b84b83b693bbf3feb8e6e/uploads/`

| Local file | Document | URL (after base) | Retrieved (IST) | Bytes | Pages | sha256 |
|---|---|---|---|---|---|---|
| `r1_allotment_final.pdf` | Round 1 allotment result | `2025/08/20250813289226788.pdf` | 2026-11-20 19:51:32 | 4123031 | 1107 | `95c607c2dbd784c1c0b0a386e9859a022dea36522fc6931727ed9cb67869a8f0` |
| `r2_allotment_final.pdf` | Round 2 allotment result | `2025/09/202509182057444522.pdf` | 2026-11-20 19:51:33 | 9808078 | 3237 | `a4575f18bf6cffe64f603203a16f4b59904046206002b30d10b2d39a2c0980eb` |
| `r3_allotment_final.pdf` | Round 3 allotment result | `2025/10/202510231856675154.pdf` | 2026-11-20 19:51:34 | 8917291 | 1930 | `6d670410f5100ab341a29e108b0f3c65ae5c0edfb515fdcf7cae4fa183d807c6` |
| `seat_matrix_r1_aiq_except_cu.pdf` | Round 1 seat matrix, All India Quota except central universities | `2025/07/2025080440.pdf` | 2026-11-20 19:51:35 | 1095532 | 149 | `5d8f0b73bc58c907f898e7c43eb9ecb32336cb42ad365c47780b48cda3af9731` |
| `seat_matrix_r1_aiims_bhu_jipmer.pdf` | Round 1 seat matrix, AIIMS, BHU and JIPMER | `2025/07/2025072378.pdf` | 2026-11-20 19:51:36 | 498278 | 14 | `89567f15ee0e2c942b2805198662e534b85bd5ac4c8709f8a70d12e201e491ca` |
| `seat_matrix_r1_central_universities.pdf` | Round 1 seat matrix, central universities | `2025/07/2025072341.pdf` | 2026-11-20 19:51:35 | 470136 | 9 | `04b3348087e12fb05b3e0009e44c3fc376f875ac0ce7749409e8b18593d2ed85` |
| `seat_matrix_r1_deemed.pdf` | Round 1 seat matrix, deemed universities | `2025/07/2025072244.pdf` | 2026-11-20 19:51:36 | 466927 | 6 | `73e9d3d5307288dc6e61d94dd9453401217240dd9a226104a5c5f1c4975491e4` |
| `seat_matrix_r1_esic_ip.pdf` | Round 1 seat matrix, ESIC insured persons | `2025/07/2025072276.pdf` | 2026-11-20 19:51:36 | 430693 | 1 | `c7b806c540f79b4743fa8b17e144eee321d5b52539d8c2b5eb37ed063a28df13` |
| `notices/r2_result_revision_notice.pdf` | Round 2 result revision notice | `2025/09/202509181478352888.pdf` | 2026-11-20 19:51:43 | 341791 | 1 | `5c8a5d46078e086f6cc9d0c9cfa6463b2b01d87d7c7f5fd6ef91bd8b421bab5d` |
| `notices/r2_result_clarification_notice.pdf` | Round 2 result clarification notice | `2025/09/20250918502693653.pdf` | 2026-11-20 19:51:44 | 343081 | 1 | `f2866434f3388fcc480cea000381756a5d10638d695b4a7cff76bd315ce7de93` |

Page counts are from `pdfinfo`, byte counts from `stat` and fingerprints from `shasum -a 256`. A second download of every file the same day produced identical sha256 values.

## Notes

- Round 2 result. On 18 September 2025 MCC issued a notice that the Round 2 result was being withdrawn for revision (Ref. U-11011/07/2025-MEC). A clarification notice issued the same day (Ref. U-11011/07/2025-MEC-(UG R2)) stated that the result remains unchanged as declared on 18.09.2025 at 11:40 AM. The Round 2 file above is therefore the standing result. Both notices are kept.
- Round 3 result. The file is the final allotment result, titled "Revised NEET-UG Counselling Seats Allotment -2025 Round 3". The earlier provisional result is not included.
- Seat matrices. Only the Round 1 final seat matrices are included. Later rounds publish vacancy lists rather than full seat matrices. The B.Sc. Nursing seat matrix is not included, so nursing institutes have no seat-matrix state.
- Not included: the Stray Vacancy and Special Stray round results and the later BDS and B.Sc. Nursing rounds.
