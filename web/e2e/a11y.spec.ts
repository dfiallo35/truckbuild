import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import { choose } from "./support";

/**
 * Stage 7's accessibility pass, run rather than eyeballed.
 *
 * axe catches the mechanical half -- contrast, names, roles, landmark structure -- across every
 * page at both breakpoints. It does not catch keyboard traps or a focus order that makes no
 * sense, so the configurator gets explicit keyboard specs below; between them they cover what
 * a manual pass would, and unlike a manual pass they keep covering it.
 *
 * WCAG 2.1 AA is the bar, which is what "Accessibility 95+" in the stage file amounts to.
 */

const WCAG = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];

const PAGES = [
  { name: "home", path: "/" },
  { name: "platform index", path: "/builds" },
  { name: "platform detail", path: "/builds/bristlecone" },
  { name: "purpose", path: "/purposes/expedition" },
  { name: "configurator", path: "/configurator/bristlecone" },
  { name: "request form", path: "/configurator/bristlecone/request" },
  { name: "contact", path: "/contact" },
  { name: "process", path: "/process" },
  { name: "about", path: "/about" },
  { name: "gallery", path: "/gallery" },
  { name: "privacy", path: "/legal/privacy" },
];

async function scan(page: Page) {
  return new AxeBuilder({ page }).withTags(WCAG).analyze();
}

/** axe violations, printed so a failure names the element instead of just a rule id. */
function describe(results: Awaited<ReturnType<typeof scan>>) {
  return results.violations
    .map(
      (violation) =>
        `${violation.id} (${violation.impact}): ${violation.help}\n` +
        violation.nodes.map((node) => `    ${node.target.join(" ")}`).join("\n"),
    )
    .join("\n");
}

for (const { name, path } of PAGES) {
  test(`${name} has no WCAG AA violations`, async ({ page }) => {
    await page.goto(path);
    const results = await scan(page);
    expect(describe(results)).toBe("");
  });
}

test.describe("configurator keyboard operation", () => {
  // Skipped on the mobile project: a touch device has no Tab key, and asserting one here
  // would be testing Playwright's emulation rather than the product.
  test.skip(({ isMobile }) => !!isMobile, "keyboard specs are desktop-only");

  test("the step rail is one tab stop, browsed with arrows", async ({ page }) => {
    await page.goto("/configurator/bristlecone");

    const tabs = page.getByRole("tab");
    const first = tabs.first();
    await first.focus();
    await expect(first).toHaveAttribute("aria-selected", "true");

    // Roving tabindex: arrows move between steps, and the rail stays a single stop in the
    // tab order rather than making a visitor press Tab past every step to reach the options.
    await page.keyboard.press("ArrowDown");
    await expect(tabs.nth(1)).toBeFocused();
    await expect(tabs.nth(1)).toHaveAttribute("aria-selected", "true");
    await expect(first).toHaveAttribute("tabindex", "-1");

    await page.keyboard.press("End");
    await expect(tabs.last()).toBeFocused();
    await page.keyboard.press("Home");
    await expect(first).toBeFocused();
  });

  test("an option can be selected without a mouse", async ({ page }) => {
    await page.goto("/configurator/bristlecone");

    const heater = page.getByRole("checkbox", { name: /^Diesel-Fired Cabin Heater/i });
    await page.getByRole("tab", { name: /Water & Thermal/i }).click();
    await heater.focus();
    await expect(heater).toBeFocused();

    await page.keyboard.press("Space");
    await expect(heater).toBeChecked();
  });

  test("a price change is announced, not just shown", async ({ page }) => {
    await page.goto("/configurator/bristlecone");

    // The visible price bar is a flash of colour; this is the same information for someone
    // who cannot see it. Losing it is invisible in a screenshot, which is why it is asserted.
    const live = page.locator("[aria-live=polite]");
    await page.getByRole("tab", { name: /Recovery & Protection/i }).click();
    await choose(page, "Heavy-Duty Winch Bumper");

    await expect(live).toContainText(/Heavy-Duty Winch Bumper added/i);
    await expect(live).toContainText(/Build total \$/i);
  });

  test("the build sheet traps focus and closes on Escape", async ({ page }) => {
    await page.goto("/configurator/bristlecone");

    await page.getByRole("button", { name: /Review build/i }).click();
    const sheet = page.getByRole("dialog", { name: /Bristlecone/i });
    await expect(sheet).toBeVisible();

    await page.keyboard.press("Escape");
    await expect(sheet).toBeHidden();
  });

  test("the modal build sheet passes axe while open", async ({ page }) => {
    await page.goto("/configurator/bristlecone");
    await page.getByRole("button", { name: /Review build/i }).click();
    await expect(page.getByRole("dialog", { name: /Bristlecone/i })).toBeVisible();

    // Scanned open because a dialog is exactly where contrast and naming regressions hide:
    // it is not on screen during a normal page scan.
    const results = await scan(page);
    expect(describe(results)).toBe("");
  });
});
