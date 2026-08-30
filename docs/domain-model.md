# Domain model

The vocabulary matters — get it right once and both services agree.

- **Platform** — a configurable product line (the reference site's "model"). Has a slug, chassis basis, base
  price, hero/gallery imagery, spec highlights, standard equipment, and an ordered list of option groups.
- **OptionGroup** — one step in the configurator (e.g. "Habitat", "Power System", "Recovery"). Has a
  selection mode (`single` | `multi`), a `required` flag, and a display style (`card` | `swatch` | `toggle`).
- **Option** — a choice within a group. Has a price delta (may be `0` for included items), description,
  an optional thumbnail (a swatch group's colour chip), and an optional **model effect** (see below) for
  the 3D build view.
- **OptionRule** — a relation between options: `requires` or `excludes`. This is the compatibility engine.
- **Build** — a platform plus a set of selected option slugs. Shareable via URL and priceable.
- **Quote** — a submitted build plus contact details, intended use, and timeline.

Slugs are the public identifiers throughout. They appear in URLs and in shared builds, so they must be stable;
treat renaming one as a breaking change.

## Placeholder catalog

Three purpose-led platforms, deliberately spanning different upfit verticals so the data model is properly
exercised. **All names, prices, and specs are demo content to be replaced with the real company's.**

| Platform | Purpose | Chassis basis | Starting at |
|---|---|---|---|
| **Bristlecone** | Expedition / overland habitat | Ram 5500 4x4 (regular / crew cab) | $214,500 |
| **Ironwood** | Mobile workshop & service body | Ford F-550 (crew cab) | $168,900 |
| **Sentinel** | Response & command | Ford F-600 (crew cab) | $232,000 |

Each carries 6–8 option groups. Bristlecone, for example:

Cab & Chassis → Habitat Shell → Interior Layout → Power System → Water & Thermal → Suspension & Tires →
Recovery & Protection → Exterior Finish

### Rules that must exist

These are chosen to exercise the engine rather than to be exhaustive:

- The 12,000 lb winch **requires** the heavy front bumper.
- The 600 Ah lithium bank **excludes** the compact galley (space conflict).
- The rooftop tent **excludes** the maximum-size solar array.

## The 3D build model

The catalog describes a platform's build view with two entities, added in
[Stage 14](stages/14-build-model-catalog.md). They replaced a 2D layered-image composite —
[Stage 16](stages/16-3d-viewer.md) built the WebGL viewer that reads them and
[Stage 17](stages/17-retire-2d-composite.md) removed the composite and its `layer` assets entirely:

- **BuildModel**, one per platform — the GLB behind the build view, plus how the camera should
  frame it (`camera_orbit_deg`, `camera_distance_m`, `camera_target_y_m`). The URL, content hash
  and byte size are filled in by [Stage 15](stages/15-blob-storage-ingest.md)'s
  `python -m app.assets sync`, never by `seed/catalog.yaml`.
- **OptionModelEffect**, at most one per option — how selecting it changes the model. **Geometry**
  (a crew cab, a rooftop tent) names `nodes`: mesh names already present in the platform's GLB,
  toggled visible. **Finish** (a paint colour) names `material_target` plus `base_color_hex`
  instead, since one body mesh per colour would multiply the GLB by the number of finishes. An
  option may use either, both, or neither.

**Node naming convention:** `<platform>_<group>_<option>`, using each entity's own slug —
e.g. `bristlecone_recovery-protection_winch-12000`. This is a contract with whoever authors the
GLB, not something the application enforces; a node absent from the file simply reveals nothing.
