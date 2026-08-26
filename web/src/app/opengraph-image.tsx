import { ImageResponse } from "next/og";

import { SITE_DESCRIPTION, SITE_NAME } from "@/lib/site";

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const alt = `${SITE_NAME} — ${SITE_DESCRIPTION}`;

const CANVAS = "#0b0b0c";
const INK = "#f2f0ec";
const INK_MUTED = "#a3a2a0";
const ACCENT = "#f5a524";

export default function Image() {
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
        style={{ display: "flex", width: 64, height: 6, backgroundColor: ACCENT, marginBottom: 32 }}
      />
      <div
        style={{
          display: "flex",
          fontSize: 76,
          fontWeight: 700,
          letterSpacing: -1,
          textTransform: "uppercase",
          color: INK,
        }}
      >
        {SITE_NAME}
      </div>
      <div
        style={{ display: "flex", fontSize: 30, color: INK_MUTED, marginTop: 16, maxWidth: 900 }}
      >
        {SITE_DESCRIPTION}
      </div>
    </div>,
    { ...size },
  );
}
