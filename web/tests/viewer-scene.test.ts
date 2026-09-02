import { describe, expect, it } from "vitest";

import { framingScaleForAspect, resolveSelection, type ViewerEffect } from "@/lib/viewer/scene";

/**
 * `resolveSelection`'s pure half: no WebGL, no canvas -- just which node names a selection
 * should show or hide, and which named material gets which override. `scene.ts`'s
 * `applySelection` is a thin wrapper that looks these names up in the `Map`s built at load.
 */

const CAB_CREW: ViewerEffect = {
  nodes: ["cab_crew"],
  materialTarget: null,
  baseColorHex: null,
  metalness: null,
  roughness: null,
};

const SHELL_EXTENDED: ViewerEffect = {
  nodes: ["shell_extended"],
  materialTarget: null,
  baseColorHex: null,
  metalness: null,
  roughness: null,
};

const PAINT_BLACK: ViewerEffect = {
  nodes: [],
  materialTarget: "body_paint",
  baseColorHex: "#1b1b1b",
  metalness: 0.4,
  roughness: 0.3,
};

const PAINT_TAN: ViewerEffect = {
  nodes: [],
  materialTarget: "body_paint",
  baseColorHex: "#c2a374",
  metalness: 0.2,
  roughness: 0.5,
};

const EFFECTS: Record<string, ViewerEffect> = {
  "cab-crew": CAB_CREW,
  "shell-extended": SHELL_EXTENDED,
  "paint-black": PAINT_BLACK,
  "paint-tan": PAINT_TAN,
};

describe("resolveSelection", () => {
  it("shows the nodes of selected options and hides every other effect node", () => {
    const { visibleNodes, hiddenNodes } = resolveSelection(EFFECTS, ["cab-crew"]);
    expect(visibleNodes).toEqual(new Set(["cab_crew"]));
    expect(hiddenNodes).toEqual(new Set(["shell_extended"]));
  });

  it("shows the union of nodes across every selected option", () => {
    const { visibleNodes, hiddenNodes } = resolveSelection(EFFECTS, ["cab-crew", "shell-extended"]);
    expect(visibleNodes).toEqual(new Set(["cab_crew", "shell_extended"]));
    expect(hiddenNodes).toEqual(new Set());
  });

  it("hides every effect node when nothing is selected", () => {
    const { visibleNodes, hiddenNodes } = resolveSelection(EFFECTS, []);
    expect(visibleNodes).toEqual(new Set());
    expect(hiddenNodes).toEqual(new Set(["cab_crew", "shell_extended"]));
  });

  it("ignores a selected slug the effect map does not name", () => {
    const { visibleNodes, hiddenNodes } = resolveSelection(EFFECTS, ["not-a-real-option"]);
    expect(visibleNodes).toEqual(new Set());
    expect(hiddenNodes).toEqual(new Set(["cab_crew", "shell_extended"]));
  });

  it("resolves a material override from the selected option targeting it", () => {
    const { materialOverrides } = resolveSelection(EFFECTS, ["paint-black"]);
    expect(materialOverrides.get("body_paint")).toEqual({
      baseColorHex: "#1b1b1b",
      metalness: 0.4,
      roughness: 0.3,
    });
  });

  it("has no override for a material no selected option targets", () => {
    const { materialOverrides } = resolveSelection(EFFECTS, ["cab-crew"]);
    expect(materialOverrides.has("body_paint")).toBe(false);
  });

  it("resolves deterministically when two selected options share a material target", () => {
    // Single-select groups never hand two options for the same target to a real caller, but
    // the function itself has to resolve *something* deterministic if it is ever asked to --
    // here, the one declared later in the effect map.
    const { materialOverrides } = resolveSelection(EFFECTS, ["paint-black", "paint-tan"]);
    expect(materialOverrides.get("body_paint")?.baseColorHex).toBe("#c2a374");
  });
});

/**
 * The build view fills its pane rather than sitting in a 16:9 box inside it, so the frame's aspect
 * is now whatever the layout hands over. `framingScaleForAspect` is what keeps a platform's
 * authored framing meaning the same thing in a pane taller than it is wide -- the axis a truck is
 * long on is the one a camera at a fixed distance crops first.
 */
describe("framingScaleForAspect", () => {
  // What the scale is for: the visible width at the camera's distance, which should not move.
  const visibleWidth = (aspect: number) => framingScaleForAspect(aspect) * aspect;

  it("leaves the authored framing alone on a frame at least as wide as it was authored for", () => {
    expect(framingScaleForAspect(16 / 9)).toBe(1);
    expect(framingScaleForAspect(21 / 9)).toBe(1);
  });

  it("holds the visible width as the frame narrows", () => {
    const reference = visibleWidth(16 / 9);
    expect(visibleWidth(4 / 3)).toBeCloseTo(reference, 10);
    expect(visibleWidth(1)).toBeCloseTo(reference, 10);
    // The narrowest column the three-pane grid produces on a small laptop.
    expect(visibleWidth(0.3)).toBeCloseTo(reference, 10);
  });

  it("only ever backs the camera off, never pushes it in", () => {
    for (const aspect of [0.3, 1, 4 / 3, 16 / 9, 3]) {
      expect(framingScaleForAspect(aspect)).toBeGreaterThanOrEqual(1);
    }
  });

  it("falls back to the authored framing for a frame with no measurable aspect", () => {
    // A hidden or zero-height pane, which is what a resize during teardown hands over.
    expect(framingScaleForAspect(0)).toBe(1);
    expect(framingScaleForAspect(Number.NaN)).toBe(1);
  });
});
