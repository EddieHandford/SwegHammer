"""Which archetype templates cite a real-meta source, and which tune to a metric?

The Tyranid list defect (docs/TYRANID_LIST_FIDELITY.md) was findable only because
that template named its sources in a comment, so the fielded army could be read
against them. This reports, per faction block in code/archetypes.py:

    sources     count of http(s) URLs in the block
    wr-tuning   count of comment lines quoting a SIMULATED win rate as the
                reason for a composition choice ("iter17 lands at 53.1% sim")

The second is the concerning one. Tuning a LIST to make the Stage-1 metric come
out right is fitting the input to the answer: the archetype is supposed to be an
independent observation of what real players field, and the win rate is supposed
to be the test of the simulator, not of the list.

Run: PYTHONHASHSEED=0 python -m scripts._archetype_citation_audit
"""
from __future__ import annotations
import re

from code.archetypes import ARCHETYPES

PATH = "code/archetypes.py"
URL = re.compile(r"https?://[^\s)\"']+")
# "53.1% sim", "sim 33.4%", "lands at 72%", "real-meta WR by ~+24pt",
# "recover Votann sim from -11.6pt iter16 regression", "iter17 fix"
#
# WIDENED after the first run undercounted. The original pattern matched only
# percentage-and-"sim" phrasings, so it scored Leagues of Votann at ZERO despite
# its comment justifying the Hekaton Land Fortress as a "mandatory inclusion for
# iter17 fix to recover Votann sim from -11.6pt iter16 regression" — composition
# chosen to move the metric, in different words. A detector's coverage is not the
# same as the thing it is supposed to detect.
WR = re.compile(
    r"(\d{2}\.\d|\d{2})\s*%\s*sim|sim\s+\d{2}\.\d\s*%|lands? at \d{2}(\.\d)?%"
    r"|WR by|iter\d+\s+(fix|regression|baseline)|regression|sim\s+[-+]?\d+(\.\d)?pt"
    r"|recover\s+\w+\s+sim", re.I)

# A URL is only a LIST SOURCE if it identifies a specific article or event.
# A bare domain cites nothing checkable, and a rules wiki documents datasheets
# rather than what anyone actually brought to a tournament.
RULES_WIKI = ("wahapedia.ru", "bsdata", "github.com/BSData")


def _classify_url(u: str) -> str:
    if any(w in u for w in RULES_WIKI):
        return "rules wiki"
    # strip scheme, then check whether anything follows the host
    rest = u.split("://", 1)[-1]
    path = rest.split("/", 1)[1] if "/" in rest else ""
    if len(path.strip("/")) < 3:
        return "bare domain"
    return "specific"


def main() -> None:
    lines = open(PATH, encoding="utf-8").read().splitlines()
    # Locate each faction block by its top-level '    "Faction": {' line.
    starts = []
    for i, ln in enumerate(lines):
        m = re.match(r'^    "([^"]+)": \{\s*$', ln)
        if m and m.group(1) in ARCHETYPES:
            starts.append((i, m.group(1)))
    # Bound the LAST faction block at the line that closes the ARCHETYPES dict
    # literal (a bare "}" at column zero). Without this the final block in file
    # order swallows every module-level function after the dict, which inflated
    # its source and line counts and made it look the best-documented.
    end = len(lines)
    for i, ln in enumerate(lines):
        if ln == "}" and i > (starts[-1][0] if starts else 0):
            end = i + 1
            break
    starts.append((end, None))

    rows = []
    for (i, fac), (j, _) in zip(starts, starts[1:]):
        block = lines[i:j]
        # comments immediately preceding the block belong to it too
        k = i - 1
        while k >= 0 and (lines[k].strip().startswith("#") or not lines[k].strip()):
            k -= 1
        block = lines[k + 1:j]
        text = "\n".join(block)
        urls = URL.findall(text)
        kinds = [_classify_url(u) for u in urls]
        rows.append((fac, kinds.count("specific"), len(urls),
                     len(WR.findall(text)), len(block)))

    rows.sort(key=lambda r: (r[1], -r[3]))
    print("=== archetype provenance, per faction block ===")
    print(f"{'faction':<24}{'list sources':>13}{'all urls':>10}"
          f"{'metric-tuning':>15}{'lines':>7}")
    for fac, n_spec, n_url, n_wr, n_lines in rows:
        flag = ""
        if n_spec == 0 and n_url == 0:
            flag = "   <-- NO CITATION AT ALL"
        elif n_spec == 0:
            flag = "   <-- only bare domains / rules wiki: cites no LIST"
        elif n_wr >= 3:
            flag = "   <-- heavily metric-tuned"
        print(f"{fac:<24}{n_spec:>13}{n_url:>10}{n_wr:>15}{n_lines:>7}{flag}")
    print()
    print(f"  templates citing NO url at all:            "
          f"{sum(1 for r in rows if r[2] == 0)} of {len(rows)}")
    print(f"  templates citing no SPECIFIC list source:  "
          f"{sum(1 for r in rows if r[1] == 0)} of {len(rows)}")
    print(f"  templates tuned to the simulated win rate: "
          f"{sum(1 for r in rows if r[3] > 0)} of {len(rows)}")


if __name__ == "__main__":
    main()
