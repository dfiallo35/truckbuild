export const SITE_NAME = "TruckBuild";
export const SITE_DESCRIPTION = "Purpose-built truck upfits, engineered and configured to order.";

// The deployed origin. This is a compile-time constant, not an environment variable, so it
// feeds metadataBase, canonical URLs, sitemap.xml, and JSON-LD at build time -- changing the
// domain means a rebuild, not a redeploy of the same artifact.
export const SITE_URL = "https://truckbuild.vercel.app";

export const PRIMARY_NAV: ReadonlyArray<{ label: string; href: string }> = [
  { label: "Builds", href: "/builds" },
  { label: "Process", href: "/process" },
  { label: "Gallery", href: "/gallery" },
  { label: "About", href: "/about" },
];

export const SALES_EMAIL = "sales@truckbuild.example";
export const SALES_PHONE = "+1 (555) 010-2044";

export const FOOTER_COLUMNS: ReadonlyArray<{
  heading: string;
  links: ReadonlyArray<{ label: string; href: string }>;
}> = [
  {
    heading: "Company",
    links: [
      { label: "Builds", href: "/builds" },
      { label: "Our process", href: "/process" },
      { label: "Gallery", href: "/gallery" },
      { label: "About", href: "/about" },
    ],
  },
  {
    heading: "Talk to us",
    links: [
      { label: "Contact", href: "/contact" },
      { label: SALES_EMAIL, href: `mailto:${SALES_EMAIL}` },
      { label: SALES_PHONE, href: `tel:${SALES_PHONE.replace(/[^+\d]/g, "")}` },
    ],
  },
  {
    heading: "Legal",
    links: [{ label: "Privacy", href: "/legal/privacy" }],
  },
];
