import { Footer } from "@/components/Footer";
import { Header } from "@/components/Header";

/**
 * Marketing chrome. The configurator deliberately sits outside this group: it is a full-bleed
 * workspace with its own minimal bar, not a page with a site header on top of it.
 */
export default function SiteLayout({ children }: LayoutProps<"/">) {
  return (
    <>
      <Header />
      <main className="flex flex-1 flex-col">{children}</main>
      <Footer />
    </>
  );
}
