"use client";

import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { BuildSheet } from "@/components/configurator/BuildSheet";
import { BuildViewer } from "@/components/configurator/BuildViewer";
import { OptionPanel } from "@/components/configurator/OptionPanel";
import { PriceBar } from "@/components/configurator/PriceBar";
import { StepRail } from "@/components/configurator/StepRail";
import type { Platform } from "@/lib/api";
import {
  BUILD_PARAM,
  decodeSelection,
  encodeSelection,
  optionBySlug,
  toPriceable,
  toRuleable,
  toggleOption,
} from "@/lib/build";
import { formatCents, priceBuild } from "@/lib/pricing";
import { validateSelection } from "@/lib/rules";

/**
 * Build state, and the one place it is written.
 *
 * The selection is held in React and mirrored into the query string on every change, which is
 * what makes a build shareable and refresh-safe without a round trip. The URL is written with
 * `history.replaceState` rather than a router navigation: a configurator that pushed a history
 * entry per click would take thirty presses of Back to leave. Back and Forward across entries
 * that do exist still restore the build they encode -- that is what the popstate listener is for.
 */
export function ConfiguratorShell({ platform }: { platform: Platform }) {
  const searchParams = useSearchParams();
  const [selected, setSelected] = useState(() =>
    decodeSelection(platform, searchParams.get(BUILD_PARAM)),
  );
  const [stepIndex, setStepIndex] = useState(0);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [announcement, setAnnouncement] = useState("");

  const panelRef = useRef<HTMLDivElement>(null);
  const focusPanelNext = useRef(false);

  const options = useMemo(() => optionBySlug(platform), [platform]);
  const priceable = useMemo(() => toPriceable(platform), [platform]);
  const ruleable = useMemo(() => toRuleable(platform), [platform]);

  const breakdown = useMemo(
    () => priceBuild(priceable, selected),
    // priceBuild throws on a slug the platform does not have; decodeSelection has already
    // filtered those out, so anything reaching here belongs to this platform.
    [priceable, selected],
  );
  const violations = useMemo(() => validateSelection(ruleable, selected), [ruleable, selected]);

  const nameOf = useCallback((slug: string) => options.get(slug)?.name ?? slug, [options]);

  const commit = useCallback(
    (next: string[], spokenChange: string) => {
      setSelected(next);
      setAnnouncement(
        `${spokenChange}. Build total ${formatCents(priceBuild(priceable, next).total_cents)}.`,
      );

      const url = new URL(window.location.href);
      url.searchParams.set(BUILD_PARAM, encodeSelection(platform, next));
      window.history.replaceState(null, "", url);
    },
    [platform, priceable],
  );

  const select = useCallback(
    (slug: string) => {
      const next = toggleOption(platform, selected, slug);
      if (next.length === selected.length && next.every((s, i) => s === selected[i])) return;
      commit(next, `${nameOf(slug)} ${next.includes(slug) ? "added" : "removed"}`);
    },
    [commit, nameOf, platform, selected],
  );

  // Back and Forward land on a URL that already describes a build; read it rather than
  // leaving the page showing a selection the address bar disagrees with.
  useEffect(() => {
    const onPopState = () => {
      const raw = new URLSearchParams(window.location.search).get(BUILD_PARAM);
      setSelected(decodeSelection(platform, raw));
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, [platform]);

  const goToStep = useCallback((index: number, moveFocus = false) => {
    focusPanelNext.current = moveFocus;
    setStepIndex(index);
  }, []);

  // Arrow-key browsing of the step rail keeps focus on the rail, the way tabs are expected to
  // behave. A click or a "Next step" press moves focus into the panel, where the content the
  // press was about now lives.
  useEffect(() => {
    if (!focusPanelNext.current) return;
    focusPanelNext.current = false;
    panelRef.current?.focus();
  }, [stepIndex]);

  const group = platform.option_groups[stepIndex];

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="grid min-h-0 flex-1 grid-rows-[auto_1fr] overflow-y-auto md:grid-cols-[15rem_minmax(0,1fr)_24rem] md:grid-rows-1 md:overflow-hidden lg:grid-cols-[17rem_minmax(0,1fr)_26rem]">
        <StepRail
          groups={platform.option_groups}
          selected={selected}
          activeIndex={stepIndex}
          onSelectStep={goToStep}
        />

        <BuildViewer platform={platform} selected={selected} activeGroupSlug={group?.slug} />

        <OptionPanel
          ref={panelRef}
          group={group}
          stepNumber={stepIndex + 1}
          stepCount={platform.option_groups.length}
          selected={selected}
          violations={violations}
          platform={platform}
          onToggle={select}
          onStep={goToStep}
          nameOf={nameOf}
        />
      </div>

      <PriceBar
        totalCents={breakdown.total_cents}
        optionCount={selected.length}
        violationCount={violations.length}
        sheetOpen={sheetOpen}
        onToggleSheet={() => setSheetOpen((open) => !open)}
      />

      {sheetOpen ? (
        <BuildSheet
          platform={platform}
          selected={selected}
          breakdown={breakdown}
          violations={violations}
          nameOf={nameOf}
          onClose={() => setSheetOpen(false)}
        />
      ) : null}

      <p aria-live="polite" className="sr-only">
        {announcement}
      </p>
    </div>
  );
}
