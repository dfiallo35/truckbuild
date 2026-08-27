import { expect, test } from "@playwright/test";

import { choose } from "./support";

/**
 * The half of Stage 7's smoke test that writes: submitting a build as a lead.
 *
 * Separated from configurator.spec.ts because it is not safe to run anywhere. A pass here
 * stores a real quote row and emails the sales inbox, so pointing it at production means
 * putting fake leads in front of whoever reads that inbox. It runs against a local stack by
 * default and against anything else only when told:
 *
 *   E2E_BASE_URL=https://staging… E2E_ALLOW_WRITES=1 pnpm exec playwright test quote
 *
 * The production equivalent is the by-hand step in docs/deploy.md, where a human submits one
 * quote and confirms it arrives -- which also tests the part of the pipeline (real email
 * delivery) that no browser spec can see.
 */

const baseURL = process.env.E2E_BASE_URL ?? "http://localhost:3000";
const isLocal = baseURL.includes("localhost") || baseURL.includes("127.0.0.1");

test.skip(
  !isLocal && process.env.E2E_ALLOW_WRITES !== "1",
  "submits a real lead; set E2E_ALLOW_WRITES=1 to run against a non-local target",
);

test("a configured build becomes a quote with a reference number", async ({ page }) => {
  await page.goto("/configurator/bristlecone");

  const rail = page.getByRole("tab", { name: /Recovery & Protection/i });
  await rail.scrollIntoViewIfNeeded();
  await rail.click();
  await choose(page, "Heavy-Duty Winch Bumper");

  const shown = await page.getByTestId("build-total").innerText();

  await page.getByRole("button", { name: /Review build/i }).click();
  await page.getByRole("link", { name: /Request this build/i }).click();
  await expect(page).toHaveURL(/\/configurator\/bristlecone\/request/);

  // The build crossed on the query string rather than in a record, so the form must be
  // showing the same total the configurator was.
  await expect(page.getByText(shown, { exact: false }).first()).toBeVisible();

  await page.getByLabel("Name").fill("Playwright Smoke Test");
  await page.getByLabel("Email").fill("e2e@truckbuild.example");
  await page
    .getByLabel(/Anything else/i)
    .fill("Automated end-to-end check — please ignore.")
    .catch(() => {
      // The notes field is optional and its label may change; the submission is the assertion.
    });

  // The form will not submit before the spam control's minimum dwell time has elapsed, which
  // is exactly the thing a script hitting the form instantly would trip.
  await page.waitForTimeout(3_000);

  await page.getByRole("button", { name: /Request|Send/i }).click();

  await expect(page).toHaveURL(/\/thank-you/, { timeout: 20_000 });
  // The reference is what the customer quotes back, and the one thing that proves the row was
  // actually stored rather than the form merely navigating.
  await expect(page.getByText(/Reference/i).first()).toBeVisible();
  await expect(page.locator("body")).toHaveText(/[A-Z0-9]{4,}/);
});
