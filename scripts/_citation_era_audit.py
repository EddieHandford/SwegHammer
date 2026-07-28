"""Date every archetype citation against the tenth-edition window.

This project simulates TENTH edition against the May 2026 Warp Friends
aggregate. Two ways a citation can be wrong, and they are different problems:

  EDITION   the source is an event played after eleventh edition launched on
            20 June 2026. Disqualified outright - the rules are not the ones
            being simulated.
  ERA       the source is tenth edition but from a distant part of it. The
            Aeldari template cites two 2025 tournament lists against a May 2026
            target; Aeldari were dominant in 2025 and are LAST of 22 by May
            2026, so the simulator faithfully plays a list from an era when the
            faction was strong. Same edition, wrong meta.

The boundary was verified 2026-07-27: eleventh edition launched 20 June 2026
(Armageddon launch box; core rules 27 June), tenth ran from June 2023.

TWO LIMITATIONS, BOTH LOAD-BEARING - read them before trusting the table.

1. WORK DATES LOOK LIKE EVENT DATES. A date in a comment may be when the work
   was done, not when the event was played. Those were already conflated once
   here: SWEG_EC_LIST3 records a "live source lookup" on 2026-07-08 and its
   event date is still unestablished. Chaos Daemons reads AFTER BOUNDARY on a
   2026-07 date that is almost certainly the SWEG_DAEMONS_BELAKOR build date,
   and Chaos Space Marines reads STRADDLES on a "verified 2026-06-11" line.
   Every hit is a PROMPT TO CHECK, never a verdict.

2. IT ONLY SCANS THE DICT BLOCK. Gated list overrides defined elsewhere in the
   module are invisible to it. Emperor's Children reads NO CITATION here and
   that is FALSE - SWEG_EC_LIST3 carries a full citation, it just lives beside
   `_effective_template` rather than in the faction's dict entry. Treat "NO
   CITATION" as "no citation in the block", and grep the module for the
   faction name before concluding anything.

Run: PYTHONHASHSEED=0 python -m scripts._citation_era_audit
"""
from __future__ import annotations
import re

from code.archetypes import ARCHETYPES

PATH = "code/archetypes.py"

# The target the simulator is calibrated against.
TARGET = "2026-05"
# Eleventh edition launch. Anything played at or after this is disqualified.
EDITION_BOUNDARY = "2026-06-20"
# Tenth edition opened here.
EDITION_OPEN = "2023-06-24"

URL = re.compile(r"https?://[^\s)\"']+")
# Dates in any shape these comments actually use.
ISO = re.compile(r"\b(20\d\d)-(\d\d)(?:-(\d\d))?\b")
SLASH = re.compile(r"/(20\d\d)/(\d\d)/")
MONTH = re.compile(
    r"\b(january|february|march|april|may|june|july|august|september|october"
    r"|november|december)\s+(20\d\d)\b", re.I)
SLUG_MONTH = re.compile(
    r"-(january|february|march|april|may|june|july|august|september|october"
    r"|november|december)-(20\d\d)", re.I)
MONTHS = {m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"])}
# A bare year attached to an event name ("Nova Open 2025").
BARE_YEAR = re.compile(r"\b(20\d\d)\b")

RULES_WIKI = ("wahapedia.ru", "bsdata", "github.com/BSData")


def _dates(text: str):
    """Every (year, month) pair the text mentions, most specific patterns first."""
    out = set()
    for y, mo, _d in ISO.findall(text):
        out.add((int(y), int(mo)))
    for y, mo in SLASH.findall(text):
        out.add((int(y), int(mo)))
    for name, y in MONTH.findall(text) + SLUG_MONTH.findall(text):
        out.add((int(y), MONTHS[name.lower()]))
    if not out:
        for y in BARE_YEAR.findall(text):
            out.add((int(y), 0))          # year only, month unknown
    return sorted(out)


def _classify(year: int, month: int) -> str:
    if year > 2026 or (year == 2026 and month >= 7):
        return "AFTER BOUNDARY"
    if year == 2026 and month == 6:
        return "STRADDLES BOUNDARY"
    if year == 2026 and 1 <= month <= 5:
        return "in window"
    if year == 2026 and month == 0:
        return "2026, month unknown"
    if 2023 <= year <= 2025:
        return "tenth edition, EARLIER ERA"
    if year < 2023:
        return "BEFORE TENTH EDITION"
    return "unclear"


def main() -> None:
    lines = open(PATH, encoding="utf-8").read().splitlines()
    starts = []
    for i, ln in enumerate(lines):
        m = re.match(r'^    "([^"]+)": \{\s*$', ln)
        if m and m.group(1) in ARCHETYPES:
            starts.append((i, m.group(1)))
    end = len(lines)
    for i, ln in enumerate(lines):
        if ln == "}" and i > (starts[-1][0] if starts else 0):
            end = i + 1
            break
    starts.append((end, None))

    print("=== archetype citation dating against the tenth-edition window ===")
    print(f"    target {TARGET} | eleventh edition from {EDITION_BOUNDARY} | "
          f"tenth from {EDITION_OPEN}\n")

    flagged = []
    for (i, fac), (j, _) in zip(starts, starts[1:]):
        k = i - 1
        while k >= 0 and (lines[k].strip().startswith("#") or not lines[k].strip()):
            k -= 1
        text = "\n".join(lines[k + 1:j])
        urls = [u for u in URL.findall(text)]
        wiki_only = urls and all(any(w in u for w in RULES_WIKI) for u in urls)
        found = _dates(text)

        if not urls:
            verdict, detail = "NO CITATION", "no source of any kind"
        elif wiki_only:
            verdict, detail = "RULES WIKI ONLY", "cites datasheets, not a roster"
        elif not found:
            verdict, detail = "UNDATED", "source named but no date anywhere"
        else:
            kinds = {_classify(y, m) for y, m in found}
            # Report the WORST date present, never the best. A block that cites
            # a 2025 list and also says "May 2026 meta" in prose must not read
            # as clear just because an in-window date appears somewhere - that
            # is exactly the Aeldari case this tool exists to catch, and an
            # earlier draft of it cleared Aeldari for that reason.
            verdict = ("AFTER BOUNDARY" if "AFTER BOUNDARY" in kinds else
                       "STRADDLES BOUNDARY" if "STRADDLES BOUNDARY" in kinds else
                       "MIXED ERA" if ("tenth edition, EARLIER ERA" in kinds
                                       and len(kinds) > 1) else
                       "tenth edition, EARLIER ERA"
                       if "tenth edition, EARLIER ERA" in kinds else
                       "in window" if "in window" in kinds else
                       sorted(kinds)[0])
            detail = ", ".join(f"{y}-{m:02d}" if m else f"{y}" for y, m in found)

        bad = verdict not in ("in window",)
        mark = "  <--" if bad else ""
        print(f"  {fac:<24}{verdict:<28}{detail[:46]}{mark}")
        if bad:
            flagged.append((fac, verdict))

    print()
    print(f"  templates needing a source check: {len(flagged)} of {len(starts) - 1}")
    print()
    print("  EVERY hit is a prompt to check, not a verdict. A date in a comment")
    print("  may be when the WORK was done, not when the EVENT was played -")
    print("  that conflation already happened once here (SWEG_EC_LIST3). Only an")
    print("  event date clears or condemns a source.")


if __name__ == "__main__":
    main()
