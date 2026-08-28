import {
  apiErrorSchema,
  catalogSchema,
  platformSchema,
  quoteSchema,
  type Catalog,
  type EnquiryPayload,
  type LeadResult,
  type Platform,
  type QuotePayload,
} from "@/lib/contract";

/**
 * Transport: HTTP calls to FastAPI and the Zod parse at the boundary. Wire shapes live in
 * `lib/contract.ts` -- this file is what actually reaches the network.
 */

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
 */
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
