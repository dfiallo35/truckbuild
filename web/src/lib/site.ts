export const SITE_NAME = "TruckBuild";

export const PRIMARY_NAV: ReadonlyArray<{ label: string; href: string }> = [
  { label: "Platforms", href: "/platforms" },
];

export const SALES_EMAIL = "sales@truckbuild.example";
export const SALES_PHONE = "+1 (555) 010-2044";

export const FOOTER_COLUMNS: ReadonlyArray<{
  heading: string;
  links: ReadonlyArray<{ label: string; href: string }>;
}> = [
  {
    heading: "Platforms",
    links: [{ label: "Browse platforms", href: "/platforms" }],
  },
  {
    heading: "Talk to us",
    links: [
      { label: SALES_EMAIL, href: `mailto:${SALES_EMAIL}` },
      { label: SALES_PHONE, href: `tel:${SALES_PHONE.replace(/[^+\d]/g, "")}` },
    ],
  },
];
