# Testing strategy

| Layer | Tool | What it covers |
|---|---|---|
| Pricing & rules (backend) | pytest | Every `requires`/`excludes` rule, base + delta arithmetic, empty and maximal builds |
| API contract | pytest + httpx | Catalog shape, quote validation rejection, admin auth, tampered-price rejection |
| Pricing mirror (front end) | Vitest | **Shared fixtures with the pytest suite** so client and server prices cannot drift |
| Build encoding | Vitest | URL round-trip: encode → decode → identical selection |
| Telemetry | pytest | Request ids survive the hop between services; the Sentry scrubber drops lead data |
| Configurator flow | Playwright | Configure → see price change → hit an incompatibility → submit → thank-you |
| Accessibility | Playwright + axe | WCAG 2.1 AA on every page, both breakpoints, plus keyboard operation of the configurator |
| Responsive layout | Playwright | The configurator's three panes collapse to stacked on a phone, with no sideways overflow |
| Client JS budget | `pnpm bundle:check` | Per-route gzipped script size, read back out of the prerendered HTML |

## End-to-end specs

`web/e2e/` belongs to Playwright; `web/tests/` belongs to Vitest. The split is load-bearing rather than
tidy — Vitest's config globs `tests/**/*.test.ts`, and two runners in one directory each try to execute
the other's files.

The specs run against a local production build by default, and against a deployment when `E2E_BASE_URL`
is set — that is how Stage 7's production smoke test is executed rather than clicked through:

```bash
cd web
pnpm e2e                                        # local; starts `pnpm start` itself
E2E_BASE_URL=https://truckbuild.vercel.app pnpm e2e   # the deployed site
```

`configurator.spec.ts` and `a11y.spec.ts` are read-only and safe to point anywhere. `quote.spec.ts`
stores a real quote and emails sales, so it skips itself against a non-local target unless
`E2E_ALLOW_WRITES=1` says otherwise.

Interactive elements are addressed by ARIA role and visible text, never by test id. That is deliberate
double duty: a spec that can find an option by role is evidence a screen reader can, so a change that
breaks the accessible name breaks the suite.

Follow TDD for `services/pricing.py` and `services/rules.py` specifically. They are pure and total, and they
are the place where a silent bug costs real money.

## Shared fixtures

The pricing mirror only stays honest if both implementations are tested against the same data. Keep a single
JSON fixture file consumed by both pytest and Vitest — a case added on one side then fails on the other,
which is exactly the alarm we want.
