"""Scratch: FUNCTION-LEVEL byte-identical-off proof for SWEG_LEADER_SQUAD_DEDUPE.
My change only touches bind_leaders. This re-implements the OLD per-unit loop
verbatim and compares its bindings to the NEW bind_leaders (gate default-off) on
the same armies across all factions/seeds. Identical => the OFF path is
byte-identical, so the eval is byte-identical off (nothing else changed).
Read-only. Not committed."""
from __future__ import annotations
import random

from code.army_builder import build_faction_random_army
from code.attachment import (
    bind_leaders, _attach_targets, _is_attachable_character, _MAX_LEADERS_PER_SQUAD,
)
from scripts.evaluate_vs_meta import FACTIONS


def old_bind(army) -> dict:
    """Verbatim copy of the pre-change per-unit loop. Returns {id(unit): host_sid}."""
    from code.leaders import lookup_ability, _name_to_catalog_keys
    squad_keys: dict = {}
    for u in army.units:
        kw = set(u.profile.unit_keywords or ())
        if "CHARACTER" in kw:
            continue
        sid = getattr(u, "squad_id", None)
        if sid is None:
            continue
        keys = squad_keys.setdefault(sid, set())
        for k in _name_to_catalog_keys(u.profile.name):
            keys.add(k)
    amap = _attach_targets()
    load: dict = {}
    out: dict = {}
    for u in army.units:
        out[id(u)] = None
        if not _is_attachable_character(u.profile):
            continue
        cat_keys = _name_to_catalog_keys(u.profile.name)
        attach = ()
        for ck in cat_keys:
            if ck in amap:
                attach = amap[ck]
                break
        if not attach:
            ability = lookup_ability(u.profile.name)
            if ability is not None:
                attach = (ability.attach_keys if ability.attach_keys is not None
                          else ability.host_keys)
        if not attach:
            continue
        legal = [sid for sid, keys in squad_keys.items()
                 if load.get(sid, 0) < _MAX_LEADERS_PER_SQUAD
                 and any(k in attach for k in keys)]
        if not legal:
            continue
        sid = min(legal, key=lambda s: load.get(s, 0))
        out[id(u)] = sid
        load[sid] = load.get(sid, 0) + 1
    return out


total = mism = armies = 0
bad = []
for fac in FACTIONS:
    for seed in range(3):
        armies += 1
        a = build_faction_random_army("A", fac, 2000, rng=random.Random(seed), use_archetype=True)
        ref = old_bind(a)                    # OLD behaviour
        bind_leaders(a)                      # NEW code, gate default-off
        for u in a.units:
            total += 1
            new = getattr(u, "_attach_host_squad_id", None)
            if new != ref[id(u)]:
                mism += 1
                bad.append((fac, seed, u.profile.name, ref[id(u)], new))

print(f"# function-level byte-identical-off: compared {total} unit-bindings "
      f"over {armies} armies ({len(FACTIONS)} factions x 3 seeds)")
if mism:
    print(f"# {mism} MISMATCHES -> OFF path NOT byte-identical:")
    for fac, s, nm, r, n in bad[:25]:
        print(f"  {fac} seed={s} {nm[:30]}: old={r} new={n}")
else:
    print("# ZERO mismatches -> gate-off bind_leaders is byte-identical to the old loop.")
