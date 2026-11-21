// Readable institute label from MCC's full display_name (name joined to its address).
// Mirrors services/retrieval/src/neet_retrieval/names.py name_part / short_name; keep the two in step.

const NAME_JOIN = /\s+,|,(?=\S)/;

const ADDRESS_WORDS = new Set([
  "road", "rd", "lane", "nagar", "street", "st", "po", "post", "near", "opp", "district", "dist",
  "pin", "campus", "sector", "plot", "block", "floor", "office", "dean", "principal", "the",
  "admission", "cell", "phase", "marg", "salai", "village", "via", "taluk", "tehsil",
]);

const hasDigit = (s: string) => /\d/.test(s);
const words = (s: string) => s.toLowerCase().match(/[a-z]+/g) ?? [];

function shortName(display: string, maxParts = 3): string {
  const parts: string[] = [];
  for (const part of display.split(",")) {
    const p = part.trim();
    if (!p || hasDigit(p) || parts.length === maxParts) break;
    if (parts.length && p.split(/\s+/)[0].toLowerCase() === parts[0].split(/\s+/)[0].toLowerCase()) break;
    parts.push(p);
  }
  return parts.length ? parts.join(", ") : display.replace(/\d/g, "").trim();
}

function cityLike(part: string, name: string): boolean {
  const w = words(part);
  const first = words(name).slice(0, 1);
  return w.length > 0 && w.length <= 3 && !hasDigit(part) && w[0] !== first[0] && !w.some((x) => ADDRESS_WORDS.has(x));
}

/** "AIIMS, Deogarh ,AIIMS Deoghar Devipur, …" -> "AIIMS, Deogarh". */
export function namePart(display: string): string {
  const m = NAME_JOIN.exec(display);
  if (!m) return shortName(display).trim();
  let name = display.slice(0, m.index).trim();
  if (!name.includes(",")) {
    const next = display.slice(m.index + m[0].length).split(",", 1)[0].trim();
    if (cityLike(next, name)) name = `${name}, ${next}`;
  }
  return name;
}
