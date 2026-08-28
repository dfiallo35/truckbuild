/** Cents to a display string -- the one place either half of the configurator formats money. */

const currency = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

export function formatCents(cents: number): string {
  return currency.format(cents / 100);
}

/** Price deltas read as "+$3,400" / "Included", never as a bare zero. */
export function formatDelta(cents: number): string {
  if (cents === 0) return "Included";
  return `${cents > 0 ? "+" : "−"}${currency.format(Math.abs(cents) / 100)}`;
}
