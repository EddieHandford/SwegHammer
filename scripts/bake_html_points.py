"""Generate a self-contained HTML points-lookup page from data/sweg_points_v1.json.

Usage:
    python scripts/bake_html_points.py
    python scripts/bake_html_points.py --out docs/sweghammer_points.html

The page is a single-file artefact for handing to playtesters. Five sections,
all single-page-scroll: hero with the equation showcase, the top coefficients,
faction multipliers grid, the searchable unit table, and a methodology block.
"""

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
_DATA_FILE = _REPO_ROOT / "data" / "sweg_points_v1.json"
_DEFAULT_OUT = _REPO_ROOT / "docs" / "sweghammer_points.html"

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SwegHammer &mdash; Recalibrated v{version} | Points Reference</title>
<style>
  :root {{
    --bg: #0b0d12;
    --surface: #14171f;
    --surface-2: #1a1d27;
    --border: #2c2f3e;
    --text: #e6e6e6;
    --muted: #8a8f9b;
    --gold: #c9a84c;
    --gold-soft: rgba(201, 168, 76, 0.15);
    --blue: #9bd6ff;
    --green: #6cc97c;
    --green-soft: rgba(108, 201, 124, 0.18);
    --red: #d65f5f;
    --red-soft: rgba(214, 95, 95, 0.18);
    --font: 'Segoe UI', system-ui, sans-serif;
    --mono: 'Cascadia Code', 'Consolas', 'Menlo', monospace;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html {{ scroll-behavior: smooth; }}
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: var(--font);
    font-size: 14px;
    line-height: 1.55;
    min-height: 100vh;
  }}
  a {{ color: var(--blue); text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}

  /* ----- Sticky top nav ----- */
  .topnav {{
    position: sticky;
    top: 0;
    z-index: 100;
    background: rgba(11, 13, 18, 0.92);
    backdrop-filter: blur(10px);
    border-bottom: 1px solid var(--border);
    padding: 12px 24px;
    display: flex;
    align-items: center;
    gap: 24px;
    flex-wrap: wrap;
  }}
  .topnav-brand {{
    font-weight: 600;
    color: var(--gold);
    letter-spacing: 0.04em;
    font-size: 0.95rem;
  }}
  .topnav-links {{
    display: flex;
    gap: 20px;
    flex-wrap: wrap;
  }}
  .topnav-links a {{
    color: var(--muted);
    font-size: 0.85rem;
    text-decoration: none;
    transition: color 0.15s;
  }}
  .topnav-links a:hover {{ color: var(--gold); }}
  .topnav-version {{
    margin-left: auto;
    font-size: 0.7rem;
    color: var(--muted);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 3px 8px;
    font-variant-numeric: tabular-nums;
  }}

  /* ----- Hero ----- */
  .hero {{
    padding: 72px 24px 48px;
    text-align: center;
    background: radial-gradient(ellipse at top, rgba(201, 168, 76, 0.07) 0%, transparent 60%);
  }}
  .hero h1 {{
    font-size: 3.2rem;
    font-weight: 700;
    letter-spacing: 0.02em;
    color: var(--gold);
    margin-bottom: 6px;
  }}
  .hero-tagline {{
    font-size: 1.05rem;
    color: var(--muted);
    margin-bottom: 36px;
    letter-spacing: 0.02em;
  }}
  .stat-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 16px;
    max-width: 820px;
    margin: 0 auto 40px;
  }}
  .stat-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 18px 14px;
    transition: border-color 0.15s, transform 0.15s;
  }}
  .stat-card:hover {{
    border-color: var(--gold);
    transform: translateY(-2px);
  }}
  .stat-value {{
    font-size: 1.85rem;
    font-weight: 700;
    color: var(--gold);
    font-variant-numeric: tabular-nums;
    line-height: 1;
    margin-bottom: 4px;
  }}
  .stat-label {{
    font-size: 0.75rem;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }}
  .hero-blurb {{
    max-width: 680px;
    margin: 0 auto;
    color: var(--text);
    font-size: 0.98rem;
    line-height: 1.7;
  }}

  /* ----- Math-only callout (prominent v1 disclosure) ----- */
  .math-only-callout {{
    max-width: 680px;
    margin: 28px auto 0;
    padding: 16px 22px;
    background: linear-gradient(90deg, rgba(155, 214, 255, 0.08), rgba(155, 214, 255, 0.02));
    border: 1px solid rgba(155, 214, 255, 0.25);
    border-left: 3px solid var(--blue);
    border-radius: 6px;
    text-align: left;
    color: var(--text);
    font-size: 0.9rem;
    line-height: 1.6;
  }}
  .math-only-callout strong {{
    color: var(--blue);
    letter-spacing: 0.04em;
    text-transform: uppercase;
    font-size: 0.75rem;
    display: block;
    margin-bottom: 4px;
  }}

  /* ----- Section shell ----- */
  section {{
    padding: 64px 24px;
    border-top: 1px solid var(--border);
  }}
  section h2 {{
    font-size: 1.45rem;
    font-weight: 600;
    color: var(--gold);
    letter-spacing: 0.02em;
    margin-bottom: 12px;
    text-align: center;
  }}
  .section-sub {{
    text-align: center;
    color: var(--muted);
    font-size: 0.9rem;
    max-width: 640px;
    margin: 0 auto 32px;
    line-height: 1.65;
  }}

  /* ----- Equation showcase ----- */
  .equation-box {{
    max-width: 720px;
    margin: 0 auto;
    background: var(--surface);
    border: 1px solid var(--border);
    border-left: 3px solid var(--gold);
    border-radius: 6px;
    padding: 28px 32px;
    font-family: var(--mono);
    font-size: 1.02rem;
    line-height: 2;
  }}
  .equation-box .formula {{
    color: var(--text);
    text-align: center;
  }}
  .equation-box .formula .var {{ color: var(--gold); }}
  .equation-box .formula .op {{ color: var(--muted); }}
  .equation-caption {{
    max-width: 680px;
    margin: 28px auto 0;
    color: var(--muted);
    font-size: 0.88rem;
    text-align: center;
    line-height: 1.7;
  }}

  /* ----- Features bar chart ----- */
  .features-list {{
    max-width: 720px;
    margin: 0 auto;
  }}
  .feature-row {{
    display: grid;
    grid-template-columns: 220px 1fr 70px;
    align-items: center;
    gap: 14px;
    padding: 8px 0;
    border-bottom: 1px solid var(--border);
    font-size: 0.85rem;
  }}
  .feature-row:last-child {{ border-bottom: none; }}
  .feature-row .feature-name {{
    color: var(--text);
    font-family: var(--mono);
    font-size: 0.8rem;
  }}
  .feature-bar-bg {{
    position: relative;
    height: 18px;
    background: var(--surface);
    border-radius: 3px;
    overflow: hidden;
  }}
  .feature-bar {{
    position: absolute;
    top: 0; bottom: 0;
    border-radius: 3px;
    transition: width 0.4s ease-out;
  }}
  .feature-bar.pos {{
    left: 50%;
    background: linear-gradient(90deg, var(--gold-soft), var(--gold));
  }}
  .feature-bar.neg {{
    right: 50%;
    background: linear-gradient(270deg, var(--red-soft), var(--red));
  }}
  .feature-bar-zero {{
    position: absolute;
    left: 50%;
    top: 0; bottom: 0;
    width: 1px;
    background: var(--muted);
    opacity: 0.4;
  }}
  .feature-coef {{
    color: var(--text);
    font-family: var(--mono);
    font-variant-numeric: tabular-nums;
    font-size: 0.82rem;
    text-align: right;
  }}
  .feature-coef.pos {{ color: var(--gold); }}
  .feature-coef.neg {{ color: var(--red); }}

  /* ----- Scatter plot (GW vs SwegHammer) ----- */
  .scatter-wrap {{
    max-width: 720px;
    margin: 0 auto;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 14px;
  }}
  .scatter-wrap svg {{
    width: 100%;
    height: auto;
    display: block;
  }}
  .scatter-wrap svg circle {{
    cursor: crosshair;
    transition: r 0.1s;
  }}
  .scatter-wrap svg circle:hover {{
    r: 4.5;
    stroke: var(--text);
    stroke-width: 1;
  }}
  .scatter-legend {{
    max-width: 720px;
    margin: 12px auto 0;
    display: flex;
    gap: 24px;
    justify-content: center;
    flex-wrap: wrap;
    font-size: 0.78rem;
    color: var(--muted);
  }}
  .scatter-legend .legend-dot {{
    display: inline-block;
    width: 9px;
    height: 9px;
    border-radius: 50%;
    margin-right: 6px;
    vertical-align: middle;
  }}
  .scatter-legend .legend-dot.pos {{ background: var(--gold); }}
  .scatter-legend .legend-dot.neg {{ background: var(--red); }}
  .scatter-legend .legend-dot.neu {{ background: var(--muted); }}

  /* ----- Faction multipliers grid (kept around for fallbacks; unused in v1 layout) ----- */
  .faction-grid {{
    max-width: 900px;
    margin: 0 auto;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 10px;
  }}
  .faction-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 12px 14px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    transition: transform 0.15s, border-color 0.15s;
  }}
  .faction-card:hover {{ transform: translateY(-1px); }}
  .faction-card.over {{ border-left: 3px solid var(--green); }}
  .faction-card.under {{ border-left: 3px solid var(--red); }}
  .faction-card.neutral {{ border-left: 3px solid var(--muted); }}
  .faction-card-name {{
    font-size: 0.82rem;
    color: var(--text);
  }}
  .faction-card-mult {{
    font-family: var(--mono);
    font-size: 0.85rem;
    font-variant-numeric: tabular-nums;
    font-weight: 600;
  }}
  .faction-card.over .faction-card-mult {{ color: var(--green); }}
  .faction-card.under .faction-card-mult {{ color: var(--red); }}
  .faction-card.neutral .faction-card-mult {{ color: var(--muted); }}

  /* ----- Browse: controls + table (preserved from previous version) ----- */
  .controls {{
    display: flex;
    gap: 10px;
    padding: 14px 0;
    flex-wrap: wrap;
    align-items: center;
    max-width: 1100px;
    margin: 0 auto;
  }}
  .controls input[type=text] {{
    flex: 1;
    min-width: 200px;
    max-width: 420px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    color: var(--text);
    padding: 8px 12px;
    font-size: 13px;
    outline: none;
    transition: border-color 0.15s;
  }}
  .controls input[type=text]:focus {{ border-color: var(--gold); }}
  .controls select {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    color: var(--text);
    padding: 8px 12px;
    font-size: 13px;
    outline: none;
    cursor: pointer;
    max-width: 220px;
  }}
  .controls .sort-label {{
    color: var(--muted);
    font-size: 12px;
    white-space: nowrap;
  }}
  .controls select.sort-sel {{ max-width: 200px; }}
  .browse-statbar {{
    max-width: 1100px;
    margin: 0 auto;
    display: flex;
    gap: 24px;
    padding: 8px 0;
    font-size: 12px;
    color: var(--muted);
    flex-wrap: wrap;
  }}
  .browse-statbar span b {{ color: var(--text); }}
  .table-wrap {{
    overflow-x: auto;
    max-width: 1100px;
    margin: 0 auto;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    margin-top: 8px;
  }}
  thead th {{
    text-align: left;
    padding: 10px 10px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.07em;
    text-transform: uppercase;
    color: var(--muted);
    border-bottom: 1px solid var(--border);
    white-space: nowrap;
    cursor: pointer;
    user-select: none;
  }}
  thead th:hover {{ color: var(--text); }}
  thead th.sorted {{ color: var(--gold); }}
  tbody tr {{
    border-bottom: 1px solid var(--border);
    transition: background 0.1s;
  }}
  tbody tr:hover {{ background: var(--surface); }}
  td {{
    padding: 8px 10px;
    vertical-align: middle;
    white-space: nowrap;
  }}
  td.name {{ white-space: normal; min-width: 180px; }}
  td.faction {{ color: var(--blue); font-size: 12px; }}
  td.pts {{ font-variant-numeric: tabular-nums; text-align: right; }}
  td.gw {{ color: var(--muted); }}
  td.delta {{ font-variant-numeric: tabular-nums; text-align: right; font-weight: 500; }}
  td.delta.pos {{ color: var(--green); }}
  td.delta.neg {{ color: var(--red); }}
  td.delta.neu {{ color: var(--muted); }}
  .no-results {{
    text-align: center;
    padding: 48px 0;
    color: var(--muted);
    font-size: 13px;
  }}

  /* ----- Methodology ----- */
  .methodology {{
    max-width: 720px;
    margin: 0 auto;
    color: var(--text);
    line-height: 1.7;
  }}
  .methodology h3 {{
    font-size: 1rem;
    color: var(--gold);
    margin: 28px 0 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }}
  .methodology h3:first-child {{ margin-top: 0; }}
  .methodology p {{ font-size: 0.92rem; margin-bottom: 10px; }}
  .methodology ol, .methodology ul {{
    padding-left: 22px;
    margin-bottom: 14px;
    font-size: 0.92rem;
  }}
  .methodology li {{ margin-bottom: 8px; }}
  .methodology strong {{ color: var(--gold); }}
  .methodology code {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 3px;
    padding: 1px 6px;
    font-family: var(--mono);
    font-size: 0.85rem;
  }}

  footer {{
    padding: 24px;
    text-align: center;
    border-top: 1px solid var(--border);
    color: var(--muted);
    font-size: 11px;
    font-family: var(--mono);
  }}

  @media (max-width: 720px) {{
    .hero h1 {{ font-size: 2.2rem; }}
    .hero {{ padding: 48px 16px 32px; }}
    section {{ padding: 48px 16px; }}
    .equation-box {{ padding: 18px; font-size: 0.88rem; }}
    .feature-row {{ grid-template-columns: 140px 1fr 60px; gap: 8px; }}
    .feature-row .feature-name {{ font-size: 0.72rem; }}
    .topnav-links {{ gap: 12px; }}
    .topnav-links a {{ font-size: 0.78rem; }}
  }}
</style>
</head>
<body>

<nav class="topnav">
  <span class="topnav-brand">&#9876;&#65039; SwegHammer</span>
  <div class="topnav-links">
    <a href="#equation">The Equation</a>
    <a href="#features">What Drives Cost</a>
    <a href="#scatter">vs Games Workshop</a>
    <a href="#methodology">How It Works</a>
    <a href="#browse">Browse Units</a>
  </div>
  <span class="topnav-version">v{version} &middot; math-only</span>
</nav>

<header class="hero">
  <h1>SwegHammer</h1>
  <p class="hero-tagline">Math-fitted points for Warhammer 40,000</p>

  <div class="math-only-callout">
    <strong>v1 release &middot; alpha playtest</strong>
    Every unit priced by one regression equation fitted to Games Workshop's printed prices, then nudged per faction by real tournament results. This is an early alpha &mdash; expect rough edges on named characters and rare profiles. Tell us what feels wrong.
  </div>

  <div class="stat-grid">
    <div class="stat-card">
      <div class="stat-value">{unit_count}</div>
      <div class="stat-label">Units priced</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">{faction_count}</div>
      <div class="stat-label">Factions</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">{r_squared_pct}%</div>
      <div class="stat-label">Variance vs GW (R&#178;)</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">{feature_count}</div>
      <div class="stat-label">Stat features</div>
    </div>
  </div>

  <p class="hero-blurb">
    Every unit in the game priced by the same regression equation &mdash; over stat lines, weapon profiles, special keywords, leader auras, even Necron reanimation &mdash; then nudged up or down by its faction's real tournament win rate. No hand-pricing. No favouritism. The same maths for every model in your army.
  </p>
</header>

<section id="equation">
  <h2>The Equation</h2>
  <p class="section-sub">
    The whole pipeline boils down to two lines. The regression learns the &beta; coefficients from GW's printed prices; the faction multiplier comes from real tournament data.
  </p>
  <div class="equation-box">
    <div class="formula">
      <span class="op">log</span>(<span class="var">price&#8202;<sub>model</sub></span>) = <span class="var">&beta;<sub>0</sub></span> + &sum;<sub>i</sub> <span class="var">&beta;<sub>i</sub></span> &middot; <span class="op">transform<sub>i</sub></span>(<span class="var">feature<sub>i</sub></span>)
    </div>
    <div class="formula" style="margin-top: 12px;">
      <span class="var">price&#8202;<sub>final</sub></span> = <span class="op">round<sub>5</sub></span>(<span class="op">exp</span>(<span class="var">log&#8202;price</span>) &times; <span class="var">faction&#8202;mult</span>)
    </div>
  </div>
  <p class="equation-caption">
    Fit on {feature_count} features &mdash; wounds, toughness, save, AP, attacks, damage, hit probability, weapon keywords (precision, lance, assault, indirect fire, anti-X), leader aura buffs, secondary weapon profile, and a handful of cross-stat interaction terms. Hits <strong>R&#178; = {r_squared}</strong> against GW prices with a mean absolute error of <strong>{mae_pts_str} points per model</strong>.
  </p>
</section>

<section id="features">
  <h2>What drives a unit's cost?</h2>
  <p class="section-sub">
    Four big buckets the equation cares about. Bars show how much each bucket pushes the typical unit's price up on average. Durability is the heaviest hitter; offensive output and mobility round things out; special abilities (keywords like Precision and Lance, plus leader auras) are a smaller-but-real fourth pillar.
  </p>
  <div class="features-list">
    {feature_rows}
  </div>
</section>

<section id="scatter">
  <h2>SwegHammer vs Games Workshop</h2>
  <p class="section-sub">
    Every priced unit, one dot. The diagonal is &ldquo;SwegHammer agrees with Games Workshop&rdquo;. Dots above the line cost <strong>more</strong> in SwegHammer than in GW; dots below cost <strong>less</strong>. Hover any dot to see the unit and the swing. Log scale on both axes so small units and Titans share the chart.
  </p>
  <div class="scatter-wrap">
    {scatter_svg}
  </div>
  <div class="scatter-legend">
    <span><span class="legend-dot pos"></span> SwegHammer marks up (vs GW)</span>
    <span><span class="legend-dot neu"></span> Within &plusmn;5%</span>
    <span><span class="legend-dot neg"></span> SwegHammer marks down</span>
  </div>
</section>

<section id="methodology">
  <h2>How it works</h2>
  <div class="methodology">
    <h3>One equation, fitted to real prices</h3>
    <p>
      Every unit's price comes from a single regression equation. We read each unit's stat line (wounds, toughness, save, weapon attacks, damage, special keywords, leader auras &mdash; {feature_count} features in total) and the equation predicts what the unit should cost. The coefficients aren't picked by hand &mdash; they're learned by asking the equation to match Games Workshop's own printed prices as closely as possible. Result: R&sup2; = {r_squared}, mean absolute error {mae_pts_str} points per model.
    </p>

    <h3>Then nudged by what's actually winning</h3>
    <p>
      Games Workshop's prices are a starting point but they're not always right &mdash; the meta moves and some factions over-perform while others fall behind. After the equation predicts a price, we multiply by a per-faction correction based on real tournament win rates. A faction over-performing at its current GW prices gets marked up; one under-performing gets marked down.
    </p>

    <h3>Data sources</h3>
    <ul>
      <li><strong>Stat lines:</strong> BSData WH40k 10th edition v10.6.0 (community-maintained datasheet repository).</li>
      <li><strong>Tournament meta:</strong> Warp Friends rolling aggregate, May 2026 (~10,000 games).</li>
      <li><strong>Per-unit overrides:</strong> hand-tuned for cases where the underlying data is ambiguous.</li>
    </ul>

    <h3>What it doesn't do</h3>
    <ul>
      <li>Doesn't account for unit-vs-unit matchup rock-paper-scissors. The equation prices each unit on average against all opponents.</li>
      <li>Doesn't bake in detachment-specific synergies. Run a unit inside a detachment that loves it and the SwegHammer price might still feel low.</li>
      <li>Doesn't capture every named-character ability. Bespoke once-per-battle abilities, complex psychic powers, and stratagem-targeted effects mostly aren't visible to the equation.</li>
    </ul>

    <h3>Limitations &amp; caveats</h3>
    <p>
      SwegHammer is research-grade balance work, not an official Games Workshop product. This is an early alpha &mdash; some character pricing will be off, tell us when you find one. Super-heavy and Apocalypse units (Titans, Knights, strongpoints) are priced by the same equation as everything else; predictions for those rare profiles carry more uncertainty than mid-tier infantry but we want playtesters to be able to field them, so we don't fall back to the printed cost.
    </p>

    <h3>Provenance</h3>
    <p>
      Built {built_at}. Sources: <code>github.com/EddieHandford/SwegHammer</code>.
    </p>
  </div>
</section>

<section id="browse">
  <h2>Browse units</h2>
  <p class="section-sub">
    All {unit_count} priced units. &Delta;% is the change from GW's printed price &mdash; positive means SwegHammer thinks the unit is undercosted by GW.
  </p>
  <div class="controls">
    <input type="text" id="search" placeholder="Search unit name&#8230;" oninput="applyFilters()">
    <select id="faction-sel" onchange="applyFilters()">
      <option value="">All factions</option>
      {faction_options}
    </select>
    <span class="sort-label">Sort:</span>
    <select class="sort-sel" id="sort-sel" onchange="applyFilters()">
      <option value="faction_name">Faction &rarr; Name</option>
      <option value="name">Unit name</option>
      <option value="sweg_asc">Sweg pts (low&#8594;high)</option>
      <option value="sweg_desc">Sweg pts (high&#8594;low)</option>
      <option value="delta_desc">Biggest increase first</option>
      <option value="delta_asc">Biggest decrease first</option>
    </select>
  </div>
  <div class="browse-statbar">
    <span>Showing <b id="shown-count">{unit_count}</b> of <b>{unit_count}</b> units</span>
    <span>Built <b>{built_at}</b></span>
  </div>
  <div class="table-wrap">
    <table id="main-table">
      <thead>
        <tr>
          <th onclick="sortBy('faction')">Faction</th>
          <th onclick="sortBy('name')">Unit</th>
          <th onclick="sortBy('gw')" title="Games Workshop printed cost per model">GW pts</th>
          <th onclick="sortBy('sweg')" title="SwegHammer equation price per model">Sweg pts</th>
          <th onclick="sortBy('delta')" title="Percentage change from GW price">&Delta;%</th>
        </tr>
      </thead>
      <tbody id="tbody"></tbody>
    </table>
    <div class="no-results" id="no-results" style="display:none">No units match your search.</div>
  </div>
</section>

<footer>sweghammer_points.html &mdash; generated {generated_at}</footer>

<script>
const UNITS = {units_json};

let _sortKey = 'faction_name';
let _sortDir = 1;

function sortBy(key) {{
  if (_sortKey === key) {{ _sortDir *= -1; }} else {{ _sortKey = key; _sortDir = 1; }}
  applyFilters();
}}

function applyFilters() {{
  const q = document.getElementById('search').value.toLowerCase().trim();
  const fac = document.getElementById('faction-sel').value;
  const sortSel = document.getElementById('sort-sel').value;

  let rows = UNITS.filter(u => {{
    if (fac && u.faction !== fac) return false;
    if (q && !u.name.toLowerCase().includes(q) && !u.faction.toLowerCase().includes(q)) return false;
    return true;
  }});

  const sortKey = sortSel || _sortKey;
  rows.sort((a, b) => {{
    if (sortKey === 'faction_name') {{
      const fc = a.faction.localeCompare(b.faction);
      return fc !== 0 ? fc : a.name.localeCompare(b.name);
    }}
    if (sortKey === 'name') return a.name.localeCompare(b.name);
    if (sortKey === 'sweg_asc' || sortKey === 'sweg') return a.sweg - b.sweg;
    if (sortKey === 'sweg_desc') return b.sweg - a.sweg;
    if (sortKey === 'gw') return a.gw - b.gw;
    if (sortKey === 'delta' || sortKey === 'delta_desc') return b.delta - a.delta;
    if (sortKey === 'delta_asc') return a.delta - b.delta;
    if (sortKey === 'faction') return a.faction.localeCompare(b.faction);
    return 0;
  }});

  const tbody = document.getElementById('tbody');
  const noRes = document.getElementById('no-results');

  if (rows.length === 0) {{
    tbody.innerHTML = '';
    noRes.style.display = '';
  }} else {{
    noRes.style.display = 'none';
    tbody.innerHTML = rows.map(u => {{
      const d = u.delta;
      const dCls = d > 2 ? 'pos' : d < -2 ? 'neg' : 'neu';
      const dStr = d > 0 ? '+' + d.toFixed(1) + '%' : d.toFixed(1) + '%';
      const gwStr = u.gw !== null ? u.gw : '&mdash;';
      return `<tr>
        <td class="faction">${{u.faction}}</td>
        <td class="name">${{u.name}}</td>
        <td class="pts gw">${{gwStr}}</td>
        <td class="pts">${{u.sweg}}</td>
        <td class="delta ${{dCls}}">${{dStr}}</td>
      </tr>`;
    }}).join('');
  }}

  document.getElementById('shown-count').textContent = rows.length;
}}

applyFilters();
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Helpers — turn raw sweg_points_v1.json into the HTML fragments we inject.
# ---------------------------------------------------------------------------

# Map raw feature names (as fitted in code/equation_data_fit.py) to short,
# human-friendly labels for display in the "What drives a unit's cost?" panel.
# Anything not in the map falls back to a title-cased prettify of the key.
_FRIENDLY_NAMES = {
    "wounds_per_model": "Wounds per model",
    "wounds_per_model_sq": "Wounds per model (squared)",
    "toughness": "Toughness",
    "toughness_sq": "Toughness (squared)",
    "toughness_cubed": "Toughness (cubed)",
    "toughness_x_wounds": "Toughness × Wounds",
    "total_wounds": "Total wounds in squad",
    "save_quality": "Armour save quality",
    "invuln_quality": "Invulnerable save quality",
    "fnp_quality": "Feel No Pain quality",
    "save_quality_x_wounds": "Armour × Wounds",
    "effective_wounds": "Effective wounds",
    "ranged_attacks": "Ranged attacks",
    "ranged_strength": "Ranged strength",
    "ranged_ap_abs": "Ranged AP",
    "ranged_ap_abs_sq": "Ranged AP (squared)",
    "ranged_damage_per_shot": "Ranged damage / shot",
    "ranged_damage_per_shot_sq": "Ranged damage / shot (squared)",
    "ranged_range": "Weapon range (inches)",
    "ranged_hit_prob": "Ballistic skill",
    "log_ranged_damage_per_shot": "Ranged damage (log)",
    "log_ranged_attacks": "Ranged attacks (log)",
    "log_melee_damage_per_shot": "Melee damage (log)",
    "log_melee_attacks": "Melee attacks (log)",
    "ranged_attacks_sqrt": "Ranged attacks (√)",
    "melee_attacks_sqrt": "Melee attacks (√)",
    "ranged_attacks_x_strength": "Ranged attacks × Strength",
    "melee_attacks_x_strength": "Melee attacks × Strength",
    "ranged_dmg_x_attacks": "Ranged attacks × damage",
    "melee_dmg_x_attacks": "Melee attacks × damage",
    "total_ranged_attacks": "Squad-wide ranged attacks",
    "total_melee_attacks": "Squad-wide melee attacks",
    "melee_attacks": "Melee attacks",
    "melee_strength": "Melee strength",
    "melee_ap_abs": "Melee AP",
    "melee_ap_abs_sq": "Melee AP (squared)",
    "melee_damage_per_shot": "Melee damage / shot",
    "melee_damage_per_shot_sq": "Melee damage / shot (squared)",
    "melee_hit_prob": "Weapon skill",
    "move": "Movement (inches)",
    "oc": "Objective Control",
    "move_x_oc": "Move × OC (mobile scoring)",
    "min_models": "Squad size (min models)",
    "lethal_hits": "Lethal Hits keyword",
    "sustained_hits": "Sustained Hits N",
    "melee_sustained_hits": "Melee Sustained Hits N",
    "twin_linked": "Twin-linked keyword",
    "devastating_wounds": "Devastating Wounds keyword",
    "blast": "Blast keyword",
    "torrent": "Torrent (auto-hits)",
    "melta": "Melta N",
    "rapid_fire": "Rapid Fire N",
    "ignores_cover": "Ignores Cover",
    "precision": "Precision (snipe characters)",
    "lance": "Lance (charge bonus)",
    "heavy": "Heavy (stationary +1)",
    "assault": "Assault (advance & shoot)",
    "hazardous": "Hazardous (self-harm)",
    "pistol": "Pistol (engagement shooting)",
    "indirect_fire": "Indirect Fire (no LoS)",
    "one_shot": "One Shot weapon",
    "fights_first": "Fights First",
    "firing_deck": "Firing Deck N",
    "n_anti_keywords": "Anti-X keyword count",
    "best_anti_threshold_quality": "Best Anti-X threshold",
    "deadly_demise": "Deadly Demise on death",
    "leadership_quality": "Leadership quality",
    "reanimates_with_army": "Reanimation Protocols (Necrons)",
    "deep_strike": "Deep Strike",
    "scout_distance": "Scout N inches",
    "infiltrator": "Infiltrators",
    "lone_operative": "Lone Operative",
    "stealth": "Stealth (-1 to hit)",
    "secondary_attacks": "Secondary weapon attacks",
    "secondary_strength": "Secondary weapon strength",
    "secondary_ap_abs": "Secondary weapon AP",
    "secondary_damage_per_shot": "Secondary weapon damage",
    "secondary_hit_probability": "Secondary weapon BS/WS",
    "secondary_pistol": "Secondary Pistol",
    "expected_ranged_dmg_vs_meq": "Expected damage vs Marines (ranged)",
    "expected_melee_dmg_vs_meq": "Expected damage vs Marines (melee)",
    "precision_x_ranged_attacks": "Precision × Ranged attacks",
    "pistol_x_ranged_attacks": "Pistol × Ranged attacks",
    "assault_x_move": "Assault × Move",
    "lance_x_melee_attacks": "Lance × Melee attacks",
    "heavy_x_ranged_attacks": "Heavy × Ranged attacks",
    "fights_first_x_melee_attacks": "Fights First × Melee attacks",
    "is_monster_x_wounds": "Monster × Wounds",
    "is_vehicle_x_wounds": "Vehicle × Wounds",
    "is_character_x_wounds": "Character × Wounds",
    "is_monster": "Monster keyword",
    "is_vehicle": "Vehicle keyword",
    "is_character": "Character keyword",
    "is_fly": "Fly keyword",
    "has_aura": "Has any leader aura",
    "aura_reroll_hit_ones": "Aura: re-roll hit 1s",
    "aura_reroll_wound_ones": "Aura: re-roll wound 1s",
    "aura_plus_one_to_hit": "Aura: +1 to hit",
    "aura_plus_one_to_wound": "Aura: +1 to wound",
    "aura_plus_one_attack": "Aura: +N attacks",
    "aura_plus_one_strength_ranged": "Aura: +1 Strength (ranged)",
    "aura_plus_one_toughness": "Aura: +1 Toughness",
    "aura_plus_one_ap_melee": "Aura: improved melee AP",
    "aura_extra_invuln_quality": "Aura: invulnerable save",
    "aura_fnp_quality": "Aura: Feel No Pain",
    "aura_heal_per_round": "Aura: heal per round",
    "aura_revive_per_round": "Aura: revive per round",
    "aura_cp_discount_per_round": "Aura: +CP per round (warlord)",
    "aura_cp_refund_per_battle": "Aura: CP refund (warlord)",
    "aura_first_strat_free": "Aura: first stratagem free (warlord)",
}


def _friendly_name(raw: str) -> str:
    if raw in _FRIENDLY_NAMES:
        return _FRIENDLY_NAMES[raw]
    return raw.replace("_", " ").title()


def _render_family_rollups(family_rollups) -> str:
    """Build the HTML bar-chart rows for per-family contributions to log(price).

    Each row is one feature family (Durability, Ranged offense, …). The bar
    length scales with the family's average absolute contribution per unit;
    the colour and numeric label show the average SIGNED contribution. This
    sidesteps the multicollinearity that makes individual coefficients
    visually confusing — sums across a whole family are stable and
    interpretable even when wounds_per_model and toughness_x_wounds
    individually carry opposing signs.
    """
    if not family_rollups:
        return '<div class="no-results">No family rollup data available.</div>'

    items = [
        (family, float(stats.get("signed_mean", 0)), float(stats.get("abs_mean", 0)))
        for family, stats in family_rollups.items()
    ]
    items.sort(key=lambda x: -x[2])
    max_abs = max((abs_mean for _, _, abs_mean in items), default=1.0) or 1.0

    rows_html = []
    for family, signed_mean, abs_mean in items:
        pct = (abs_mean / max_abs) * 50.0
        bar_cls = "pos" if signed_mean >= 0 else "neg"
        coef_cls = "pos" if signed_mean >= 0 else "neg"
        signed_str = f"{signed_mean:+.3f}"
        rows_html.append(
            f'<div class="feature-row">'
            f'<div class="feature-name">{family}</div>'
            f'<div class="feature-bar-bg">'
            f'<div class="feature-bar-zero"></div>'
            f'<div class="feature-bar {bar_cls}" style="width: {pct:.1f}%;"></div>'
            f'</div>'
            f'<div class="feature-coef {coef_cls}">{signed_str}</div>'
            f'</div>'
        )
    return "\n    ".join(rows_html)


def _render_scatter_svg(units, width: int = 720, height: int = 480) -> str:
    """Inline-SVG scatter plot of GW vs SwegHammer per-model price.

    Log-log axes so a 12-pt cultist and a 3,500-pt Warlord Titan share the
    same chart honestly. The y=x diagonal is the &quot;SwegHammer agrees with
    GW&quot; reference; dots above the line are marked up vs GW, dots below
    are marked down. Each dot carries an SVG `<title>` so hovering shows the
    unit name and the swing &mdash; no JS required.
    """
    # Filter to units with a positive GW baseline and a positive Sweg price.
    pts = [
        (float(u["gw"]), float(u["sweg"]), u["name"], u["faction"])
        for u in units
        if u.get("gw") and u.get("gw", 0) > 0 and u.get("sweg") and u.get("sweg", 0) > 0
    ]
    if not pts:
        return '<div class="no-results">No price data to plot.</div>'

    # Log10 transform both axes. Use a shared range so the diagonal is at 45°.
    log_xs = [math.log10(gw) for gw, _, _, _ in pts]
    log_ys = [math.log10(sw) for _, sw, _, _ in pts]
    lo = min(min(log_xs), min(log_ys))
    hi = max(max(log_xs), max(log_ys))
    # Round to nice powers of 10 padded by half a decade on each side.
    lo = math.floor(lo * 2) / 2 - 0.1
    hi = math.ceil(hi * 2) / 2 + 0.1

    padding_l = 52
    padding_r = 14
    padding_t = 14
    padding_b = 36
    plot_w = width - padding_l - padding_r
    plot_h = height - padding_t - padding_b

    def sx(log_val: float) -> float:
        return padding_l + (log_val - lo) / (hi - lo) * plot_w

    def sy(log_val: float) -> float:
        return height - padding_b - (log_val - lo) / (hi - lo) * plot_h

    parts = [
        f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
        f'role="img" aria-label="SwegHammer vs Games Workshop price scatter plot">'
    ]

    # Plot background.
    parts.append(
        f'<rect x="{padding_l}" y="{padding_t}" '
        f'width="{plot_w}" height="{plot_h}" fill="rgba(255,255,255,0.02)" stroke="none"/>'
    )

    # y = x reference diagonal.
    parts.append(
        f'<line x1="{sx(lo):.1f}" y1="{sy(lo):.1f}" x2="{sx(hi):.1f}" y2="{sy(hi):.1f}" '
        f'stroke="rgba(201,168,76,0.4)" stroke-width="1" stroke-dasharray="4,4"/>'
    )

    # Ticks at nice powers of 10 + half-decades.
    tick_values = [10, 20, 50, 100, 200, 500, 1000, 2000, 5000]
    for tv in tick_values:
        log_tv = math.log10(tv)
        if lo <= log_tv <= hi:
            x = sx(log_tv)
            y_axis = sy(lo)
            parts.append(
                f'<line x1="{x:.1f}" y1="{y_axis:.1f}" x2="{x:.1f}" y2="{y_axis + 4:.1f}" '
                f'stroke="#666"/>'
            )
            parts.append(
                f'<text x="{x:.1f}" y="{y_axis + 18:.1f}" text-anchor="middle" '
                f'fill="#8a8f9b" font-size="10" font-family="Cascadia Code, monospace">{tv}</text>'
            )
            yt = sy(log_tv)
            x_axis = sx(lo)
            parts.append(
                f'<line x1="{x_axis:.1f}" y1="{yt:.1f}" x2="{x_axis - 4:.1f}" y2="{yt:.1f}" '
                f'stroke="#666"/>'
            )
            parts.append(
                f'<text x="{x_axis - 7:.1f}" y="{yt + 3.5:.1f}" text-anchor="end" '
                f'fill="#8a8f9b" font-size="10" font-family="Cascadia Code, monospace">{tv}</text>'
            )

    # Axis labels.
    parts.append(
        f'<text x="{padding_l + plot_w / 2:.1f}" y="{height - 6:.1f}" text-anchor="middle" '
        f'fill="#8a8f9b" font-size="11">Games Workshop pts / model (log scale)</text>'
    )
    parts.append(
        f'<text x="14" y="{padding_t + plot_h / 2:.1f}" text-anchor="middle" '
        f'fill="#8a8f9b" font-size="11" '
        f'transform="rotate(-90, 14, {padding_t + plot_h / 2:.1f})">SwegHammer pts / model (log scale)</text>'
    )

    # Sort points so high-delta dots draw on top of in-range ones.
    def delta_pct(gw: float, sw: float) -> float:
        return (sw - gw) / gw * 100.0

    pts_sorted = sorted(pts, key=lambda p: abs(delta_pct(p[0], p[1])))
    for gw, sw, name, faction in pts_sorted:
        x = sx(math.log10(gw))
        y = sy(math.log10(sw))
        d_pct = delta_pct(gw, sw)
        if abs(d_pct) < 5:
            fill = "rgba(138, 143, 155, 0.45)"
        elif d_pct > 0:
            fill = "rgba(201, 168, 76, 0.55)"
        else:
            fill = "rgba(214, 95, 95, 0.55)"
        # Escape any quotes/&/<> in the unit name for the SVG title.
        safe_name = name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
        safe_faction = faction.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
        sign = "+" if d_pct >= 0 else ""
        parts.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.6" fill="{fill}">'
            f'<title>{safe_name} ({safe_faction}): GW {gw:g} &#8594; Sweg {sw:g} ({sign}{d_pct:.1f}%)</title>'
            f'</circle>'
        )

    parts.append('</svg>')
    return "\n".join(parts)


def _render_faction_cards(faction_multipliers) -> str:
    """Build the HTML grid of per-faction multiplier cards.

    Ordered by multiplier descending so the biggest over-performers sit first,
    matching how a playtester reads "who got marked up the most".
    """
    if not faction_multipliers:
        return '<div class="no-results">No faction multipliers available.</div>'

    items = sorted(faction_multipliers.items(), key=lambda x: -x[1])
    cards_html = []
    for faction, mult in items:
        if mult > 1.02:
            cls = "over"
        elif mult < 0.98:
            cls = "under"
        else:
            cls = "neutral"
        cards_html.append(
            f'<div class="faction-card {cls}">'
            f'<span class="faction-card-name">{faction}</span>'
            f'<span class="faction-card-mult">{mult:.2f}&times;</span>'
            f'</div>'
        )
    return "\n    ".join(cards_html)


def _format_built_at(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return iso_str[:10]


def bake(data_path: Path, out_path: Path) -> None:
    with open(data_path) as f:
        data = json.load(f)

    prices = data["prices"]
    version = data.get("version", "1.0.0")
    built_at = _format_built_at(data.get("built_at", ""))
    fit = data.get("fit_metrics", {})
    r_squared_val = float(fit.get("r_squared", 0))
    r_squared = f"{r_squared_val:.4f}"
    r_squared_pct = f"{r_squared_val * 100:.1f}"
    mae_log = f"{fit.get('mae_log', 0):.4f}"
    mae_price = float(fit.get("mae_price", 0))
    mae_pts_str = f"{mae_price:.1f}"
    feature_count = data.get("feature_count", "?")
    family_rollups = data.get("family_contributions_avg", {})
    faction_multipliers_active = data.get("faction_multipliers_active", {})

    # Collect units as a flat list for embedding.
    units = []
    factions_seen: set[str] = set()
    for _key, u in prices.items():
        gw = u.get("gw_pts_per_model")
        sweg = u.get("sweg_pts_per_model")
        delta = u.get("delta_pct", 0.0)
        faction = u.get("faction", "Unknown")
        name = u.get("name", _key)
        factions_seen.add(faction)
        units.append({
            "name": name,
            "faction": faction,
            "gw": round(gw, 1) if gw is not None else None,
            "sweg": int(sweg) if sweg is not None else 0,
            "delta": round(delta, 1) if delta is not None else 0.0,
        })

    factions_sorted = sorted(factions_seen)
    faction_options = "\n    ".join(
        f'<option value="{f}">{f}</option>' for f in factions_sorted
    )

    units_json = json.dumps(units, separators=(",", ":"))
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    feature_rows = _render_family_rollups(family_rollups)
    scatter_svg = _render_scatter_svg(units)

    html = _HTML_TEMPLATE.format(
        version=version,
        unit_count=len(units),
        faction_count=len(factions_sorted),
        faction_options=faction_options,
        built_at=built_at,
        r_squared=r_squared,
        r_squared_pct=r_squared_pct,
        mae_log=mae_log,
        mae_pts_str=mae_pts_str,
        feature_count=feature_count,
        feature_rows=feature_rows,
        scatter_svg=scatter_svg,
        units_json=units_json,
        generated_at=generated_at,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    size_kb = out_path.stat().st_size / 1024
    print(f"Written {out_path}  ({size_kb:.1f} KB, {len(units)} units)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Bake standalone HTML points reference.")
    parser.add_argument("--data", default=str(_DATA_FILE), help="Path to sweg_points_v1.json")
    parser.add_argument("--out", default=str(_DEFAULT_OUT), help="Output HTML path")
    args = parser.parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        print(f"ERROR: data file not found: {data_path}", file=sys.stderr)
        sys.exit(1)

    bake(data_path, Path(args.out))


if __name__ == "__main__":
    main()
