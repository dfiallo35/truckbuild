"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useActionState } from "react";

import {
  Field,
  FormNotice,
  SpamControls,
  SubmitButton,
  TextAreaField,
  TimelineField,
} from "@/components/leads/LeadFields";
import { requestBuild } from "@/lib/actions";
import { BUILD_PARAM, encodeSelection } from "@/lib/build";
import { useBuildView } from "@/lib/buildView";
import type { Platform } from "@/lib/contract";
import { formatCents, formatDelta } from "@/lib/format";
import { IDLE_LEAD_STATE } from "@/lib/leads";

/**
 * Handing the work order across the counter: the build on the left, priced and locked, the
 * details we need to quote it on the right.
 *
 * The build itself still lives in the query string, so this reads the same URL the configurator
 * wrote and repairs it the same way -- a customer who edits the address bar, or opens a link
 * from six months ago, gets a build that still makes sense rather than an error.
 */
export function BuildRequest({ platform }: { platform: Platform }) {
  const searchParams = useSearchParams();
  const [state, action] = useActionState(requestBuild, IDLE_LEAD_STATE);

  const { selected, breakdown, violations } = useBuildView(platform, searchParams);

  const encoded = encodeSelection(platform, selected);
  const backToConfigurator = `/configurator/${platform.slug}?${BUILD_PARAM}=${encoded}`;
  const nameOf = (slug: string) =>
    platform.option_groups.flatMap((group) => group.options).find((o) => o.slug === slug)?.name ??
    slug;

  /**
   * What has to be fixed before this build can be sent: what the client-side rules engine can
   * see, plus anything the server said about the selection. The server's are the ones that
   * matter -- it validates against the live catalog -- and without this they would have no
   * field to appear beside, since the selection is a hidden input rather than something the
   * customer typed.
   */
  const blockers = [
    ...violations.map((violation) =>
      violation.kind === "requires"
        ? `${nameOf(violation.option)} needs the ${nameOf(violation.needs!)}.`
        : `${nameOf(violation.option)} cannot be fitted with the ${nameOf(violation.conflicts_with!)}.`,
    ),
    ...(state.errors.option_slugs ?? []),
  ];

  const chosen = new Set(selected);
  const lines = platform.option_groups
    .map((group) => ({ group, options: group.options.filter((o) => chosen.has(o.slug)) }))
    .filter((line) => line.options.length > 0);

  return (
    <div className="mx-auto grid w-full max-w-6xl gap-12 px-6 py-12 md:grid-cols-[1fr_1.1fr] md:gap-16 md:px-10 md:py-16">
      <aside className="flex flex-col gap-6 md:sticky md:top-8 md:self-start">
        <div className="flex flex-col gap-1">
          <span className="font-data text-accent text-xs tracking-[0.22em] uppercase">
            Your build
          </span>
          <h1 className="font-display text-ink text-3xl tracking-tight uppercase md:text-4xl">
            {platform.name}
          </h1>
          <p className="text-ink-faint text-xs">{platform.chassis_basis}</p>
        </div>

        <dl className="border-border flex flex-col border-t">
          <div className="border-border flex items-baseline justify-between gap-4 border-b py-3">
            <dt className="text-ink-muted text-sm">Base vehicle</dt>
            <dd className="font-data text-ink text-sm tabular-nums">
              {formatCents(breakdown.base_price_cents)}
            </dd>
          </div>

          {lines.map(({ group, options }) => (
            <div key={group.slug} className="border-border border-b py-3">
              <dt className="font-data text-ink-faint mb-2 text-[0.625rem] tracking-[0.18em] uppercase">
                {group.name}
              </dt>
              {options.map((option) => (
                <dd
                  key={option.slug}
                  className="flex items-baseline justify-between gap-4 py-0.5 text-sm"
                >
                  <span className="text-ink-muted">{option.name}</span>
                  <span
                    className={`font-data shrink-0 text-sm tabular-nums ${
                      option.price_delta_cents === 0 ? "text-ink-faint" : "text-ink"
                    }`}
                  >
                    {formatDelta(option.price_delta_cents)}
                  </span>
                </dd>
              ))}
            </div>
          ))}

          <div className="flex items-baseline justify-between gap-4 pt-4">
            <dt className="font-display text-sm tracking-[0.1em] uppercase">Build total</dt>
            <dd className="font-display text-accent text-2xl tabular-nums">
              {formatCents(breakdown.total_cents)}
            </dd>
          </div>
        </dl>

        <p className="text-ink-faint text-xs">
          An estimate from the options you picked. We confirm the final price with you — freight,
          registration, and any custom work are quoted with it.
        </p>

        <Link
          href={backToConfigurator}
          className="font-data text-ink-muted hover:text-accent focus-visible:outline-accent self-start text-xs tracking-[0.14em] uppercase focus-visible:outline-2 focus-visible:outline-offset-4"
        >
          ← Keep configuring
        </Link>
      </aside>

      <form action={action} className="flex flex-col gap-6">
        <div className="flex flex-col gap-2">
          <h2 className="font-display text-ink text-xl tracking-tight uppercase">
            Send it to a build specialist
          </h2>
          <p className="text-ink-muted text-sm">
            We price it properly, check what the chassis will take, and come back within one
            business day.
          </p>
        </div>

        <FormNotice message={state.message} />

        {blockers.length > 0 ? (
          <div className="border-accent/40 bg-accent/5 flex flex-col gap-2 border-l-2 px-4 py-3">
            <p className="font-data text-accent text-[0.6875rem] tracking-[0.12em] uppercase">
              Resolve before sending
            </p>
            {blockers.map((blocker) => (
              <p key={blocker} className="text-ink text-xs">
                {blocker}
              </p>
            ))}
            <Link
              href={backToConfigurator}
              className="font-data text-accent self-start text-[0.6875rem] tracking-[0.12em] uppercase underline underline-offset-4"
            >
              Fix it in the configurator
            </Link>
          </div>
        ) : null}

        <input type="hidden" name="platform_slug" value={platform.slug} readOnly />
        <input type="hidden" name="option_slugs" value={encoded} readOnly />
        <SpamControls />

        <div className="grid gap-6 sm:grid-cols-2">
          <Field label="Name" name="name" errors={state.errors} required autoComplete="name" />
          <Field
            label="Email"
            name="email"
            type="email"
            errors={state.errors}
            required
            autoComplete="email"
          />
        </div>

        <Field
          label="Phone (optional)"
          name="phone"
          type="tel"
          errors={state.errors}
          autoComplete="tel"
        />

        <TimelineField />

        <TextAreaField
          label="What's the job?"
          name="intended_use"
          errors={state.errors}
          placeholder="Payload, terrain, crew size — whatever tells us the work."
        />

        <TextAreaField
          label="Anything else (optional)"
          name="notes"
          errors={state.errors}
          rows={3}
          placeholder="Deadlines, trade-in, a spec you already know you need."
        />

        <SubmitButton disabled={violations.length > 0}>Send build request</SubmitButton>
      </form>
    </div>
  );
}
