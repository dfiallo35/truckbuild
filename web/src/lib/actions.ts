"use server";

import { headers } from "next/headers";
import { redirect } from "next/navigation";

import { submitEnquiry, submitQuote } from "@/lib/api";
import {
  errorState,
  parseBuildRequest,
  parseEnquiry,
  UNREACHABLE_MESSAGE,
  type LeadFormState,
} from "@/lib/leads";

/**
 * The forms' only route to FastAPI.
 *
 * A Server Action rather than a route handler or a client-side `fetch`: the API origin and any
 * secret stay on the server, and the form still works the moment the HTML lands, before any
 * JavaScript has hydrated.
 */

async function visitorAddress(): Promise<string | null> {
  const requestHeaders = await headers();
  return requestHeaders.get("x-forwarded-for") ?? requestHeaders.get("x-real-ip");
}

export async function requestBuild(
  _previous: LeadFormState,
  formData: FormData,
): Promise<LeadFormState> {
  const payload = parseBuildRequest(formData);

  let ref: string;
  try {
    const result = await submitQuote(payload, await visitorAddress());
    if (!result.ok) return errorState(result.error);
    ref = result.quote.ref;
  } catch {
    return { status: "error", message: UNREACHABLE_MESSAGE, errors: {} };
  }

  // Outside the try: `redirect` works by throwing, and catching it here would swallow the
  // navigation and leave the customer staring at the form they just submitted.
  redirect(`/thank-you?ref=${encodeURIComponent(ref)}`);
}

export async function sendEnquiry(
  _previous: LeadFormState,
  formData: FormData,
): Promise<LeadFormState> {
  const payload = parseEnquiry(formData);

  let ref: string;
  try {
    const result = await submitEnquiry(payload, await visitorAddress());
    if (!result.ok) return errorState(result.error);
    ref = result.quote.ref;
  } catch {
    return { status: "error", message: UNREACHABLE_MESSAGE, errors: {} };
  }

  redirect(`/thank-you?ref=${encodeURIComponent(ref)}`);
}
