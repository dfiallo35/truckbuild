# Stage 16 — the 3D viewer

> **Status: not started.**

**Goal:** `/configurator/[slug]` renders the platform's GLB in WebGL, and selecting an option
changes the truck on screen with no network request — the property the 2D layer composite was built
to preserve, kept.

**Prerequisite:** Stage 15 checkpoint passes, and at least one platform has a real model in Blob.

**Load the `frontend-design` skill before starting.** `docs/PLAN.md` requires it for visual work, and
a default three.js scene — grey background, default tone mapping, a lone directional light — is
precisely the "reads as templated" failure a dark cinematic site cannot absorb. The lighting and
environment are the product here, in the same way the photography is on the marketing pages.

## The two budgets this stage has to respect

1. **`web/scripts/bundle-budget.mjs` budgets `configurator/bristlecone.html` at 210 KiB gzipped**,
   of which ~170 KiB is React and the Next runtime. three.js with a GLTF loader is 130–160 KiB
   gzipped on its own. The viewer therefore *must* be a lazily imported chunk; there is no version
   of this that fits in the route's initial script.

2. **The budget script cannot currently see a lazy chunk.** It reads `<script src>` refs out of the
   prerendered HTML, which is the honest measure of what the browser fetches *first* — and a
   `ssr: false` dynamic import appears in none of them. Left alone, the viewer would ship
   unmeasured while the route budget stayed green. Step 6 closes that hole; it is not optional
   polish.

## The no-WebGL position, stated plainly

Stage 17 removes the 2D composite, so a visitor without WebGL has no build view. This is a chosen
trade, not an oversight, and it is mitigated at near-zero cost rather than by building a second
viewer: the `<canvas>` needs a poster while the GLB downloads anyway, so `platform.hero_image`
serves as that poster **and** as the terminal state when WebGL is unavailable, with one line of
explanation. That is a static image — an option toggle will not change it.

If that proves unacceptable in testing, the recovery is to revive the layer composite from git
history, which is why its removal is a separate later stage and not part of this one.

## Steps

1. **Dependency** — `cd web && pnpm add three` and `pnpm add -D @types/three`.

   **Not** React Three Fiber or drei. The scene is one model, one environment, and orbit controls;
   R3F's reconciler is weight bought for a component tree this does not have, and it would put the
   render loop inside React's, which step 2 deliberately avoids.

2. **`web/src/lib/viewer/scene.ts`** — framework-free and imperative. `createScene(canvas, model)`
   returns `{ applySelection(slugs), resize(), dispose() }`.

   React owns the selection; this owns the WebGL, and the two meet at one function call. Node and
   material lookups are resolved **once** by name at load into a `Map`, so a toggle costs the nodes
   that option names rather than a full scene traversal on every click.

   `dispose()` is not optional bookkeeping: geometries, materials, textures and the WebGL context
   all leak past unmount without it, and the configurator is a route people navigate in and out of.

3. **`BuildViewer.tsx`** keeps its name, its `data-testid="build-viewer"` and its `role="img"` +
   generated description — `e2e/configurator.spec.ts` and `e2e/a11y.spec.ts` both depend on all
   three, and this stage should not be a test rewrite. It becomes a thin shell that:

   - renders `platform.hero_image` as the poster immediately,
   - `next/dynamic(() => import("./BuildViewer3D"), { ssr: false })` for the canvas,
   - swaps poster → canvas on first frame,
   - keeps the poster and shows one explanatory line if WebGL is unavailable or the GLB fails,
   - keeps the poster with no note if `platform.model` is `null` — a platform whose model has not
     been synced yet is a normal state, not an error.

4. **`BuildViewer3D.tsx`** — owns the canvas ref, one `useEffect` for `createScene` / `dispose`, one
   for `applySelection(selected)`, a `ResizeObserver` for the canvas box, and
   `prefers-reduced-motion` honoured by disabling auto-rotate and the material cross-fade. The
   existing composite already respects it via `motion-reduce:`; the canvas has to do it in JS
   because Tailwind cannot reach inside a render loop.

5. **Accessibility.** A `<canvas>` is opaque to a screen reader, so the wrapper keeps `role="img"`
   with a description built from `model.alt_text` plus the selected option names — the same sentence
   the composite generates today, from better source text. Orbit gets keyboard equivalents (arrow
   keys on a focusable wrapper) and a visible focus ring: `e2e/a11y.spec.ts` runs axe over this
   route and keyboard operation is already covered, so a mouse-only control would be a regression
   against a test that exists.

6. **Close the budget hole** — `web/scripts/bundle-budget.mjs` gains a second budget map for **named
   lazy chunks**, resolved from `.next/app-build-manifest.json` rather than from `<script src>` in
   the HTML, and a `viewer: 180` KiB gzipped entry. Keep the existing route budgets exactly as they
   are: the two measure different things — what loads first, and what loads at all — and both are
   worth failing on.

7. **`next.config.ts`** — add `images.remotePatterns` for `*.public.blob.vercel-storage.com`, for
   posters served from Blob later. **No CSP change is needed**: the existing headers set
   `frame-ancestors` only, not `connect-src`, so the cross-origin GLB fetch is already permitted.
   Confirm that rather than assuming it.

8. **Tests.**
   - Vitest over `scene.ts`'s pure half — which nodes and which material override a given selection
     resolves to. No WebGL, no canvas, no jsdom heroics; if that logic is not extractable into a
     pure function, the module is shaped wrong.
   - `e2e/configurator.spec.ts`: the existing responsive and price-total specs must keep passing
     against the same testid, unchanged. Add one that the canvas mounts and that toggling an option
     does not navigate.

## Checkpoint

```bash
cd web
pnpm lint && pnpm test
pnpm build                    # must still print "- Cache Components enabled"
pnpm bundle:check             # route budgets AND the new viewer-chunk budget
pnpm e2e
```

By hand, at `localhost:3000/configurator/bristlecone`:

- toggle Crew Cab and Extended Shell — geometry changes, DevTools Network stays quiet
- toggle a paint finish — the material changes
- reload a `?o=…` URL — the shared build restores in 3D
- disable WebGL in DevTools — poster plus the explanatory line, page still usable
- navigate away and back a few times, watching `renderer.info` — no climbing geometry count

## Done when

The configurator renders the truck in 3D, options change it with no network request, `pnpm build`
still reports Cache Components enabled, `bundle:check` passes **both** budgets, axe is clean,
keyboard orbit works, and the scene disposes without leaking on unmount.
