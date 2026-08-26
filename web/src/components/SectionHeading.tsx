type SectionHeadingProps = {
  eyebrow?: string;
  title: string;
  description?: string;
  align?: "left" | "center";
  className?: string;
};

export function SectionHeading({
  eyebrow,
  title,
  description,
  align = "left",
  className = "",
}: SectionHeadingProps) {
  const alignClasses = align === "center" ? "items-center text-center" : "items-start text-left";

  return (
    <div className={`flex flex-col gap-3 ${alignClasses} ${className}`}>
      {eyebrow ? (
        <span className="font-data text-accent text-xs tracking-[0.22em] uppercase">{eyebrow}</span>
      ) : null}
      <h2 className="font-display text-ink text-3xl tracking-tight uppercase md:text-5xl">
        {title}
      </h2>
      {description ? (
        <p className="text-ink-muted max-w-2xl text-base md:text-lg">{description}</p>
      ) : null}
    </div>
  );
}
