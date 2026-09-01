import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Cache Components (Next.js 16 PPR). This is what lets catalog data live in FastAPI while
  // marketing pages still prerender: catalog reads sit inside `use cache` functions tagged
  // with `catalog` / `platform-<slug>`, and FastAPI revalidates those tags on change.
  // See docs/decisions.md.
  cacheComponents: true,

  // This repo already has its own CLAUDE.md/AGENTS.md conventions (see docs/); don't let
  // `next dev` regenerate its own stub copies in web/ on every run.
  agentRules: false,

  images: {
    formats: ["image/avif", "image/webp"],
    // Posters (`platform.hero_image`) served from Vercel Blob once that migration happens --
    // see Stage 16 of the archived development plan (Notion). The GLB itself is fetched directly by `scene.ts`, not
    // through `next/image`, and needs no entry here.
    remotePatterns: [{ protocol: "https", hostname: "*.public.blob.vercel-storage.com" }],
  },

  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          // MIME sniffing turns a user-supplied file served from this origin into a script.
          { key: "X-Content-Type-Options", value: "nosniff" },
          // No one has a reason to frame a configurator, and clickjacking a "Request this
          // build" button is a real lead-theft shape.
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Content-Security-Policy", value: "frame-ancestors 'none'" },
          // Send the origin to other sites, the full path only within this one, so an outbound
          // link cannot leak a visitor's configured build in a Referer header.
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          // Nothing here uses any of these; denying them means a future dependency cannot
          // start using them quietly.
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=(), interest-cohort=()",
          },
          // Two years, which is what preload lists require. Harmless before a custom domain
          // exists, and one less thing to remember on the day one does.
          {
            key: "Strict-Transport-Security",
            value: "max-age=63072000; includeSubDomains; preload",
          },
        ],
      },
    ];
  },
};

export default nextConfig;
