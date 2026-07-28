"""Triage every default-OFF gate whose citation reads as a rules claim.

`scripts/_gate_sweep.py` finds them; this prints what each one actually SAYS so a
human can sort it into one of three buckets, which the keyword scan cannot
distinguish:

  MISSING MECHANIC — a rule the army owns and cannot currently use. Under
      fidelity-first these should be ON.
  LIST CHOICE      — a detachment or army-construction option. Switching it on
      changes WHICH army is fielded, which is a list decision, not a fidelity
      fix. (Astra Militarum's Recon Element and Grizzled Company are both this.)
  HEURISTIC        — artificial-intelligence piloting wearing a rules-flavoured
      citation, e.g. a targeting bias justified by quoting the secondary it
      chases.

Read-only. Run: python -m scripts._offgate_triage
"""
from __future__ import annotations
import glob
import json

# The non-Astra-Militarum default-off gates with rules-claim citations, from
# scripts/_gate_sweep.py.
TARGETS = [
    ("SWEG_ACTION_ECONOMY", "simulator.tactical_deck_full"),
    ("SWEG_SECONDARY_HANDCAP", "simulator.secondary_two_card_hand_cap"),
    ("SWEG_WARP_RIFTS", "simulator.warp_rifts"),
    ("SWEG_VOTANN_HEARTHBAND", "HEARTHBAND.hearthband_methodical_annihilation"),
    ("SWEG_VOTANN_KAHL_LETHAL", "LeaderAbility.Warrior-Forged Leadership"),
    ("SWEG_EC_DAEMONETTE_FF", "simulator.ec_daemonette_fights_first"),
    ("SWEG_CHALLENGER_GAP_CAPPED", "simulator.challenger_cards"),
    ("SWEG_OVERWATCH_MOVE", "simulator.fire_overwatch"),
    ("SWEG_M4", "simulator.m4_squad_cluster"),
    ("SWEG_MELEE_HOLD_OBJECTIVE", "simulator.melee_hold_objective"),
    ("SWEG_OVERRIDE_MELEE_PRECEDENCE", "simulator.override_melee_precedence"),
    ("SWEG_CUSTODES_MASTER_STANCES", "simulator.custodes_master_of_stances"),
    ("SWEG_DG_CONTAGION_ESCALATION", "simulator.contagions_of_nurgle"),
    ("SWEG_IK_DEFENDER_COVER", "simulator.ik_defender_selfless_protector"),
    ("SWEG_GTG", "simulator.go_to_ground"),
    ("SWEG_TAU_NOVA_CHARGE", "simulator.tau_nova_charge"),
]

LIST_MARKERS = ("detachment rule", "detachment)", "army construction", "template")
HEUR_MARKERS = ("heuristic", "not a rules claim", "not a 10e rules claim",
                "artificial-intelligence piloting", "instrument", "read-only")


def load():
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
    cit = load()
    for gate, key in TARGETS:
        v = cit.get(key)
        print("=" * 78)
        print(f"{gate}")
        if not v:
            print("   (no citation found under that key)")
            continue
        rule = v.get("rule_name", "")
        text = v.get("quoted_text", "")
        eff = (v.get("effect", "") + " " + v.get("trigger", "")).lower()
        if any(m in eff for m in HEUR_MARKERS):
            bucket = "HEURISTIC"
        elif any(m in rule.lower() or m in eff for m in LIST_MARKERS):
            bucket = "LIST CHOICE (probably) — verify"
        else:
            bucket = "MISSING MECHANIC (candidate) — verify"
        print(f"   bucket: {bucket}")
        print(f"   rule  : {rule[:100]}")
        print(f"   text  : {text[:220]}")


if __name__ == "__main__":
    main()
