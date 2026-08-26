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
  },
};

export default nextConfig;
