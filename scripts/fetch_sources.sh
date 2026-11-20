#!/usr/bin/env bash
# Re-download the raw MCC NEET-UG 2025 source PDFs into data/raw/mcc/2025/ and verify each sha256
# against data/raw/MANIFEST.md. Sources are the official MCC CDN only (linked from
# https://mcc.nic.in/archive-ug/); no mirrors.
#
# Usage: scripts/fetch_sources.sh            # download missing files, verify all
#        scripts/fetch_sources.sh --force    # re-download everything, verify all
# Exit status: 0 if every file is present and matches its sha256, 1 otherwise.
set -euo pipefail

cd "$(dirname "$0")/.."
dest=data/raw/mcc/2025
base=https://cdnbbsr.s3waas.gov.in/s3e0f7a4d0ef9b84b83b693bbf3feb8e6e/uploads
force=0
[[ "${1:-}" == "--force" ]] && force=1

# path (relative to $dest) | URL path (relative to $base) | sha256
files=(
  "r1_allotment_final.pdf|2025/08/20250813289226788.pdf|95c607c2dbd784c1c0b0a386e9859a022dea36522fc6931727ed9cb67869a8f0"
  "r2_allotment_final.pdf|2025/09/202509182057444522.pdf|a4575f18bf6cffe64f603203a16f4b59904046206002b30d10b2d39a2c0980eb"
  "r3_allotment_final.pdf|2025/10/202510231856675154.pdf|6d670410f5100ab341a29e108b0f3c65ae5c0edfb515fdcf7cae4fa183d807c6"
  "seat_matrix_r1_aiq_except_cu.pdf|2025/07/2025080440.pdf|5d8f0b73bc58c907f898e7c43eb9ecb32336cb42ad365c47780b48cda3af9731"
  "seat_matrix_r1_aiims_bhu_jipmer.pdf|2025/07/2025072378.pdf|89567f15ee0e2c942b2805198662e534b85bd5ac4c8709f8a70d12e201e491ca"
  "seat_matrix_r1_central_universities.pdf|2025/07/2025072341.pdf|04b3348087e12fb05b3e0009e44c3fc376f875ac0ce7749409e8b18593d2ed85"
  "seat_matrix_r1_deemed.pdf|2025/07/2025072244.pdf|73e9d3d5307288dc6e61d94dd9453401217240dd9a226104a5c5f1c4975491e4"
  "seat_matrix_r1_esic_ip.pdf|2025/07/2025072276.pdf|c7b806c540f79b4743fa8b17e144eee321d5b52539d8c2b5eb37ed063a28df13"
  "notices/r2_result_revision_notice.pdf|2025/09/202509181478352888.pdf|5c8a5d46078e086f6cc9d0c9cfa6463b2b01d87d7c7f5fd6ef91bd8b421bab5d"
  "notices/r2_result_clarification_notice.pdf|2025/09/20250918502693653.pdf|f2866434f3388fcc480cea000381756a5d10638d695b4a7cff76bd315ce7de93"
)

sha256() { shasum -a 256 "$1" | cut -d' ' -f1; }

status=0
for entry in "${files[@]}"; do
  IFS='|' read -r rel url want <<<"$entry"
  path="$dest/$rel"
  mkdir -p "$(dirname "$path")"
  if [[ $force -eq 1 || ! -f "$path" ]]; then
    tmp="$path.part"
    if curl -sS -L --fail --retry 3 --max-time 300 -A 'Mozilla/5.0' -o "$tmp" "$base/$url"; then
      if [[ "$(sha256 "$tmp")" == "$want" ]]; then
        mv "$tmp" "$path"
        echo "fetched  $rel  ($(TZ=Asia/Kolkata date '+%Y-%m-%dT%H:%M:%S%z'))"
      else
        echo "MISMATCH $rel: downloaded file has sha256 $(sha256 "$tmp"), manifest says $want" >&2
        echo "         kept as $tmp for inspection; the source may have been replaced on mcc.nic.in" >&2
        status=1
        continue
      fi
    else
      rm -f "$tmp"
      echo "FAILED   $rel: could not download $base/$url" >&2
      echo "         download it in a browser from that URL and save it as $path" >&2
      status=1
      continue
    fi
  fi
  got=$(sha256 "$path")
  if [[ "$got" == "$want" ]]; then
    echo "ok       $rel"
  else
    echo "MISMATCH $rel: sha256 $got, manifest says $want" >&2
    status=1
  fi
done
exit $status
