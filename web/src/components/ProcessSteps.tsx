export type ProcessStep = {
  title: string;
  description: string;
};

/**
 * A literal sequence -- each step depends on the last -- so numbering here encodes real order,
 * not decoration (see frontend-design guidance on numbered markers).
 */
export function ProcessSteps({ steps }: { steps: ReadonlyArray<ProcessStep> }) {
  return (
    <ol className="divide-border border-border grid divide-y border-t md:grid-cols-4 md:divide-x md:divide-y-0 md:border-t-0">
      {steps.map((step, index) => (
        <li key={step.title} className="flex flex-col gap-4 py-8 pr-6 md:px-8 md:py-0">
          <span className="font-data text-accent text-sm tracking-[0.14em]">
            {String(index + 1).padStart(2, "0")}
          </span>
          <h3 className="font-display text-ink text-xl tracking-tight uppercase">{step.title}</h3>
          <p className="text-ink-muted text-sm leading-relaxed">{step.description}</p>
        </li>
      ))}
    </ol>
  );
}
