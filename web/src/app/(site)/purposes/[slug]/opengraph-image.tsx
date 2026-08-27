import { ImageResponse } from "next/og";

import { getPurpose, PURPOSES } from "@/lib/purposes";
import { SITE_NAME } from "@/lib/site";

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export function generateStaticParams() {
  return PURPOSES.map((purpose) => ({ slug: purpose.slug }));
}

const CANVAS = "#0b0b0c";
const INK = "#f2f0ec";
const INK_MUTED = "#a3a2a0";
const ACCENT = "#f5a524";

export default async function Image(props: PageProps<"/purposes/[slug]">) {
  const { slug } = await props.params;
  const purpose = getPurpose(slug);

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
        {purpose?.name ?? SITE_NAME}
      </div>
      {purpose ? (
        <div
          style={{ display: "flex", fontSize: 30, color: INK_MUTED, marginTop: 16, maxWidth: 900 }}
        >
          {purpose.tagline}
        </div>
      ) : null}
    </div>,
    { ...size },
  );
}
