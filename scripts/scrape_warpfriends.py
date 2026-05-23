"""Scrape Warp Friends weekly per-faction win-rate posts and roll up to SwegHammer's
22-faction list.

Background
----------
The Warp Friends WordPress archive at ``warpfriends.wordpress.com`` publishes
weekly per-faction win-rate tables hand-scraped from Best Coast Pairings. Each
post contains a primary single-week faction table:

    Faction | Subfaction | #Players | Wins | Games | X-0/X-1 | Tourn Wins | Win%

We pull the last N weekly posts (default: the five hard-coded dates the survey
identified), strip out per-subfaction rows (those whose Faction column ends in
``*``), keep the faction-aggregate rows, and roll up to SwegHammer's
22-faction list.

Rollup map
----------
Warp Friends publishes 28 faction buckets including six Space Marine chapters.
SwegHammer treats Adeptus Astartes as one bucket, so we game-weighted-aggregate
the six chapters together. We also string-normalise three labels and DROP
``Imperial Agents`` (not in SwegHammer's faction list). Any unmapped string is
surfaced in the JSON metadata; missing data raises (no silent fallbacks, per
``CLAUDE.md`` rule 13).

Stats per faction
-----------------
For each SwegHammer faction across the included weeks:

  * ``win_rate`` -- game-weighted mean (``sum(wins) / sum(games) * 100``).
  * ``total_games`` -- summed across weeks and across rolled-in chapters.
  * ``weekly_win_rates`` -- the per-week values that fed the rollup
    (for transparency / future charting). For Adeptus Astartes the per-week
    value is itself a game-weighted aggregate across the six chapters in that
    week.
  * ``week_to_week_stdev`` -- population standard deviation of the per-week
    win rates. This is the meta-volatility signal: how much does this faction
    swing between independent weekly tournament samples.
  * ``binomial_ci_95_halfwidth`` -- the binomial 95% confidence-interval half
    width on the aggregate sample, in win-rate points:
    ``1.96 * sqrt(p*(1-p)/n) * 100`` where ``p = win_rate/100``,
    ``n = total_games``. This is the sampling-noise floor on the aggregate.
  * ``noise_floor`` -- ``max(week_to_week_stdev, binomial_ci_95_halfwidth)``.
    The answer to "below what mean-absolute-error are we chasing noise?" for
    this faction.
  * ``rolled_from`` -- the raw Warp Friends source strings that contributed.

The script writes ``data/warpfriends_rolling.json`` next to the repo's other
calibration JSON, and is re-runnable: edit ``WEEK_POSTS`` (or pass dates on
the command line in a future revision) and re-run with
``python -m scripts.scrape_warpfriends``.

Network policy: standard-library ``urllib.request`` only. No new dependencies.
HTML parsing is regex-based because the Warp Friends WordPress theme renders a
stable ``<table>`` shape and the chunks of text we need are tightly local.

The fail-loud bit
-----------------
A post that does not yield a parseable single-week table -- for example, the
2026-05-11 post which the survey identified as containing only the long
rolling table -- is surfaced in metadata under ``skipped_weeks`` with a
``reason`` string, and its rows do not feed the rollup. Mixing a 62k-game
rolling table into a game-weighted mean alongside four 5k-game weekly
snapshots would silently bias the result toward the rolling sample. Better to
say loudly "we used 4 of 5 weeks" than to fudge.
"""

from __future__ import annotations

import json
import math
import re
import statistics
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Configuration: the five weekly posts we're rolling up.
# ---------------------------------------------------------------------------

# (week_date_iso, post_permalink). Post URLs are the publication URLs, which
# are typically two days after the week label in the title.
WEEK_POSTS: List[Tuple[str, str]] = [
    ("2026-05-18", "https://warpfriends.wordpress.com/2026/05/20/40k-meta-stats-from-may-18-2026/"),
    ("2026-05-11", "https://warpfriends.wordpress.com/2026/05/13/40k-meta-stats-from-may-11-2026/"),
    ("2026-05-05", "https://warpfriends.wordpress.com/2026/05/06/40k-meta-stats-from-may-5-2026/"),
    ("2026-04-27", "https://warpfriends.wordpress.com/2026/04/29/40k-meta-stats-from-april-27-2026/"),
    ("2026-03-30", "https://warpfriends.wordpress.com/2026/04/01/40k-meta-stats-from-march-30-2026/"),
]

# The 22 SwegHammer faction names. Order matters for the output JSON ordering.
SWEG_FACTIONS: List[str] = [
    "Adeptus Astartes", "Necrons", "Aeldari", "Tyranids", "Orks", "T'au Empire",
    "Death Guard", "Adeptus Custodes", "Thousand Sons", "Leagues of Votann",
    "Chaos Space Marines", "World Eaters", "Emperor's Children", "Chaos Daemons",
    "Astra Militarum", "Adeptus Mechanicus", "Adepta Sororitas", "Grey Knights",
    "Drukhari", "Genestealer Cults", "Imperial Knights", "Chaos Knights",
]

# Warp Friends source strings that aggregate into a single SwegHammer faction.
SM_CHAPTERS: List[str] = [
    "Space Marines", "Black Templars", "Blood Angels",
    "Dark Angels", "Deathwatch", "Space Wolves",
]

# String normalisations: WF source string -> SwegHammer faction name.
NORMALISE: Dict[str, str] = {
    "Tau": "T'au Empire",
    "Sisters of Battle": "Adepta Sororitas",
    "Genestealer Cult": "Genestealer Cults",
    # Pass-through factions whose WF spelling already matches SwegHammer:
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
# All six Astartes chapters fold into "Adeptus Astartes".
for _chapter in SM_CHAPTERS:
    NORMALISE[_chapter] = "Adeptus Astartes"

# Explicit drops. Imperial Agents is not in SwegHammer's faction list and
# carries low sample counts (~30-40 games/wk) so dropping it does not skew
# the rollup, but we still log it for visibility.
DROP_STRINGS = {"Imperial Agents"}

# Total-games sanity threshold. A single weekly post should produce a primary
# table whose Games column sums to between 1000 and ~12000. If we see a sum
# above this cap we are looking at a rolling/cumulative table (e.g. the
# 2026-05-11 post, ~62000) and should NOT feed it into the rollup.
WEEKLY_GAMES_SUM_CAP = 12_000

# Z-score for 95% two-sided binomial confidence interval.
Z_95 = 1.96


# ---------------------------------------------------------------------------
# Fetch + parse.
# ---------------------------------------------------------------------------

HEADERS = {
    # WordPress doesn't strictly require it but a real UA keeps us out of
    # any anti-bot quirks if the theme adds them later.
    "User-Agent": "Mozilla/5.0 (SwegHammer scraper; contact via repo)",
    "Accept": "text/html,application/xhtml+xml",
}


def fetch_html(url: str, timeout: float = 30.0) -> str:
    """Fetch raw HTML for a URL. Raises ``RuntimeError`` on non-200 / errors."""
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} fetching {url}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"URL error fetching {url}: {exc.reason}") from exc


# Match a single <tr>...</tr> chunk (multiline-friendly).
_TR_RE = re.compile(r"<tr\b[^>]*>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
# Each <td>/<th> cell.
_CELL_RE = re.compile(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", re.IGNORECASE | re.DOTALL)
# Strip any HTML tag inside a cell.
_TAG_RE = re.compile(r"<[^>]+>")
# Whitespace collapse.
_WS_RE = re.compile(r"\s+")


def _clean_cell(cell_html: str) -> str:
    """Strip tags + collapse whitespace + unescape common entities.

    Also normalises curly quotes to straight ASCII so that downstream string
    matching against SwegHammer faction names (e.g. ``Emperor's Children``)
    survives the Warp Friends house style which uses U+2019.
    """
    text = _TAG_RE.sub(" ", cell_html)
    text = (text
            .replace("&nbsp;", " ")
            .replace("&amp;", "&")
            .replace("&#39;", "'")
            .replace("&#8217;", "'")
            .replace("&rsquo;", "'")
            .replace("&lsquo;", "'")
            .replace("&quot;", '"')
            .replace("’", "'")
            .replace("‘", "'")
            .replace("“", '"')
            .replace("”", '"'))
    return _WS_RE.sub(" ", text).strip()


def parse_tables(html: str) -> List[List[List[str]]]:
    """Split out every <table>..</table> as a list of rows-of-cells."""
    table_chunks = re.findall(r"<table\b[^>]*>(.*?)</table>",
                              html, flags=re.IGNORECASE | re.DOTALL)
    tables: List[List[List[str]]] = []
    for chunk in table_chunks:
        rows: List[List[str]] = []
        for tr_html in _TR_RE.findall(chunk):
            cells = [_clean_cell(c) for c in _CELL_RE.findall(tr_html)]
            if cells:
                rows.append(cells)
        if rows:
            tables.append(rows)
    return tables


_PCT_RE = re.compile(r"^(\d+(?:\.\d+)?)\s*%$")
_INT_RE = re.compile(r"^-?\d+$")


def _parse_pct(cell: str) -> Optional[float]:
    m = _PCT_RE.match(cell)
    return float(m.group(1)) if m else None


def _parse_int(cell: str) -> Optional[int]:
    cell = cell.replace(",", "")
    return int(cell) if _INT_RE.match(cell) else None


def extract_faction_rows(
    tables: List[List[List[str]]],
) -> Tuple[Optional[List[Tuple[str, float, int]]], str]:
    """Find the per-faction win-rate table in a parsed page and return
    ``(rows, note)``.

    ``rows`` is a list of ``(faction_string, win_pct, games)``. ``note`` is a
    short status string describing what we found ("ok", "rolling-table-skipped",
    etc.). On structural failure we return ``(None, reason)``.

    Heuristic: scan all tables, find one whose first row's first cell is
    "Faction" (the column header) and which contains a Win % and a Games
    column. Pick the cleanest faction-only rows (skip per-subfaction lines,
    which Warp Friends marks with a "*" suffix on the faction name).
    """
    candidate: Optional[List[Tuple[str, float, int]]] = None
    games_sum: int = 0
    for table in tables:
        if not table:
            continue
        header = [c.lower() for c in table[0]]
        if not header or "faction" not in header[0]:
            continue
        # Locate Win % column and Games column by header label.
        win_col: Optional[int] = None
        games_col: Optional[int] = None
        for i, h in enumerate(header):
            if h.startswith("win") and "%" in h:
                win_col = i
            elif h in {"games played", "games"} or h.startswith("games"):
                games_col = i
        if win_col is None or games_col is None:
            continue
        rows: List[Tuple[str, float, int]] = []
        for cells in table[1:]:
            if len(cells) <= max(win_col, games_col):
                continue
            faction = cells[0].strip()
            if not faction or faction.endswith("*"):
                # subfaction breakout row -- skip
                continue
            # Some breakouts put the chapter name in cell[1]; the faction
            # column itself empty. Already filtered by `if not faction`.
            win_pct = _parse_pct(cells[win_col])
            games = _parse_int(cells[games_col])
            if win_pct is None or games is None:
                continue
            rows.append((faction, win_pct, games))
        if not rows:
            continue
        table_games = sum(g for _, _, g in rows)
        if candidate is None or table_games < games_sum:
            # Prefer the smaller-games candidate (i.e., the single-week one)
            # when multiple match. Rolling tables would be > WEEKLY_GAMES_SUM_CAP.
            candidate = rows
            games_sum = table_games

    if candidate is None:
        return None, "no-faction-table-found"
    if games_sum > WEEKLY_GAMES_SUM_CAP:
        return None, (f"rolling-table-only (sum={games_sum} games > cap "
                      f"{WEEKLY_GAMES_SUM_CAP}); no single-week breakdown "
                      f"published in this post")
    return candidate, "ok"


# ---------------------------------------------------------------------------
# Rollup.
# ---------------------------------------------------------------------------

def rollup_week(
    raw_rows: List[Tuple[str, float, int]],
) -> Tuple[Dict[str, Tuple[int, int]], List[str]]:
    """Roll one week's raw WF rows into SwegHammer faction buckets.

    Returns ``(buckets, unmapped)`` where ``buckets`` maps SwegHammer faction
    -> ``(wins, games)`` for that week, and ``unmapped`` is the list of raw
    faction strings that did not map (excluding the explicit drop list).
    """
    buckets: Dict[str, Tuple[int, int]] = {}
    unmapped: List[str] = []
    for raw_name, win_pct, games in raw_rows:
        if raw_name in DROP_STRINGS:
            continue
        target = NORMALISE.get(raw_name)
        if target is None:
            unmapped.append(raw_name)
            continue
        # Reconstruct integer wins from the published WR + games count. The
        # published Win% is rounded to 0.1pt, so this is approximate but is
        # the best reconstruction available and is symmetric across factions.
        wins = int(round(win_pct * games / 100.0))
        prev_w, prev_g = buckets.get(target, (0, 0))
        buckets[target] = (prev_w + wins, prev_g + games)
    return buckets, unmapped


def compute_faction_stats(
    weekly: Dict[str, List[Optional[Tuple[int, int]]]],
) -> Dict[str, Dict[str, object]]:
    """Compute per-faction aggregate + noise stats.

    ``weekly[faction]`` is a list parallel to the included weeks. Each entry
    is either ``(wins, games)`` for that week or ``None`` if the faction had
    no data that week (the rollup will skip the slot rather than treating it
    as zero).
    """
    out: Dict[str, Dict[str, object]] = {}
    for fac in SWEG_FACTIONS:
        slots = weekly.get(fac, [])
        # Per-week WRs (skip weeks with no data; do not coerce missing to 0)
        per_week: List[float] = []
        total_wins = 0
        total_games = 0
        for entry in slots:
            if entry is None:
                continue
            w, g = entry
            if g <= 0:
                continue
            per_week.append(100.0 * w / g)
            total_wins += w
            total_games += g
        if total_games <= 0:
            # Genuinely no data is a hard fail; SwegHammer expects all 22.
            raise RuntimeError(
                f"No data across any included week for SwegHammer faction "
                f"{fac!r}. Refusing to silently fill in 50% -- check the "
                f"rollup map.")
        win_rate = 100.0 * total_wins / total_games
        # Population stdev (we treat the 5 (or N) weeks as the population of
        # observed samples, not a sample of a hypothetical infinite stream).
        if len(per_week) >= 2:
            w2w = statistics.pstdev(per_week)
        else:
            w2w = 0.0
        p = win_rate / 100.0
        binom_hw = 100.0 * Z_95 * math.sqrt(p * (1.0 - p) / total_games)
        noise = max(w2w, binom_hw)
        rolled_from = sorted([k for k, v in NORMALISE.items() if v == fac])
        out[fac] = {
            "win_rate": round(win_rate, 2),
            "total_games": total_games,
            "weekly_win_rates": [round(x, 2) for x in per_week],
            "week_to_week_stdev": round(w2w, 3),
            "binomial_ci_95_halfwidth": round(binom_hw, 3),
            "noise_floor": round(noise, 3),
            "rolled_from": rolled_from,
        }
    return out


# ---------------------------------------------------------------------------
# Top-level driver.
# ---------------------------------------------------------------------------

def main(out_path: Optional[Path] = None) -> Dict[str, object]:
    repo_root = Path(__file__).resolve().parent.parent
    if out_path is None:
        out_path = repo_root / "data" / "warpfriends_rolling.json"

    skipped_weeks: List[Dict[str, str]] = []
    included_weeks: List[str] = []
    unmapped_strings: Dict[str, List[str]] = {}
    weekly_buckets: Dict[str, List[Optional[Tuple[int, int]]]] = {
        fac: [] for fac in SWEG_FACTIONS
    }

    for week_iso, url in WEEK_POSTS:
        html = fetch_html(url)
        tables = parse_tables(html)
        rows, note = extract_faction_rows(tables)
        if rows is None:
            skipped_weeks.append({"week": week_iso, "url": url, "reason": note})
            # Append a None slot for every faction so positional rollup stays
            # honest about which week was missing.
            for fac in SWEG_FACTIONS:
                weekly_buckets[fac].append(None)
            continue
        buckets, unmapped = rollup_week(rows)
        included_weeks.append(week_iso)
        if unmapped:
            unmapped_strings[week_iso] = sorted(set(unmapped))
        for fac in SWEG_FACTIONS:
            weekly_buckets[fac].append(buckets.get(fac))  # may be None

    # Compress the per-faction slot lists to only the included weeks (drop
    # the slots that align with skipped weeks).
    skipped_set = {w["week"] for w in skipped_weeks}
    keep_indices = [i for i, (wk, _u) in enumerate(WEEK_POSTS)
                    if wk not in skipped_set]
    for fac in SWEG_FACTIONS:
        weekly_buckets[fac] = [weekly_buckets[fac][i] for i in keep_indices]

    factions = compute_faction_stats(weekly_buckets)

    total_games = sum(int(f["total_games"]) for f in factions.values())

    payload = {
        "metadata": {
            "scraped_at": date.today().isoformat(),
            "source": "warpfriends.wordpress.com",
            "primary_upstream": "Best Coast Pairings (hand-scraped by Warp Friends)",
            "weeks_requested": [w for w, _ in WEEK_POSTS],
            "weeks_included": included_weeks,
            "weeks_skipped": skipped_weeks,
            "rollup_method": ("game-weighted mean of weekly per-faction win "
                              "rates; SM chapters aggregated into Adeptus "
                              "Astartes; subfaction breakout rows (Faction*) "
                              "ignored"),
            "total_games_across_weeks": total_games,
            "unmapped_strings_surfaced": unmapped_strings,
            "dropped_strings": sorted(DROP_STRINGS),
            "weekly_games_sum_cap": WEEKLY_GAMES_SUM_CAP,
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
    print(f"Wrote rolling-mean win rates for {len(payload['factions'])} factions.")
    print(f"  Weeks included: {md['weeks_included']}")
    if md["weeks_skipped"]:
        print(f"  Weeks skipped: {md['weeks_skipped']}")
    if md["unmapped_strings_surfaced"]:
        print(f"  Unmapped strings: {md['unmapped_strings_surfaced']}")
    print(f"  Total games (aggregate across factions across weeks): "
          f"{md['total_games_across_weeks']:,}")
    sys.exit(0)
