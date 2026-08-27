# Features

What the site actually does, page by page, and the mechanics behind the parts that are not obvious
from looking at them. For how it is built, see [architecture.md](architecture.md); for the entities
and vocabulary, [domain-model.md](domain-model.md).

> Catalog names, prices, specs, and photography are **demo placeholders** (Bristlecone, Ironwood,
> Sentinel) standing in for the real company's data.

## The pages

| Path | What it is |
|---|---|
| `/` | Home — hero, the three platforms with live starting prices, the purpose verticals, proof strip, process summary |
| `/builds` | Platform index, filterable by purpose |
| `/builds/[slug]` | Platform detail — imagery, spec highlights, standard equipment, and the way into the configurator |
| `/purposes/[slug]` | Editorial vertical (Expedition · Service · Response) routing to the platform that serves it |
| `/configurator/[slug]` | **The configurator.** Full-bleed, three panes, live pricing |
| `/configurator/[slug]/request` | Lead form with the configured build attached |
| `/process` | How an upfit actually runs, start to delivery |
| `/gallery` | Photography |
| `/about` | The company |
| `/contact` | General enquiry form — no build attached |
| `/thank-you` | Confirmation with the reference number |
| `/legal/privacy` | Privacy notice |

Plus `sitemap.xml`, `robots.txt`, generated Open Graph images, a 404, and a global error boundary.

Marketing pages sit in a route group with the shared header and footer. The configurator sits
outside it — it needs the full viewport and its own minimal bar, and a nested layout cannot remove a
parent's chrome.

## The configurator

The centre of the product. Three panes on desktop — step rail, viewer, option panel — collapsing to
**stacked viewer-over-panel** on a phone, which is a real layout branch rather than a scaled-down
copy.

### Choosing options

Each option group is one step. Groups declare their own behaviour, and the UI follows the data:

| Group property | Effect |
|---|---|
| `selection_mode: single` | Renders **radios**; picking a new one swaps the old |
| `selection_mode: multi` | Renders **checkboxes**; each toggles independently |
| `required: true` | Cannot be emptied — a build with no cab is not a build |
| `display_style: swatch` | A colour/finish grid instead of rows |

The inputs are real radios and checkboxes, visually hidden (`sr-only`) with a styled `<label>`
wrapping them. That is why keyboards and screen readers work with no extra code — and why the
end-to-end specs address every control by ARIA role and visible text. A spec that can find an option
by role is evidence a screen reader can, so breaking the accessible name breaks the suite.

### Live pricing

The total updates on every click, computed **in the browser** by `web/src/lib/pricing.ts` — no
network round trip, no spinner. When it moves, the delta appears beside the total for a beat and then
clears.

That mirror of the Python implementation is [deliberate duplication](architecture.md#boundaries-that-must-hold),
kept honest by a shared test fixture. **It is never trusted**: `POST /v1/quotes` recomputes the price
server-side from the database and stores that.

### Compatibility, explained rather than enforced

The interesting design decision. Options carry `requires` / `excludes` rules, and a conflicting
choice is **not blocked** — it is allowed, then explained.

There are three layers of it:

1. **Before you click.** An option that would conflict carries an inline hint — *"Needs the
   Heavy-Duty Winch Bumper"* — wired up with `aria-describedby`, so the warning reaches a screen
   reader too.
2. **After you click.** A conflict notice appears on the step that can *resolve* it, which may be
   either side of the rule. It says what the problem is in plain language: *"The 12,000 lb Winch
   mounts to the Heavy-Duty Winch Bumper, which is not in this build."*
3. **The way out is one press.** The notice carries the action — *"Add the Heavy-Duty Winch Bumper"*
   — rather than leaving you to find it.

Blocking the click would have been less code. It would also leave a visitor unable to tell whether
they had misunderstood the product or hit a bug.

### Shareable builds

The selection lives in the URL as `?o=slug-a,slug-b`. Copy it, send it, reload it, hit back — the
build survives all four, with no account and no database round trip.

Because a shared link outlives the catalog it was built from, decoding **repairs** the URL instead of
failing: unknown slugs are dropped, a single-select group keeps one choice, a required group falls
back to its default. A rule-violating combination is deliberately kept, so the configurator can
explain it.

Options are always re-encoded in catalog order, so the same set of choices always produces the same
string.

### The build sheet

"Review build" opens a native `<dialog>` — itemised lines, deltas, and the total. Escape closes it,
focus is trapped while open, and the same axe scan that covers the pages covers the sheet while it is
open, because a dialog is exactly where a contrast or naming regression hides.

### Keyboard and assistive technology

- The step rail is a **tablist with roving tabindex** — one stop in the tab order, arrows to move
  between steps, Home/End to jump. Not one Tab press per step.
- Price changes are **announced**, not just shown: an `aria-live` region carries *"Heavy-Duty Winch
  Bumper added · Build total $216,700"*. The visible flash and the announcement tell both audiences
  the same thing.
- Every page is scanned against **WCAG 2.1 AA** with axe, at two breakpoints.

## The lead pipeline

Two entry points, one pipeline:

| Form | Endpoint | Carries |
|---|---|---|
| `/configurator/[slug]/request` | `POST /v1/quotes` | The full configured build |
| `/contact` | `POST /v1/enquiries` | Contact details, optionally a platform |

Submission goes through a **Server Action**, so the browser never learns the API origin. The action
forwards the visitor's address so rate limiting buckets per visitor rather than putting every
submission in the world into one bucket.

On the server:

1. **Re-validate** — unknown slugs, single-select groups with two choices, required groups with none,
   and every compatibility rule.
2. **Recompute the price** from the database, ignoring anything the client claimed.
3. **Generate a reference** (`TB-XXXXXX`), retrying against the unique index rather than generating
   one and hoping.
4. **Notify sales** by email — or log it, when `RESEND_API_KEY` is unset.

Every rejection comes back in one error shape, so the form renders the message beside the field at
fault instead of showing a generic failure.

### Spam controls

Three, all tuned generously on the principle that **turning away a real customer costs more than
storing a junk lead**:

| Control | How it works |
|---|---|
| Honeypot | A field a human never fills and a bot usually does |
| Minimum submit time | A form completed impossibly fast is not a person |
| Per-IP rate limit | A window per address |

> On serverless the rate limiter is **per-instance rather than global**, because its counters live in
> process memory. It still blunts a naive flood; it is not the control it was. See
> [deploy.md](deploy.md).

## Admin

Unlisted endpoints behind a single bearer token, compared in constant time. The guard is on the
router, so a route added there is protected by construction.

| Endpoint | Purpose |
|---|---|
| `GET /v1/admin/quotes` | Leads, newest first — paginated, filterable by kind and platform, searchable by reference, name, or email |
| `GET /v1/admin/quotes/{ref}` | One lead in full, by the reference the customer quotes on the phone |
| `POST /v1/admin/revalidate` | Bust the site's catalog cache by hand |

That last one exists for the edit the seed cannot see — a price changed directly in Postgres, a row
fixed during an incident — where the data is already right and only the cache disagrees. Naming no
tags drops everything the catalog touches, the right default for *"I changed something and I am not
certain what it reaches."*

Auth being one shared token is an [accepted risk](decisions.md#accepted-risks), honest for two or
three people reading leads. The upgrade path is real accounts.

## SEO and metadata

- **Prerendered pages.** Marketing pages render from cache rather than a live API call, so crawlers
  get HTML immediately — the whole point of the [Cache Components design](architecture.md#the-central-tension-and-how-it-is-resolved).
- **Generated Open Graph images** per platform and per purpose.
- **JSON-LD** structured data, canonical URLs, `sitemap.xml`, and `robots.txt`.
- `SITE_URL` in `web/src/lib/site.ts` feeds all of it. It is a **compile-time constant, not an
  environment variable**, so changing the domain is a rebuild rather than a redeploy.

Measured on the deployment: **SEO 100** on both `/` and `/builds/bristlecone`.

## Performance

| Technique | Detail |
|---|---|
| Modern image formats | `next/image` with AVIF/WebP for all photography |
| Self-hosted fonts | `next/font` — no third-party font request |
| Explicit fetch priority | Viewer layers for the open step load `high`, the rest `low`, so the images you are about to see win the bandwidth race |
| Per-route JS budgets | `pnpm bundle:check` reads gzipped client JS back out of the prerendered HTML and fails over budget |

The budget check exists because **Next 16's Turbopack build summary has no per-route bundle column**,
so there is otherwise nothing to notice a regression against. The configurator — the heaviest route —
sits at ~192 KiB gzipped against a 210 KiB budget.

Measured on the deployment: **Performance 99, Accessibility 100** on both `/` and
`/builds/bristlecone`.

## Resilience

- **A slow or down API does not take the site down.** Pages render from cache; the API is read at
  build time and on invalidation, not per request.
- **Catalog edits reach the site without a deploy**, over the revalidation webhook.
- **A stale shared build URL still works**, repaired rather than rejected.
- **A crashed page reports itself** to a first-party route — no error SDK is shipped to visitors.

## Deliberately not built

User accounts and saved builds, financing calculators, dealer/inventory management, real-time
build-slot availability, a 3D/WebGL viewer, i18n, and a CMS. The catalog seed file plus the
revalidation webhook is the seam a CMS would plug into. See [decisions.md](decisions.md).
