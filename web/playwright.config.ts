import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end specs, in `e2e/` rather than `tests/`.
 *
 * `tests/` belongs to Vitest, whose config globs `tests/**\/*.test.ts` -- the pricing mirror
 * lives there. Two runners sharing a directory means each one tries to execute the other's
 * files, so the split is load-bearing rather than tidiness.
 *
 * The same specs run against a local production build and against the deployed site, which is
 * what Stage 7 asks for: set E2E_BASE_URL to the deployment and no server is started locally.
 */
// Port 3100, not 3000, and that is load-bearing. `next dev` normally holds 3000, and a
// `reuseExistingServer` that finds it will quietly run the whole suite against the dev server
// instead of the production build -- passing or failing for reasons that have nothing to do
// with what shipped. On its own port the suite always gets the build it asked for.
const E2E_PORT = 3100;
const baseURL = process.env.E2E_BASE_URL ?? `http://localhost:${E2E_PORT}`;
const isLocal = baseURL.includes("localhost") || baseURL.includes("127.0.0.1");

export default defineConfig({
  testDir: "./e2e",
  // A configurator assertion that passes only when it runs alone is not evidence of anything.
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  // `github` annotates the failing line in the diff; `html` is the artifact CI uploads, and
  // `never` stops it trying to open a browser on a runner that has none.
  reporter: process.env.CI
    ? [["github"], ["list"], ["html", { open: "never" }]]
    : [["list"], ["html", { open: "never" }]],

  use: {
    baseURL,
    trace: "on-first-retry",
    // The full Chromium build rather than Playwright's default `chromium-headless-shell`. The
    // shell is a stripped binary that exists to start fast; this suite asserts layout,
    // contrast and focus behaviour, so it should run against the browser a visitor would
    // actually use. It also means one browser download instead of two.
    channel: "chromium",
  },

  projects: [
    {
      name: "desktop",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      // Stage 7 calls for the configurator verified on a phone specifically, where the
      // three-pane desktop layout has to collapse to a stacked one. That is a real layout
      // branch, not a scaled-down copy, so it gets its own project rather than a resize.
      name: "mobile",
      use: { ...devices["Pixel 7"] },
    },
  ],

  // Against a deployment there is nothing to start. Locally, run the production build rather
  // than `next dev`: prerendering and Cache Components behave differently in dev, and those
  // are precisely what these specs are meant to be checking.
  webServer: isLocal
    ? {
        command: `pnpm start --port ${E2E_PORT}`,
        url: baseURL,
        // Never reuse. A server already on this port is one a previous run left behind, and it
        // is serving whatever `.next` held at the time -- which is exactly the stale-build
        // result this suite exists to rule out.
        reuseExistingServer: false,
        timeout: 120_000,
      }
    : undefined,
});
