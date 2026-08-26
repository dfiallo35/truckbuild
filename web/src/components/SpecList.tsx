type Spec = {
  label: string;
  value: string;
};

type SpecListProps = {
  specs: ReadonlyArray<Spec>;
  className?: string;
};

/**
 * Renders like a stenciled equipment placard: uppercase mono labels, tabular values, a hairline
 * rule between rows. The recurring motif for anywhere the site reads out a hard number.
 */
export function SpecList({ specs, className = "" }: SpecListProps) {
  return (
    <dl className={`divide-border font-data divide-y text-sm ${className}`}>
      {specs.map((spec) => (
        <div key={spec.label} className="flex items-baseline justify-between gap-4 py-2.5">
          <dt className="text-ink-faint tracking-[0.14em] uppercase">{spec.label}</dt>
          <dd className="text-ink tabular-nums">{spec.value}</dd>
        </div>
      ))}
    </dl>
  );
}
