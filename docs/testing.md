# Testing strategy

| Layer | Tool | What it covers |
|---|---|---|
| Pricing & rules (backend) | pytest | Every `requires`/`excludes` rule, base + delta arithmetic, empty and maximal builds |
| API contract | pytest + httpx | Catalog shape, quote validation rejection, admin auth, tampered-price rejection |
| Pricing mirror (front end) | Vitest | **Shared fixtures with the pytest suite** so client and server prices cannot drift |
| Build encoding | Vitest | URL round-trip: encode → decode → identical selection |
| Configurator flow | Playwright | Configure → see price change → hit an incompatibility → submit → thank-you |
| Visual | Playwright screenshots | Home and one configurator step, to catch layout regressions |

Follow TDD for `services/pricing.py` and `services/rules.py` specifically. They are pure and total, and they
are the place where a silent bug costs real money.

## Shared fixtures

The pricing mirror only stays honest if both implementations are tested against the same data. Keep a single
JSON fixture file consumed by both pytest and Vitest — a case added on one side then fails on the other,
which is exactly the alarm we want.
