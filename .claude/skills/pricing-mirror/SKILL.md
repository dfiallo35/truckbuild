---
name: pricing-mirror
description: Keeps TruckBuild's two implementations of price_build and validate_selection in sync — Python in api/app/services/ (authoritative) and TypeScript in web/src/lib/ (instant UI feedback) — using a shared fixture file so they cannot silently drift. Use this whenever you touch pricing arithmetic, price deltas, base prices, option compatibility rules, requires/excludes relations, or any of pricing.py, rules.py, pricing.ts, rules.ts. Also use it when adding or repricing an option, adding a rule, or writing tests for any of the above — including when the change looks like it only affects one side, because a one-sided change is exactly the failure this skill exists to prevent.
---

# Pricing mirror

## Why this exists

`price_build` and `validate_selection` are implemented **twice on purpose**:

| Implementation | Location | Role |
|---|---|---|
| Python | `api/app/services/pricing.py`, `api/app/services/rules.py` | **Authoritative.** What the customer is actually quoted. |
| TypeScript | `web/src/lib/pricing.ts`, `web/src/lib/rules.ts` | UX affordance only. Instant price updates as options are clicked. |

`docs/decisions.md` records this as a knowingly accepted risk. The duplication buys a configurator
that responds instantly instead of waiting on a network round trip per click. What contains the risk
is not discipline — it is a **single shared fixture file that both test suites consume**. A case added
on one side fails on the other, which is precisely the alarm we want.

If the two ever drift despite this, the documented fallback is to delete the TypeScript mirror and
call a debounced `POST /v1/price` instead. Reach for that only if the fixtures stop holding the line.

## Seeing both halves at once

`codegraph explore "price_build"` (or `"validate_selection"`) returns both implementations' current
source in one call, because the CodeGraph index at `.codegraph/` spans `api/` and `web/` together.
That matters here specifically: the failure this skill exists to prevent is editing one half while
looking only at one half, and a single query that puts the Python and the TypeScript side by side
removes the opportunity. Its blast-radius list also names the callers and the covering tests, which is
what tells you whether a change reaches the configurator UI as well as the quote endpoint.

## The shared fixture

**`fixtures/pricing-cases.json`** at the repo root — deliberately outside both `api/` and `web/` so
neither service owns it.

Each case is a platform slug, a selection, and the expected outcome:

```json
{
  "cases": [
    {
      "name": "winch requires heavy bumper",
      "platform": "bristlecone",
      "selected": ["winch-12000", "bumper-standard"],
      "expected_total_cents": null,
      "expected_violations": [
        { "kind": "requires", "option": "winch-12000", "needs": "bumper-heavy" }
      ]
    },
    {
      "name": "base build, no options",
      "platform": "bristlecone",
      "selected": [],
      "expected_total_cents": 21450000,
      "expected_violations": []
    }
  ]
}
```

Prices are integer **cents**. Floating-point money drifts differently in Python and JavaScript, and
a mirror whose two halves round differently is worse than no mirror at all.

## Workflow: changing pricing or rules

Work fixture-first. The fixture is the specification; both implementations are just ways of satisfying it.

1. **Add or edit the case in `fixtures/pricing-cases.json`.** Cover the satisfied *and* the violated
   side of any rule — a rule that only has a passing test is half-tested.
2. **Run both suites and watch them fail.** A case that passes before you write the code is not
   testing what you think it is.
   ```bash
   cd api && uv run pytest tests/test_pricing.py tests/test_rules.py
   cd web && pnpm test
   ```
3. **Change the Python side first.** It is authoritative; the TypeScript side is catching up to it,
   never the other way around.
4. **Mirror it in TypeScript.**
5. **Run both suites again.** Both green, or the change is not done.

If you only have a reason to change one side, stop and work out why. Either the fixture is missing a
case that would have caught it, or the two implementations were already out of sync.

## Constraints that make this work

**`pricing.py` and `rules.py` import nothing from `fastapi` or `sqlmodel`.** They take plain data and
return plain data. Purity is what lets them be tested without a database and mirrored without dragging
server concerns into the browser. If you find yourself wanting a `Session` in one of these modules, the
query belongs in the router or a separate service that then calls the pure function.

**The server price is authoritative at submission.** `POST /v1/quotes` recomputes the total from the
platform and option slugs and ignores any client-supplied price. A price arriving from a browser is
user input, not a fact. The mirror is for showing a number quickly, never for deciding what to charge.

**Slugs are the contract.** The fixture, the seed YAML, the URL query string, and both implementations
all key on option slugs. Renaming one breaks shared build URLs — see the `catalog-change` skill.

## Signals you should be in this skill

Someone asks to change a price, add an option, add a "you can't have X with Y" constraint, fix a total
that looks wrong, or write tests for the configurator's math. All of those touch the mirror even when
the request names only one service.
