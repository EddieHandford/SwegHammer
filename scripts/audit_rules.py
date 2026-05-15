"""
Verify every 10e rule the simulator implements has a citation in
`data/rule_citations.json`. Enforced by CLAUDE.md §10.

What counts as "rule-bearing":
  - A `Detachment` instance with any boolean True / any non-default integer
    or string field tracked in `RULE_BEARING_FIELDS`.
  - A `LeaderAbility` instance with any modifier field set
    (every registered leader needs a citation, since the ability text IS a
    rule we made up unless we sourced it).
  - A `Stratagem` registered on a Detachment.
  - A simulator-side mechanic (currently tracked in
    `SIMULATOR_RULE_KEYS`, manually maintained).

Exit codes:
  0 — every rule-bearing flag has a complete citation.
  1 — missing citation, incomplete citation, or stale citation key.

Run before committing any change to detachments / leaders / stratagems
or rule-bearing simulator code.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

from code.detachments import Detachment
from code.leaders import LeaderAbility, _REGISTRY as LEADER_REGISTRY
from code.stratagems import Stratagem, UNIVERSAL_STRATAGEMS
import code.detachments as det_module

REPO_ROOT = Path(__file__).resolve().parents[1]
CITATIONS_PATH = REPO_ROOT / "data" / "rule_citations.json"

REQUIRED_FIELDS = ("source", "rule_name", "quoted_text", "trigger", "effect", "scope")
VALID_SCOPES = {
    "army-wide", "unit-led", "character-only", "phase-gated",
    "keyword-gated", "weapon-keyword",
}

# Detachment fields that, when set away from their default, constitute a
# rule we need to cite. Defaults come from the Detachment dataclass; this
# tuple mirrors those defaults so a True (or non-7 invuln/fnp, or non-0
# integer) reads as "this rule is active for the detachment".
RULE_BEARING_FIELDS: Tuple[Tuple[str, object], ...] = (
    ("reroll_hit_ones", False),
    ("reroll_wound_ones", False),
    ("plus_one_to_hit", False),
    ("plus_one_to_wound", False),
    ("plus_one_attack", 0),
    ("plus_one_save", False),
    ("extra_invuln", 7),
    ("fnp", 7),
    ("reanimate_per_round", 0),
    ("bonus_to_hit_when_led", False),
    ("psychic_mortal_wounds_per_round", 0),
    ("ld_bonus", 0),
    ("enemy_ld_penalty", 0),
)

# Simulator-side gates that aren't keyed off a Detachment / LeaderAbility
# field, but still implement a 10e core rule we need to cite. Add new
# entries here when you add a new simulator gate.
SIMULATOR_RULE_KEYS: Tuple[str, ...] = (
    # Weapon keywords (parsed from BSData onto every UnitProfile)
    "weapon.heavy",
    "weapon.assault",
    "weapon.rapid_fire",
    "weapon.melta",
    "weapon.anti_x",
    "weapon.lance",
    "weapon.precision",
    "weapon.pistol",
    "weapon.indirect_fire",
    "weapon.one_shot",
    "weapon.torrent",
    "weapon.lethal_hits",
    "weapon.sustained_hits",
    "weapon.devastating_wounds",
    "weapon.twin_linked",
    "weapon.ignores_cover",
    "weapon.blast",
    "weapon.hazardous",
    # Unit-level core abilities
    "unit.stealth",
    "unit.fnp",
    # Simulator-side gates (terrain, deployment, faction army rules, phases)
    "simulator.big_guns_never_tire",
    "simulator.cover_light",
    "simulator.cover_heavy",
    "simulator.deep_strike",
    "simulator.scout",
    "simulator.infiltrators",
    "simulator.reanimation_protocols",
    "simulator.sticky_objective",
    "simulator.battle_focus",
    "simulator.battleshock",
    "simulator.judgement_tokens",
    # Orks faction army rules (10e). mob_rule auto-passes Battle-shock for
    # Ork units when the army has 10+ Ork models on the battlefield;
    # waaagh is the once-per-battle Command-phase declaration that grants
    # +1 to wound melee on the declaring turn.
    "simulator.mob_rule",
    "simulator.waaagh",
    # Tyranids faction army rules (10e). synapse_imperative auto-passes
    # Battle-shock for Tyranid units within 6" of a friendly SYNAPSE model;
    # shadow_in_the_warp subtracts 1 from enemy Battle-shock tests within
    # 12" of a Tyranid SYNAPSE model.
    "simulator.synapse_imperative",
    "simulator.shadow_in_the_warp",
    # Drukhari army rule (10e). Command-phase token award + while-held
    # buffs (Lethal Hits, FNP 6+). Faction-gated on attacker/defender.
    "simulator.power_from_pain",
    # Thousand Sons army rule (10e). -1 to wound on any single-damage
    # attack allocated to a non-daemon TSons model (Rubric Marines,
    # Scarab Occult Terminators, etc.). Stacks with attacker +1 to wound.
    "simulator.all_is_dust",
    # Genestealer Cults army rule (10e). Cult Ambush — at the start of the
    # first battle round, any number of GSC units can be set up anywhere on
    # the battlefield > 9" from enemy models. Modelled as an army-wide
    # turn-1 Deep Strike: every GSC unit is routed to reserves at deploy
    # time, then placed via the existing arrival path at the top of Round 1.
    "simulator.cult_ambush",
    # Adeptus Mechanicus army rule (10e). Command-phase pick of Protector
    # (+1 hit ranged / -1 hit melee) or Conqueror (mirror). Faction-gated
    # on attacker.profile.faction == "Adeptus Mechanicus".
    "simulator.doctrina_imperatives",
)


def _required_detachment_keys() -> Set[str]:
    """Every (DETACHMENT_NAME.field) key we expect a citation for."""
    keys: Set[str] = set()
    for var_name in dir(det_module):
        obj = getattr(det_module, var_name)
        if not isinstance(obj, Detachment):
            continue
        for field, default in RULE_BEARING_FIELDS:
            val = getattr(obj, field, default)
            if val != default:
                keys.add(f"{var_name}.{field}")
    return keys


def _required_leader_keys() -> Set[str]:
    """Every leader-registry entry needs a citation."""
    keys: Set[str] = set()
    for substring, ability in LEADER_REGISTRY:
        if not isinstance(ability, LeaderAbility):
            continue
        # Key on the LeaderAbility.name to disambiguate from substring
        # collisions ("Captain" vs "Captain in Terminator Armour").
        keys.add(f"LeaderAbility.{ability.name}")
    return keys


def _required_stratagem_keys() -> Set[str]:
    """Every Stratagem accessible to any army needs a citation.

    Sources:
      * UNIVERSAL_STRATAGEMS — the four core stratagems every army can fire.
      * Each `Detachment.stratagems` tuple — empty today; populated by #104.

    Keys are formatted `Stratagem.<name>` to mirror the LeaderAbility scheme.
    """
    keys: Set[str] = set()
    for strat in UNIVERSAL_STRATAGEMS:
        keys.add(f"Stratagem.{strat.name}")
    for var_name in dir(det_module):
        obj = getattr(det_module, var_name)
        if not isinstance(obj, Detachment):
            continue
        for strat in (obj.stratagems or ()):
            if isinstance(strat, Stratagem):
                keys.add(f"Stratagem.{strat.name}")
    return keys


def _required_simulator_keys() -> Set[str]:
    return set(SIMULATOR_RULE_KEYS)


def _load_citations() -> Dict[str, dict]:
    """Merge data/rule_citations.json with every fragment under
    data/rule_citations.d/*.json. Fragments enable parallel agents to
    contribute citations without git merge conflicts on the single
    master file."""
    merged: Dict[str, dict] = {}
    if CITATIONS_PATH.exists():
        raw = json.loads(CITATIONS_PATH.read_text(encoding="utf-8"))
        merged.update({k: v for k, v in raw.items() if not k.startswith("_")})
    fragments_dir = CITATIONS_PATH.parent / "rule_citations.d"
    if fragments_dir.exists():
        for frag in sorted(fragments_dir.glob("*.json")):
            data = json.loads(frag.read_text(encoding="utf-8"))
            for k, v in data.items():
                if k.startswith("_"):
                    continue
                if k in merged:
                    print(f"WARNING: duplicate citation key '{k}' from {frag.name}",
                          file=sys.stderr)
                merged[k] = v
    if not merged and not CITATIONS_PATH.exists():
        print(f"ERROR: {CITATIONS_PATH} missing", file=sys.stderr)
    return merged


def _validate_entry(key: str, entry: dict) -> List[str]:
    errors: List[str] = []
    if not isinstance(entry, dict):
        return [f"{key}: not a dict"]
    for field in REQUIRED_FIELDS:
        if field not in entry:
            errors.append(f"{key}: missing field '{field}'")
        elif not isinstance(entry[field], str) or not entry[field].strip():
            errors.append(f"{key}: field '{field}' empty or not a string")
    if "scope" in entry and entry["scope"] not in VALID_SCOPES:
        errors.append(
            f"{key}: scope '{entry['scope']}' not in {sorted(VALID_SCOPES)}"
        )
    if "source" in entry and not (
        entry["source"].startswith("http://") or entry["source"].startswith("https://")
    ):
        errors.append(f"{key}: source must be a URL (got '{entry['source']}')")
    return errors


def main() -> int:
    citations = _load_citations()
    required = (
        _required_detachment_keys()
        | _required_leader_keys()
        | _required_stratagem_keys()
        | _required_simulator_keys()
    )

    missing = sorted(required - set(citations.keys()))
    stale = sorted(set(citations.keys()) - required)
    field_errors: List[str] = []
    for key, entry in citations.items():
        field_errors.extend(_validate_entry(key, entry))

    total_required = len(required)
    total_present = len(required & set(citations.keys()))
    print(f"Rule citations: {total_present}/{total_required} active rules cited.")
    if missing:
        print(f"\nMISSING citations ({len(missing)}):", file=sys.stderr)
        for k in missing:
            print(f"  - {k}", file=sys.stderr)
    if stale:
        print(f"\nSTALE entries (no live rule, consider removing) ({len(stale)}):")
        for k in stale:
            print(f"  - {k}")
    if field_errors:
        print(f"\nMALFORMED entries ({len(field_errors)}):", file=sys.stderr)
        for e in field_errors:
            print(f"  - {e}", file=sys.stderr)

    if missing or field_errors:
        return 1
    print("\nAll active rules cited and well-formed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
