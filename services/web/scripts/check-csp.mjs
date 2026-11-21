// Verifies the CSP script-src hash in nginx/security-headers.conf matches the inline theme script
// in index.html (source) and dist/index.html (what nginx serves, when built). Run by `npm run build`.
import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const conf = readFileSync(path.join(root, "nginx/security-headers.conf"), "utf8");
const inConf = [...conf.matchAll(/'sha256-([A-Za-z0-9+/=]+)'/g)].map((m) => m[1]);

let bad = 0;
for (const file of ["index.html", "dist/index.html"]) {
  const p = path.join(root, file);
  if (!existsSync(p)) continue;
  const scripts = [...readFileSync(p, "utf8").matchAll(/<script>([\s\S]*?)<\/script>/g)].map((m) => m[1]);
  for (const body of scripts) {
    const h = createHash("sha256").update(body, "utf8").digest("base64");
    const ok = inConf.includes(h);
    if (!ok) bad++;
    console.log(`${ok ? "ok  " : "FAIL"} ${file} inline script sha256-${h}`);
  }
}
if (bad) {
  console.error("CSP hash mismatch: update script-src in nginx/security-headers.conf.");
  process.exit(1);
}
