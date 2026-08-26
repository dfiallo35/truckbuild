import { ImageResponse } from "next/og";

import { getCatalog, getPlatform } from "@/lib/catalog";
import { SITE_NAME } from "@/lib/site";

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export async function generateStaticParams() {
  const catalog = await getCatalog();
  return catalog.platforms.map((platform) => ({ slug: platform.slug }));
}

const CANVAS = "#0b0b0c";
const INK = "#f2f0ec";
const INK_MUTED = "#a3a2a0";
const ACCENT = "#f5a524";

export default async function Image(props: PageProps<"/builds/[slug]">) {
  const { slug } = await props.params;
  const platform = await getPlatform(slug);
  const price = platform ? (platform.base_price_cents / 100).toLocaleString("en-US") : null;

  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "flex-end",
        padding: 80,
        backgroundColor: CANVAS,
        backgroundImage: `radial-gradient(circle at 78% 88%, rgba(245,165,36,0.35), transparent 60%)`,
      }}
    >
      <div
        style={{
          display: "flex",
          fontSize: 24,
          letterSpacing: 4,
          textTransform: "uppercase",
          color: ACCENT,
        }}
      >
        {SITE_NAME}
      </div>
      <div
        style={{
          display: "flex",
          fontSize: 80,
          fontWeight: 700,
          letterSpacing: -1,
          textTransform: "uppercase",
          color: INK,
          marginTop: 16,
        }}
      >
        {platform?.name ?? SITE_NAME}
      </div>
      {platform ? (
        <div
          style={{ display: "flex", fontSize: 30, color: INK_MUTED, marginTop: 16, maxWidth: 900 }}
        >
          {platform.purpose}
        </div>
      ) : null}
      {price ? (
        <div style={{ display: "flex", fontSize: 34, color: ACCENT, marginTop: 32 }}>
          Starting at ${price}
        </div>
      ) : null}
    </div>,
    { ...size },
  );
}
