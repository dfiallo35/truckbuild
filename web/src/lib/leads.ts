import type { ApiErrorBody, EnquiryPayload, QuotePayload } from "@/lib/api";

/**
 * Turning a submitted `<form>` into an API payload, and an API rejection back into something a
 * form can render beside the field at fault.
 *
 * Pure on purpose: the Server Actions in `src/lib/actions.ts` do the I/O, this does the
 * shaping, and Vitest can hold the shape still without a network.
 */

export type LeadFieldErrors = Record<string, string[]>;

export type LeadFormState = {
  status: "idle" | "error";
  /** The headline the form shows above itself; "" when there is nothing to say. */
  message: string;
  errors: LeadFieldErrors;
};

export const IDLE_LEAD_STATE: LeadFormState = { status: "idle", message: "", errors: {} };

/** Filled in by a bot, never by a person -- see api/app/modules/quotes/domain/spam.py. */
export const HONEYPOT_FIELD = "website";

/** When the form was rendered, so the API can tell typing from scripting. */
export const STARTED_AT_FIELD = "started_at";

export const UNREACHABLE_MESSAGE =
  "We couldn't reach the build desk. Try again in a moment, or email sales directly.";

function text(formData: FormData, name: string): string {
  const value = formData.get(name);
  return typeof value === "string" ? value.trim() : "";
}

/**
 * How long the form was open. Computed here rather than trusted from the browser as a number:
 * the client sends when it started, this side owns "now".
 */
export function elapsedMs(formData: FormData, now: number = Date.now()): number | null {
  const raw = text(formData, STARTED_AT_FIELD);
  const startedAt = Number(raw);
  if (!raw || !Number.isFinite(startedAt)) return null;
  return now - startedAt;
}

export function parseOptionSlugs(raw: string): string[] {
  return raw
    .split(",")
    .map((slug) => slug.trim())
    .filter((slug) => slug.length > 0);
}

function common(formData: FormData, now?: number) {
  return {
    contact: {
      name: text(formData, "name"),
      email: text(formData, "email"),
      phone: text(formData, "phone"),
    },
    intended_use: text(formData, "intended_use"),
    timeline: text(formData, "timeline"),
    notes: text(formData, "notes"),
    website: text(formData, HONEYPOT_FIELD),
    elapsed_ms: elapsedMs(formData, now),
  };
}

export function parseBuildRequest(formData: FormData, now?: number): QuotePayload {
  return {
    ...common(formData, now),
    platform_slug: text(formData, "platform_slug"),
    option_slugs: parseOptionSlugs(text(formData, "option_slugs")),
  };
}

export function parseEnquiry(formData: FormData, now?: number): EnquiryPayload {
  return {
    ...common(formData, now),
    platform_slug: text(formData, "platform_slug") || null,
  };
}

/**
 * API field paths keyed by the input they belong to. The API names the payload path
 * (`contact.email`); a form knows its inputs by name (`email`), so the `contact.` prefix is
 * dropped here rather than in every field that renders an error.
 */
export function toFieldErrors(error: ApiErrorBody): LeadFieldErrors {
  const errors: LeadFieldErrors = {};
  for (const item of error.errors) {
    if (!item.field) continue;
    const key = item.field.replace(/^contact\./, "");
    (errors[key] ??= []).push(item.message);
  }
  return errors;
}

/**
 * A rejection the form can render. Errors that name no field -- a rate limit, a rejected
 * submission -- survive as the headline message, which is the only place they would be seen.
 */
export function errorState(error: ApiErrorBody): LeadFormState {
  const fieldErrors = toFieldErrors(error);
  const unattached = error.errors.filter((item) => !item.field).map((item) => item.message);
  const noFieldsNamed = Object.keys(fieldErrors).length === 0;

  return {
    status: "error",
    message: noFieldsNamed && unattached.length > 0 ? unattached.join(" ") : error.message,
    errors: fieldErrors,
  };
}
