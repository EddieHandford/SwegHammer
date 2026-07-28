"""Are Astra Militarum characters actually PROTECTED, or only nominally attached?

`is_attachment_protected` shields an attached leader only while its host squad
still contains a living NON-CHARACTER (bodyguard) model. Astra Militarum measures
99 percent "attached" yet its characters die at 61-66 percent against opponents'
17. Two very different explanations:

  (a) they are attached to real bodyguard squads and the bodyguards simply die —
      faithful, since 10e exposes a leader once its Bodyguard unit is destroyed; or
  (b) they are attached to hosts that contain no bodyguard at all (a Cadian
      Command Squad is itself an all-CHARACTER unit), so the attachment is
      nominal and confers zero protection from turn one.

This measures protection AT DEPLOYMENT and at end of battle, per datasheet.

Run: PYTHONHASHSEED=0 python -m scripts._am_protection_probe
"""
from __future__ import annotations
import collections
import os
import random

import code.simulator as SIM
from code.attachment import is_attachment_protected
from code.army_builder import build_faction_random_army
from scripts.evaluate_vs_meta import _pick_rotation_map, _pick_primary_mission, FACTIONS

FAC = os.environ.get("PP_FACTION", "Astra Militarum")
N = int(os.environ.get("PP_N", "3"))
OPPS = ["Adeptus Astartes", "Necrons", "Adepta Sororitas",
        "Genestealer Cults", "Death Guard", "Aeldari"]
_idx = {f: i for i, f in enumerate(FACTIONS)}


def main() -> None:
    os.environ["PYTHONHASHSEED"] = "0"
    per = collections.defaultdict(lambda: collections.Counter())
    games = 0
    for opp in OPPS:
        for seed in range(N):
            ps = (_idx[FAC] * 1000 + _idx[opp]) * 100 + seed
            random.seed(ps)
            swap = (os.environ.get("SWEG_SIDE_ROLLOFF", "1") != "0"
                    and random.Random(ps ^ 0x51DE).random() < 0.5)
            fa, fb = (opp, FAC) if swap else (FAC, opp)
            a = build_faction_random_army("A", fa, 2000, rng=random.Random(seed), use_archetype=True)
            b = build_faction_random_army("B", fb, 2000, rng=random.Random(seed + 10000), use_archetype=True)
            batt = SIM.Battle(a, b, map_=_pick_rotation_map(seed),
                              primary_mission=_pick_primary_mission(ps))
            me = batt.b if swap else batt.a
            # `bind_leaders` runs INSIDE Battle.run()'s setup, not in the
            # constructor — sampling at construction reads every leader as
            # unattached (an error this probe made on its first version). Hook
            # the first round instead: bindings are in place, casualties are not.
            _orig_round = batt._run_round
            _sampled = {"done": False}

            def _wrapped(rnd, _o=_orig_round, _m=me, _s=_sampled):
                if not _s["done"]:
                    _s["done"] = True
                    for u in _m.units:
                        if "CHARACTER" not in set(u.profile.unit_keywords or ()):
                            continue
                        d = per[u.profile.name or "?"]
                        d["n"] += 1
                        if getattr(u, "_attach_host_squad_id", None) is not None:
                            d["attached"] += 1
                        if is_attachment_protected(u, _m.units):
                            d["protected_at_deploy"] += 1
                return _o(rnd)

            batt._run_round = _wrapped
            batt.run()
            for u in me.units:
                if "CHARACTER" not in set(u.profile.unit_keywords or ()):
                    continue
                d = per[u.profile.name or "?"]
                if not u.is_alive:
                    d["died"] += 1
            games += 1

    print(f"=== {FAC} character protection, {games} games ===")
    print(f"{'datasheet':28s} {'models':>7s} {'attached':>9s} {'PROTECTED':>10s} {'died':>7s}")
    tot = collections.Counter()
    for name, d in sorted(per.items(), key=lambda kv: -kv[1]["n"]):
        n = max(1, d["n"])
        for k, v in d.items():
            tot[k] += v
        print(f"{name[:28]:28s} {d['n']:7d} {100*d['attached']/n:8.0f}% "
              f"{100*d['protected_at_deploy']/n:9.0f}% {100*d['died']/n:6.0f}%")
    n = max(1, tot["n"])
    print(f"\n{'TOTAL':28s} {tot['n']:7d} {100*tot['attached']/n:8.0f}% "
          f"{100*tot['protected_at_deploy']/n:9.0f}% {100*tot['died']/n:6.0f}%")
    print("\nIf ATTACHED is high but PROTECTED is low, the attachment is nominal:")
    print("the host squad contains no non-CHARACTER bodyguard model to shield behind.")


if __name__ == "__main__":
    main()
