"""Scratch: for AM seed 5, after bind_leaders, report each AM CHARACTER's
attach state (bound host squad_id? host has bodyguard?), then run the game and
report HOW each character died (ranged vs melee) and whether its host was still
alive at death. Distinguishes 'not bound (coverage gap)' from 'bound but AI
peels it into melee'. Read-only. Not committed."""
from __future__ import annotations
import random

from code.army_builder import build_faction_random_army
from code.attachment import bind_leaders, _is_attachable_character, _host_squad_has_bodyguard
from code.events import BattleStarted, UnitKilled, UnitFought, UnitShot, RoundStarted, EventLog
from code.simulator import Battle
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission, FACTIONS

A_FAC, B_FAC, SEED = "Astra Militarum", "Adeptus Astartes", 5
_fac_idx = {f: i for i, f in enumerate(FACTIONS)}
pair_seed = (_fac_idx[A_FAC] * 1000 + _fac_idx[B_FAC]) * 100 + SEED

random.seed(pair_seed)
a = build_faction_random_army("A", A_FAC, 2000, rng=random.Random(SEED), use_archetype=True)
b = build_faction_random_army("B", B_FAC, 2000, rng=random.Random(SEED + 10000), use_archetype=True)

bind_leaders(a)
units = list(getattr(a, "units", []) or [])
chars = [u for u in units if "CHARACTER" in set(u.profile.unit_keywords or ())]
print(f"# AM army: {len(units)} model-units, {len(chars)} CHARACTER model-units")
print(f"{'character':30} {'attachable':>10} {'host_sqid':>9} {'host_bg?':>8}")
char_uids = {}
for u in chars:
    host = getattr(u, "_attach_host_squad_id", None)
    attachable = _is_attachable_character(u.profile)
    hbg = _host_squad_has_bodyguard(units, host) if host is not None else "n/a"
    print(f"{u.profile.name[:30]:30} {str(attachable):>10} {str(host):>9} {str(hbg):>8}")
    char_uids[u.uid] = u.profile.name

# run and track how each character dies
log = EventLog()
map_ = _pick_rotation_map(SEED)
primary = _pick_primary_mission(pair_seed)
Battle(a, b, subscribers=[log], map_=map_, primary_mission=primary).run()
ev = log.events

# last attacker mode against each character before its death
last_hit = {}   # char_uid -> ("ranged"/"melee", attacker_name)
name_of = {}
for e in ev:
    if isinstance(e, BattleStarted):
        for u in e.units:
            name_of[u.uid] = u.name
for e in ev:
    if isinstance(e, UnitShot) and e.target_uid in char_uids:
        last_hit[e.target_uid] = ("ranged", name_of.get(e.attacker_uid, "?"))
    elif isinstance(e, UnitFought) and e.target_uid in char_uids:
        last_hit[e.target_uid] = ("melee", name_of.get(e.attacker_uid, "?"))

print(f"\n# character deaths (how the killing damage was delivered):")
for e in ev:
    if isinstance(e, UnitKilled) and e.unit_uid in char_uids:
        mode, atk = last_hit.get(e.unit_uid, ("?", "?"))
        print(f"  DIED: {char_uids[e.unit_uid][:28]:28}  last hit by {mode:6} from {atk[:22]}")
