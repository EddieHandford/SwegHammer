# BCP-1 access report

Survey of the Best Coast Pairings public API. Outcome: not accessible from this
session under the brief's constraints. No JSON aggregate was written.

## What I tried

1. `GET https://newprod-api.bestcoastpairings.com/v1/events` (no params) — HTTP 400.
2. `GET https://newprod-api.bestcoastpairings.com/v1/events?eventType=0&limit=10` — HTTP 400.
3. `GET https://newprod-api.bestcoastpairings.com/v1/events?limit=5&eventType=0&gameSystem=40k` — HTTP 400.
4. `GET https://newprod-api.bestcoastpairings.com/v1/events?limit=5&eventType=0&gameType=1&startDate=2026-02-22` — HTTP 400.
5. `GET https://newprod-api.bestcoastpairings.com/v1/eventlistings?startDate=2026-02-22&gameType=1` — HTTP 403.
6. `GET https://newprod-api.bestcoastpairings.com/` — HTTP 403.
7. Legacy endpoint from the 2020 `specialprocedures/best-coast-pairings` scraper
   (`https://lrs9glzzsf.execute-api.us-east-1.amazonaws.com/prod/eventlistings`)
   — `ECONNREFUSED`. The endpoint has been retired.
8. Fetched the JS web app at `warhammer.bestcoastpairings.com/` and
   `bestcoastpairings.com/event/uBAyja0aC7` — both are client-rendered single
   page applications, the WebFetch HTML→markdown pass reduces them to just the
   page title, so the API host and required headers cannot be read off the
   bundle this way.

## What the failure modes suggest

The 400 vs 403 split across paths means the host is alive and the routes exist,
but the requests are being rejected at the gateway before the handler runs.
This is consistent with AWS API Gateway requiring a custom header pair
(`client-id`, `x-api-key`, or a Cognito JWT) issued to the BCP web bundle.
WebFetch in this harness sends a fixed `User-Agent` and an `Accept` header and
nothing else — there is no way to add custom request headers through it.

## What would unblock a future run

One of the following — all out of scope for a `WebFetch`-only survey:

- A read-only `client-id` / `x-api-key` pair (BCP have historically issued
  these on request to community statisticians — Goonhammer, Woehammer,
  Stats and Ladders all consume the same API). Email is the usual route.
- A `requests`/`httpx` based scraper run outside the harness, with the
  client headers harvested from a real browser DevTools session. This would
  also need rate-limit pacing and a faction-name normalization map built
  from a first pass.
- Authoring a small Playwright/Selenium script that drives the JS app
  itself and reads the in-flight XHR responses. Same constraint — needs
  to run outside this harness.

## Recommendation

Defer BCP-1 until either (a) a client header pair is in hand, or (b) the
work moves to a local script the user runs directly. The current
hand-curated `APPROX_FACTIONS` block in `scripts/evaluate_vs_meta.py`
stays in place for now; no `data/bcp_faction_winrates.json` written this
session because the brief said not to fabricate.
