"""How many Markerlight weapons does a Pathfinder Team actually carry?

The T'au Guided investigation (task #42) turns entirely on this number.
`Battle._run_markerlight_phase` collapses a squad to ONE Markerlight attempt,
giving 1.73 attempts per shooting phase and 3.5 percent Guided uptime. Its
stated reasoning is that a ten-model Strike Team should not fire ten
Markerlights, which is right - but the rule it cites says a unit "can be
selected to shoot with those WEAPONS", plural, and a real Pathfinder team
carries several Markerlight models.

If a Pathfinder Team carries three or four Markerlights, the simulator
under-models the faction's army rule by roughly that factor. If it carries one,
the modelling is correct and T'au's residual lives elsewhere.

CLAUDE.md rule 6 makes BSData the canonical stat source for this project, and it
is cached in-repo, so this reads the local catalogue rather than the web. It
prints every T'au datasheet carrying a Markerlight together with its per-model
loadout, so the count can be read rather than inferred.

Run: PYTHONHASHSEED=0 python -m scripts._pathfinder_markerlight_check
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PARSED = ROOT / "data" / "bsdata" / "parsed.json"


def main() -> None:
    if not PARSED.exists():
        print(f"missing {PARSED}")
        return
    data = json.loads(PARSED.read_text(encoding="utf-8"))
    units = data.get("units", data) if isinstance(data, dict) else data
    if isinstance(units, dict):
        items = list(units.items())
    else:
        items = [(u.get("key") or u.get("name", "?"), u) for u in units]

    print("=== T'au datasheets carrying a Markerlight (BSData cache) ===\n")
    found = 0
    for key, u in items:
        if not isinstance(u, dict):
            continue
        fac = (u.get("faction") or "")
        if "au" not in fac.lower() or "empire" not in fac.lower():
            continue
        blob = json.dumps(u).lower()
        if "markerlight" not in blob:
            continue
        found += 1
        name = u.get("name", key)
        mm = u.get("min_models") or u.get("minModels") or 1
        print(f"--- {name}   (min_models {mm}) ---")
        loadouts = u.get("model_loadouts") or u.get("modelLoadouts") or []
        if not loadouts:
            # Fall back to whatever weapon lists exist on the entry.
            for field in ("ranged", "ranged_weapons", "weapons"):
                w = u.get(field)
                if w:
                    for entry in w:
                        nm = (entry.get("name") if isinstance(entry, dict)
                              else str(entry))
                        if nm and "markerlight" in nm.lower():
                            print(f"    weapon: {nm}")
            print()
            continue
        for ml in loadouts:
            cnt = ml.get("count", 1)
            nm = ml.get("name", "?")
            marks = [w for w in (ml.get("ranged") or [])
                     if "markerlight" in str(w.get("name", "")).lower()]
            tag = ""
            if marks:
                tag = "   <-- MARKERLIGHT x" + str(
                    sum(int(w.get("count", 1) or 1) for w in marks))
            print(f"    {cnt:>3}x {nm[:40]:<42}{tag}")
        print()

    if not found:
        print("  No T'au datasheet in the cache mentions a Markerlight.")
        print("  Either the faction key differs or the cache does not carry")
        print("  weapon-ability text; check Wahapedia instead.")
        return
    print(f"  {found} datasheet(s) carry a Markerlight.")
    print()
    print("  The number that matters is how many Markerlight-equipped MODELS a")
    print("  Pathfinder Team fields. The simulator grants the squad ONE attempt")
    print("  regardless; if the datasheet shows several, that is the factor by")
    print("  which Guided uptime is under-modelled.")


if __name__ == "__main__":
    main()
