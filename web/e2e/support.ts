import { expect, type Locator, type Page } from "@playwright/test";

/** A price as rendered anywhere on the site. */
export const CURRENCY = /\$[\d,]+/;

/** The build total in the price bar, as an integer of dollars. */
export async function totalDollars(page: Page): Promise<number> {
  const text = await page.getByTestId("build-total").innerText();
  const digits = text.replace(/[^\d]/g, "");
  expect(digits, `price bar showed "${text}"`).not.toBe("");
  return Number(digits);
}

/**
 * An option's underlying checkbox or radio, matched from the *start* of its accessible name.
 *
 * The anchor is necessary rather than tidy: options reference each other by name, so the
 * winch's conflict hint contains the string "Heavy-Duty Winch Bumper" and an unanchored match
 * resolves to two controls. Every accessible name here begins with the option's own name.
 */
export function option(page: Page, name: string): Locator {
  return page.getByRole("checkbox", { name: new RegExp(`^${name}`, "i") });
}

/**
 * Select an option the way a person does: by clicking its row.
 *
 * The input itself is `sr-only` — visually hidden so the row can be styled, still a real
 * checkbox so keyboards and screen readers work. Playwright's `.check()` clicks the element it
 * is given, and here that click is intercepted by the `<label>` wrapping it. Clicking the label
 * is both what actually happens in a browser and what the markup intends, so this reaches for
 * the ancestor rather than reaching for `force: true` — which would suppress exactly the
 * actionability checks worth keeping.
 */
export async function choose(page: Page, name: string): Promise<Locator> {
  const input = option(page, name);
  await input.locator("xpath=ancestor::label[1]").click();
  await expect(input).toBeChecked();
  return input;
}

/**
 * Open the step whose tab carries this name. Works on both layouts: the rail is a vertical
 * tablist on desktop and a horizontal scroller on a phone, but it is a tablist in both, which
 * is the point of driving it by role.
 */
export async function openStep(page: Page, name: RegExp): Promise<void> {
  const tab = page.getByRole("tab", { name });
  await tab.scrollIntoViewIfNeeded();
  await tab.click();
  await expect(tab).toHaveAttribute("aria-selected", "true");
}
