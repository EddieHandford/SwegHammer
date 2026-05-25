# Tournament data source survey — 2026-05-22

## TL;DR

The **Warp Friends WordPress archive** at `warpfriends.wordpress.com` is the
single best independent data source we found: weekly updates,
structured Markdown tables with every faction and game counts, hand-scraped
from Best Coast Pairings, and freshness within 2 days of the survey. Use it
as the primary calibration target — it is literally where our existing
`TOURNAMENT_TARGET` numbers already came from, but the public archive
covers all 22 factions every week, not just the 10 we currently have. The
`stat-check.com` dashboard exists and pulls from a wider set of upstreams
(Best Coast Pairings, TourneyKeeper, Mini Headquarters), but is a
JavaScript single-page application and not WebFetch-reachable; it would
need a headless browser or an undocumented JavaScript Object Notation
endpoint to scrape. Everything else surveyed is either prose-only, gated,
or a rebroadcast of these two.

Recommendation: build a Warp Friends weekly-archive scraper (server-side
rendered Markdown — trivial to parse) and use Stat Check only as a
cross-check if we get a headless-browser solution later.

## Source-by-source

### Warp Friends WordPress archive

- URL: `https://warpfriends.wordpress.com/` — most recent post
  `https://warpfriends.wordpress.com/2026/05/20/40k-meta-stats-from-may-18-2026/`
- WebFetch-reachable: **yes** (server-rendered WordPress, content in HTML)
- Has 10th edition 2026 per-faction win-rate data: **yes, all 22 factions
  including the 12 priority factions we are missing**
- Freshness: **weekly cadence, May 18 2026 post published May 20** —
  matches our calibration window
- Sample size: 1,124 players across 25 tournaments, 5,644 games, single-week
  aggregate (May 18 week). Per-faction sample is ~50-450 games depending on
  faction popularity. Across multiple weekly archives we can roll up to
  several thousand games per faction trivially.
- Independence: hand-scraped from Best Coast Pairings (the site states
  "Data is gathered by hand from Bestcoastpairings.com"). Lineage =
  Best Coast Pairings → human scrape → WordPress post. Same upstream as a
  hypothetical Best Coast Pairings API integration would give us, but no
  authentication required and no API key needed.
- Sample numbers (from May 18 2026 post):
  - Drukhari: **52.9%** (189 games)
  - Chaos Space Marines: **59.4%** (426 games)
- Structured: **yes, Markdown table** in the post body — WebFetch returns
  the table cleanly in one call.

**Full faction table snapshot — May 18 2026 post:**

| Faction | Win % | Games |
|---|---|---|
| Adeptus Custodes | 46.9% | 243 |
| Adeptus Mechanicus | 43.4% | 122 |
| Aeldari | 44.1% | 118 |
| Astra Militarum | 46.9% | 258 |
| Black Templars | 48.2% | 85 |
| Blood Angels | 40.2% | 169 |
| Chaos Daemons | 48.4% | 159 |
| Chaos Knights | 45.7% | 162 |
| Chaos Space Marines | 59.4% | 426 |
| Dark Angels | 48.4% | 213 |
| Death Guard | 48.3% | 325 |
| Deathwatch | 56.0% | 91 |
| Drukhari | 52.9% | 189 |
| Emperor's Children | 51.9% | 291 |
| Genestealer Cult | 55.3% | 47 |
| Grey Knights | 46.2% | 106 |
| Imperial Agents | 51.5% | 33 |
| Imperial Knights | 45.2% | 250 |
| Leagues of Votann | 51.8% | 139 |
| Necrons | 54.0% | 354 |
| Orks | 50.5% | 182 |
| Sisters of Battle | 52.5% | 141 |
| Space Marines | 43.9% | 374 |
| Space Wolves | 37.5% | 136 |
| Tau | 55.4% | 354 |
| Thousand Sons | 48.3% | 230 |
| Tyranids | 53.5% | 271 |
| World Eaters | 51.7% | 176 |

**Full faction table snapshot — May 5 2026 post (for cross-week sanity
check):**

| Faction | Win % | Games |
|---|---|---|
| Emperor's Children | 56.8% | 227 |
| Thousand Sons | 62.1% | 240 |
| Chaos Space Marines | 53.5% | 411 |
| Death Guard | 50.4% | 280 |
| Chaos Daemons | 50.3% | 179 |
| Chaos Knights | 45.6% | 103 |
| World Eaters | 44.2% | 269 |
| Drukhari | 48.7% | 193 |
| Tau | 50.7% | 404 |
| Necrons | 49.7% | 461 |
| Tyranids | 46.1% | 282 |
| Astra Militarum | 50.2% | 267 |
| Space Marines | 44.0% | 530 |
| Adeptus Custodes | 48.9% | 270 |
| Adeptus Mechanicus | 44.4% | 133 |
| Leagues of Votann | 47.8% | 226 |
| Adepta Sororitas | 50.3% | 147 |
| Grey Knights | 53.0% | 83 |
| Genestealer Cult | 49.1% | 55 |
| Imperial Knights | 50.5% | 196 |

The five most recent posts are May 18, May 11, May 5, April 27, and
March 30 — weekly cadence with one slip. Rolling up the last 4-5 posts
puts most factions into the ≥500 sample-size band, and the most popular
factions (Space Marines, Chaos Space Marines, Necrons, T'au) easily clear
≥1000 across two weeks.

- Notes: This *is* the Warp Friends archive — same brand whose 10
  factions we already pin to inside `TOURNAMENT_TARGET`. We were quoting
  numbers from a single tournament report; the public WordPress archive
  publishes the full 22-faction table every week with game counts.
  Calling this "new data" is a misnomer — it is the same upstream we
  already trust, but with full faction coverage we have not been using.

### Stat Check (`stat-check.com`)

- URL: `https://www.stat-check.com/the-meta`
- WebFetch-reachable: **no — JavaScript-rendered dashboard**. WebFetch
  retrieves only the documentation prose and not the interactive charts.
  The page itself describes "three interlinked charts" which clicking
  through filters by faction — a single-page application.
- Has 10th edition 2026 per-faction win-rate data: **yes**, per
  documentation, sourced from "all Warhammer 40,000 events across the
  globe with a minimum of 25 players and 5 rounds".
- Freshness: claimed real-time / continuously updated.
- Sample size: largest of any source surveyed (multi-platform
  aggregation), but exact per-faction counts not visible to WebFetch.
- Independence: aggregates **TourneyKeeper + Best Coast Pairings + Mini
  Headquarters**. The Best Coast Pairings half overlaps with Warp Friends'
  upstream; TourneyKeeper and Mini Headquarters are genuinely additional
  game volume. So this is partially independent of Warp Friends.
- Sample numbers (Drukhari / Chaos Space Marines): **not retrievable**
  via WebFetch.
- Notes: Would require a headless browser (Playwright / Selenium) or
  reverse-engineering the page's JavaScript Object Notation endpoints to
  scrape. Strongest source on paper, but the highest engineering cost.

### Goonhammer 40kStats (`40kstats.goonhammer.com` →
`40kstats.tabletopbattles.com`)

- URL: `http://40kstats.tabletopbattles.com/` (subdomain
  `40kstats.goonhammer.com` 301-redirects there)
- WebFetch-reachable: **partially** — page skeleton loads but the win
  rate tables are JavaScript-populated and arrive empty from WebFetch.
- Has 10th edition 2026 per-faction win-rate data: yes per the section
  header "Win Rate and Points by Faction" but content not visible to
  static fetch.
- Freshness: unknown, date fields render empty to WebFetch.
- Sample size: unknown.
- Independence: not stated on the landing page; rebranded from a
  Goonhammer subdomain to `tabletopbattles.com`, which suggests
  third-party-hosted aggregation. Goonhammer's editorial articles cite
  Stat Check and Best Coast Pairings interchangeably, so this is
  probably not independent of Stat Check.
- Sample numbers: not retrievable via WebFetch.
- Notes: Same headless-browser problem as Stat Check.

### Goonhammer Competitive Innovations articles

- URL pattern:
  `https://www.goonhammer.com/40k-competitive-innovations-in-10th-*`
- WebFetch-reachable: **yes** (WordPress, server-rendered), but the
  individual articles I tried returned empty body extractions — possibly
  WebFetch cache stalemate. Even when they do extract, the content is
  **prose, not structured tables**. Each article is event-by-event
  narrative ("a 279-player Supermajor in Maastricht on April 24"…).
- Has aggregate per-faction win-rate table: **no, not in the per-week
  articles**. Goonhammer's aggregate work is on the Hammer of Math
  series and the 40kStats subdomain (above), not in Competitive
  Innovations.
- Notes: Useful for narrative context and individual-event drill-down,
  not useful as a direct calibration target.

### Woehammer (`woehammer.com`)

- URL: `https://woehammer.com/` and per-event posts.
- WebFetch-reachable: yes (WordPress).
- Has 10th edition 2026 per-faction win-rate data: **not in their recent
  output**. Their most recent dataslate-style aggregate posts in 2026
  are Age of Sigmar focused. The 40k content in 2026 has been
  methodology-only ("Why faction win rates alone are bad",
  "Why early win rates lie") rather than fresh aggregates.
- Notes: Once a strong 40k source, currently inactive for 40k aggregates.
  Skip.

### r/WarhammerCompetitive weekly threads

- WebFetch-reachable: subreddit is Reddit, reachable but rate-limited
  and frequently locked behind the new Reddit gating.
- Has structured per-faction data: **no — community discussion threads,
  prose only**. Tables are sometimes pasted by users but unstructured
  and not authoritative. The threads themselves frequently link to
  Stat Check, Warp Friends, and 40kStats.
- Notes: Skip — these threads are downstream of the sources above.

### New Recruit (`newrecruit.eu`)

- URL: `https://www.newrecruit.eu/stats`
- WebFetch-reachable: **no — Next.js single-page application**. WebFetch
  returns navigation chrome but no data.
- Has data: navigation lists "Factions", "Detachments", "Results Matrix",
  "Internal Balance", "Health Check" sections, so per-faction data
  almost certainly exists in the rendered application, but invisible to
  WebFetch.
- Independence: New Recruit's tournament-tool installed-base is European
  and partially overlapping with Best Coast Pairings but with a chunk of
  events that Best Coast Pairings does not capture. Probably genuinely
  independent for European events.
- Notes: Would require headless browser. Worth revisiting later if we
  want a cross-continent sanity check on Stat Check.

### Frontline Gaming (`frontlinegaming.org`)

- URL: ITC rankings page redirected to a 404 on the path I tried; the
  Independent Tournament Circuit hub has reorganised.
- Has data: ITC tracks tournament results, but ITC scoring is its own
  metric (a season-long points system), not a clean per-faction
  game-level win rate.
- Notes: Skip for our use case — wrong shape of data.

### Tabletop Tactics

- Not surveyed in detail — they are a battle-report and tutorial channel,
  not a statistics aggregator. Confirmed by general search results that
  return no aggregate stats page from their domain.

## Recommendation

**Primary recommendation: build a Warp Friends WordPress scraper.** One
fetch per weekly post, parse the Markdown table, accumulate the last 4
weeks for ≥500 games per faction on the small ones and ≥1000 on the
popular ones. This source is:

- Server-rendered HTML, WebFetch-friendly with zero JavaScript.
- Weekly cadence with consistent table format we can parse with a
  regular expression.
- Sourced from Best Coast Pairings (the same upstream our existing 10
  pinned factions came from), so the units of measurement are
  consistent with what `TOURNAMENT_TARGET` already encodes.
- Covers all 22 factions every week — directly closes the 12-faction
  gap that `APPROX_FACTIONS` is currently filling with 48-51% guesses.

**Secondary recommendation: don't invest in Stat Check or Goonhammer
40kStats until Warp Friends proves insufficient.** Both would need a
headless-browser scraper, which is a significant engineering hop. The
Warp Friends archive's BCP lineage already overlaps with most of what
those sources show, so the marginal value of adding them is modest until
we want a true cross-source check.

**No user action required.** No API keys, no logins, no rate-limit
negotiation. The Warp Friends archive is publicly listed and indexed,
and weekly posts are reachable via predictable URL patterns
(`/YYYY/MM/DD/40k-meta-stats-from-MONTH-DAY-2026/`).

**Next step for the data-source agent that follows this survey:** wire a
`scripts/scrape_warpfriends.py` that fetches the last N weekly posts,
parses the per-faction Markdown table, aggregates game-weighted win
rates, and writes a replacement structure for `TOURNAMENT_TARGET` to a
JSON file under `data/`. Keep the existing target as a frozen baseline
for change comparison.

## Real-meta vs current TOURNAMENT_TARGET (2026-05-23)

`scripts/scrape_warpfriends.py` was run on 2026-05-23 against the five
weekly posts listed in this doc. Four of the five rolled up cleanly; the
2026-05-11 post was skipped because it published only a rolling /
cumulative table (per-faction game sum ~41,710) rather than the usual
single-week snapshot, and mixing a rolling table into a game-weighted
mean alongside four week-scoped tables would silently bias the
aggregate. The rollup therefore covers the four weeks
2026-05-18, 2026-05-05, 2026-04-27, 2026-03-30, totalling 31,841
faction-games. Results live in `data/warpfriends_rolling.json`.

The table below compares the current `TOURNAMENT_TARGET` baked into
`scripts/evaluate_vs_meta.py` against the freshly-rolled game-weighted
mean. The noise floor column is the larger of (population standard
deviation of the four weekly win rates, binomial 95% confidence
half-width on the aggregate sample) — i.e. the answer to "below what
mean absolute error is calibration chasing noise" for that faction. The
gap column shows new mean minus old target, sorted by absolute size
descending.

| Faction | Old target | Rolling mean | Total games | Noise floor | Gap |
|---|---:|---:|---:|---:|---:|
| Chaos Space Marines | 46.0 | 55.63 | 1,979 | 2.48 | +9.63 |
| Chaos Daemons | 47.0 | 52.60 | 960 | 3.16 | +5.60 |
| Emperor's Children | 48.0 | 53.32 | 1,234 | 5.67 | +5.32 |
| World Eaters | 50.0 | 44.93 | 1,291 | 3.42 | -5.07 |
| Aeldari | 44.4 | 41.55 | 970 | 3.10 | -2.85 |
| Leagues of Votann | 46.0 | 48.04 | 1,045 | 3.03 | +2.04 |
| Adepta Sororitas | 49.0 | 50.75 | 670 | 3.79 | +1.75 |
| Astra Militarum | 47.0 | 45.28 | 1,725 | 3.18 | -1.72 |
| Imperial Knights | 46.0 | 47.71 | 1,094 | 2.96 | +1.71 |
| Adeptus Custodes | 48.0 | 49.53 | 1,369 | 2.65 | +1.53 |
| Drukhari | 51.0 | 52.36 | 848 | 3.36 | +1.36 |
| Adeptus Astartes | 48.0 | 46.95 | 6,599 | 2.16 | -1.05 |
| Tyranids | 48.0 | 46.96 | 1,365 | 3.82 | -1.04 |
| Thousand Sons | 54.6 | 53.89 | 1,080 | 8.75 | -0.71 |
| Genestealer Cults | 46.0 | 46.68 | 452 | 4.60 | +0.68 |
| Adeptus Mechanicus | 45.0 | 44.40 | 545 | 4.17 | -0.60 |
| Death Guard | 48.0 | 47.61 | 1,441 | 2.58 | -0.39 |
| Orks | 44.9 | 45.27 | 1,195 | 2.90 | +0.37 |
| Chaos Knights | 45.0 | 44.71 | 879 | 3.29 | -0.29 |
| Necrons | 53.2 | 53.46 | 2,413 | 3.22 | +0.26 |
| Grey Knights | 47.0 | 46.74 | 537 | 4.22 | -0.26 |
| T'au Empire | 54.5 | 54.28 | 2,150 | 4.23 | -0.22 |

**Top-line numbers.** Mean absolute gap (old vs new) across the 22
factions is **2.02 pts**, so on average the hand-curated targets are
already pretty close to a real four-week aggregate. The mean per-faction
noise floor — the average of the "below this is noise" thresholds — is
**3.67 pts**. That is the practical mean-absolute-error floor the
simulator should not expect to undercut from real-meta data at the
current sample size; the current 2.0 pt mean-absolute-error target sits
beneath it. The implication is not that the target should be relaxed
unconditionally, but that any single faction landing inside its own
noise band should not be chased further with rule edits.

**Biggest movers.** Chaos Space Marines is the one large surprise:
55.6% over four weeks is 9.6 pts above the 46.0% target the simulator
is calibrated against, and the noise floor (2.5 pts) is small enough
that this is signal not sample variance. Chaos Daemons and Emperor's
Children also drift +5pt high, and World Eaters drifts -5pt low — the
Chaos block in general looks like it should re-target ~52% rather than
the current ~47-50% average. Aeldari shifts -2.85 (the rolling sample
runs cooler than the hand-curated 44.4). Everything else is inside
±2 pts and inside its noise band.

**Meta-volatility signals.** Thousand Sons' noise floor of 8.75pt comes
from a week-to-week swing of 45-66% across the four samples — that
faction is genuinely meta-unstable in this window (likely a recent
detachment dataslate moving the needle), and the current target of
54.6 happens to land inside the volatility band. Emperor's Children
(5.67), Genestealer Cults (4.60), and T'au (4.23) are the next most
volatile.

**Survey/scraper output only — no consumer changes yet.** The numbers
above are not wired into `evaluate_vs_meta.py`. The user makes the call
on whether to replace `TOURNAMENT_TARGET` with the rolling mean
(directly, or as a per-faction overlay that triggers when the gap
exceeds the noise floor).
