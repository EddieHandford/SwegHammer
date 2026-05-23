"""Reconstruct Stage 1 mean-absolute-error progress over time from git history.

Scrapes commit messages and pull request descriptions for canonical
post-iteration mean-absolute-error readings, tags each value with the
evaluation mode in force at that point (random_fill vs archetype, point
budget, sample size), and renders the series to ``docs/mae_progress.png``.

The evaluation mode shifted twice during the calibration history. Without
tagging, those pivots look like step regressions when they are actually
metric-definition changes. The pivot dates below are taken from
``docs/AUTO_LOOP_LOG.md`` and the commit log:

  * up to 2026-05-17 12:00 BST  - random_fill, 1000pt budget
  * 2026-05-17 12:00 - 18:00    - archetype, 1000pt budget
  * 2026-05-17 18:00 onwards    - archetype, 2000pt budget

A separate horizontal line marks the 2.0pt Stage 1 target. A companion
csv is written next to the png so the raw series can be re-plotted or
inspected without re-running the scrape.

Usage:
    python -m scripts.plot_mae_progress
"""

from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import matplotlib.dates as mdates
import matplotlib.pyplot as plt

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PNG = REPO_ROOT / "docs" / "mae_progress.png"
OUTPUT_CSV = REPO_ROOT / "docs" / "mae_progress.csv"

MODE_RANDOM_FILL = "random_fill 1000pt"
MODE_ARCHETYPE_1K = "archetype 1000pt"
MODE_ARCHETYPE_2K = "archetype 2000pt"

ARCHETYPE_1K_START = datetime(2026, 5, 17, 12, 0, tzinfo=timezone.utc)
ARCHETYPE_2K_START = datetime(2026, 5, 17, 17, 0, tzinfo=timezone.utc)

STAGE_1_TARGET = 2.0


@dataclass
class Reading:
    when: datetime
    sha: str
    label: str
    mae: float
    mode: str
    parked: bool
    source: str  # "commit" or "pull-request"


def mode_for(when: datetime) -> str:
    if when >= ARCHETYPE_2K_START:
        return MODE_ARCHETYPE_2K
    if when >= ARCHETYPE_1K_START:
        return MODE_ARCHETYPE_1K
    return MODE_RANDOM_FILL


def run(cmd: list[str]) -> str:
    result = subprocess.run(
        cmd, cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8"
    )
    if result.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} failed: {result.stderr}")
    return result.stdout


COMMIT_SEP = "<<<COMMIT>>>"
FIELD_SEP = "<<<F>>>"


def iter_commits() -> Iterable[tuple[str, datetime, str, str]]:
    raw = run(
        [
            "git",
            "log",
            "--all",
            f"--pretty=format:{COMMIT_SEP}%H{FIELD_SEP}%aI{FIELD_SEP}%s{FIELD_SEP}%b",
        ]
    )
    for chunk in raw.split(COMMIT_SEP):
        chunk = chunk.strip()
        if not chunk:
            continue
        parts = chunk.split(FIELD_SEP, 3)
        if len(parts) < 4:
            continue
        sha, iso, subject, body = parts
        when = datetime.fromisoformat(iso).astimezone(timezone.utc)
        yield sha, when, subject, body


# Subjects of the canonical post-iter closure commits. The keyword set
# names the iter as a "closure" event (vs a one-off fix commit that
# happens to mention MAE in the body). The "after" number is the second
# figure in the "A -> B" arrow; "parked" iters revert to A.
ITER_CLOSE_RX = re.compile(
    r"#?iter\s*(\d+)\s+"
    r"(log closure|log|close|complete|PARKED|paused)\b"
    r".*?MAE\s+(\d+(?:\.\d+)?)\s*[-→>]+\s*(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)

# iter 0 baseline.
ITER_BASELINE_RX = re.compile(
    r"iter\s*0\s+baseline\s*:\s*MAE\s+(\d+(?:\.\d+)?)\s*pt", re.IGNORECASE
)


def scrape_commits() -> list[Reading]:
    out: list[Reading] = []
    seen_iters: set[tuple[int, str]] = set()
    for sha, when, subject, body in iter_commits():
        text = f"{subject}\n{body}"

        m = ITER_BASELINE_RX.search(text)
        if m:
            out.append(
                Reading(
                    when=when,
                    sha=sha[:9],
                    label="iter 0 baseline",
                    mae=float(m.group(1)),
                    mode=mode_for(when),
                    parked=False,
                    source="commit",
                )
            )
            continue

        m = ITER_CLOSE_RX.search(subject)
        if not m:
            continue
        iter_n = int(m.group(1))
        kind = m.group(2).lower()
        before, after = float(m.group(3)), float(m.group(4))
        parked = "park" in kind
        # PARKED iters reverted, so the merged-state value is the "before".
        value = before if parked else after
        key = (iter_n, kind)
        if key in seen_iters:
            continue
        seen_iters.add(key)
        out.append(
            Reading(
                when=when,
                sha=sha[:9],
                label=f"iter {iter_n}" + (" (parked)" if parked else ""),
                mae=value,
                mode=mode_for(when),
                parked=parked,
                source="commit",
            )
        )

    return out


# Pull request bodies give us values from before the auto-loop, when the
# state was driven by feature-PRs rather than iter-by-iter calibration.
# These are hand-extracted anchor points keyed by pull-request number; we
# look them up in the live ``gh`` output to verify the merge dates.
PR_ANCHORS: dict[int, tuple[float, str, str]] = {
    8: (5.06, MODE_RANDOM_FILL, "PR8: 10e rules buildout"),
    10: (4.42, MODE_RANDOM_FILL, "PR10: Stratagems + CP economy"),
    12: (7.01, MODE_RANDOM_FILL, "PR12: May 15 sprint (N=200 honest)"),
    14: (6.94, MODE_RANDOM_FILL, "PR14: BSData refresh + faction calibration"),
    15: (4.76, MODE_RANDOM_FILL, "PR15: Auto-loop iter 1-7 close (N=40)"),
}


def scrape_pull_requests() -> list[Reading]:
    raw = run(
        [
            "gh",
            "pr",
            "list",
            "--state",
            "all",
            "--limit",
            "30",
            "--json",
            "number,mergedAt,title",
        ]
    )
    data = json.loads(raw)
    out: list[Reading] = []
    for pr in data:
        n = pr["number"]
        if n not in PR_ANCHORS:
            continue
        merged = pr.get("mergedAt")
        if not merged:
            continue
        when = datetime.fromisoformat(merged.replace("Z", "+00:00"))
        mae, mode, label = PR_ANCHORS[n]
        out.append(
            Reading(
                when=when,
                sha=f"#{n}",
                label=label,
                mae=mae,
                mode=mode,
                parked=False,
                source="pull-request",
            )
        )
    return out


def collect_readings() -> list[Reading]:
    readings = scrape_commits() + scrape_pull_requests()
    readings.sort(key=lambda r: r.when)
    return readings


def render(readings: list[Reading]) -> None:
    fig, ax = plt.subplots(figsize=(12, 6.5))

    palette = {
        MODE_RANDOM_FILL: "#1f77b4",
        MODE_ARCHETYPE_1K: "#ff7f0e",
        MODE_ARCHETYPE_2K: "#d62728",
    }

    for mode, colour in palette.items():
        xs = [r.when for r in readings if r.mode == mode and not r.parked]
        ys = [r.mae for r in readings if r.mode == mode and not r.parked]
        if xs:
            ax.plot(xs, ys, marker="o", linewidth=1.6, color=colour, label=mode)

        xp = [r.when for r in readings if r.mode == mode and r.parked]
        yp = [r.mae for r in readings if r.mode == mode and r.parked]
        if xp:
            ax.scatter(
                xp,
                yp,
                marker="x",
                s=60,
                color=colour,
                alpha=0.7,
                label=f"{mode} (parked attempt)",
            )

    ax.axhline(
        STAGE_1_TARGET,
        color="green",
        linestyle="--",
        linewidth=1.2,
        label=f"Stage 1 target ({STAGE_1_TARGET}pt)",
    )

    for cutover, text in [
        (ARCHETYPE_1K_START, "pivot: archetype eval"),
        (ARCHETYPE_2K_START, "pivot: 2000pt budget"),
    ]:
        ax.axvline(cutover, color="grey", linestyle=":", linewidth=1)
        ax.text(
            mdates.date2num(cutover),
            0.97,
            text,
            transform=ax.get_xaxis_transform(),
            rotation=90,
            verticalalignment="top",
            horizontalalignment="right",
            fontsize=8,
            color="grey",
        )

    for r in readings:
        ax.annotate(
            r.label.replace("iter ", "i"),
            xy=(r.when, r.mae),
            xytext=(3, 4),
            textcoords="offset points",
            fontsize=7,
            color="dimgrey",
        )

    ax.set_xlabel("Commit date (UTC)")
    ax.set_ylabel("Mean absolute error vs Warp Friends meta (points)")
    ax.set_title(
        "SwegHammer Stage 1 calibration progress\n"
        "Each marker is a closed iteration or merged feature pull request"
    )
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.grid(alpha=0.3)
    ax.legend(loc="upper left", fontsize=8, framealpha=0.9)

    fig.autofmt_xdate()
    fig.tight_layout()
    OUTPUT_PNG.parent.mkdir(exist_ok=True)
    fig.savefig(OUTPUT_PNG, dpi=140)
    print(f"wrote {OUTPUT_PNG.relative_to(REPO_ROOT)}")


def write_csv(readings: list[Reading]) -> None:
    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["when", "sha", "label", "mae", "mode", "parked", "source"],
        )
        writer.writeheader()
        for r in readings:
            row = asdict(r)
            row["when"] = r.when.isoformat()
            writer.writerow(row)
    print(f"wrote {OUTPUT_CSV.relative_to(REPO_ROOT)}")


def main() -> int:
    readings = collect_readings()
    if not readings:
        print("no readings found", file=sys.stderr)
        return 1
    print(f"collected {len(readings)} readings")
    for r in readings:
        marker = "x" if r.parked else "*"
        print(
            f"  {marker} {r.when.date()} {r.sha:10s} {r.mode:22s} "
            f"MAE={r.mae:5.2f}  {r.label}"
        )
    write_csv(readings)
    render(readings)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
