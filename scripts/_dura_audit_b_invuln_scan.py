"""Durability fidelity wave, audit B (defensive coverage) — scratch script.

Self-contained BSData scan: for every top-level model `selectionEntry` in the
Imperial Knights and Chaos Knights library catalogues, resolve its OWN direct
invulnerable-save infoLink/inline-profile (not one belonging to a different,
merely-nearby selectionEntry — walking the XML tree properly avoids the
line-range mistake an earlier draft of this script made) and print the
target's `Description` characteristic verbatim, so "ranged attacks only" vs
unconditional can be read directly off the source rather than guessed from
the sim's own (possibly buggy) extraction.

Run with: `python -m scripts._dura_audit_b_invuln_scan` from the repo root.
Read-only: does not touch any tracked file.
"""
from __future__ import annotations

import gzip
import io
import xml.etree.ElementTree as ET
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE = REPO_ROOT / "data" / "bsdata" / "cache"

FILES = {
    "IK_LIBRARY": CACHE / "Imperium - Imperial Knights - Library.cat.gz",
    "CK_LIBRARY": CACHE / "Chaos - Chaos Knights Library.cat.gz",
}
GST = CACHE / "Warhammer 40,000.gst.gz"


def _strip_ns(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def _load(path: Path) -> ET.Element:
    with gzip.open(path, "rb") as fh:
        data = fh.read()
    return ET.parse(io.BytesIO(data)).getroot()


def _build_profile_index(root: ET.Element) -> dict:
    idx = {}
    for prof in root.iter():
        if _strip_ns(prof.tag) == "profile":
            pid = prof.get("id")
            if pid:
                idx[pid] = prof
    return idx


def _description(profile_elem) -> str | None:
    if profile_elem is None:
        return None
    for ch in profile_elem.iter():
        if _strip_ns(ch.tag) == "characteristic" and ch.get("name") == "Description":
            return (ch.text or "").strip()
    return None


def scan_file(root: ET.Element, combined_idx: dict):
    """Yield (unit_name, entry_id, invuln_links, inline_invuln) for every
    top-level type="model" selectionEntry, using ONLY that entry's own direct
    <infoLinks>/<profiles> children (never a nested/sibling entry's)."""
    for entry in root.iter():
        if _strip_ns(entry.tag) != "selectionEntry" or entry.get("type") != "model":
            continue
        name = entry.get("name")
        eid = entry.get("id")

        own_infolinks = next(
            (c for c in entry if _strip_ns(c.tag) == "infoLinks"), None
        )
        invuln_links = []
        if own_infolinks is not None:
            for il in own_infolinks:
                if _strip_ns(il.tag) != "infoLink":
                    continue
                ilname = il.get("name") or ""
                if "invulnerable save" in ilname.lower():
                    target = combined_idx.get(il.get("targetId"))
                    invuln_links.append((ilname, il.get("targetId"), _description(target)))

        own_profiles = next(
            (c for c in entry if _strip_ns(c.tag) == "profiles"), None
        )
        inline_invuln = []
        if own_profiles is not None:
            for prof in own_profiles:
                if _strip_ns(prof.tag) != "profile":
                    continue
                pname = prof.get("name") or ""
                if pname.lower().startswith("invulnerable save"):
                    inline_invuln.append((pname, prof.get("id"), _description(prof)))
                # NOTE: the Imperial Cerastus Knight Acheron divergence (see
                # docs/_DURA_AUDIT_B_DEFENSES.md #2) authors its invulnerable
                # save under a profile named after the UNIT ITSELF, not
                # "Invulnerable Save...", so it is deliberately NOT matched by
                # the check above -- this mirrors the mapper's real Shape-3
                # filter (code/bsdata/mapper.py) exactly, including its blind
                # spot, so this scan's silence on that unit reproduces the
                # bug rather than papering over it. Cross-check any entry
                # whose typeName == "Abilities" AND name == the unit's own
                # name AND whose Description mentions "invulnerable save" by
                # hand if auditing a new codex release.
        if invuln_links or inline_invuln:
            yield name, eid, invuln_links, inline_invuln


def main() -> None:
    combined_idx: dict = {}
    roots: dict[str, ET.Element] = {}
    for label, path in list(FILES.items()) + [("GST", GST)]:
        root = _load(path)
        roots[label] = root
        combined_idx.update(_build_profile_index(root))

    for label in FILES:
        print(f"===== {label} =====")
        for name, eid, links, inline in scan_file(roots[label], combined_idx):
            print(f"  {name}  (id={eid})")
            for ilname, tid, desc in links:
                print(f"    infoLink '{ilname}' -> {tid}: {desc}")
            for pname, pid, desc in inline:
                print(f"    inline profile '{pname}' (id={pid}): {desc}")
        print()


if __name__ == "__main__":
    main()
