# Stat Check access report (2026-05-23)

Survey of `stat-check.com`'s 10th Edition Meta Data Dashboard as a second
real-meta calibration target alongside `data/warpfriends_rolling.json`.
Outcome: direct fetch is not possible from this session; a Playwright-based
local scraper has been shipped as `scripts/scrape_statcheck.py` for the user
to run.

## Why a second source

`data/warpfriends_rolling.json` derives from Best Coast Pairings only (via
Warp Friends' hand scrape). Stat Check aggregates **Best Coast Pairings +
TourneyKeeper + Mini Headquarters**, filtered to events with at least 25
players and 5 rounds. The TourneyKeeper and Mini Headquarters halves are
genuinely additional game volume (mainly European events), so Stat Check is
a useful cross-check on whether the Warp Friends roll-up is biased by the
Best Coast Pairings-only sample.

## What stat-check.com actually serves

The page at `stat-check.com/the-meta` and the dashboard at
`stat-check.com/meta-data-dashboard` are both Squarespace pages. They render
identical 200,584-byte HTML shells regardless of which URL is requested -
all the actual data lives in client-side JavaScript blocks. The pages do
not contain a `__NEXT_DATA__` blob, an `__INITIAL_STATE__` blob, or any
embedded `/api/...` fetch URLs.

Squarespace block-type enumeration found only ``alignment``, ``content``,
``embed``, ``horizontalrule``, ``html``, ``image``, ``socialaccountlinks``,
``website`` blocks (and two custom block types 47 and 1337, both confirmed
to be horizontal rules / text styles, not data blocks).

The data is rendered by **one embedded Tableau Public viz**:

- Workbook: `StatCheckThe40kMetaDataDashboard-10thEdition`
- View: `StateoftheGame`
- Loaded via the standard Tableau embed pattern
  (`<object class='tableauViz'>` with a child `<script>` that loads
  `https://public.tableau.com/javascripts/api/viz_v1.js`)
- The static thumbnail it falls back to is at
  `https://public.tableau.com/static/images/St/StatCheckThe40kMetaDataDashboard-10thEdition/StateoftheGame/1.png`

There is no Google Sheets, no Looker Studio, no Datawrapper, no Flourish,
no direct JSON API. Everything funnels through Tableau Public.

## What I tried for direct fetch

1. `GET stat-check.com/api/meta/factions` - HTTP 404.
2. `GET stat-check.com/api/factions` - HTTP 404.
3. `GET stat-check.com/api/meta` - HTTP 404.
4. `GET api.stat-check.com/factions` - `ECONNREFUSED` (host does not exist).
5. Raw HTML grep of `stat-check.com/the-meta` and
   `/meta-data-dashboard` for `__NEXT_DATA__`, `__INITIAL_STATE__`,
   `__APOLLO_STATE__`, any `/api/` fetch path, Google Sheets references,
   `iframe src` - all absent. Only the Tableau embed `<object>` is present.
6. `GET tools.squarewebsites.org/api/gss-html/?...` - the Google Sheets
   proxy used by the third-party `custom-table.js` plugin loaded on the
   page. Confirmed the plugin is loaded but no `data-gss-key` attribute
   exists anywhere on `/the-meta` or `/meta-data-dashboard`, so the
   plugin has nothing to render. (`custom-table` is loaded site-wide for
   other Stat Check pages, not for this dashboard.)
7. `GET public.tableau.com/views/StatCheckThe40kMetaDataDashboard-10thEdition/StateoftheGame.csv`
   - HTTP 404. The legacy direct-CSV endpoint is gone.
8. `POST public.tableau.com/vizql/w/.../v/.../bootstrapSession/sessions/empty`
   - HTTP 410 Gone. The legacy `bootstrapSession` endpoint that older
   `tableau-scraper`-style Python libraries used has been retired by Tableau.
9. `GET public.tableau.com/views/.../StateoftheGame?:format=csv`,
   `?:embed=y&:format=csv`, `.json`, `.xlsx` - all return HTTP 200 with
   1,438 bytes of the new Tableau Public Vite SPA shell
   (`<script type="module" src="/app/assets/index-BOYYIe0q.js">`). The
   query-string export hints that worked pre-2024 are no-ops on the new
   front end.
10. `GET public.tableau.com/profile/api/StatCheck40k`,
    `/profile/api/v1/profiles/StatCheck40k`, `/api/profile/StatCheck40k`
    - HTTP 404 across the lot.

## What the failure modes mean

Tableau Public migrated to a Vite single-page application at `/app/`
behind AWS WAF some time in 2024-2025. The page bootstrap involves a
captcha-SDK script (`c17315bd03da.edge.captcha-sdk.awswaf.com`) and a
GTM tag that fires before the data layer attaches. The legacy direct
data endpoints (`bootstrapSession`, `.csv` download, `.json` download,
profile API) have all been retired. The data is now served only to a
browser that:

1. Loads the SPA bundle
2. Passes the AWS WAF challenge (typically a hidden JavaScript challenge
   for headless browsers, not always a visible captcha)
3. Lets Tableau's client-side library make the new vizql POSTs that
   replace `bootstrapSession`

`urllib` / `Invoke-WebRequest` / `WebFetch` cannot do any of those three
things. The only viable path is a real browser - Playwright or Selenium.

## What I shipped

- `scripts/scrape_statcheck.py` - Playwright-based scraper. The script
  drives a headless Chromium to the Tableau viz URL, intercepts every
  `/vizql/.../sessions/` response over a configurable threshold size,
  parses the captured JSON blobs for faction-name tokens with adjacent
  game-count and win-rate numbers, normalises raw labels into
  SwegHammer's 22-faction list, and writes `data/statcheck_meta.json`
  with the same top-level shape as `data/warpfriends_rolling.json`.
- `data/statcheck_meta.json` - stub with metadata only, empty `factions`
  block, and an `instructions` field telling the next reader how to
  populate it. Per CLAUDE.md rule 13 (fail loud, no silent defaults)
  the script will not write a partial file with synthesised numbers; it
  will raise instead, leaving the stub in place.

The script is not runnable from the agent worktree because the harness
has no `pip` access. The user (or a future continuous-integration job)
needs to run it with:

```
pip install playwright
playwright install chromium
python -m scripts.scrape_statcheck
```

## What would unblock a future fully-automated run

Three options, all out of scope for this session:

- A continuous-integration job (GitHub Actions has Playwright pre-bakes)
  that runs `scrape_statcheck.py` weekly and commits the refreshed
  `data/statcheck_meta.json`.
- A change of upstream on Stat Check's side - if they ever republish the
  underlying numbers as a Google Sheet via the same `custom-table` plugin
  used on other Stat Check pages, the scraper can be replaced with a
  one-call `urllib` fetch.
- Reverse-engineer the AWS WAF challenge well enough to spoof it from
  `urllib` plus a session cookie. Not worth doing - the WAF challenge
  changes and a Playwright scraper is more resilient.

## What this changes for calibration

Nothing yet. Until the user runs `scripts/scrape_statcheck.py` locally
the stub `data/statcheck_meta.json` carries no usable numbers, and
`scripts/evaluate_vs_meta.py` is untouched (out of scope per the brief).
When the file is populated, the parent session that owns
`evaluate_vs_meta.py` can wire it as either a sanity-check overlay on
top of `warpfriends_rolling.json` or as a second `TOURNAMENT_TARGET`
column for cross-source mean-absolute-error reporting. The faction-name
normalisation table in `scripts/scrape_statcheck.py` is intentionally
mirror-image-aligned with `scripts/scrape_warpfriends.py`, so the
22-faction keys will match cleanly when both files are loaded together.

Sample cross-check values for the two priority factions (Chaos Space
Marines and Drukhari) were requested in the brief; they cannot be
provided in this session because no Stat Check data was retrieved. They
will appear in `data/statcheck_meta.json` once the user runs the script.
The Warp Friends comparison points to expect them to land near are
Chaos Space Marines 55.6% (n=1,979) and Drukhari 52.4% (n=848) from
the four-week rolling roll-up dated 2026-05-18.
