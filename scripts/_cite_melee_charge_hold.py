"""Add the citation for simulator.melee_charge_hold."""
from __future__ import annotations
import collections
import json

PATH = "data/rule_citations.d/keywords_and_mechanics.json"
KEY = "simulator.melee_charge_hold"


def main() -> None:
    d = json.load(open(PATH, encoding="utf-8"), object_pairs_hook=collections.OrderedDict)
    if KEY in d:
        print("already cited — no change")
        return
    d[KEY] = collections.OrderedDict([
        ("source", "https://wahapedia.ru/wh40k10ed/the-rules/core-rules/#MOVEMENT-PHASE"),
        ("rule_name", "Advance move - a unit that Advances cannot declare a charge"),
        ("quoted_text", "A unit that Advances can't shoot or declare a charge later this turn."),
        ("trigger", "SWEG_MELEE_CHARGE_HOLD=1 (unset or '0' is the byte-identical kill-switch); the moving unit is MELEE_ONLY by roles.combat_profile, is about to Advance, carries no charge-after-Advance permission (Murderer's Cowl, the Gladius Assault doctrine, or a transient Apoplectic Frenzy grant), and a NORMAL move would leave a live on-board enemy within Battle._MELEE_CHARGE_HOLD_EXPECTED_2D6 (7 inches, the expected 2D6 charge roll) of it."),
        ("effect", "ARTIFICIAL-INTELLIGENCE PILOTING HEURISTIC - not a 10e rules claim; the rule quoted above is the cost it exists to price. The unit takes a Normal move instead of an Advance, preserving its charge. This is the CHARGE half of the advance-suppression family in Battle._do_move: every existing entry point (simulator.am_advance_discipline, ck_ranged_hold, votann_ranged_hold, tsons_ranged_hold, soror_ranged_hold, astartes_ranged_hold, ec_ranged_hold, tyranids_ranged_hold) weighs only forfeited SHOOTING, gating on ranged damage per activation and weapon range, so a melee-only unit was never protected and paid its charge for ground it did not need. Measured on Tyranids with scripts/_melee_advance_probe.py: Hormagaunts forfeit the charge to an Advance on 74.9 percent of activations at default and 95.7 percent once SWEG_MELEE_ONLY_ENGAGE points them at the enemy, which is why that gate closes distance (median 16.0 to 12.2 inches) while REDUCING charge connection (11 to 3 percent); 227 points of dedicated assault swarm returns 1.7 melee wounds a game. The threshold is the EXPECTED 2D6 roll (7 inches) rather than its 12-inch maximum, so a unit facing an unlikely charge still advances to close ground - the same shape as the ranged family's downstream can-I-actually-damage guard. Units that may charge after Advancing are exempt, exactly as the ranged family exempts [ASSAULT]."),
        ("scope", "keyword-gated"),
    ])
    json.dump(d, open(PATH, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    open(PATH, "a", encoding="utf-8").write("\n")
    print("cited simulator.melee_charge_hold")


if __name__ == "__main__":
    main()
