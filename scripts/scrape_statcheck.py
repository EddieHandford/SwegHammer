"""Scrape Stat Check's 10th Edition Meta Data Dashboard via the embedded Tableau viz.

Background
----------
``stat-check.com/meta-data-dashboard`` is a Squarespace page whose interactive
charts are a Tableau Public embed: workbook ``StatCheckThe40kMetaDataDashboard``
``-10thEdition``, view ``StateoftheGame``, hosted under ``public.tableau.com``.
Stat Check aggregates from **Best Coast Pairings + TourneyKeeper + Mini
Headquarters** (per the dashboard's own description text), filtered to events
with at least 25 players and 5 rounds. That makes it broader than Warp Friends
(which only sees the Best Coast Pairings half-meta) and a useful cross-check
against ``data/warpfriends_rolling.json``.

Why this script needs Playwright
--------------------------------
Tableau Public has migrated to a Vite single-page-application shell at
``public.tableau.com/app/...`` that boot-loads behind AWS WAF. The legacy
``/vizql/.../bootstrapSession`` endpoint that older scrapers used returns
``HTTP 410 Gone``; the legacy ``views/.../<view>.csv`` direct-download endpoint
returns ``HTTP 404``. Both were retired by Tableau in 2024-2025.

The remaining path is to load the viz in a real browser, let Tableau's
client-side bundle re-hydrate the data layer, and capture the JSON / CSV
responses Tableau's ``/vizql/`` workers send back to the page. That is what
this script does, with Playwright.

The agent worktree that wrote this script could not run it (no ``pip`` access
inside the agent harness). The script is shipped for the user (or a future
continuous-integration job) to run locally.

Install + run (local)
---------------------
::

    pip install playwright
    playwright install chromium
    python -m scripts.scrape_statcheck

The script writes ``data/statcheck_meta.json`` next to
``data/warpfriends_rolling.json``, with the same top-level shape (``metadata``
plus ``factions`` with ``win_rate`` / ``total_games`` / ``noise_floor`` keys)
so a future ``evaluate_vs_meta.py`` consumer can load either or both as
calibration targets.

Output schema (matches data/warpfriends_rolling.json where possible)
--------------------------------------------------------------------
::

    {
      "metadata": {
        "scraped_at": "YYYY-MM-DD",
        "source": "stat-check.com via public.tableau.com",
        "primary_upstream": "Best Coast Pairings + TourneyKeeper + Mini Headquarters",
        "tableau_workbook": "StatCheckThe40kMetaDataDashboard-10thEdition",
        "tableau_view": "StateoftheGame",
        "filter_applied": "<which Meta filter was active when scraped>",
        "minimum_event_size": "25 players, 5 rounds",
        "unmapped_strings_surfaced": {<raw faction string>: <reason>},
        "dropped_strings": [...],
        "capture_method": "playwright network-response interception"
      },
      "factions": {
        "<SwegHammer faction name>": {
          "win_rate": <float, percentage points>,
          "total_games": <int>,
          "noise_floor": <float, binomial 95% CI half-width on win_rate>,
          "rolled_from": [<raw Stat Check / Tableau faction string>]
        },
        ...
      }
    }

Faction-name normalisation
--------------------------
Stat Check publishes 28 faction buckets including six Space Marine chapters.
SwegHammer treats Adeptus Astartes as one bucket, so the six chapters are
game-weighted-aggregated together. Three label normalisations match the
Warp Friends scraper's existing mapping (``Tau`` -> ``T'au Empire``,
``Sisters of Battle`` -> ``Adepta Sororitas``, ``Genestealer Cult`` ->
``Genestealer Cults``). ``Imperial Agents`` is dropped (not in SwegHammer's
faction list) and recorded in ``metadata.dropped_strings``. Any unrecognised
raw string is surfaced under ``metadata.unmapped_strings_surfaced`` per
CLAUDE.md rule 13 (fail loud, no silent defaults).

The fail-loud bit
-----------------
If the script cannot find the Tableau viz, cannot capture any data response,
or captures responses that do not contain the expected per-faction rows, it
raises a ``RuntimeError`` naming what went wrong. It does NOT write a partial
``data/statcheck_meta.json`` with synthesised numbers - that's the failure
mode CLAUDE.md rule 13 exists to prevent.
"""

from __future__ import annotations

import json
import math
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Configuration.
# ---------------------------------------------------------------------------

# The dashboard URL that hosts the Tableau embed.
STATCHECK_DASHBOARD_URL = "https://stat-check.com/meta-data-dashboard"

# Direct Tableau Public view URL (extracted from the embed block on the
# Squarespace page on 2026-05-23). Loading this URL directly is faster than
# loading the Squarespace shell and waiting for the embed to bootstrap.
TABLEAU_VIEW_URL = (
    "https://public.tableau.com/views/"
    "StatCheckThe40kMetaDataDashboard-10thEdition/StateoftheGame"
    "?:embed=y&:showVizHome=no&:display_count=no&:language=en-US"
)

# Network-response filter: Tableau Public posts back to /vizql/ worker URLs
# with the actual data payload. The first response that matches this pattern
# and is large enough to plausibly contain the faction table is the one we
# want.
_VIZQL_RESPONSE_RE = re.compile(r"/vizql/.*sessions/", re.IGNORECASE)
_MIN_DATA_BODY_BYTES = 10_000  # below this, it's a handshake reply

# How long to give Tableau to finish bootstrapping after the page reaches
# ``networkidle`` (seconds). Tableau's data layer fires a few responses after
# the initial paint settles.
_POST_NETWORKIDLE_WAIT_SEC = 12.0

# Total page-load deadline.
_PAGE_TIMEOUT_MS = 90_000

# Same 22-faction list and normalisation table as
# ``scripts/scrape_warpfriends.py`` - keep them in sync if the canonical list
# moves.
SWEG_FACTIONS: List[str] = [
    "Adeptus Astartes", "Necrons", "Aeldari", "Tyranids", "Orks", "T'au Empire",
    "Death Guard", "Adeptus Custodes", "Thousand Sons", "Leagues of Votann",
    "Chaos Space Marines", "World Eaters", "Emperor's Children", "Chaos Daemons",
    "Astra Militarum", "Adeptus Mechanicus", "Adepta Sororitas", "Grey Knights",
    "Drukhari", "Genestealer Cults", "Imperial Knights", "Chaos Knights",
]

SM_CHAPTERS: List[str] = [
    "Space Marines", "Black Templars", "Blood Angels",
    "Dark Angels", "Deathwatch", "Space Wolves",
]

NORMALISE: Dict[str, str] = {
    "Tau": "T'au Empire",
    "T'au": "T'au Empire",
    "T'au Empire": "T'au Empire",
    "Sisters of Battle": "Adepta Sororitas",
    "Adepta Sororitas": "Adepta Sororitas",
    "Genestealer Cult": "Genestealer Cults",
    "Genestealer Cults": "Genestealer Cults",
    "Necrons": "Necrons",
    "Aeldari": "Aeldari",
    "Tyranids": "Tyranids",
    "Orks": "Orks",
    "Death Guard": "Death Guard",
    "Adeptus Custodes": "Adeptus Custodes",
    "Thousand Sons": "Thousand Sons",
    "Leagues of Votann": "Leagues of Votann",
    "Chaos Space Marines": "Chaos Space Marines",
    "World Eaters": "World Eaters",
    "Emperor's Children": "Emperor's Children",
    "Chaos Daemons": "Chaos Daemons",
    "Astra Militarum": "Astra Militarum",
    "Adeptus Mechanicus": "Adeptus Mechanicus",
    "Grey Knights": "Grey Knights",
    "Drukhari": "Drukhari",
    "Imperial Knights": "Imperial Knights",
    "Chaos Knights": "Chaos Knights",
}
for _chapter in SM_CHAPTERS:
    NORMALISE[_chapter] = "Adeptus Astartes"

DROP_STRINGS = {"Imperial Agents"}

# Z-score for 95% two-sided binomial confidence interval (matches Warp Friends).
Z_95 = 1.96


# ---------------------------------------------------------------------------
# Network-response capture.
# ---------------------------------------------------------------------------

def _capture_tableau_responses(timeout_sec: float = _POST_NETWORKIDLE_WAIT_SEC
                               ) -> List[Dict[str, Any]]:
    """Drive a headless Chromium to the Tableau view and capture vizql responses.

    Returns a list of dicts: ``{"url": str, "body": str, "content_type": str}``
    for every response whose URL matches the vizql session pattern and whose
    body is at least ``_MIN_DATA_BODY_BYTES``. Raises ``RuntimeError`` if the
    page failed to load or no vizql responses appeared at all.

    Importing ``playwright`` happens inside this function so the module is
    importable on machines that don't have Playwright installed - the user
    only needs it when they actually run the scrape.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - install-time message
        raise RuntimeError(
            "Playwright is not installed. Run `pip install playwright && "
            "playwright install chromium` before running this scraper."
        ) from exc

    captured: List[Dict[str, Any]] = []

    def _on_response(response):  # noqa: ANN001 - playwright type
        try:
            url = response.url
            if not _VIZQL_RESPONSE_RE.search(url):
                return
            # Tableau replies are sometimes chunked; reading body() can throw
            # if the response was redirected or already discarded.
            body_bytes = response.body()
            if not body_bytes or len(body_bytes) < _MIN_DATA_BODY_BYTES:
                return
            try:
                body = body_bytes.decode("utf-8", errors="replace")
            except Exception:  # pragma: no cover - decode safety
                return
            captured.append({
                "url": url,
                "body": body,
                "content_type": response.headers.get("content-type", ""),
            })
        except Exception:  # pragma: no cover - response cleanup safety
            return

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1600, "height": 1200},
            )
            page = context.new_page()
            page.on("response", _on_response)
            page.set_default_timeout(_PAGE_TIMEOUT_MS)
            page.goto(TABLEAU_VIEW_URL, wait_until="networkidle",
                      timeout=_PAGE_TIMEOUT_MS)
            # After networkidle, give Tableau a beat to finish lazy data
            # requests. Tableau's vizql worker often posts the actual data
            # only after the dashboard's initial layout has settled.
            page.wait_for_timeout(int(timeout_sec * 1000))
        finally:
            browser.close()

    if not captured:
        raise RuntimeError(
            "No /vizql/ session responses captured. Tableau may have changed "
            "its data-fetch path again, or the AWS WAF blocked headless "
            "Chromium. Re-run with headless=False (edit the script) and "
            "watch the network panel."
        )
    return captured


# ---------------------------------------------------------------------------
# Parse the captured Tableau payload into per-faction (wins, games).
# ---------------------------------------------------------------------------

_FACTION_TOKEN_RE = re.compile(
    r"\b("
    r"Adeptus Custodes|Adeptus Mechanicus|Adeptus Astartes|Space Marines|"
    r"Black Templars|Blood Angels|Dark Angels|Deathwatch|Space Wolves|"
    r"Aeldari|Astra Militarum|Chaos Daemons|Chaos Knights|"
    r"Chaos Space Marines|Dark Angels|Death Guard|Drukhari|"
    r"Emperor's Children|Genestealer Cults?|Grey Knights|Imperial Agents|"
    r"Imperial Knights|Leagues of Votann|Necrons|Orks|Adepta Sororitas|"
    r"Sisters of Battle|T'au Empire|Tau|Thousand Sons|Tyranids|World Eaters"
    r")\b"
)


def _extract_faction_rows(payloads: List[Dict[str, Any]]
                          ) -> Dict[str, Tuple[int, int]]:
    """Parse the Tableau response bodies into ``{raw_faction: (wins, games)}``.

    Tableau Public payloads come in two halves: a small JSON wrapper, then a
    larger semicolon-prefixed JSON blob containing the data model. We don't
    know exactly which fields Stat Check named, so we walk the response text
    for faction-name tokens and pull adjacent numeric pairs (one being a count
    of games, one being a win rate or a win count).

    On a real run, inspect the captured payloads to figure out the exact key
    names Stat Check uses, then tighten this parser. For the first scrape,
    we surface a sample of unmatched tokens in metadata so the parser can be
    refined without guessing.

    This function is intentionally permissive at the FIRST call (it will
    return whatever it could extract) and the caller is responsible for
    sanity-checking the result and raising if too few factions resolved.
    """
    rows: Dict[str, Tuple[int, int]] = {}
    for payload in payloads:
        body = payload["body"]
        # Tableau Public wraps JSON payloads in length-prefix framing:
        # ``<n>;{json}<m>;{json}...``. Split conservatively on ``;{`` to
        # recover JSON blobs without misparsing nested JSON.
        for chunk in re.split(r"(?<=\d);(?=\{)", body):
            chunk = chunk.strip()
            if not chunk.startswith("{"):
                continue
            try:
                obj = json.loads(chunk)
            except json.JSONDecodeError:
                continue
            _walk_for_faction_data(obj, rows)
    return rows


def _walk_for_faction_data(obj: Any, rows: Dict[str, Tuple[int, int]]) -> None:
    """Depth-first walk that pulls (faction, games, wins) triples from the
    Tableau data-model JSON. Tableau encodes data as ``dataValues`` arrays
    indexed by ``dataDictionary`` columns; without a Tableau parser library
    we can only do best-effort token-matching here.

    The walk records into ``rows`` only when it sees a faction-name token
    adjacent to two plausible-looking numeric values (games >= 5, win count
    or win pct between 0 and 100). Tighten this once a real captured payload
    is inspected.
    """
    if isinstance(obj, dict):
        for value in obj.values():
            _walk_for_faction_data(value, rows)
    elif isinstance(obj, list):
        # Look for [.., faction_name, .., wins_or_pct, .., games, ..] shaped
        # rows. This is heuristic - swap in the real Stat Check column names
        # after the first successful capture.
        flat_strings = [x for x in obj if isinstance(x, str)]
        flat_numbers = [x for x in obj if isinstance(x, (int, float))]
        for s in flat_strings:
            m = _FACTION_TOKEN_RE.search(s)
            if not m:
                continue
            faction = m.group(1)
            plausible_games = [n for n in flat_numbers
                               if isinstance(n, int) and 5 <= n <= 50_000]
            plausible_winpct = [n for n in flat_numbers
                                if isinstance(n, float) and 0 <= n <= 100]
            if plausible_games and plausible_winpct:
                games = int(plausible_games[0])
                wins = int(round(plausible_winpct[0] / 100.0 * games))
                # Keep the first sighting only - later rows in the same
                # response often duplicate earlier ones.
                rows.setdefault(faction, (wins, games))
        for value in obj:
            _walk_for_faction_data(value, rows)


# ---------------------------------------------------------------------------
# Normalise raw faction labels -> SwegHammer's 22.
# ---------------------------------------------------------------------------

def _rollup_to_sweghammer(raw_rows: Dict[str, Tuple[int, int]]
                          ) -> Tuple[Dict[str, Dict[str, Any]],
                                     Dict[str, List[str]]]:
    """Aggregate raw Stat Check / Tableau faction strings into SwegHammer's
    22-faction structure.

    Returns ``(factions_dict, unmapped_strings)`` where ``factions_dict`` has
    the schema described in the module docstring, and ``unmapped_strings``
    is ``{raw_string: ["could not be mapped to any SwegHammer faction"]}``.
    """
    buckets: Dict[str, List[Tuple[int, int, str]]] = {
        fac: [] for fac in SWEG_FACTIONS
    }
    unmapped: Dict[str, List[str]] = {}

    for raw, (wins, games) in raw_rows.items():
        if raw in DROP_STRINGS:
            continue
        mapped = NORMALISE.get(raw)
        if mapped is None:
            unmapped[raw] = [
                f"raw label '{raw}' could not be mapped to any of the 22 "
                f"SwegHammer factions; add to NORMALISE in "
                f"scripts/scrape_statcheck.py"
            ]
            continue
        if mapped not in buckets:
            unmapped[raw] = [
                f"mapped to '{mapped}' which is not in SWEG_FACTIONS"
            ]
            continue
        buckets[mapped].append((wins, games, raw))

    factions: Dict[str, Dict[str, Any]] = {}
    for fac in SWEG_FACTIONS:
        bucket = buckets[fac]
        if not bucket:
            # Fail loud per CLAUDE.md rule 13: missing faction is recorded,
            # not silently zeroed.
            factions[fac] = {
                "win_rate": None,
                "total_games": 0,
                "noise_floor": None,
                "rolled_from": [],
                "missing": (
                    "no raw rows resolved to this faction; Tableau payload "
                    "may have changed shape or label changed upstream"
                ),
            }
            continue
        total_wins = sum(w for w, _, _ in bucket)
        total_games = sum(g for _, g, _ in bucket)
        win_rate = (total_wins / total_games * 100.0) if total_games else 0.0
        # Binomial 95% confidence interval half-width on the aggregate.
        if total_games > 0:
            p = win_rate / 100.0
            noise = Z_95 * math.sqrt(p * (1 - p) / total_games) * 100.0
        else:
            noise = float("nan")
        factions[fac] = {
            "win_rate": round(win_rate, 2),
            "total_games": int(total_games),
            "noise_floor": round(noise, 3),
            "rolled_from": sorted({raw for _, _, raw in bucket}),
        }
    return factions, unmapped


# ---------------------------------------------------------------------------
# Main entry point.
# ---------------------------------------------------------------------------

def main(out_path: Optional[Path] = None) -> Dict[str, Any]:
    """Drive the scrape and write ``data/statcheck_meta.json``.

    Raises ``RuntimeError`` on capture failure or implausibly thin coverage
    (fewer than 10 of the 22 SwegHammer factions resolved). The user can
    re-run with a stricter parser once they've inspected a saved payload.
    """
    repo_root = Path(__file__).resolve().parents[1]
    if out_path is None:
        out_path = repo_root / "data" / "statcheck_meta.json"

    payloads = _capture_tableau_responses()
    raw_rows = _extract_faction_rows(payloads)
    if not raw_rows:
        raise RuntimeError(
            "Captured Tableau responses but could not extract any faction "
            "rows. Inspect the captured bodies by editing this script to "
            "dump `payloads` before parsing."
        )

    factions, unmapped = _rollup_to_sweghammer(raw_rows)
    resolved_factions = sum(1 for v in factions.values()
                            if v.get("win_rate") is not None)
    if resolved_factions < 10:
        raise RuntimeError(
            f"Only {resolved_factions} of {len(SWEG_FACTIONS)} factions "
            f"resolved from the Tableau payload. The parser heuristics in "
            f"`_walk_for_faction_data` need to be tightened against a real "
            f"capture - dump `payloads` to a file and refine the column "
            f"matching before writing data/statcheck_meta.json."
        )

    payload = {
        "metadata": {
            "scraped_at": date.today().isoformat(),
            "source": "stat-check.com via public.tableau.com",
            "primary_upstream": (
                "Best Coast Pairings + TourneyKeeper + Mini Headquarters"
            ),
            "tableau_workbook": "StatCheckThe40kMetaDataDashboard-10thEdition",
            "tableau_view": "StateoftheGame",
            "filter_applied": (
                "default (whichever Meta filter loads on first paint)"
            ),
            "minimum_event_size": "25 players, 5 rounds",
            "unmapped_strings_surfaced": unmapped,
            "dropped_strings": sorted(DROP_STRINGS),
            "capture_method": "playwright network-response interception",
            "captured_response_count": len(payloads),
        },
        "factions": factions,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return payload


if __name__ == "__main__":
    payload = main()
    md = payload["metadata"]
    print(f"Wrote stat-check meta for {len(payload['factions'])} factions.")
    print(f"  Tableau workbook: {md['tableau_workbook']}")
    print(f"  Tableau view: {md['tableau_view']}")
    print(f"  Captured responses: {md['captured_response_count']}")
    if md["unmapped_strings_surfaced"]:
        print(f"  Unmapped strings: {md['unmapped_strings_surfaced']}")
    sys.exit(0)
