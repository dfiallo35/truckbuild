/**
 * Per-route client JavaScript budget.
 *
 * Next 16's Turbopack build summary reports which routes prerendered but not how much script
 * each one ships, so the number that actually matters here -- what a phone downloads to make
 * the configurator interactive -- is invisible in CI. This reads it back out of the build.
 *
 * The prerendered HTML is the honest source: whatever `<script src>` it references is what the
 * browser fetches. Sizes are gzipped, because that is what goes over the wire.
 *
 * Run after `pnpm build`, from web/:  node scripts/bundle-budget.mjs
 */

import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { gzipSync } from "node:zlib";
import { join } from "node:path";

const APP_DIR = ".next/server/app";

/**
 * Budgets in KiB, gzipped, for the whole route -- shared framework chunks included.
 *
 * Roughly 170 KiB of every entry here is React plus the Next runtime, which no amount of
 * application discipline removes; the headroom above that floor is the part these numbers
 * are actually guarding. The configurator gets the most because it is the only genuinely
 * interactive route, and it is also the one most worth watching: it is reached on a phone,
 * in a driveway, on a truck's worth of buying intent.
 */
const BUDGETS_KIB = {
  "configurator/bristlecone.html": 210,
  "configurator/bristlecone/request.html": 205,
  "index.html": 205,
  "builds/bristlecone.html": 205,
  "purposes/expedition.html": 205,
  "contact.html": 205,
};

function routeScriptBytes(htmlPath) {
  const html = readFileSync(htmlPath, "utf8");
  const refs = new Set(
    [...html.matchAll(/\/_next\/(static\/[A-Za-z0-9_./-]+\.js)/g)].map((m) => m[1]),
  );

  let gzipped = 0;
  for (const ref of refs) {
    const file = join(".next", ref);
    // A referenced chunk that is not on disk means the manifest and the output disagree,
    // which would silently under-report the budget rather than fail it.
    if (!existsSync(file)) throw new Error(`${htmlPath} references a missing chunk: ${ref}`);
    gzipped += gzipSync(readFileSync(file)).length;
  }

  return { chunks: refs.size, gzipped };
}

if (!existsSync(APP_DIR)) {
  console.error(`No build output at ${APP_DIR}. Run \`pnpm build\` first.`);
  process.exit(1);
}

// Dynamic-segment shells (`configurator/[slug].html`) are the PPR fallbacks and reference no
// scripts of their own; measuring them would report a reassuring 0 KiB for the busiest route
// in the app. Concrete prerendered pages are the ones a visitor actually loads.
const pages = execFileSync("find", [APP_DIR, "-name", "*.html"], { encoding: "utf8" })
  .trim()
  .split("\n")
  .map((path) => ({ path, route: path.slice(APP_DIR.length + 1) }))
  .filter(({ route }) => !route.includes("[") && !route.startsWith("_"))
  .sort((a, b) => a.route.localeCompare(b.route));

const failures = [];
const rows = [];

for (const { path, route } of pages) {
  const { chunks, gzipped } = routeScriptBytes(path);
  const kib = gzipped / 1024;
  const budget = BUDGETS_KIB[route];

  rows.push(
    [
      kib.toFixed(1).padStart(7),
      "KiB gz ",
      String(chunks).padStart(2),
      "chunks ",
      route.padEnd(40),
      budget ? `budget ${budget} KiB` : "",
    ].join(" "),
  );

  if (budget !== undefined && kib > budget) {
    failures.push(`${route}: ${kib.toFixed(1)} KiB gz exceeds its ${budget} KiB budget`);
  }
}

console.log(rows.join("\n"));

const unmeasured = Object.keys(BUDGETS_KIB).filter(
  (route) => !pages.some((page) => page.route === route),
);
if (unmeasured.length) {
  // A budget whose route was renamed stops guarding anything while still looking green.
  console.error(`\nBudgeted route(s) missing from the build: ${unmeasured.join(", ")}`);
  process.exit(1);
}

if (failures.length) {
  console.error(`\n${failures.length} route(s) over budget:\n  ${failures.join("\n  ")}`);
  process.exit(1);
}

console.log(`\nAll ${Object.keys(BUDGETS_KIB).length} budgeted routes within budget.`);
