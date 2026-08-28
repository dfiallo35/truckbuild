"use client";

import Image from "next/image";
import { useMemo, type Ref } from "react";

import type { Option, OptionGroup, Platform } from "@/lib/contract";
import { toRuleable } from "@/lib/build";
import { formatDelta } from "@/lib/format";
import { violationsIfSelected, type RuleViolation } from "@/lib/rules";

/**
 * One step of the build. Options are native radios or checkboxes under the hood, so arrow keys,
 * Space and screen readers all behave without being re-implemented.
 *
 * Incompatibilities are explained, never silently blocked: an option that would conflict says
 * what it conflicts with before it is clicked, and a conflict already in the build offers the
 * one-press way out of it.
 */
export function OptionPanel({
  ref,
  group,
  stepNumber,
  stepCount,
  selected,
  violations,
  platform,
  onToggle,
  onStep,
  nameOf,
}: {
  ref: Ref<HTMLDivElement>;
  group: OptionGroup;
  stepNumber: number;
  stepCount: number;
  selected: string[];
  violations: RuleViolation[];
  platform: Platform;
  onToggle: (slug: string) => void;
  onStep: (index: number, moveFocus?: boolean) => void;
  nameOf: (slug: string) => string;
}) {
  const ruleable = useMemo(() => toRuleable(platform), [platform]);
  const slugsHere = useMemo(() => new Set(group.options.map((o) => o.slug)), [group]);

  // Conflicts are shown on the step that can resolve them, either side of the rule.
  const relevant = violations.filter(
    (violation) =>
      slugsHere.has(violation.option) ||
      (violation.needs && slugsHere.has(violation.needs)) ||
      (violation.conflicts_with && slugsHere.has(violation.conflicts_with)),
  );

  return (
    <div
      ref={ref}
      role="tabpanel"
      id="step-panel"
      aria-labelledby={`step-tab-${group.slug}`}
      tabIndex={-1}
      className="border-border bg-canvas-raised/40 focus-visible:outline-accent flex min-h-0 flex-col -outline-offset-2 focus-visible:outline-2 md:overflow-y-auto md:border-l"
    >
      <div className="border-border flex flex-col gap-1 border-b px-5 py-5">
        <span className="font-data text-ink-faint text-[0.625rem] tracking-[0.2em] uppercase">
          Step {stepNumber} of {stepCount} · {group.required ? "Required" : "Optional"}
        </span>
        <h2 className="font-display text-ink text-xl tracking-tight uppercase">{group.name}</h2>
        <p className="text-ink-faint text-xs">
          {group.selection_mode === "single" ? "Pick one" : "Pick any that apply"}
        </p>
      </div>

      {relevant.length > 0 ? (
        <div className="flex flex-col gap-2 px-5 pt-5">
          {relevant.map((violation) => (
            <ConflictNotice
              key={`${violation.kind}-${violation.option}`}
              violation={violation}
              nameOf={nameOf}
              onResolve={onToggle}
            />
          ))}
        </div>
      ) : null}

      <div className="flex-1 px-5 py-5">
        <fieldset className="flex flex-col gap-2">
          <legend className="sr-only">{group.name}</legend>

          {group.display_style === "swatch" ? (
            <div className="grid grid-cols-3 gap-3">
              {group.options.map((option) => (
                <SwatchOption
                  key={option.slug}
                  option={option}
                  group={group}
                  checked={selected.includes(option.slug)}
                  onToggle={onToggle}
                />
              ))}
            </div>
          ) : (
            group.options.map((option) => (
              <RowOption
                key={option.slug}
                option={option}
                group={group}
                checked={selected.includes(option.slug)}
                blockers={
                  selected.includes(option.slug)
                    ? []
                    : violationsIfSelected(ruleable, selected, option.slug)
                }
                nameOf={nameOf}
                onToggle={onToggle}
              />
            ))
          )}
        </fieldset>
      </div>

      <div className="border-border bg-canvas-raised sticky bottom-0 flex items-center justify-between gap-3 border-t px-5 py-4">
        <button
          type="button"
          disabled={stepNumber === 1}
          onClick={() => onStep(stepNumber - 2, true)}
          className="font-data text-ink-muted hover:text-ink focus-visible:outline-accent text-xs tracking-[0.14em] uppercase focus-visible:outline-2 focus-visible:outline-offset-4 disabled:invisible"
        >
          Back
        </button>
        <button
          type="button"
          disabled={stepNumber === stepCount}
          onClick={() => onStep(stepNumber, true)}
          className="border-border-strong text-ink hover:border-accent hover:text-accent focus-visible:outline-accent font-display border px-5 py-2.5 text-xs tracking-[0.1em] uppercase transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 disabled:invisible"
        >
          Next step
        </button>
      </div>
    </div>
  );
}

function ConflictNotice({
  violation,
  nameOf,
  onResolve,
}: {
  violation: RuleViolation;
  nameOf: (slug: string) => string;
  onResolve: (slug: string) => void;
}) {
  const subject = nameOf(violation.option);

  const [message, action, target] =
    violation.kind === "requires"
      ? [
          `The ${subject} mounts to the ${nameOf(violation.needs!)}, which is not in this build.`,
          `Add the ${nameOf(violation.needs!)}`,
          violation.needs!,
        ]
      : [
          `The ${subject} and the ${nameOf(violation.conflicts_with!)} need the same space.`,
          `Remove the ${nameOf(violation.conflicts_with!)}`,
          violation.conflicts_with!,
        ];

  return (
    <div
      data-testid="conflict-notice"
      className="border-accent/40 bg-accent/5 flex flex-col gap-2 border-l-2 px-4 py-3"
    >
      <p className="text-ink text-xs leading-relaxed">{message}</p>
      <button
        type="button"
        onClick={() => onResolve(target)}
        className="font-data text-accent hover:text-accent-hover focus-visible:outline-accent self-start text-[0.6875rem] tracking-[0.12em] uppercase underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-4"
      >
        {action}
      </button>
    </div>
  );
}

function inputProps(group: OptionGroup, option: Option, checked: boolean) {
  return {
    type: group.selection_mode === "single" ? ("radio" as const) : ("checkbox" as const),
    name: `group-${group.slug}`,
    value: option.slug,
    checked,
  };
}

function RowOption({
  option,
  group,
  checked,
  blockers,
  nameOf,
  onToggle,
}: {
  option: Option;
  group: OptionGroup;
  checked: boolean;
  blockers: RuleViolation[];
  nameOf: (slug: string) => string;
  onToggle: (slug: string) => void;
}) {
  const hintId = blockers.length > 0 ? `hint-${option.slug}` : undefined;

  return (
    <label
      className={`group has-focus-visible:outline-accent flex cursor-pointer gap-3 border px-4 py-3.5 transition-colors has-focus-visible:outline-2 has-focus-visible:outline-offset-2 ${
        checked
          ? "border-accent/60 bg-accent/[0.06]"
          : "border-border hover:border-border-strong bg-transparent"
      }`}
    >
      <input
        {...inputProps(group, option, checked)}
        onChange={() => onToggle(option.slug)}
        aria-describedby={hintId}
        className="sr-only"
      />

      <span
        aria-hidden
        className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center border ${
          group.selection_mode === "single" ? "rounded-full" : "rounded-[2px]"
        } ${checked ? "border-accent bg-accent" : "border-border-strong"}`}
      >
        {checked ? (
          <svg viewBox="0 0 12 12" className="text-accent-ink h-3 w-3" fill="none">
            <path
              d="M2.5 6.2l2.3 2.3 4.7-5"
              stroke="currentColor"
              strokeWidth={1.8}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        ) : null}
      </span>

      <span className="flex min-w-0 flex-1 flex-col gap-1">
        <span className="flex items-baseline justify-between gap-3">
          <span className="text-ink text-sm leading-snug">{option.name}</span>
          <span
            className={`font-data shrink-0 text-xs tabular-nums ${
              option.price_delta_cents === 0 ? "text-ink-faint" : "text-accent"
            }`}
          >
            {formatDelta(option.price_delta_cents)}
          </span>
        </span>

        {option.description ? (
          <span className="text-ink-faint text-xs leading-relaxed">{option.description}</span>
        ) : null}

        {blockers.length > 0 ? (
          <span id={hintId} className="font-data text-accent/80 text-[0.6875rem] tracking-wide">
            {blockers
              .map((blocker) =>
                blocker.kind === "requires"
                  ? `Needs the ${nameOf(blocker.needs!)}`
                  : `Conflicts with the ${nameOf(blocker.conflicts_with!)}`,
              )
              .join(" · ")}
          </span>
        ) : null}
      </span>
    </label>
  );
}

function SwatchOption({
  option,
  group,
  checked,
  onToggle,
}: {
  option: Option;
  group: OptionGroup;
  checked: boolean;
  onToggle: (slug: string) => void;
}) {
  return (
    <label className="group has-focus-visible:outline-accent flex cursor-pointer flex-col gap-2 has-focus-visible:outline-2 has-focus-visible:outline-offset-4">
      <input
        {...inputProps(group, option, checked)}
        onChange={() => onToggle(option.slug)}
        className="sr-only"
      />
      <span
        className={`relative block aspect-square overflow-hidden border-2 transition-colors ${
          checked ? "border-accent" : "border-border group-hover:border-border-strong"
        }`}
      >
        {option.swatch ? (
          <Image src={option.swatch.url} alt="" fill sizes="120px" className="object-cover" />
        ) : null}
      </span>
      <span className={`text-[0.6875rem] leading-tight ${checked ? "text-ink" : "text-ink-muted"}`}>
        {option.name}
      </span>
      {option.price_delta_cents !== 0 ? (
        <span className="font-data text-accent text-[0.625rem] tabular-nums">
          {formatDelta(option.price_delta_cents)}
        </span>
      ) : null}
    </label>
  );
}
