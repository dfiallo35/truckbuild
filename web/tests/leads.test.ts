import { describe, expect, it } from "vitest";

import {
  errorState,
  parseBuildRequest,
  parseEnquiry,
  toFieldErrors,
  type LeadFormState,
} from "@/lib/leads";

/**
 * The form-to-payload seam. What is being pinned here: a submitted build carries slugs and
 * contact details and *no price*, and an API rejection comes back attached to the field that
 * caused it.
 */

function form(fields: Record<string, string>): FormData {
  const data = new FormData();
  for (const [name, value] of Object.entries(fields)) data.append(name, value);
  return data;
}

const FILLED = {
  name: "  Dana Reyes ",
  email: "dana@example.com",
  phone: "+1 555 0100",
  timeline: "3–6 months",
  intended_use: "Two-up desert travel.",
  notes: "",
  website: "",
  started_at: "1000",
  platform_slug: "bristlecone",
  option_slugs: "cab-regular, shell-standard ,,winch-12000",
};

describe("parseBuildRequest", () => {
  it("carries the selection as slugs, trimmed and without gaps", () => {
    expect(parseBuildRequest(form(FILLED), 10_000).option_slugs).toEqual([
      "cab-regular",
      "shell-standard",
      "winch-12000",
    ]);
  });

  it("trims contact details", () => {
    expect(parseBuildRequest(form(FILLED), 10_000).contact).toEqual({
      name: "Dana Reyes",
      email: "dana@example.com",
      phone: "+1 555 0100",
    });
  });

  it("never sends a price, whatever the form was carrying", () => {
    const payload = parseBuildRequest(form({ ...FILLED, total_cents: "1" }), 10_000);
    expect(payload).not.toHaveProperty("total_cents");
    expect(JSON.stringify(payload)).not.toContain("total_cents");
  });

  it("computes how long the form was open from this side's clock", () => {
    expect(parseBuildRequest(form(FILLED), 10_000).elapsed_ms).toBe(9_000);
  });

  it("reports no timing rather than a wrong one when the form never set it", () => {
    expect(parseBuildRequest(form({ ...FILLED, started_at: "" }), 10_000).elapsed_ms).toBeNull();
    expect(parseBuildRequest(form({ ...FILLED, started_at: "x" }), 10_000).elapsed_ms).toBeNull();
  });
});

describe("parseEnquiry", () => {
  it("treats an unpicked platform as no platform rather than an empty slug", () => {
    expect(parseEnquiry(form({ ...FILLED, platform_slug: "" })).platform_slug).toBeNull();
  });

  it("keeps a named platform of interest", () => {
    expect(parseEnquiry(form(FILLED)).platform_slug).toBe("bristlecone");
  });
});

describe("toFieldErrors", () => {
  it("keys errors by the input they belong to, not by the payload path", () => {
    const errors = toFieldErrors({
      code: "validation_error",
      message: "Some details need another look.",
      errors: [{ field: "contact.email", message: "not a valid email", code: "value_error" }],
    });
    expect(errors).toEqual({ email: ["not a valid email"] });
  });

  it("collects every message for one field", () => {
    const errors = toFieldErrors({
      code: "invalid_selection",
      message: "This build needs a change.",
      errors: [
        { field: "option_slugs", message: "Winch needs the bumper.", code: "requires" },
        { field: "option_slugs", message: "Exterior Finish needs a choice.", code: null },
      ],
    });
    expect(errors.option_slugs).toHaveLength(2);
  });

  it("drops errors that name no field, which belong in the headline", () => {
    expect(toFieldErrors({ code: "rate_limited", message: "Slow down.", errors: [] })).toEqual({});
  });
});

describe("errorState", () => {
  const state = (over: Partial<LeadFormState> = {}): LeadFormState => ({
    status: "error",
    message: "",
    errors: {},
    ...over,
  });

  it("shows the envelope message when the errors are attached to fields", () => {
    expect(
      errorState({
        code: "invalid_selection",
        message: "This build needs a change.",
        errors: [{ field: "option_slugs", message: "Winch needs the bumper.", code: "requires" }],
      }),
    ).toEqual(
      state({
        message: "This build needs a change.",
        errors: { option_slugs: ["Winch needs the bumper."] },
      }),
    );
  });

  it("promotes unattached messages to the headline, where they can still be read", () => {
    expect(
      errorState({
        code: "rejected",
        message: "We couldn't accept this submission.",
        errors: [{ field: null, message: "Email us directly.", code: null }],
      }).message,
    ).toBe("Email us directly.");
  });
});
