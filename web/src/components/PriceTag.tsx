const formatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

type PriceTagProps = {
  cents: number;
  label?: string;
  size?: "sm" | "lg";
  className?: string;
};

export function PriceTag({
  cents,
  label = "Starting at",
  size = "lg",
  className = "",
}: PriceTagProps) {
  const amount = formatter.format(cents / 100);
  const amountClasses = size === "lg" ? "text-3xl md:text-4xl" : "text-lg";

  return (
    <p className={`flex flex-col gap-1 ${className}`}>
      <span className="font-data text-ink-faint text-xs tracking-[0.18em] uppercase">{label}</span>
      <span className={`font-display text-accent tabular-nums ${amountClasses}`}>{amount}</span>
    </p>
  );
}
