"""Class 5, rebuilt: STRUCTURED flags the code sets versus the rule text quoted.

The first attempt (`scripts/_fabrication_sweep.py`) scanned effect PROSE for
mechanic names and failed — 126 hits, the top six all false, because prose cannot
separate "grants Lethal Hits" from "the sim already models Rendax Lethal Hits" or
"the prior fabricated proxy was removed". That script is marked untrustworthy.

This one reads the STRUCTURED registry instead. `code/leaders.py` defines
`LeaderAbility` objects whose FIELDS are the actual mechanical grants the engine
applies — `lethal_hits`, `plus_one_to_hit`, `fnp`, `sustained_hits` and so on.
A field set True is a grant the simulator really makes; if the corresponding
mechanic never appears in that ability's quoted rule text, the grant has no
textual authority. That is the fabrication class the decision ledger records
being bitten by before (removed `LeaderAbility` proxies, the Khorne Berzerkers
`_screen_target_bonus` mislabelling, Awakened Dynasty run wrong for weeks).

Structured, so it cannot be fooled by narrative — but still a SHORTLIST: a quote
may be truncated in the citation, and an effect may legitimately paraphrase
(a "+1 to Hit" grant citing "improve the Ballistic Skill by 1" is correct).
Adjudicate every hit against the quote printed beside it.

Read-only. Run: python -m scripts._fabrication_sweep2
"""
from __future__ import annotations
import glob
import json

# LeaderAbility field -> the words that must appear in the rule text for the
# grant to have textual authority. Any one of them suffices.
FIELD_WORDS = {
    "lethal_hits": ("lethal hits",),
    "sustained_hits": ("sustained hits",),
    "devastating_wounds": ("devastating wounds",),
    "fnp": ("feel no pain", "ignore that lost wound", "6+++", "5+++"),
    "plus_one_to_hit": ("add 1 to the hit", "improve the ballistic", "improve the weapon skill",
                        "add 1 to hit"),
    "plus_one_to_wound": ("add 1 to the wound", "add 1 to wound"),
    "plus_one_strength": ("add 1 to the strength", "strength characteristic"),
    "plus_one_attack": ("add 1 to the attacks", "attacks characteristic"),
    "reroll_hit_ones": ("re-roll a hit roll of 1", "re-roll hit rolls of 1", "re-roll one hit"),
    "reroll_hits": ("re-roll the hit", "re-roll hit rolls"),
    "reroll_wound_ones": ("re-roll a wound roll of 1", "re-roll wound rolls of 1"),
    "reroll_wounds": ("re-roll the wound", "re-roll wound rolls"),
    "invulnerable_save": ("invulnerable save",),
    "ignores_cover": ("ignores cover",),
    "precision": ("precision",),
}


def citations():
    out = {}
    for f in glob.glob("data/rule_citations.d/*.json") + glob.glob("data/rule_citations.json"):
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        for k, v in d.items():
            if isinstance(v, dict):
                out[k] = v
    return out


def main() -> None:
    try:
        import code.leaders as L
    except Exception as exc:  # pragma: no cover
        print("could not import code.leaders:", exc)
        return

    # Use the FULL registry by name. An earlier version scanned dir(L) for any
    # list of pairs and latched onto `_AM_OFFICER_REGISTRY_ENTRIES` (4 entries)
    # instead of `_REGISTRY` (66) — a silent 94 percent coverage loss that made
    # the sweep look conclusive while reading almost nothing.
    reg = getattr(L, "_REGISTRY", None)
    if not reg:
        print("could not locate code.leaders._REGISTRY")
        return

    cits = citations()
    hits = []
    for name, ability in reg:
        # Citations key on the ABILITY name ("Senior Officer"), the registry on
        # the PROFILE name ("Cadian Castellan"). Keying on the profile made every
        # entry read "NO CITATION" — a lookup failure masquerading as a finding.
        cit = (cits.get(f"LeaderAbility.{getattr(ability, 'name', '')}")
               or cits.get(f"LeaderAbility.{name}"))
        quote = (cit or {}).get("quoted_text", "") or ""
        low_q = quote.lower()
        for field, words in FIELD_WORDS.items():
            val = getattr(ability, field, None)
            if not val:
                continue
            # SENTINELS: this codebase stores "no save" / "no Feel No Pain" as 7
            # (unrollable on a d6), which is TRUTHY. An earlier version of this
            # sweep reported every Astra Militarum leader as granting Feel No
            # Pain purely because of it — verified false against the code.
            if field in ("fnp", "invulnerable_save"):
                try:
                    if int(val) >= 7:
                        continue
                except (TypeError, ValueError):
                    pass
            if not quote:
                hits.append((name, field, "NO CITATION", ""))
                continue
            if not any(w in low_q for w in words):
                hits.append((name, field, "not in quote", quote[:150]))

    print(f"registry entries: {len(reg)}")
    print(f"STRUCTURED GRANTS with no matching words in the quoted rule: {len(hits)}\n")
    print("shortlist — adjudicate each against the quote (paraphrase is legitimate)\n")
    for name, field, why, quote in sorted(hits)[:30]:
        print(f"== {name}   field={field}   ({why})")
        if quote:
            print(f"   quote: {quote}")
        print()


if __name__ == "__main__":
    main()
