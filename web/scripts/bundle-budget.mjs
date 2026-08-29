/**
 * Client JavaScript budgets: what a route loads first, and what a lazy chunk costs once it
 * does load.
 *
 * Next 16's Turbopack build summary reports which routes prerendered but not how much script
 * each one ships, so the number that actually matters here -- what a phone downloads to make
 * the configurator interactive -- is invisible in CI. This reads it back out of the build.
 *
 * The two halves below measure different things and both are worth failing on: the prerendered
 * HTML's `<script src>` refs are the honest measure of what loads first, and are silent by
 * design about anything `next/dynamic` split out of that -- which is what the loadable manifest
 * half exists to catch instead. Sizes are gzipped throughout, because that is what goes over
 * the wire.
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

/**
 * Budgets in KiB, gzipped, for named **lazy** chunks -- code `next/dynamic` split out of a
 * route's first load, which the section above cannot see by design: a lazy chunk's entire
 * point is that the prerendered HTML does not reference it, so a regression that made it
 * eager would show up above but a regression that made it enormous would not show up at all.
 *
 * Resolved from the loadable manifest Next writes per page rather than from `<script src>`.
 * The stage that added this (`docs/stages/16-3d-viewer.md`) named
 * `.next/app-build-manifest.json`, which is what a webpack build produces; this repo's actual
 * `next build` runs on Turbopack, which instead writes one
 * `.next/server/app/<route>/page/react-loadable-manifest.json` per page, keyed by an
 * unstable per-build module id rather than a name -- so `manifestPage` below points at the
 * page and every chunk that page's manifest names is summed under the one budget.
 *
 * three.js plus its GLTF loader and orbit controls run 130-160 KiB gzipped on their own
 * (see the stage file); 180 KiB leaves headroom without hiding a real regression.
 */
const LAZY_CHUNK_BUDGETS_KIB = {
  viewer: { manifestPage: "configurator/[slug]", budget: 180 },
};

function lazyChunkBytes(manifestPage) {
  const manifestPath = join(APP_DIR, manifestPage, "page", "react-loadable-manifest.json");
  if (!existsSync(manifestPath)) {
    throw new Error(
      `No loadable manifest at ${manifestPath} -- did the dynamic import move or get removed?`,
    );
  }

  const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
  const files = new Set(Object.values(manifest).flatMap((entry) => entry.files));

  let gzipped = 0;
  for (const file of files) {
    const chunkPath = join(".next", file);
    if (!existsSync(chunkPath)) {
      throw new Error(`Loadable manifest for ${manifestPage} references a missing chunk: ${file}`);
    }
    gzipped += gzipSync(readFileSync(chunkPath)).length;
  }

  return { chunks: files.size, gzipped };
}

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

const lazyRows = [];
for (const [name, { manifestPage, budget }] of Object.entries(LAZY_CHUNK_BUDGETS_KIB)) {
  const { chunks, gzipped } = lazyChunkBytes(manifestPage);
  const kib = gzipped / 1024;

  lazyRows.push(
    [
      kib.toFixed(1).padStart(7),
      "KiB gz ",
      String(chunks).padStart(2),
      "chunks ",
      `lazy:${name}`.padEnd(40),
      `budget ${budget} KiB`,
    ].join(" "),
  );

  if (kib > budget) {
    failures.push(
      `lazy:${name} (${manifestPage}): ${kib.toFixed(1)} KiB gz exceeds its ${budget} KiB budget`,
    );
  }
}
console.log(lazyRows.join("\n"));

if (failures.length) {
  console.error(`\n${failures.length} route(s) over budget:\n  ${failures.join("\n  ")}`);
  process.exit(1);
}

console.log(
  `\nAll ${Object.keys(BUDGETS_KIB).length} budgeted routes and ${Object.keys(LAZY_CHUNK_BUDGETS_KIB).length} lazy chunk(s) within budget.`,
);
