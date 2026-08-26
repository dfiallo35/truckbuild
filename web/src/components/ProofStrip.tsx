export type ProofStat = {
  value: string;
  label: string;
};

export function ProofStrip({ stats }: { stats: ReadonlyArray<ProofStat> }) {
  return (
    <dl className="divide-border border-border grid divide-y border-y sm:grid-cols-2 sm:divide-x sm:divide-y-0 md:grid-cols-4">
      {stats.map((stat) => (
        <div key={stat.label} className="flex flex-col gap-2 px-6 py-8 md:px-8">
          <dd className="font-display text-accent text-3xl tabular-nums md:text-4xl">
            {stat.value}
          </dd>
          <dt className="font-data text-ink-faint text-xs tracking-[0.14em] uppercase">
            {stat.label}
          </dt>
        </div>
      ))}
    </dl>
  );
}
