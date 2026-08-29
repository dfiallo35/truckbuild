import { expect, test } from "@playwright/test";

import { choose, CURRENCY, openStep, option, totalDollars } from "./support";

/**
 * Stage 7's production smoke test, as a spec.
 *
 * Everything here is read-only, so it is safe to point at the deployed site:
 *   E2E_BASE_URL=https://… pnpm exec playwright test
 * The half of the checkpoint that writes a lead lives in quote.spec.ts, which does not run
 * against production unless explicitly allowed.
 *
 * Every interactive element is addressed by role and visible text. The options are real radios
 * and checkboxes under a `sr-only` class, so a spec that can find them by role is also evidence
 * that a screen reader can -- the a11y assertion comes free, and a change that breaks the
 * accessible name breaks the suite. Test ids appear only for structural containers that
 * legitimately carry no role, like the price readout and the viewer.
 */

test.describe("configurator", () => {
  test("home lists the platforms with starting prices", async ({ page }) => {
    await page.goto("/");

    // By test id rather than by name: the purpose cards further down the page carry
    // photography whose alt text names a platform, so matching on "Bristlecone" finds those
    // too. The distinction being drawn here is structural, not textual.
    const cards = page.getByTestId("platform-card");
    await expect(cards).toHaveCount(3);

    // A card whose price did not come back from the API is the failure this guards: the page
    // still renders, just without the number that makes it a sales tool.
    for (const name of ["Bristlecone", "Ironwood", "Sentinel"]) {
      await expect(cards.filter({ hasText: name })).toContainText(CURRENCY);
    }
  });

  test("reaches the configurator from the home page", async ({ page }) => {
    await page.goto("/");

    await page
      .getByRole("link", { name: /Bristlecone/ })
      .first()
      .click();
    await expect(page).toHaveURL(/\/builds\/bristlecone/);

    await page
      .getByRole("link", { name: /Start customizing/i })
      .first()
      .click();
    await expect(page).toHaveURL(/\/configurator\/bristlecone/);
    await expect(page.getByTestId("build-total")).toContainText(CURRENCY);
  });

  test("selecting an option moves the price and the URL", async ({ page }) => {
    await page.goto("/configurator/bristlecone");

    const before = await totalDollars(page);

    await openStep(page, /Recovery & Protection/i);
    await choose(page, "Heavy-Duty Winch Bumper");
    // $2,200 is the catalog delta for this option. Asserting the direction rather than the
    // exact figure would pass just as happily if the mirror started returning nonsense.
    expect(await totalDollars(page)).toBe(before + 2200);

    await expect(page).toHaveURL(/[?&]o=[^&]*bumper-heavy/);
  });

  test("a shared build URL restores the identical build", async ({ page, context }) => {
    await page.goto("/configurator/bristlecone");

    await openStep(page, /Recovery & Protection/i);
    await choose(page, "Heavy-Duty Winch Bumper");
    await openStep(page, /Water & Thermal/i);
    await choose(page, "Diesel-Fired Cabin Heater");

    const shared = page.url();
    const total = await totalDollars(page);
    expect(shared).toMatch(/[?&]o=/);

    // A second tab, as a person actually shares one -- not a reload, which could pass on
    // client state that a cold load would never have.
    const restored = await context.newPage();
    await restored.goto(shared);

    expect(await totalDollars(restored)).toBe(total);
    await openStep(restored, /Recovery & Protection/i);
    await expect(option(restored, "Heavy-Duty Winch Bumper")).toBeChecked();
    await openStep(restored, /Water & Thermal/i);
    await expect(option(restored, "Diesel-Fired Cabin Heater")).toBeChecked();

    await restored.close();
  });

  test("the winch explains its dependency instead of silently failing", async ({ page }) => {
    await page.goto("/configurator/bristlecone");
    await openStep(page, /Recovery & Protection/i);

    // Before it is even clicked: the catalog says the winch requires the heavy-duty bumper,
    // and the option row is expected to say so up front.
    const winch = option(page, "12,000 lb Winch");
    // Asserted on the element `aria-describedby` points at, which both checks the hint is
    // shown and that the wiring a screen reader follows actually resolves to it.
    await expect(page.locator("#hint-winch-12000")).toContainText(
      /Needs the Heavy-Duty Winch Bumper/i,
    );

    await choose(page, "12,000 lb Winch");

    // Selected anyway -- this configurator explains conflicts rather than blocking them.
    await expect(winch).toBeChecked();
    const notice = page.getByTestId("conflict-notice").first();
    await expect(notice).toBeVisible();
    await expect(notice).toContainText(/Heavy-Duty Winch Bumper/i);
    await expect(page.getByTestId("build-total")).toContainText(CURRENCY);

    // And the way out is one press, on the step that can resolve it.
    await notice.getByRole("button", { name: /Add the Heavy-Duty Winch Bumper/i }).click();
    await expect(option(page, "Heavy-Duty Winch Bumper")).toBeChecked();
    await expect(page.getByTestId("conflict-notice")).toHaveCount(0);
  });

  test("the build sheet totals what the price bar totals", async ({ page }) => {
    await page.goto("/configurator/bristlecone");

    await openStep(page, /Recovery & Protection/i);
    await choose(page, "Heavy-Duty Winch Bumper");
    const total = await totalDollars(page);

    await page.getByRole("button", { name: /Review build/i }).click();
    // A native <dialog> opened with showModal(), so it is addressable as one.
    const sheet = page.getByRole("dialog", { name: /Bristlecone/i });
    await expect(sheet).toBeVisible();
    await expect(sheet).toContainText(`$${total.toLocaleString("en-US")}`);
  });

  test("the 3D canvas mounts, and toggling an option updates it without navigating", async ({
    page,
  }) => {
    // Requires a platform with a synced model (Stage 15's `python -m app.assets sync`, run by
    // an operator against a real GLB -- see docs/stages/15-blob-storage-ingest.md). CI seeds
    // the catalog but never runs that sync, so `platform.model` is null there and the viewer
    // stays on its poster forever, which is the correct behaviour, not a bug this spec should
    // fail on. Skip rather than assert in that case; the WebGL path itself is covered by
    // `tests/viewer-scene.test.ts` and by hand per the stage file's checkpoint.
    await page.goto("/configurator/bristlecone");

    const canvas = page.locator('[data-testid="build-viewer"] canvas');
    const mounted = await canvas
      .waitFor({ state: "visible", timeout: 10_000 })
      .then(() => true)
      .catch(() => false);
    test.skip(!mounted, "no platform has a synced 3D model in this environment");

    // `load` fires on a real navigation, never on the `history.replaceState` an option toggle
    // does -- so a stray full page load here means something regressed the SPA behaviour, not
    // that the build total changed.
    let loadCount = 0;
    page.on("load", () => loadCount++);

    await openStep(page, /Recovery & Protection/i);
    await choose(page, "Heavy-Duty Winch Bumper");

    expect(loadCount).toBe(0);
    await expect(canvas).toBeVisible();
    await expect(page).toHaveURL(/\/configurator\/bristlecone/);
  });
});

test.describe("responsive layout", () => {
  test("the panes stack on a phone and sit side by side on a desktop", async ({
    page,
  }, testInfo) => {
    await page.goto("/configurator/bristlecone");

    const viewer = page.getByTestId("build-viewer");
    const panel = page.getByRole("tabpanel");
    await expect(viewer).toBeVisible();
    await expect(panel).toBeVisible();

    const viewerBox = await viewer.boundingBox();
    const panelBox = await panel.boundingBox();
    expect(viewerBox && panelBox).toBeTruthy();

    if (testInfo.project.name === "mobile") {
      // Stacked: the panel starts below the viewer rather than beside it. A two-pane layout
      // that survives onto a phone is the specific regression this catches -- it does not
      // look broken in a screenshot, it just pushes the options off-screen.
      expect(panelBox!.y).toBeGreaterThanOrEqual(viewerBox!.y + viewerBox!.height - 1);
      // And nothing may push the page sideways.
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      expect(overflow).toBeLessThanOrEqual(1);
    } else {
      expect(panelBox!.x).toBeGreaterThan(viewerBox!.x);
    }
  });

  test("the price bar stays in view while the options scroll", async ({ page }) => {
    await page.goto("/configurator/bristlecone");

    const total = page.getByTestId("build-total");
    await expect(total).toBeInViewport();

    // Scroll the options themselves, not the page: the configurator is a fixed-height
    // workspace whose panes scroll internally, so the cursor has to be over the pane that
    // moves. The running total is the reason to keep configuring, and scrolled off the bottom
    // of a phone it stops doing its job.
    await page.getByRole("tabpanel").hover();
    await page.mouse.wheel(0, 2000);

    await expect(total).toBeInViewport();
  });
});
