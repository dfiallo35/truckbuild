import { CTAButton } from "@/components/CTAButton";
import { SectionHeading } from "@/components/SectionHeading";

export default function Home() {
  return (
    <section className="border-border flex min-h-screen flex-col items-start justify-center gap-8 border-b px-6 md:px-10">
      <div className="mx-auto flex w-full max-w-6xl flex-col items-start gap-8">
        <SectionHeading
          eyebrow="Engineered to order"
          title="Purpose-built truck upfits"
          description="Configure a platform, watch the price update live, and get a build a shop can actually quote."
        />
        <div className="flex flex-wrap gap-4">
          <CTAButton href="/platforms">Browse platforms</CTAButton>
          <CTAButton href="/contact" variant="secondary">
            Talk to Sales
          </CTAButton>
        </div>
      </div>
    </section>
  );
}
