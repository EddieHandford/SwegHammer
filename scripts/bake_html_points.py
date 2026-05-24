"""Generate a self-contained HTML points-lookup page from data/sweg_points_v1.json.

Usage:
    python scripts/bake_html_points.py
    python scripts/bake_html_points.py --out docs/sweghammer_points.html
"""

import argparse
import json
import os
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
<title>SwegHammer — Recalibrated v{version} | Points Reference</title>
<style>
  :root {{
    --bg: #0e1117;
    --surface: #1a1d27;
    --border: #2c2f3e;
    --text: #e0e0e0;
    --muted: #888;
    --gold: #c9a84c;
    --blue: #9bd6ff;
    --green: #7eb87e;
    --red: #d65f5f;
    --font: 'Segoe UI', system-ui, sans-serif;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: var(--font);
    font-size: 14px;
    min-height: 100vh;
  }}
  header {{
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: 16px 24px;
    display: flex;
    align-items: baseline;
    gap: 12px;
    flex-wrap: wrap;
  }}
  header h1 {{
    font-size: 1.35rem;
    font-weight: 600;
    color: var(--gold);
    letter-spacing: 0.03em;
  }}
  header .badge {{
    font-size: 0.7rem;
    color: var(--muted);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 2px 6px;
  }}
  header .tagline {{
    font-size: 0.8rem;
    color: var(--muted);
    margin-left: auto;
  }}
  .controls {{
    display: flex;
    gap: 10px;
    padding: 14px 24px;
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    flex-wrap: wrap;
    align-items: center;
  }}
  .controls input[type=text] {{
    flex: 1;
    min-width: 200px;
    max-width: 420px;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 6px;
    color: var(--text);
    padding: 7px 12px;
    font-size: 13px;
    outline: none;
    transition: border-color 0.15s;
  }}
  .controls input[type=text]:focus {{ border-color: var(--gold); }}
  .controls select {{
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 6px;
    color: var(--text);
    padding: 7px 12px;
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
  .controls select.sort-sel {{
    max-width: 170px;
  }}
  .stat-bar {{
    display: flex;
    gap: 24px;
    padding: 8px 24px;
    font-size: 12px;
    color: var(--muted);
    border-bottom: 1px solid var(--border);
    flex-wrap: wrap;
  }}
  .stat-bar span b {{ color: var(--text); }}
  .table-wrap {{
    overflow-x: auto;
    padding: 0 24px 48px;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    margin-top: 12px;
  }}
  thead th {{
    text-align: left;
    padding: 9px 10px;
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
  footer {{
    position: fixed;
    bottom: 0;
    right: 0;
    padding: 4px 12px;
    font-size: 10px;
    color: var(--muted);
    background: var(--bg);
    border-top: 1px solid var(--border);
    border-left: 1px solid var(--border);
    border-radius: 6px 0 0 0;
  }}
  @media (max-width: 600px) {{
    header h1 {{ font-size: 1.1rem; }}
    .controls {{ padding: 10px 12px; }}
    .table-wrap {{ padding: 0 8px 48px; }}
    td, th {{ padding: 7px 6px; }}
  }}
</style>
</head>
<body>

<header>
  <h1>SwegHammer &#8212; Recalibrated</h1>
  <span class="badge">v{version}</span>
  <span class="tagline">Fair points, fitted to the meta &nbsp;&bull;&nbsp; {unit_count} units &nbsp;&bull;&nbsp; {faction_count} factions</span>
</header>

<div class="controls">
  <input type="text" id="search" placeholder="Search unit name&#8230;" oninput="applyFilters()" autofocus>
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

<div class="stat-bar">
  <span>Showing <b id="shown-count">{unit_count}</b> of <b>{unit_count}</b> units</span>
  <span>Built <b>{built_at}</b></span>
  <span>Equation R&#178; <b>{r_squared}</b> &nbsp;&bull;&nbsp; Mean absolute error (log space) <b>{mae_log}</b></span>
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

// Initial render
applyFilters();
</script>
</body>
</html>
"""


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
    r_squared = f"{data.get('fit_metrics', {}).get('r_squared', 0):.4f}"
    mae_log = f"{data.get('fit_metrics', {}).get('mae_log', 0):.4f}"

    # Collect units as a flat list for embedding
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

    # Sort faction dropdown alphabetically
    factions_sorted = sorted(factions_seen)
    faction_options = "\n    ".join(
        f'<option value="{f}">{f}</option>' for f in factions_sorted
    )

    units_json = json.dumps(units, separators=(",", ":"))
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    html = _HTML_TEMPLATE.format(
        version=version,
        unit_count=len(units),
        faction_count=len(factions_sorted),
        faction_options=faction_options,
        built_at=built_at,
        r_squared=r_squared,
        mae_log=mae_log,
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
