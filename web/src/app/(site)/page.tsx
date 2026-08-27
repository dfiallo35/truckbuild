import Image from "next/image";

import { CTAButton } from "@/components/CTAButton";
import { PlatformCard } from "@/components/PlatformCard";
import { ProcessSteps } from "@/components/ProcessSteps";
import { ProofStrip } from "@/components/ProofStrip";
import { PurposeCard } from "@/components/PurposeCard";
import { SectionHeading } from "@/components/SectionHeading";
import { getCatalog } from "@/lib/catalog";
import { PURPOSES } from "@/lib/purposes";

const PROCESS_STEPS = [
  {
    title: "Consult",
    description:
      "Tell us the mission — payload, terrain, crew size, timeline. We tell you what platform and options actually fit it.",
  },
  {
    title: "Design",
    description:
      "Configure every system against a live compatibility check, so an incompatible combination gets caught before a part is ordered, not after.",
  },
  {
    title: "Build",
    description:
      "Chassis to shop floor, upfit to spec, inspected at every stage by the crew that's accountable for the finished truck.",
  },
  {
    title: "Deliver",
    description:
      "A full walkthrough, complete documentation, and a truck that's ready to work its first day on the job.",
  },
] as const;

const PROOF_STATS = [
  { value: "3", label: "Platforms in production" },
  { value: "18–24 wk", label: "Average build time" },
  { value: "3-yr", label: "Structural warranty" },
  { value: "Lower 48", label: "Delivery coverage" },
] as const;

export default async function Home() {
  const catalog = await getCatalog();

  return (
    <>
      <section className="relative flex min-h-screen flex-col justify-end overflow-hidden">
        <Image
          src="/images/site/hero.jpg"
          alt=""
          fill
          priority
          sizes="100vw"
          className="object-cover"
        />
        <div className="from-canvas via-canvas/50 absolute inset-0 bg-gradient-to-t to-transparent" />
        <div className="relative mx-auto flex w-full max-w-6xl flex-col gap-8 px-6 pt-40 pb-20 md:px-10">
          <SectionHeading
            eyebrow="Engineered to order"
            title="Purpose-built trucks, configured to spec"
            description="Pick a platform, configure every system, and walk away with a build a shop can quote today — not a starting point for a conversation."
          />
          <div className="flex flex-wrap gap-4">
            <CTAButton href="/builds">Browse builds</CTAButton>
            <CTAButton href="/contact" variant="secondary">
              Talk to sales
            </CTAButton>
          </div>
        </div>
      </section>

      <section className="border-border py-section border-b px-6 md:px-10">
        <div className="mx-auto flex max-w-6xl flex-col gap-12">
          <SectionHeading
            eyebrow="Three platforms"
            title="One job each, done completely"
            description="Every platform is built around a single mission, not a trim level trying to satisfy everyone at once."
          />
          <div className="grid gap-x-8 gap-y-14 sm:grid-cols-2 lg:grid-cols-3">
            {catalog.platforms.map((platform) => (
              <PlatformCard key={platform.slug} platform={platform} />
            ))}
          </div>
        </div>
      </section>

      <section className="border-border py-section border-b px-6 md:px-10">
        <div className="mx-auto flex max-w-6xl flex-col gap-12">
          <SectionHeading
            eyebrow="Built for the job"
            title="Find your vertical"
            description="Same engineering rigor, different mission. Start from the job you're actually doing."
          />
          <div className="grid gap-6 sm:grid-cols-3">
            {PURPOSES.map((purpose) => (
              <PurposeCard key={purpose.slug} purpose={purpose} />
            ))}
          </div>
        </div>
      </section>

      <section className="border-border py-section border-b px-6 md:px-10">
        <div className="mx-auto flex max-w-6xl flex-col gap-12">
          <SectionHeading
            eyebrow="How it works"
            title="Consult to delivery"
            description="Four stages. No surprises in between."
          />
          <ProcessSteps steps={PROCESS_STEPS} />
        </div>
      </section>

      <section className="px-6 md:px-10">
        <div className="mx-auto max-w-6xl">
          <ProofStrip stats={PROOF_STATS} />
        </div>
      </section>

      <section className="py-section px-6 md:px-10">
        <div className="mx-auto flex max-w-6xl flex-col items-start gap-8">
          <SectionHeading title="Ready to spec yours?" />
          <div className="flex flex-wrap gap-4">
            <CTAButton href="/builds">Browse builds</CTAButton>
            <CTAButton href="/contact" variant="secondary">
              Talk to sales
            </CTAButton>
          </div>
        </div>
      </section>
    </>
  );
}
