import { describe, expect, it } from "vitest";

import { readoutFor, readoutsMatch } from "@/lib/viewer/progress";

/**
 * The build view's loading readout, with no DOM behind it: which phase the label names, and
 * whether the bar is entitled to claim a percentage. `BuildViewerLoading` only renders what
 * `readoutFor` returns, and `BuildViewer` throttles its renders with `readoutsMatch`.
 */

describe("readoutFor", () => {
  it("names the chunk download while no byte counts exist yet", () => {
    expect(readoutFor(null)).toEqual({ label: "Preparing viewer", percent: null });
  });

  it("reports the percentage of a measurable transfer", () => {
    expect(readoutFor({ loaded: 512, total: 2048 })).toEqual({
      label: "Loading 3D model",
      percent: 25,
    });
  });

  it("stays indeterminate when the response declared no length", () => {
    expect(readoutFor({ loaded: 900_000, total: 0 })).toEqual({
      label: "Loading 3D model",
      percent: null,
    });
  });

  it("stops trusting a length the transfer has already passed", () => {
    // `Content-Length` on a compressed response counts wire bytes; `FileLoader` counts
    // decompressed ones. Once they cross, the two were never measuring the same thing.
    expect(readoutFor({ loaded: 3000, total: 2048 })).toEqual({
      label: "Loading 3D model",
      percent: null,
    });
  });
});

describe("readoutsMatch", () => {
  it("collapses chunks that land on the same whole percent", () => {
    expect(readoutsMatch({ loaded: 1000, total: 100_000 }, { loaded: 1004, total: 100_000 })).toBe(
      true,
    );
  });

  it("lets a changed percentage through", () => {
    expect(readoutsMatch({ loaded: 1000, total: 100_000 }, { loaded: 2000, total: 100_000 })).toBe(
      false,
    );
  });

  it("lets the first unmeasurable chunk through, then collapses the rest", () => {
    expect(readoutsMatch(null, { loaded: 0, total: 0 })).toBe(false);
    expect(readoutsMatch({ loaded: 0, total: 0 }, { loaded: 900_000, total: 0 })).toBe(true);
  });
});
