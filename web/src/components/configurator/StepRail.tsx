"use client";

import { useRef } from "react";

import type { OptionGroup } from "@/lib/contract";

/**
 * The steps of the build, and what each one currently answers. Numbering earns its place here:
 * the groups are an actual sequence -- chassis before body before what bolts to the body.
 *
 * Tabs, with roving tabindex: one stop in the tab order, arrow keys to move between steps.
 */
export function StepRail({
  groups,
  selected,
  activeIndex,
  onSelectStep,
}: {
  groups: OptionGroup[];
  selected: string[];
  activeIndex: number;
  onSelectStep: (index: number, moveFocus?: boolean) => void;
}) {
  const tabs = useRef<(HTMLButtonElement | null)[]>([]);

  function onKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    const last = groups.length - 1;
    let next: number;

    switch (event.key) {
      case "ArrowDown":
      case "ArrowRight":
        next = activeIndex === last ? 0 : activeIndex + 1;
        break;
      case "ArrowUp":
      case "ArrowLeft":
        next = activeIndex === 0 ? last : activeIndex - 1;
        break;
      case "Home":
        next = 0;
        break;
      case "End":
        next = last;
        break;
      default:
        return;
    }

    event.preventDefault();
    onSelectStep(next);
    tabs.current[next]?.focus();
  }

  return (
    <div
      role="tablist"
      aria-orientation="vertical"
      aria-label="Build steps"
      onKeyDown={onKeyDown}
      className="border-border bg-canvas-raised/60 flex shrink-0 gap-1 overflow-x-auto border-b p-2 md:flex-col md:gap-0 md:overflow-x-visible md:overflow-y-auto md:border-r md:border-b-0 md:p-0"
    >
      {groups.map((group, index) => {
        const chosen = group.options.filter((option) => selected.includes(option.slug));
        const active = index === activeIndex;

        return (
          <button
            key={group.slug}
            ref={(node) => {
              tabs.current[index] = node;
            }}
            role="tab"
            id={`step-tab-${group.slug}`}
            aria-selected={active}
            aria-controls="step-panel"
            tabIndex={active ? 0 : -1}
            onClick={() => onSelectStep(index, true)}
            className={`focus-visible:outline-accent group flex shrink-0 items-start gap-3 border-l-2 px-3 py-3 text-left -outline-offset-2 transition-colors focus-visible:outline-2 md:px-4 md:py-3.5 ${
              active
                ? "border-l-accent bg-canvas-overlay"
                : "hover:bg-canvas-overlay/50 border-l-transparent"
            }`}
          >
            <span
              className={`font-data mt-0.5 text-[0.625rem] tabular-nums ${
                active ? "text-accent" : "text-ink-faint"
              }`}
            >
              {String(index + 1).padStart(2, "0")}
            </span>

            <span className="flex min-w-0 flex-col gap-0.5">
              <span
                className={`font-display text-xs tracking-[0.1em] whitespace-nowrap uppercase md:whitespace-normal ${
                  active ? "text-ink" : "text-ink-muted group-hover:text-ink"
                }`}
              >
                {group.name}
              </span>
              {/* `ink-muted`, not `ink-faint`. This line sits on `canvas-overlay` when its
                  step is the active one, where faint lands at about 4.3:1 -- under the 4.5:1
                  AA floor for text this size. Muted clears it on both backgrounds. */}
              <span className="text-ink-muted hidden truncate text-[0.6875rem] md:block">
                {chosen.length === 0
                  ? group.required
                    ? "Choose one"
                    : "None"
                  : chosen.map((option) => option.name).join(", ")}
              </span>
            </span>
          </button>
        );
      })}
    </div>
  );
}
