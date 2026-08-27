import { describe, expect, it } from "vitest";

import {
  BUILD_PARAM,
  decodeSelection,
  defaultSelection,
  encodeSelection,
  toggleOption,
} from "@/lib/build";

import { apiPlatform } from "./fixtures";

/**
 * Build state lives in the URL query string, which is what makes a build shareable and
 * refresh-safe without a database round trip. Everything here is about that round trip
 * surviving contact with a URL somebody edited, bookmarked, or shared months ago.
 */

const bristlecone = apiPlatform("bristlecone");

describe("defaultSelection", () => {
  it("selects the first option of every required group", () => {
    expect(defaultSelection(bristlecone)).toEqual([
      "cab-regular",
      "shell-standard",
      "galley-compact",
      "suspension-standard",
      "finish-satin-black",
    ]);
  });

  it("leaves optional groups empty", () => {
    const selected = new Set(defaultSelection(bristlecone));
    expect(selected.has("lithium-300ah")).toBe(false);
    expect(selected.has("rooftop-tent")).toBe(false);
  });

  it("is itself a valid, complete build", () => {
    expect(
      decodeSelection(bristlecone, encodeSelection(bristlecone, defaultSelection(bristlecone))),
    ).toEqual(defaultSelection(bristlecone));
  });
});

describe("encodeSelection", () => {
  it("joins slugs with commas", () => {
    expect(encodeSelection(bristlecone, ["cab-crew", "rooftop-tent"])).toContain("cab-crew");
    expect(encodeSelection(bristlecone, ["cab-crew", "rooftop-tent"])).toContain(",");
  });

  it("is canonical: the same build always produces the same string", () => {
    const forwards = encodeSelection(bristlecone, ["rooftop-tent", "cab-crew", "solar-standard"]);
    const backwards = encodeSelection(bristlecone, ["solar-standard", "cab-crew", "rooftop-tent"]);
    expect(forwards).toBe(backwards);
  });

  it("names the query parameter the URL actually uses", () => {
    expect(BUILD_PARAM).toBe("o");
  });
});

describe("decodeSelection", () => {
  it("round-trips a configured build", () => {
    const selection = toggleOption(
      bristlecone,
      toggleOption(bristlecone, defaultSelection(bristlecone), "cab-crew"),
      "rooftop-tent",
    );
    expect(decodeSelection(bristlecone, encodeSelection(bristlecone, selection))).toEqual(
      selection,
    );
  });

  it("falls back to the default build for a missing parameter", () => {
    expect(decodeSelection(bristlecone, null)).toEqual(defaultSelection(bristlecone));
    expect(decodeSelection(bristlecone, "")).toEqual(defaultSelection(bristlecone));
  });

  it("drops slugs this platform does not have", () => {
    // A shared URL outlives the option it names; a renamed slug must not break the page.
    const decoded = decodeSelection(bristlecone, "cab-crew,crane-3200lb,not-a-real-option");
    expect(decoded).toContain("cab-crew");
    expect(decoded).not.toContain("crane-3200lb");
    expect(decoded).not.toContain("not-a-real-option");
  });

  it("keeps only one option from a single-select group", () => {
    const decoded = decodeSelection(bristlecone, "galley-compact,galley-full,layout-bunk");
    const layout = ["galley-compact", "galley-full", "layout-bunk"].filter((s) =>
      decoded.includes(s),
    );
    expect(layout).toHaveLength(1);
  });

  it("fills in the default for a required group the URL never mentions", () => {
    expect(decodeSelection(bristlecone, "rooftop-tent")).toContain("finish-satin-black");
  });

  it("ignores blank entries and surrounding whitespace", () => {
    expect(decodeSelection(bristlecone, " cab-crew , ,rooftop-tent ")).toContain("cab-crew");
    expect(decodeSelection(bristlecone, " cab-crew , ,rooftop-tent ")).toContain("rooftop-tent");
  });

  it("does not duplicate a slug repeated in the URL", () => {
    const decoded = decodeSelection(bristlecone, "rooftop-tent,rooftop-tent");
    expect(decoded.filter((s) => s === "rooftop-tent")).toHaveLength(1);
  });

  it("keeps a selection that violates a rule, so the page can explain it", () => {
    // Silently dropping the winch would leave the visitor wondering where their click went.
    expect(decodeSelection(bristlecone, "winch-12000")).toContain("winch-12000");
  });
});

describe("toggleOption", () => {
  const base = defaultSelection(bristlecone);

  it("replaces the current choice within a single-select group", () => {
    const next = toggleOption(bristlecone, base, "cab-crew");
    expect(next).toContain("cab-crew");
    expect(next).not.toContain("cab-regular");
  });

  it("will not empty a required single-select group", () => {
    expect(toggleOption(bristlecone, base, "cab-regular")).toContain("cab-regular");
  });

  it("adds and removes within a multi-select group", () => {
    const added = toggleOption(bristlecone, base, "rooftop-tent");
    expect(added).toContain("rooftop-tent");
    expect(toggleOption(bristlecone, added, "rooftop-tent")).not.toContain("rooftop-tent");
  });

  it("leaves other groups untouched", () => {
    const next = toggleOption(bristlecone, base, "rooftop-tent");
    expect(next).toContain("finish-satin-black");
    expect(next).toContain("shell-standard");
  });

  it("ignores a slug the platform does not have", () => {
    expect(toggleOption(bristlecone, base, "crane-3200lb")).toEqual(base);
  });

  it("keeps the result in canonical order", () => {
    const next = toggleOption(bristlecone, base, "rooftop-tent");
    expect(encodeSelection(bristlecone, next).split(",")).toEqual(next);
  });
});
