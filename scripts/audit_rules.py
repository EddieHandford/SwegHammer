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
from code.enhancements import ENHANCEMENTS
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
    # Keyword-gated second-detachment buffs (#126).
    ("vehicles_reroll_hit_ones", False),
    ("canoptek_plus_one_to_wound", False),
    ("aspect_warrior_or_bike_plus_one_move", False),
    ("plague_marines_plus_one_to_wound", False),
    # Warhost (Aeldari) detachment rule (#197 — replaces the previous
    # reroll_hit_ones approximation with the real Martial Grace Battle
    # Focus token buff).
    ("martial_grace", False),
    # Mont'ka (T'au Empire) Killing Blow detachment rule (#196). Two flags,
    # both round-gated to battle rounds 1-3 in the simulator. The Lethal
    # Hits on Guided half is flagged for citation completeness but not yet
    # read by Unit.attack — SwegHammer has no Markerlight / Guided mechanic.
    ("army_wide_assault_rounds_1_3", False),
    ("lethal_hits_on_guided", False),
    # Death Guard Virulent Vectorium detachment rule (#195).
    ("worldblight_sticky_dg_objectives", False),
    # Orks War Horde detachment rule (iter-1 Cluster B B1 fix). Army-wide
    # [SUSTAINED HITS 1] on Ork melee weapons via Get Stuck In.
    ("melee_sustained_hits_army_wide", False),
    # Adeptus Custodes Shield Host detachment rule (Martial Ka'tah /
    # Martial Mastery, iter-8 fix). Replaces the iter-0 `plus_one_save`
    # defensive approximation with the canonical offensive Crit-on-5+
    # melee + melee AP+1 dual buff. APPROXIMATION: codex picks ONE bullet
    # per round; SwegHammer applies BOTH always-on.
    ("melee_crit_on_5_plus_hits", False),
    ("melee_ap_plus_one", False),
    # Astra Militarum Combined Arms detachment rule (Born Soldiers,
    # iter-14 fix). Real-rule LETHAL HITS on REGIMENT-vs-non-V/M and
    # SQUADRON-vs-V/M ranged attacks. Replaces the iter-0
    # `plus_one_to_hit` over-broad approximation.
    ("am_born_soldiers_lethal_hits", False),
    # Thousand Sons Rubricae Phalanx detachment rule (iter15). Real-rule
    # +1 to armour save vs unmodified D1 attacks on RUBRICAE models.
    # Replaces the iter-14 always-firing APPROXIMATION (All Is Dust now
    # gates on this detachment flag) — see RUBRICAE_PHALANX.all_is_dust
    # in data/rule_citations.d/detachments.json.
    ("all_is_dust", False),
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
    # 10e core "greater Level of Control" rule — applies to objective scoring
    # and sticky-claim promotion (`_score_objectives`, `_sticky_owner`).
    "simulator.objective_control_strictly_greater",
    "simulator.battle_focus",
    # Aeldari army rule (10e). Strands of Fate — 6D6 rolled at start of
    # battle into Army.fate_dice; each die later substituted for one d6
    # roll made by/against an AELDARI unit (hit, wound, save, charge,
    # advance, Battle-shock). Pool depletes per spend. Greedy AI fires
    # the substitution only when it flips a fail -> success.
    "simulator.strands_of_fate",
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
    # Death Guard army-wide FNP 5+ was a fabrication (no such rule exists
    # in the 10e codex per Wahapedia + Goonhammer review). Removed in
    # iter 15. Per-datasheet innate FNP (Plague Marines fnp=5, Deathshroud
    # fnp=4, Mortarion fnp=5) lives on profile.fnp via overrides.json /
    # parsed.json and is honoured by Unit.receive_damage already. The
    # Virulent Vectorium 2 CP "Disgustingly Resilient" stratagem is cited
    # separately under `Stratagem.Disgustingly Resilient`.
    # Death Guard army rule (10e). Nurgle's Gift / Contagions of Nurgle —
    # every DG model projects a 3" aura that subjects enemy units within
    # it to the active Contagion (radius gated to 3" per modern Nurgle's
    # Gift / Afflicted rule; older index rule was 6"). APPROXIMATION:
    # SwegHammer retains the older 3-round escalating shape: round 1 -1 T
    # (via +1 to wound in Unit.attack), round 2 -1 Ld (battleshock in
    # _run_round), round 3+ -1 to hit on enemy attackers near a DG model
    # (Unit.attack). Faction-gated on the DG aura source; never debuffs
    # DG units themselves; the round-3+ -1 to hit doesn't compound with
    # other -1-to-hit modifiers (10e cap).
    "simulator.contagions_of_nurgle",
    # Chaos Daemons army rule (10e). Shadow of Chaos — enemy units within
    # the Shadow of Chaos take Battle-shock at -1 AND, on a failed test,
    # suffer D3 mortal wounds. APPROXIMATION: the canonical zone-based
    # trigger (deployment zone + objective-gated No Man's Land + Greater
    # Daemon 6" aura) is proxied as 'within 18" of board centre while a
    # Chaos Daemons opponent has any unit alive'. See
    # data/rule_citations.d/chaos_daemons.json.
    "simulator.shadow_of_chaos",
    # Thousand Sons Rubricae Phalanx detachment rule (10e current codex).
    # +1 to the armour save when an unmodified Damage-1 attack is allocated
    # to a RUBRICAE-keyword model. APPROXIMATION (iter14): SwegHammer
    # applies the buff regardless of which TSON detachment is active, since
    # only Grand Coven is in the registry today. See
    # data/rule_citations.d/thousand_sons.json#simulator.all_is_dust.
    "simulator.all_is_dust",
    # Thousand Sons Scarab Occult Terminators datasheet ability (10e). -1
    # to the wound roll on any attack targeting the unit while it contains
    # a PSYKER model. The mandatory Aspiring Sorcerer is the PSYKER carrier
    # so the buff is effectively always-on. See
    # data/rule_citations.d/thousand_sons.json#simulator.rites_of_coalescence.
    "simulator.rites_of_coalescence",
    # Adeptus Custodes Custodian Wardens datasheet ability (10e). -1 to
    # the wound roll on any attack targeting the led Wardens unit when
    # attack S > target T. Three-way gate in Unit.attack: defender has
    # `resolute_will`, defender is actually led (host_keys check via
    # leaders.is_actually_led), attack.strength > defender.toughness.
    # See data/rule_citations.json#simulator.resolute_will.
    "simulator.resolute_will",
    # AI threat-score heuristic in `code/strategy.py._durability` folds the
    # defender's resolved Feel No Pain value into the durability denominator
    # so opponent target selection correctly reads FNP-bearing defenders as
    # harder targets. Iter 26 S1 (re-landed in iter 31 S1R). Cited as
    # `simulator.fnp_in_threat_score`.
    "simulator.fnp_in_threat_score",
    # AI threat-score heuristic in `code/strategy.py._durability` applies a
    # multiplicative squad-size durability bonus so high-model-count units
    # (Boyz mobs, Termagant broods, Cultist swarms) look harder to wipe from
    # a single-attack-decision perspective. Paired compensation for the
    # iter26-S1 FNP re-land. Iter 31 S1R. Cited as
    # `simulator.squad_size_durability_factor`.
    "simulator.squad_size_durability_factor",
    # Thousand Sons army rule (10e) — Cabal of Sorcerers. At start of
    # Shooting phase, each PSYKER attempts one of four Rituals via a
    # 2D6 Psychic test against the Ritual's Warp Charge. Real BSData
    # verbatim quoted in thousand_sons.json. Each Ritual is a separate
    # citation (Doombolt WC7, Temporal Surge WC6, Destiny's Ruin WC5,
    # Twist of Fate WC9) so the auditor can track which are wired vs
    # which are no-op approximations.
    "simulator.cabal_of_sorcerers",
    "simulator.ritual_doombolt",
    "simulator.ritual_temporal_surge",
    "simulator.ritual_destinys_ruin",
    "simulator.ritual_twist_of_fate",
    # Thousand Sons EPIC HERO Magnus the Red datasheet ability (10e).
    # "Lord of the Planet of the Sorcerers (Psychic)" — Magnus attempts
    # up to 2 Rituals per turn (vs 1 for every other PSYKER) and adds +2
    # to each of his 2D6 Psychic test results. Wired in
    # `_run_cabal_rituals` + `_cabal_attempt_ritual`. Cited in
    # data/rule_citations.d/thousand_sons.json. iter20 fix to close the
    # iter18/19 Magnus-under-performer gap.
    "simulator.magnus_lord_of_the_planet",
    # Thousand Sons EPIC HERO Magnus the Red datasheet ability (10e).
    # "Unearthly Power" — picks one of three Crimson King abilities per
    # round. Default-pick Impossible Form (-1 to incoming Damage,
    # excluding Psychic Attacks). Wired in `_run_round` after
    # `_run_cabal_rituals`. iter21 fix.
    "simulator.magnus_unearthly_power_impossible_form",
    # Thousand Sons EPIC HERO Ahriman datasheet ability (10e).
    # "Arch-Sorcerer of Tzeentch (Psychic)" — +1 to each Cabal of
    # Sorcerers Ritual Psychic test result. Wired in `_run_cabal_rituals`
    # alongside Magnus's +2/2-attempt logic. iter21 fix.
    "simulator.ahriman_arch_sorcerer",
    # Genestealer Cults army rule (10e). Cult Ambush — at the start of the
    # first battle round, any number of GSC units can be set up anywhere on
    # the battlefield > 9" from enemy models. Modelled as an army-wide
    # turn-1 Deep Strike: every GSC unit is routed to reserves at deploy
    # time, then placed via the existing arrival path at the top of Round 1.
    "simulator.cult_ambush",
    # Genestealer Cults Cult Ambush — Resurgence-point unit revival half
    # of the army rule (10e). End-of-round hook revives one dead CULT
    # INFANTRY unit per round at full Starting Strength, costing a flat
    # 3 Resurgence points (median of the codex per-unit table). Marker
    # placement, opponent-side disruption, and the per-Starting-Strength
    # cost table are NOT modelled — APPROXIMATION proxy.
    "simulator.cult_ambush_resurgence",
    # Adeptus Mechanicus army rule (10e). Command-phase pick of Protector
    # (+1 hit ranged / -1 hit melee) or Conqueror (mirror). Faction-gated
    # on attacker.profile.faction == "Adeptus Mechanicus".
    "simulator.doctrina_imperatives",
    # Core targeting restrictions (10e core rules). Both filter the ranged
    # candidate list inside Battle._do_shoot via code.army.can_target_for_ranged.
    # Look Out Sir gates non-MONSTER/VEHICLE CHARACTERS that have a non-CHARACTER
    # friendly within 3"; Lone Operative is a unit-level keyword that hard-caps
    # ranged targeting to 12".
    "simulator.look_out_sir",
    "simulator.lone_operative",
    # PRECISION keyword (10e core weapon ability). When the attacker carries
    # a PRECISION-tagged ranged weapon (unit-level `precision` flag, collapsed
    # by the mapper from BSData weapon keywords), the Look Out Sir bodyguard
    # gate inside code.army.can_target_for_ranged is bypassed — equivalent of
    # the real rule's wound-allocation override against attached CHARACTERS.
    # Lone Operative is NOT bypassed.
    "simulator.precision_keyword",
    # World Eaters army rule (10e). Blood Tithe: 1 BT awarded per friendly
    # WE death OR enemy unit destroyed by a WE unit; spent at the start of
    # any phase on benefits (1=re-roll charge, 2=+1 to wound vs target,
    # 3=+1 CP, 4=Lethal Hits on a WE unit for the phase, 5=auto-pass next
    # Battle-shock). Faction-gated on attacker.profile.faction == "World
    # Eaters" for the Lethal Hits buff; awards run off victim/killer army
    # checks in the kill-emission code paths.
    "simulator.blood_tithe",
    # Deadly Demise X (10e core). When a model with this ability is
    # destroyed, roll 1D6; on a 6 each unit within 6" suffers X mortal
    # wounds. Mapper parses the X from BSData infoLink modifiers.
    "simulator.deadly_demise",
    # Fall Back move (10e core). A unit within Engagement Range may move
    # up to M\" in the Movement phase and pass through enemy models; it
    # cannot shoot or charge that turn unless it has the FLY keyword.
    "simulator.fall_back",
    # Desperate Escape test (10e core). After a Fall Back that passed
    # through enemy models, roll 1D6 per model; each 1 destroys one model.
    "simulator.desperate_escape",
    # Adeptus Astartes Oath of Moment army rule (10e). At the start of each
    # Command phase the Marine army picks one enemy unit; Marine attacks
    # against that unit re-roll both the Hit roll and the Wound roll (any
    # failure, not just 1s). Faction-gated via code.factions.is_marine_faction
    # so every chapter codex inherits the rule.
    "simulator.oath_of_moment",
    # Adeptus Astartes Combat Doctrines (Gladius Task Force detachment, 10e).
    # Round-rotating +1 to wound: Devastator R1 (ranged), Tactical R2 (both),
    # Assault R3+ (melee). Faction-gated to Marines AND detachment-gated to
    # "Gladius Task Force" — Ironstorm Spearhead gets nothing here.
    "simulator.combat_doctrines",
    # Transports (10e core). Four sub-mechanics: embark (pre-game and end-of-
    # move), disembark (start of own Movement phase, transport hasn't moved),
    # firing_deck (X passenger weapons fire alongside the transport), and
    # destroyed_transport (force-disembark + 1D6-per-model on a 1).
    "simulator.embark",
    "simulator.disembark",
    "simulator.firing_deck",
    "simulator.destroyed_transport",
    # T'au Empire Markerlights → Guided (10e army-wide army rule). At the
    # start of each Shooting phase, MARKERLIGHT-keyword units mark enemies
    # as Guided; while the active detachment carries lethal_hits_on_guided
    # (Mont'ka), T'au ranged attackers gain [LETHAL HITS] against Guided
    # targets. Plumbed via Army.guided_enemy_uids, Battle._run_markerlight_phase,
    # and the effective_lethal_hits gate in Unit.attack.
    "simulator.markerlights",
    # T'au Empire Markerlight weapon-ability emission gates (iter27-M1).
    # Per-carrier Hit roll against the firing model's BS, plus line-of-sight
    # and 36" range gates and the can_target_for_ranged (Look Out Sir /
    # Lone Operative) check. Replaces the pre-iter27 auto-Guided pipeline
    # which gave every MARKERLIGHT-keyword unit a free mark with no roll.
    "simulator.markerlight_emission",
    # Iter-4 A5 (faction-neutral AI heuristic): cap the number of detachment
    # stratagems any one army may fire per Command phase. 10e core has no
    # hard cap, but real-player CP economy averages ~1 stratagem per
    # Command phase; without the cap, CP-rich detachments stack 3-5+ buffs
    # at round start. Enforced inside `Battle._apply_detachment_stratagems`
    # via Army.stratagems_fired_this_command_phase + `_strat_cap_reached`.
    "simulator.stratagem_per_command_phase_cap",
    # 10e core EPIC HERO rule. "EPIC HERO units can only be taken once per
    # army." Universal across every codex; the cap is faction-neutral.
    # Enforced at army-composition time by code.army_builder.is_epic_hero
    # gates in build_random_army, build_faction_random_army, and
    # code.archetypes._random_fill (which also seeds the tracker from
    # template-instantiated units so the random topup can't duplicate a
    # hero the archetype already drafted).
    "simulator.epic_hero_one_per_army",
    # 10e Ruins terrain core rule. A Ruin acts as Heavy Cover (+1 save,
    # -1 to hit) and its walls block line of sight EXCEPT when both the
    # firing model and the target model have the INFANTRY, BEAST or SWARM
    # keyword. Wired through code.map.Map.has_line_of_sight via
    # attacker_keywords / target_keywords arguments threaded from the
    # simulator's _do_shoot / _apply_firing_deck call sites. Cover
    # promotion handled alongside TerrainType.HEAVY_COVER in
    # Battle._do_shoot.
    "terrain.ruin_infantry_los",
    # 10e core-rules cap: "Hit roll modifiers are cumulative, but the Hit
    # roll for an attack can never be modified by more than -1 or +1." Same
    # text for the Wound roll. Enforced in code/units.py Unit.attack by
    # accumulating +/-1 contributions into hit_mod_delta / wound_mod_delta
    # then clamping to [-1, +1] before applying to the d6 target.
    "simulator.modifier_cap_plus_minus_one",
    # 10e core-rules cap on Save characteristic: "When all the relevant
    # modifiers have been applied, the modified characteristic or roll
    # cannot be more than +1 better than the unmodified [...]." Enforced
    # in code/units.py Unit.attack by counting +1-save sources and
    # applying at most one -1 to save_after_ap. AP is NOT a modifier and
    # stacks freely with the capped +1.
    "simulator.save_modifier_cap_plus_minus_one",
    # 10e core Charge phase: Heroic Intervention is a FREE core ability
    # for CHARACTER models (not a stratagem). Implemented in
    # `Battle._do_heroic_intervention`.
    "simulator.heroic_intervention_core",
    # 10e core Fight phase: each unit makes a free Pile-In (3" toward
    # closest enemy) BEFORE it fights and a free Consolidate (3" toward
    # closest enemy / staying in engagement) AFTER it fights.
    "simulator.pile_in",
    "simulator.consolidate",
    # 10e Leviathan Tournament Companion primary scoring cap: each army
    # scores at most 15 Primary VP per battle round (i.e. counts at most
    # 3 controlled objectives at 5 VP each). Applied in
    # `Battle._score_objectives` after per-objective awards are tallied.
    "simulator.primary_vp_cap_15",
    # SC4-A — 10e Pariah Nexus Fixed Secondary Missions. Bring it Down
    # (5 VP per enemy MONSTER/VEHICLE destroyed this round, capped 15)
    # and No Prisoners (5 VP per enemy unit destroyed this round, capped
    # 15). Wired in `Battle._score_secondaries`, called once per round
    # after `_score_objectives`. Pairs the per-round delta against a
    # round-start snapshot captured in `_run_round`.
    "simulator.secondary_bring_it_down",
    "simulator.secondary_no_prisoners",
    # SC4-B — position-tracking Pariah Nexus tactical secondaries.
    # Engage on All Fronts (5 VP if alive units span 3+ quadrants)
    # and Behind Enemy Lines (5 VP if any alive unit in enemy DZ).
    # Wired in `Battle._score_secondaries` alongside the SC4-A kill
    # secondaries.
    "simulator.secondary_engage_on_all_fronts",
    "simulator.secondary_behind_enemy_lines",
    # SC4-C — selective-kill Pariah Nexus Fixed secondaries.
    # Cull the Horde (5 VP per destroyed 10+model unit, cap 5/round)
    # and Assassination (5 VP per destroyed CHARACTER, cap 10/round).
    # Wired in `Battle._score_secondaries` via `score_round_delta`
    # returning the full 4-tuple.
    "simulator.secondary_cull_the_horde",
    "simulator.secondary_assassination",
    # CUSTODES-UNPARK — elite-army defender modifier on the kill-event
    # Pariah Nexus secondaries (Bring it Down, No Prisoners, Assassination).
    # Faction-gated to Adeptus Custodes. Cull the Horde is excluded
    # (Custodes never concedes Cull regardless of multiplier). Applied
    # in `secondaries.score_round_delta` via the defender_faction param
    # passed from `Battle._score_secondaries`.
    "simulator.secondary_elite_army_modifier",
    # LC-2 — Tactical Secondary Mission deck-draw mechanic. Gates
    # Engage / BEL behind a per-round alternating schedule per side
    # so each side scores at most one Tactical per round, matching
    # real Pariah Nexus 2-of-9 average coverage.
    "simulator.tactical_secondary_deck_draw",
    # LC-5 — Warlord designation. First CHARACTER in deploy order is
    # the Warlord; killing it grants +1 Assassination VP per real
    # Pariah Nexus rule.
    "simulator.warlord_designation",
    # Astra Militarum Voice of Command (army rule, 10e). At the start of
    # each Command phase, each AM OFFICER (CHARACTER) issues one Order to
    # an eligible BATTLELINE INFANTRY (REGIMENT) target within 6". Four
    # Orders are wired: Take Aim! (+1 to hit shooting), Fix Bayonets!
    # (+1 to wound melee, codex WS+1 approximation), First Rank Fire /
    # Second Rank Fire (+1 to hit shooting, codex +1 Attack on Rapid Fire
    # approximation), Take Cover! (+1 to save). Implemented in
    # `code.orders.dispatch_orders`; called from `Battle._run_round` at
    # the start of each Command phase. The Flexible Command stratagem
    # (Combined Arms, 2 CP) widens the eligible target set to include
    # BATTLELINE VEHICLE (SQUADRON) for the round it fires.
    "simulator.voice_of_command_orders",
    # The four wired Orders, each cited individually so the auditor can
    # track per-Order APPROXIMATION notes (Fix Bayonets! and FRFSRF are
    # approximations through different transient flags than the codex
    # text indicates).
    "Order.Take Aim!",
    "Order.Fix Bayonets!",
    "Order.First Rank, Fire! Second Rank, Fire!",
    "Order.Take Cover!",
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


def _required_enhancement_keys() -> Set[str]:
    """Every Enhancement registered in `code.enhancements.ENHANCEMENTS` needs
    a citation. Key format: `Enhancement.<name>` (matches the Stratagem and
    LeaderAbility schemes already used by the auditor)."""
    return {f"Enhancement.{e.name}" for e in ENHANCEMENTS.values()}


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
        | _required_enhancement_keys()
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
