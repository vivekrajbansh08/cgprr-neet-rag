// WCAG 2.x contrast check for every text/background pair the UI actually uses, both themes.
// Run: npm run contrast   (reads the tokens straight from src/index.css)
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const css = readFileSync(path.join(here, "../src/index.css"), "utf8");

function tokens(selector) {
  const block = css.match(new RegExp(`${selector.replace(".", "\\.")}\\s*\\{([^}]*)\\}`))[1];
  return Object.fromEntries([...block.matchAll(/--([\w-]+):\s*(#[0-9a-fA-F]{6})/g)].map((m) => [m[1], m[2]]));
}
const themes = { light: tokens(":root"), dark: tokens(".dark") };

const lum = (hex) => {
  const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const l = c.map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * l[0] + 0.7152 * l[1] + 0.0722 * l[2];
};
const ratio = (a, b) => {
  const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p);
  return (x + 0.05) / (y + 0.05);
};

// [foreground token, background token, kind, where]
// kind: text = 4.5:1, large = 3:1 (>= 24px or >= 18.66px bold), ui = 3:1 (non-text that conveys
// state or identifies a control), exempt = WCAG 1.4.3 / 1.4.11 do not apply.
const PAIRS = [
  ["foreground", "background", "text", "body text, answer text, figures"],
  ["foreground", "surface", "text", "side panel, record, table header"],
  ["foreground", "muted", "text", "active nav item, clarify panel, hover rows"],
  ["text-2", "background", "text", "secondary text, explanations"],
  ["text-2", "surface", "text", "secondary text on record / side panel"],
  ["text-2", "muted", "text", "secondary text in clarify panel"],
  ["label", "background", "text", "small-caps labels, source lines"],
  ["label", "surface", "text", "labels on record / side panel / table header"],
  ["primary-fg", "primary", "text", "primary button text and icon"],
  ["primary", "background", "text", "links, nav icons"],
  ["primary", "surface", "text", "links in record"],
  ["primary", "background", "ui", "focus ring, check icon, send button shape"],
  ["primary", "surface", "ui", "focus ring on side panel / record"],
  ["primary", "muted", "ui", "focus ring on clarify panel / active nav"],
  ["foreground", "muted", "ui", "clarify option buttons (text-identified)"],
  ["placeholder", "background", "exempt", "input placeholder (exempt: WCAG 1.4.3 placeholder/inactive)"],
  ["disabled", "background", "exempt", "disabled controls (exempt: WCAG 1.4.3 inactive UI)"],
  ["border", "background", "exempt", "hairline rules (decorative; state is carried by text)"],
  ["input", "background", "exempt", "input outline (control also identified by label + send button)"],
];
const need = { text: 4.5, large: 3, ui: 3, exempt: 0 };

let failed = 0;
const rows = [];
for (const [name, t] of Object.entries(themes)) {
  for (const [fg, bg, kind, where] of PAIRS) {
    const r = ratio(t[fg], t[bg]);
    const req = need[kind];
    const ok = kind === "exempt" ? "exempt" : r >= req ? "pass" : "FAIL";
    if (ok === "FAIL") failed++;
    rows.push([name, `--${fg} ${t[fg]}`, `--${bg} ${t[bg]}`, r.toFixed(2), kind === "exempt" ? "n/a" : `${req}:1`, ok, where]);
  }
}
const head = ["theme", "foreground", "background", "ratio", "needs", "result", "used for"];
const widths = head.map((h, i) => Math.max(h.length, ...rows.map((r) => r[i].length)));
const line = (r) => "| " + r.map((c, i) => c.padEnd(widths[i])).join(" | ") + " |";
console.log(line(head));
console.log("|" + widths.map((w) => "-".repeat(w + 2)).join("|") + "|");
rows.forEach((r) => console.log(line(r)));
console.log(failed ? `\n${failed} pair(s) FAIL` : "\nAll required pairs pass.");
process.exit(failed ? 1 : 0);
