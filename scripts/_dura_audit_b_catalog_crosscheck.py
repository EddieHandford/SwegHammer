"""Durability fidelity wave, audit B (defensive coverage) — scratch script.

Cross-checks the LIVE `code.units.UNIT_CATALOG` invulnerable-save fields
(post-mapper, post-override) for every Imperial Knights and Chaos Knights
chassis against the BSData-verbatim scan in
`scripts/_dura_audit_b_invuln_scan.py`, and prints a flat divergence table:
which chassis SHOULD be ranged-only per BSData text but currently are not
(or vice versa).

Run with: `python -m scripts._dura_audit_b_catalog_crosscheck` from the repo
root. Read-only: does not touch any tracked file.
"""
from __future__ import annotations

from code.units import UNIT_CATALOG

from scripts._dura_audit_b_invuln_scan import FILES, GST, _build_profile_index, _load, scan_file

# Map BSData selectionEntry display names -> UNIT_CATALOG keys. Built by
# lower-casing, replacing spaces/hyphens with underscores, and prefixing with
# the codex key used in this catalogue -- matched by substring since the
# catalogue key convention (e.g. "imperial_knights_library_knight_destrier")
# embeds the codex slug the display name doesn't carry.
_CODEX_PREFIX = {
    "IK_LIBRARY": "imperial_knights_library_",
    "CK_LIBRARY": "chaos_knights_library_",
}


def _slug(name: str) -> str:
    return name.lower().replace("-", " ").replace("  ", " ").strip().replace(" ", "_")


def main() -> None:
    combined_idx: dict = {}
    roots = {}
    for label, path in list(FILES.items()) + [("GST", GST)]:
        root = _load(path)
        roots[label] = root
        combined_idx.update(_build_profile_index(root))

    print(f"{'unit key':52} {'BSData says':18} {'sim melee/ranged':18} {'flag'}")
    divergences = []
    for label, prefix in _CODEX_PREFIX.items():
        for name, eid, links, inline in scan_file(roots[label], combined_idx):
            slug = _slug(name)
            candidates = [
                k for k in UNIT_CATALOG
                if k.startswith(prefix) and k[len(prefix):].replace("chaos_", "") == slug
            ]
            if not candidates:
                # try direct suffix match (chaos entries prefix "chaos_" onto
                # the shared model name, e.g. "chaos_acastus_knight_asterius")
                candidates = [k for k in UNIT_CATALOG if k.startswith(prefix) and slug in k]
            if not candidates:
                print(f"{'(' + name + ')':52} -- no catalogue key matched --")
                continue
            key = candidates[0]
            u = UNIT_CATALOG[key]
            desc = (links[0][2] if links else inline[0][2]) if (links or inline) else None
            ranged_only_expected = bool(desc) and "against ranged attacks" in desc
            melee = getattr(u, "invuln_save_melee", None)
            ranged = getattr(u, "invuln_save_ranged", None)
            sim_ranged_only = melee == 7 and ranged is not None and ranged < 7
            ok = ranged_only_expected == sim_ranged_only
            flag = "OK" if ok else "DIVERGENCE"
            print(f"{key:52} {'ranged-only' if ranged_only_expected else 'unconditional':18} "
                  f"{f'{melee}/{ranged}':18} {flag}")
            if not ok:
                divergences.append((key, desc, melee, ranged))

    print()
    if divergences:
        print(f"{len(divergences)} divergence(s) found:")
        for key, desc, melee, ranged in divergences:
            print(f"  {key}: BSData = {desc!r}; sim melee={melee} ranged={ranged}")
    else:
        print("No divergences found.")


if __name__ == "__main__":
    main()
