# Golden response bodies

`GET /v1/catalog` and `GET /v1/platforms/bristlecone`, exactly as they were served at the end of
Stage 9 — the last point at which these bodies were produced by code nobody had restructured.
Captured against the seeded local stack:

```bash
curl -s localhost:8000/v1/catalog               | jq -S . > tests/golden/catalog.json
curl -s localhost:8000/v1/platforms/bristlecone | jq -S . > tests/golden/platform-bristlecone.json
```

Stages 10–13 each rewrite the code behind them and diff against these files to prove the wire
contract did not move:

```bash
curl -s localhost:8000/v1/catalog               | jq -S . | diff tests/golden/catalog.json -
curl -s localhost:8000/v1/platforms/bristlecone | jq -S . | diff tests/golden/platform-bristlecone.json -
```

They are keyed to `seed/catalog.yaml`, so a deliberate catalog change means recapturing them in
the same commit — that is a content edit, and the diff is the review. A change to either file in
a commit that does *not* touch `seed/catalog.yaml` is the migration having broken something.
