import type { Metadata } from "next";
import { Suspense } from "react";

import { CTAButton } from "@/components/CTAButton";
import { SALES_EMAIL, SALES_PHONE } from "@/lib/site";

export const metadata: Metadata = {
  title: "Request received",
  description: "Your build request is with a TruckBuild specialist.",
  // A confirmation page belongs to one submission, not to search results.
  robots: { index: false, follow: true },
};

const NEXT_STEPS = [
  {
    heading: "A confirmation is on its way",
    body: "It repeats the build and the reference, so you have the whole thing in writing.",
  },
  {
    heading: "We price it properly",
    body: "A specialist checks the spec against the chassis, then prices freight, registration, and anything custom.",
  },
  {
    heading: "You hear from us within one business day",
    body: "Usually sooner. Reply to the confirmation and it lands with the same person.",
  },
];

export default function ThankYouPage(props: PageProps<"/thank-you">) {
  return (
    <section className="py-section px-6 md:px-10">
      <div className="mx-auto flex max-w-3xl flex-col gap-12">
        {/* An explicit h1 rather than SectionHeading: this line is the page, the way a
            platform's name is on /builds/[slug]. */}
        <div className="flex flex-col gap-3">
          <span className="font-data text-accent text-xs tracking-[0.22em] uppercase">
            Received
          </span>
          <h1 className="font-display text-ink text-3xl tracking-tight uppercase md:text-5xl">
            Your request is in
          </h1>
          <p className="text-ink-muted max-w-2xl text-base md:text-lg">
            It&apos;s on a build specialist&apos;s desk, not in a queue somewhere.
          </p>
        </div>

        {/* The reference comes from the query string, so it streams in while the rest of the
            page prerenders. */}
        <Suspense fallback={<ReferencePlate ref_={null} />}>
          <Reference searchParams={props.searchParams} />
        </Suspense>

        <ol className="border-border flex flex-col border-t">
          {NEXT_STEPS.map((step, index) => (
            <li
              key={step.heading}
              className="border-border grid gap-2 border-b py-5 sm:grid-cols-[3rem_1fr]"
            >
              <span className="font-data text-ink-faint text-xs tracking-[0.18em] tabular-nums">
                {String(index + 1).padStart(2, "0")}
              </span>
              <div className="flex flex-col gap-1">
                <h2 className="font-display text-ink text-sm tracking-[0.08em] uppercase">
                  {step.heading}
                </h2>
                <p className="text-ink-muted text-sm">{step.body}</p>
              </div>
            </li>
          ))}
        </ol>

        <div className="flex flex-col gap-6">
          <p className="text-ink-muted text-sm">
            Need us sooner? Call{" "}
            <a
              href={`tel:${SALES_PHONE.replace(/[^+\d]/g, "")}`}
              className="text-ink hover:text-accent"
            >
              {SALES_PHONE}
            </a>{" "}
            or email{" "}
            <a href={`mailto:${SALES_EMAIL}`} className="text-ink hover:text-accent">
              {SALES_EMAIL}
            </a>
            .
          </p>
          <div className="flex flex-wrap gap-4">
            <CTAButton href="/builds">See the other platforms</CTAButton>
            <CTAButton href="/process" variant="secondary">
              How a build runs
            </CTAButton>
          </div>
        </div>
      </div>
    </section>
  );
}

async function Reference({
  searchParams,
}: {
  searchParams: PageProps<"/thank-you">["searchParams"];
}) {
  const params = await searchParams;
  const raw = params.ref;
  const ref = typeof raw === "string" && /^TB-[A-Z0-9]{6}$/.test(raw) ? raw : null;
  return <ReferencePlate ref_={ref} />;
}

/**
 * The reference, set the way it is stamped on a work order: the one number the customer needs
 * to keep, large enough to read off a screen and back down a phone.
 */
function ReferencePlate({ ref_ }: { ref_: string | null }) {
  return (
    <div className="border-border bg-canvas-raised flex flex-col gap-2 border px-6 py-8">
      <span className="font-data text-ink-faint text-[0.625rem] tracking-[0.22em] uppercase">
        Reference
      </span>
      <p className="font-data text-accent text-3xl tracking-[0.24em] tabular-nums md:text-4xl">
        {ref_ ?? "—"}
      </p>
      <p className="text-ink-muted text-sm">
        {ref_
          ? "Quote it in any reply and we'll pick up where you left off."
          : "Your reference is in the confirmation email we just sent."}
      </p>
    </div>
  );
}
