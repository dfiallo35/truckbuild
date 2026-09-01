import { z } from "zod";

/**
 * Zod schemas mirroring api/app/modules/catalog/presentation/schemas.py field-for-field. Field names stay snake_case
 * to match the wire format exactly -- a renamed or retyped backend field should surface here as
 * a Zod error naming that field, not as a silent mismatch introduced by a translation layer.
 */

const assetKindSchema = z.enum(["hero", "gallery", "thumbnail"]);
const selectionModeSchema = z.enum(["single", "multi"]);
const displayStyleSchema = z.enum(["card", "swatch", "toggle"]);
const ruleRelationSchema = z.enum(["requires", "excludes"]);

const assetSchema = z.object({
  kind: assetKindSchema,
  url: z.string(),
  alt_text: z.string(),
});

/**
 * How selecting the option changes the 3D build model -- `nodes` for geometry, `material_target`
 * plus a colour for a finish. See Stage 14 of the archived development plan (Notion).
 */
const optionModelEffectSchema = z.object({
  nodes: z.array(z.string()),
  material_target: z.string().nullable(),
  base_color_hex: z.string().nullable(),
  metalness: z.number().nullable(),
  roughness: z.number().nullable(),
});

const optionSchema = z.object({
  slug: z.string(),
  name: z.string(),
  price_delta_cents: z.number().int(),
  description: z.string(),
  swatch: assetSchema.nullable(),
  model_effect: optionModelEffectSchema.nullable(),
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

/**
 * The 3D asset behind a platform's build view. `url` is `null` until Stage 15's blob sync has
 * run -- a model whose bytes are not uploaded is not a model.
 */
const buildModelSchema = z.object({
  url: z.string(),
  alt_text: z.string(),
  camera_orbit_deg: z.number(),
  camera_distance_m: z.number(),
  camera_target_y_m: z.number(),
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
  gallery: z.array(assetSchema),
  model: buildModelSchema.nullable(),
  option_groups: z.array(optionGroupSchema),
  rules: z.array(optionRuleSchema),
});

export const catalogSchema = z.object({
  platforms: z.array(platformSchema),
});

export type Asset = z.infer<typeof assetSchema>;
export type BuildModel = z.infer<typeof buildModelSchema>;
export type OptionModelEffect = z.infer<typeof optionModelEffectSchema>;
export type Option = z.infer<typeof optionSchema>;
export type OptionGroup = z.infer<typeof optionGroupSchema>;
export type OptionRule = z.infer<typeof optionRuleSchema>;
export type Platform = z.infer<typeof platformSchema>;
export type Catalog = z.infer<typeof catalogSchema>;

/**
 * Lead submission wire shapes. Note what a payload does not carry: a price. The server
 * recomputes the total from the option slugs and ignores anything else, so sending one would be
 * theatre.
 */

const quoteLineSchema = z.object({
  group_name: z.string(),
  option_slug: z.string(),
  option_name: z.string(),
  price_delta_cents: z.number().int(),
});

export const quoteSchema = z.object({
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
export const apiErrorSchema = z.object({
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
