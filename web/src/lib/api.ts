import { z } from "zod";

/**
 * Zod schemas mirroring api/app/modules/catalog/presentation/schemas.py field-for-field. Field names stay snake_case
 * to match the wire format exactly -- a renamed or retyped backend field should surface here as
 * a Zod error naming that field, not as a silent mismatch introduced by a translation layer.
 */

const assetKindSchema = z.enum(["hero", "gallery", "thumbnail", "layer"]);
const selectionModeSchema = z.enum(["single", "multi"]);
const displayStyleSchema = z.enum(["card", "swatch", "toggle"]);
const ruleRelationSchema = z.enum(["requires", "excludes"]);

const assetSchema = z.object({
  kind: assetKindSchema,
  url: z.string(),
  alt_text: z.string(),
});

/**
 * One image in the configurator viewer composite. `z_index` is what stacks it over the
 * platform's base layer, which is always 0.
 */
const layerSchema = z.object({
  url: z.string(),
  alt_text: z.string(),
  z_index: z.number().int(),
});

const optionSchema = z.object({
  slug: z.string(),
  name: z.string(),
  price_delta_cents: z.number().int(),
  description: z.string(),
  layer: layerSchema.nullable(),
  swatch: assetSchema.nullable(),
});

const optionGroupSchema = z.object({
  slug: z.string(),
  name: z.string(),
  selection_mode: selectionModeSchema,
  required: z.boolean(),
  display_style: displayStyleSchema,
  options: z.array(optionSchema),
});

const optionRuleSchema = z.object({
  subject: z.string(),
  relation: ruleRelationSchema,
  object: z.string(),
});

export const platformSchema = z.object({
  slug: z.string(),
  name: z.string(),
  purpose: z.string(),
  chassis_basis: z.string(),
  base_price_cents: z.number().int(),
  spec_highlights: z.array(z.string()),
  standard_equipment: z.array(z.string()),
  hero_image: assetSchema.nullable(),
  viewer_base: layerSchema.nullable(),
  gallery: z.array(assetSchema),
  option_groups: z.array(optionGroupSchema),
  rules: z.array(optionRuleSchema),
});

const catalogSchema = z.object({
  platforms: z.array(platformSchema),
});

export type Asset = z.infer<typeof assetSchema>;
export type Layer = z.infer<typeof layerSchema>;
export type Option = z.infer<typeof optionSchema>;
export type OptionGroup = z.infer<typeof optionGroupSchema>;
export type OptionRule = z.infer<typeof optionRuleSchema>;
export type Platform = z.infer<typeof platformSchema>;
export type Catalog = z.infer<typeof catalogSchema>;

class ApiError extends Error {
  constructor(
    message: string,
    readonly status?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function apiBaseUrl(): string {
  const url = process.env.API_BASE_URL;
  if (!url) {
    throw new Error("API_BASE_URL is not set (see .env.example)");
  }
  return url;
}

async function fetchJson(path: string): Promise<unknown> {
  const res = await fetch(`${apiBaseUrl()}${path}`);
  if (res.status === 404) {
    throw new ApiError(`not found: ${path}`, 404);
  }
  if (!res.ok) {
    throw new ApiError(`request to ${path} failed with status ${res.status}`, res.status);
  }
  return res.json();
}

export async function fetchCatalog(): Promise<Catalog> {
  return catalogSchema.parse(await fetchJson("/v1/catalog"));
}

export async function fetchPlatform(slug: string): Promise<Platform | null> {
  try {
    return platformSchema.parse(await fetchJson(`/v1/platforms/${slug}`));
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return null;
    }
    throw error;
  }
}

/**
 * Lead submission. The browser never posts here directly -- these run inside Server Actions
 * (see `src/lib/leads.ts`), which is what keeps `API_BASE_URL` server-side.
 *
 * Note what a payload does not carry: a price. The server recomputes the total from the option
 * slugs and ignores anything else, so sending one would be theatre.
 */

const quoteLineSchema = z.object({
  group_name: z.string(),
  option_slug: z.string(),
  option_name: z.string(),
  price_delta_cents: z.number().int(),
});

const quoteSchema = z.object({
  ref: z.string(),
  kind: z.enum(["build", "enquiry"]),
  platform_slug: z.string().nullable(),
  platform_name: z.string().nullable(),
  base_price_cents: z.number().int().nullable(),
  total_cents: z.number().int().nullable(),
  lines: z.array(quoteLineSchema),
  created_at: z.string(),
});

/** The one error shape the API answers every rejection with -- see api/app/errors.py. */
const apiErrorSchema = z.object({
  code: z.string(),
  message: z.string(),
  errors: z
    .array(
      z.object({
        field: z.string().nullable().default(null),
        message: z.string(),
        code: z.string().nullable().default(null),
      }),
    )
    .default([]),
});

export type Quote = z.infer<typeof quoteSchema>;
export type ApiErrorBody = z.infer<typeof apiErrorSchema>;
export type LeadResult = { ok: true; quote: Quote } | { ok: false; error: ApiErrorBody };

export type ContactPayload = { name: string; email: string; phone: string };

export type QuotePayload = {
  platform_slug: string;
  option_slugs: string[];
  contact: ContactPayload;
  intended_use: string;
  timeline: string;
  notes: string;
  website: string;
  elapsed_ms: number | null;
};

export type EnquiryPayload = Omit<QuotePayload, "platform_slug" | "option_slugs"> & {
  platform_slug: string | null;
};

async function postLead(path: string, payload: unknown, forwardedFor: string | null) {
  const res = await fetch(`${apiBaseUrl()}${path}`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      // The visitor's address, not this server's. Without it every submission in the world
      // would share one rate-limit bucket -- see api/app/modules/quotes/presentation/quotes_api.py.
      ...(forwardedFor ? { "x-forwarded-for": forwardedFor } : {}),
    },
    body: JSON.stringify(payload),
    cache: "no-store",
  });

  const body: unknown = await res.json();
  if (res.ok) {
    return { ok: true as const, quote: quoteSchema.parse(body) };
  }
  return { ok: false as const, error: apiErrorSchema.parse(body) };
}

export async function submitQuote(
  payload: QuotePayload,
  forwardedFor: string | null,
): Promise<LeadResult> {
  return postLead("/v1/quotes", payload, forwardedFor);
}

export async function submitEnquiry(
  payload: EnquiryPayload,
  forwardedFor: string | null,
): Promise<LeadResult> {
  return postLead("/v1/enquiries", payload, forwardedFor);
}
