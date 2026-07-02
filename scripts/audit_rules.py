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
    # Necrons Cursed Legion — Relentless Onslaught (Abilities #1,
    # claude/sim-calibration-6). Two clauses on one flag: +1 to Hit vs
    # objective-marker targets (Unit.attack) and [ASSAULT] on NECRONS VEHICLE /
    # MOUNTED (non-TITANIC) ranged weapons (simulator._do_shoot). Detachment-flag
    # citation: CURSED_LEGION.relentless_onslaught; simulator-gate citation:
    # simulator.relentless_onslaught (below). See
    # data/rule_citations.d/necrons.json.
    ("relentless_onslaught", False),
    # IK-KNIGHTS-V1 (2026-05-31): Imperial Knights Valourstrike Lance
    # detachment rules. Bold Gallantry grants [ASSAULT] to IK ranged weapons
    # on Advance. Bondsman abilities buff Armigers each Command phase.
    ("bold_gallantry", False),
    ("bondsman_enabled", False),
    # IK-KNIGHTS-V1 (2026-05-31): Chaos Knights Iconoclast Fiefdom detachment
    # rule. Dread Tyrants Aura grants reroll-hit-ones + reroll-wound-ones to
    # War Dogs within 9" of a friendly TITANIC CK unit.
    ("dread_tyrants_aura", False),
    # Chaos Daemons Daemonic Incursion — Warp Rifts (wave 221). Reduces the
    # Deep Strike minimum gap from 9" to 6" for Chaos Daemons units arriving
    # under this detachment (gated SWEG_WARP_RIFTS). Cited as
    # `simulator.warp_rifts` in data/rule_citations.d/chaos_daemons.json.
    ("warp_rifts", False),
    # Adepta Sororitas Hallowed Martyrs — The Blood of Martyrs (wave 234).
    # Damage-gated hit and wound bonus: +1 Hit when below Starting Strength,
    # +1 Wound when below Half-strength (both ranged and melee). Squad
    # substrate (squad_id / _squad_start_count) gates the multi-model path;
    # wound-fraction fallback for single-model units. Cited as
    # `HALLOWED_MARTYRS.soror_blood_of_martyrs` in
    # data/rule_citations.d/detachments.json.
    ("soror_blood_of_martyrs", False),
    # Adepta Sororitas Bringers of Flame — Fervent Purgation [ASSAULT] leg.
    # All Adepta Sororitas ranged weapons gain [ASSAULT] (unconditional, no
    # round gate). Read by simulator._do_shoot Advance-lockout; gated
    # SWEG_BOF_ASSAULT (default OFF). Cited as
    # `BRINGERS_OF_FLAME.army_wide_assault` in
    # data/rule_citations.d/detachments.json.
    ("army_wide_assault", False),
    # Astra Militarum Grizzled Company — Ruthless Discipline (Grotmas
    # December 2025 detachment). Two clauses on one flag: +1 to every
    # Officer's per-round Order cap (code/orders.py dispatch_orders) and a
    # re-roll of Hit rolls of 1 on both ranged and melee attacks made by a
    # unit affected by an Order (code/orders.py _apply_order stamps
    # transient_affected_by_order; code/units.py Unit.attack reads it).
    # Gated SWEG_AM_GRIZZLED (default OFF). Cited as
    # `GRIZZLED_COMPANY.grizzled_ruthless_discipline` and
    # `simulator.grizzled_ruthless_discipline` in
    # data/rule_citations.d/astra_militarum.json.
    ("grizzled_ruthless_discipline", False),
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
    # Core 10e damage allocation: each unsaved wound is allocated to one model
    # (finishing a wounded model first); a destroyed model's excess damage is
    # lost, so kills are bounded by unsaved-wound count. Implemented as the
    # squad-spillover allocation pointer in Unit.attack. See
    # data/rule_citations.d/core_damage_allocation.json.
    "simulator.damage_allocation_spillover",
    # Core 10e Unit Coherency: a unit's models must stay within 2" of another
    # model in their unit, so a coherent unit sits on ~one objective. Drives
    # squad-clustered deployment (Battle._deploy_line) and per-unit Objective
    # Control (Battle._score_objectives credits each squad to one objective).
    # See data/rule_citations.d/core_coherency.json.
    "simulator.unit_coherency",
    # Core 10e mortal wounds: unlike normal damage, excess mortal wounds carry
    # over to the next model of the same unit until all are allocated or the
    # unit is destroyed. Implemented as Battle._apply_mortal_wounds and routed
    # through every "unit suffers X mortal wounds" site. See
    # data/rule_citations.d/core_damage_allocation.json.
    "simulator.mortal_wound_spillover",
    "simulator.big_guns_never_tire",
    "simulator.cover_light",
    "simulator.cover_heavy",
    "simulator.deep_strike",
    "simulator.scout",
    "simulator.infiltrators",
    # INTELLIGENT-DEPLOYMENT (env-gated SWEG_DEPLOY). AI tactical heuristic,
    # NOT a 10e game rule: when set, each army's standard on-board units are
    # split by generic unit character (Battle._split_screen_back, reusing
    # code.roles.classify) into a forward SCREEN group (cheap high-model-count
    # chaff + forward melee) deployed at the deployment zone's inner / mid-board
    # edge, and a rear HIGH-VALUE group (gunlines, durable bricks, characters,
    # the top damage dealer) deployed at the army's board edge. Both rows stay
    # wholly inside the army's own deployment zone. Default OFF reproduces the
    # legacy single-line deploy byte-for-byte. Faithful competitive screening,
    # even-handed (faction-neutral). See
    # data/rule_citations.d/intelligent_deployment.json.
    "simulator.intelligent_deployment",
    "simulator.reanimation_protocols",
    "simulator.sticky_objective",
    # 10e core "greater Level of Control" rule — applies to objective scoring
    # and sticky-claim promotion (`_score_objectives`, `_sticky_owner`).
    "simulator.objective_control_strictly_greater",
    # 10e core "Measuring Distances" — range to an objective marker is measured
    # to the closest point of a model's base; gated SWEG_COLLISION base-edge
    # Objective Control contest in `_assign_army_oc` (fixes the big-base
    # entrenchment eviction artifact under no-overlap collision).
    "simulator.objective_control_base_range",
    # 10e core "Making a Move" — a model may be moved THROUGH friendly models but
    # not through enemy models, and may not end on top of a model; gated
    # SWEG_COLLISION friendly-pass-through / enemy-path-cap in `_move_toward`
    # (`_enemy_path_cap_t`), fixing the friend-blind self-jam.
    "simulator.collision_friendly_passthrough",
    # 10e core "Charge Move" + "Measuring Distances" — a charge move must end
    # within Engagement Range of every target, and Engagement Range (like all
    # distances) is measured between the CLOSEST POINTS OF THE BASES. Gated
    # SWEG_CHARGE_BASEEDGE base-edge charge-end placement in `_charge_baseedge_end`
    # / `_do_charge` (fixes the deep base interpenetration of big-based charge
    # targets the legacy centre-to-centre placement caused).
    "simulator.charge_end_base_to_base",
    # The MEASUREMENT half of the same rule (wave 241): the same gate controls
    # how the Engagement Range distance is MEASURED everywhere — fight
    # eligibility, the shooting melee-lock, Fall Back crossing, the charge-roll
    # requirement (`_er_gap` in code/sim/geometry.py and every caller).
    # Placement (`simulator.charge_end_base_to_base` above) and measurement
    # are two halves of one rule; shipping placement alone structurally
    # disabled melee under the adopted default.
    "simulator.engagement_range_base_edge",
    # 10e core "Charge Move" — a charge move must NOT move within Engagement
    # Range of any non-target enemy unit. Gated SWEG_CHARGE_PATH (default ON
    # since wave 242) in pick_charge_target (code/strategy.py): excludes candidates whose
    # straight-line path (part a, non-FLY only) or approximate end spot (part b,
    # all chargers) would cross or end within Engagement Range of a non-target.
    # FLY chargers are exempt from the path half (they move over enemy models).
    "simulator.charge_path_non_target",
    "simulator.battle_focus",
    # Aeldari army rule (10e). Strands of Fate — 6D6 rolled at start of
    # battle into Army.fate_dice; each die later substituted for one d6
    # roll made by/against an AELDARI unit (hit, wound, save, charge,
    # advance, Battle-shock). Pool depletes per spend. Greedy AI fires
    # the substitution only when it flips a fail -> success.
    "simulator.strands_of_fate",
    "simulator.battleshock",
    # Once-per-battle first-turn roll-off (10e mission sequence, gated
    # SWEG_ROLLOFF_ONCE) — registered so the citation is enforced, not stale.
    "simulator.first_turn_rolloff",
    # Action-economy Tactical action cards (Chapter Approved 2025-26, gated
    # SWEG_ACTION_ECONOMY) — registered so the citations are enforced, not stale.
    "simulator.secondary_establish_locus",
    "simulator.secondary_recover_assets",
    "secondaries.a_tempting_target",
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
    # Tyranids army rule (10e) — Shadow in the Warp forced Battle-shock test
    # (env-gated SWEG_SITW_TEST, default-OFF). The main half of the codex rule:
    # "each enemy unit on the battlefield must take a Battle-shock test" when
    # Shadow is unleashed. Forced regardless of below-half-strength. Implemented
    # in _apply_shadow_in_the_warp_forced_tests via the shared _battleshock_test_squad
    # helper. See data/rule_citations.d/tyranids.json.
    "simulator.shadow_in_the_warp_forced_test",
    # Drukhari army rule (10e). Command-phase token award + while-held
    # buffs (Lethal Hits, FNP 6+). Faction-gated on attacker/defender.
    "simulator.power_from_pain",
    # Drukhari Incubi "Tormentors" datasheet ability (env-gated
    # SWEG_DRUKHARI_TORMENTORS, default OFF): force a Battle-shock test on
    # enemy units within Engagement Range at Fight-phase start, and +1 to Hit
    # on Incubi melee attacks vs Battle-shocked targets.
    "simulator.drukhari_tormentors",
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
    # Chaos Daemons EPIC HERO Bloodthirster datasheet ability (10e).
    # "Relentless Carnage" — at the end of each Fight phase, the
    # Bloodthirster selects one enemy unit in 1" Engagement Range and
    # rolls 8D6; each 4+ inflicts 1 mortal wound (expected 4 per trigger,
    # FNP-eligible). Wired in `_apply_relentless_carnage`, fired once per
    # active player's fight pass after the regular fight ordering loop.
    # See data/rule_citations.d/chaos_daemons.json. DAEMONS-DIAG-5 fix
    # for the persistent -16.94pt Chaos Daemons gated under-perf at N=40
    # — the Bloodthirster's datasheet payload was wired only as the
    # Locus aura (+1 to hit) and was missing its end-of-phase mortal-
    # wound output despite being the Khorne archetype anchor.
    "simulator.relentless_carnage",
    # Chaos Daemons per-god army rules (10e). Murderer's Cowl (Khorne):
    # advance-and-charge eligibility; exempts the unit from the advance-
    # lockout-on-charge gate in _do_charge. Gloam Rot (Nurgle): -1 to wound
    # when attacker Strength > defender Toughness. Penumbral Puppetry
    # (Tzeentch): APPROXIMATION modelled via stealth (ranged-only), real rule
    # applies to all attacks. All three verified from BSData XML, Wahapedia
    # unreachable at implementation time. Cited in
    # data/rule_citations.d/chaos_daemons.json.
    "simulator.murderers_cowl",
    "simulator.gloam_rot",
    "simulator.penumbral_puppetry_approx",
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
    # Adeptus Mechanicus — Belisarius Cawl's "Invocation of Machine Vengeance"
    # Canticle (10e). Per-target designation mirroring Oath of Moment: while a
    # Belisarius Cawl model is alive, the AdMech player designates one enemy
    # unit each Command phase and friendly AdMech attacks re-roll the Hit roll
    # against it. Faction-gated on attacker.profile.faction == "Adeptus
    # Mechanicus" + the Cawl-alive gate in _pick_machine_vengeance_target.
    "simulator.machine_vengeance",
    # KNIGHTS-MULTIPROFILE-2 — ADDITIVE multi-weapon melee resolution. The
    # MUTEX counterpart `simulator.multi_profile_weapon_selection` (in
    # data/rule_citations.json) covers RANGED alt-modes; this key covers
    # the Fight-phase case where a datasheet carries MORE THAN ONE melee
    # weapon (Knight Abominant Electroscourge + Balemace; Knight Rampager
    # Reaper chainsword + Warpstrike claw) and the 10e [EXTRA ATTACKS]
    # core keyword. UnitProfile.extra_melee_profiles populated via
    # data/overrides.json today (BSData mapper does not yet emit it).
    # See data/rule_citations.d/chaos_knights.json#simulator.extra_melee_profiles.
    "simulator.extra_melee_profiles",
    # SWEG_CK_DREAD_FOCUS (default-on 2026-07-01). An AI target-selection
    # heuristic (not a separate rule): the Chaos Knights shooting picker prefers
    # Below-Half-strength enemy targets (_ck_dread_cascade_target_bonus,
    # code/strategy.py, 2.0x score multiplier), the class the Harbingers of Dread
    # / War Dog Executioner cascade rewards. Cited in
    # data/rule_citations.d/chaos_knights.json.
    "strategy.ck_dread_cascade_target",
    # SWEG_CK_RANGED_HOLD (default-on 2026-07-01). AI piloting heuristic (same as
    # simulator.am_advance_discipline, CK-scoped): Chaos Knights ranged platforms
    # (no extra_melee_profiles) hold and shoot instead of Advancing and forfeiting
    # their Shooting phase; melee platforms keep charging. Grounds in the core
    # Advance rule. Cited in data/rule_citations.d/chaos_knights.json.
    "simulator.ck_ranged_hold",
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
    # up to M\" in the Movement phase and pass through enemy models; until the
    # end of the turn it cannot shoot or declare a charge - there is NO FLY
    # exception (FLY only grants the move-over and the Desperate Escape skip).
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
    # SWEG_REEMBARK (default-off, HELD 2026-07-01). Mid-game voluntary re-embark
    # into a friendly transport within 3" after a unit's move — a piloting
    # extension of simulator.embark. Near-inert on the current archetype frame
    # (the 3" condition rarely holds); built + held. Cited in core_transports.json.
    "simulator.reembark",
    # Drukhari Skysplinter Assault detachment — Rain of Cruelty. When a
    # DRUKHARI unit disembarks from a TRANSPORT (voluntary or forced),
    # until the end of the turn its ranged weapons gain [IGNORES COVER]
    # and its melee weapons gain [LANCE]. Wired via transient per-unit
    # flags (`transient_lance_this_turn`,
    # `transient_ignores_cover_this_turn`) set in
    # `simulator._disembark` when the passenger is Drukhari AND the
    # army's detachment is Skysplinter Assault, cleared by the standard
    # transient-flag reset at the next round start.
    "simulator.skysplinter_rain_of_cruelty",
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
    # GATE 1 — SWEG_TAU_MARKERLIGHT_ALL_DETACH (default OFF). Bypasses the
    # lethal_hits_on_guided early-exit in Battle._run_markerlight_phase so the
    # base Markerlights army rule (Guided +1 to Hit + [SUSTAINED HITS 1]) runs
    # for ALL T'au detachments, not just the Mont'ka detachment that carries
    # the Lethal-Hits-on-Guided flag. The Mont'ka-specific [LETHAL HITS] still
    # only applies where that flag is set. Cited in
    # data/rule_citations.d/tau_empire.json.
    "simulator.tau_markerlight_all_detach",
    # GATE 2 — SWEG_TAU_MARKERLIGHT_BASE_LOS (default OFF). Gates the base
    # Guided buff on a line-of-sight marked set (Army.guided_los_enemy_uids,
    # built in _run_markerlight_phase without a per-carrier to-hit roll) rather
    # than the hit-roll-gated guided_enemy_uids set, matching the verbatim
    # "while targeting an enemy unit that is visible to one or more friendly
    # MARKERLIGHT units" condition. The Mont'ka [LETHAL HITS] consumer keeps
    # reading guided_enemy_uids. Cited in data/rule_citations.d/tau_empire.json.
    "simulator.tau_markerlight_base_los",
    # SWEG_TAU_MARKERLIGHT_IGNORES_COVER (default OFF). For the Greater Good grants
    # [IGNORES COVER] to a Guided attack against a Spotted unit marked by a
    # MARKERLIGHT Observer; modelled as a third OR-arm in the Unit.attack
    # ignore_cover boolean (guided_los_enemy_uids membership + T'au faction). A
    # companion AI target-bias _tau_guided_target_bonus concentrates fire on the
    # Spotted unit. Cited in data/rule_citations.d/tau_empire.json.
    "simulator.tau_markerlight_ignores_cover",
    # SWEG_TAU_NOVA_CHARGE (default-on 2026-07-01). Riptide once-per-battle
    # [DEVASTATING WOUNDS] (datasheet ability, BSData id 8fb6-aff7-75ac-f206),
    # via Battle._apply_nova_charge in the shooting activation. Cited in
    # data/rule_citations.d/tau_empire.json.
    "simulator.tau_nova_charge",
    # SWEG_CUSTODES_KATAH_LETHAL (default-on 2026-07-01). Martial Ka'tah RENDAX
    # stance [LETHAL HITS] on all Adeptus Custodes melee (the optimal stance the
    # sim models; BSData shared rule id e348-7090-3aff-ee2c). Unit.attack sets
    # effective_lethal_hits. Cited in data/rule_citations.d/adeptus_custodes.json.
    "simulator.custodes_katah_lethal",
    # SWEG_CUSTODES_ADVANCED_FIREPOWER. Caladius Grav-tank "Advanced Firepower"
    # (BSData profile id 60a4-507e-da36-683c): weapon-and-target-conditional
    # ranged [LETHAL HITS] (blaze cannon vs MONSTER/VEHICLE, accelerator cannon
    # vs everything else). Unit.attack sets effective_lethal_hits. Cited in
    # data/rule_citations.d/adeptus_custodes.json.
    "simulator.custodes_advanced_firepower",
    # SWEG_CUSTODES_MASTER_STANCES. Shield-Captain "Master of the Stances"
    # (BSData profile id e6a6-1d13-3027-3fce): once per battle the led unit
    # fights with BOTH Ka'tah stances — adds DACATARAI [SUSTAINED HITS 1] on
    # top of the modelled RENDAX. Battle._apply_master_of_stances. Cited in
    # data/rule_citations.d/adeptus_custodes.json.
    "simulator.custodes_master_of_stances",
    # SWEG_CUSTODES_SLAYERS_OF_TYRANTS. Allarus Custodians "Slayers of
    # Tyrants" (BSData profile id d569-61db-406d-1d42): re-roll the Wound roll
    # vs CHARACTER/MONSTER/VEHICLE targets, both modes, via the TWIN-LINKED
    # path (_effective_twin_linked). Cited in
    # data/rule_citations.d/adeptus_custodes.json.
    "simulator.custodes_slayers_of_tyrants",
    # SWEG_IK_CANIS_SINGLE. Canis Rex phantom-second-model fix: BSData folds
    # the ejected-pilot Sir Hekhtur into the Canis Rex entry as a second
    # model_loadouts slot, so the sim fielded two permanent 26-wound TITANIC
    # combatants in every Imperial Knights game. Loader gate sets the unit to
    # one model and drops the Hekhtur slot. Cited in
    # data/rule_citations.d/imperial_knights.json.
    "simulator.ik_canis_single",
    # SWEG_R5_SECOND_LAST. Chapter Approved 2025-26 round-5 going-second
    # primary-scoring timing (score at end of turn, not Command phase).
    # Battle._run_round_vanilla_turns. Cited in
    # data/rule_citations.d/core_primary_vp_cap.json.
    "simulator.primary_vp_round5_second_player",
    # SWEG_OC_PER_MARKER. Level of Control computed per marker (removes the
    # wave-67 one-marker-per-squad clamp). Battle._score_objectives
    # _assign_army_oc. Cited in data/rule_citations.d/core_win_condition.json.
    "simulator.oc_per_marker",
    # SWEG_FILL_TEMPLATE_POOL. Template-first random fill (evaluation-frame
    # list-realism mechanism from the 2026-07-01 archetype audit; owner-
    # authorized fidelity-first). code/archetypes.py _random_fill. Cited in
    # data/rule_citations.d/core_win_condition.json.
    "simulator.fill_template_pool",
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
    # 10e core TOWERING keyword terrain rule. When either the firing model or
    # the target model has the TOWERING (or AIRCRAFT) keyword, Woods / OBSCURING
    # terrain does not block the line of sight. TOWERING does NOT see over RUIN
    # walls (unlike Woods) - only AIRCRAFT gets a blanket Ruin pass, and a
    # TOWERING model sees out of a Ruin only when it is itself within it. Wired
    # in code.map._has_towering + code.map._los_query (towering flag skips the
    # OBSCURING block; ruin_pass is AIRCRAFT-only). See
    # data/rule_citations.d/core_terrain_ruins.json.
    "simulator.towering_los",
    # 10e Ruins terrain core rule. A Ruin grants the single Benefit of Cover
    # (+1 save - same as LIGHT/HEAVY cover; no terrain -1-to-hit in 10e) and its
    # walls block line of sight for everyone EXCEPT AIRCRAFT (and a model wholly
    # within the Ruin can see out). The INFANTRY/BEAST Ruin exception is
    # MOVEMENT ONLY now and grants no line of sight (the stale 9th-edition
    # shoot-through-walls pass was removed). Wired through
    # code.map.Map.has_line_of_sight via attacker_keywords / target_keywords
    # threaded from the simulator's _do_shoot / _apply_firing_deck call sites.
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
    # CORE-RULES-AUDIT (2026-05-31): simulator.heroic_intervention_core REMOVED
    # — Heroic Intervention is not a 10e rule (9e mechanic deleted at 10e
    # launch). See docs/CORE_RULES_AUDIT.md #1.
    # 10e core Fight phase: each unit makes a free Pile-In (3" toward
    # closest enemy) BEFORE it fights and a free Consolidate (3" toward
    # closest enemy / staying in engagement) AFTER it fights. When no
    # enemy is reachable within 3", the unit may instead consolidate
    # onto the nearest objective marker (simulator.consolidate_objective).
    "simulator.pile_in",
    "simulator.consolidate",
    "simulator.consolidate_objective",
    # 10e Leviathan Tournament Companion primary scoring cap: each army
    # scores at most 15 Primary VP per battle round (i.e. counts at most
    # 3 controlled objectives at 5 VP each). Applied in
    # `Battle._score_objectives` after per-objective awards are tallied.
    "simulator.primary_vp_cap_15",
    # Wave 187 (#71) — primary MISSION rotation. The sim previously scored
    # every game as Take and Hold (the most holder-friendly primary); the
    # real CA-2025-26 deck rotates ten primaries, several anti-holding. Modelled
    # in `Battle._score_objectives` (branch on `Battle.primary_mission`).
    "simulator.primary_mission_rotation",
    "simulator.primary_purge_the_foe",
    "simulator.primary_scorched_earth",
    "simulator.primary_scorched_earth_burn",
    # Wave 202 (#87) — Terraform primary: 4VP/controlled marker (cap 12) + 1VP per
    # marker terraformed by you (the Terraform Action, `_assign_terraform_actions` /
    # `_resolve_terraforms`, marks forward markers your spare bodies control).
    "simulator.primary_terraform",
    # Wave 203 (#87) — The Ritual primary: 5VP per No Man's Land marker controlled
    # (cap 15); home-zone markers score nothing (the_ritual branch of _score_objectives).
    "simulator.primary_the_ritual",
    # 10e Imperial / Chaos Knights "Damaged: Wounds Remaining" datasheet ability,
    # both clauses. OC half: Battle._effective_oc (wave 85). Hit half: Unit.attack
    # hit_mod_delta -= 1 when on the Damaged bracket (wave 188). Registered here so
    # the citation auditor enforces both (pre-existing gap: the OC key was cited in
    # data/rule_citations.d/imperial_knights.json since wave 85 but never registered).
    "simulator.damaged_objective_control_bracket",
    "simulator.damaged_hit_bracket",
    # #77 — the GENERALIZED, data-driven Damaged bracket (gated SWEG_DMGBRACKET):
    # applies the real per-datasheet OC + Hit penalty to every model with a bracket,
    # superseding the two Knight-only keys above. Data is BSData-sourced (rule 7).
    "simulator.damaged_bracket",
    # Task #92 — per-attack-type conditional invulnerable save (Wyches 4+ melee /
    # 6+ ranged; Ion Shield ranged-only). Gated SWEG_COND_INVULN; generalises and
    # subsumes simulator.ion_shield_ranged_only.
    "simulator.conditional_invuln_save",
    # Wave 217 — Chaos Space Marines Legionaries "Veterans of the Long War"
    # (melee Wound-roll re-rolls, upgraded to full re-roll near objectives).
    # Gated SWEG_VETERANS.
    "simulator.veterans_of_the_long_war",
    # EC-DAEMONETTE-FF (recovered 2026-06-29 from git c6b40b9, lost in a
    # re-anchor). Daemonettes' Fights First is detachment-gated (Carnival of
    # Excess) in BSData but extract_fights_first() over-extracts it as always-on.
    # Gate SWEG_EC_DAEMONETTE_FF suppresses it for Emperor's Children Daemonettes.
    # Cited in data/rule_citations.d/emperors_children.json.
    "simulator.ec_daemonette_fights_first",
    # Two-card hand cap for the legacy-union secondary fallback (env-gated
    # SWEG_SECONDARY_HANDCAP, default OFF; recovered 2026-06-29 from git 58acc4b).
    # When ON, Battle._score_secondaries_deck caps the round total at the two
    # highest-scoring chosen cards, modelling the Chapter Approved 2025-26 rule
    # that a player has at most TWO active Secondary Mission cards. OFF sums all
    # cards byte-identically. See data/rule_citations.d/core_secondary_hand_cap.json.
    "simulator.secondary_two_card_hand_cap",
    # CSM wave — Chaos Terminator Squad "Despoilers": when making a Dark Pact,
    # re-roll the Hit roll until the end of the phase. Gated SWEG_CSM_ABILITIES.
    # Cited in data/rule_citations.d/keywords_and_mechanics.json.
    "simulator.csm_despoilers",
    # CSM wave — Possessed "Unholy Bloodshed": once per battle, when making a
    # Dark Pact, weapons gain [DEVASTATING WOUNDS] until the end of the phase.
    # Gated SWEG_CSM_ABILITIES. Cited in data/rule_citations.d/keywords_and_mechanics.json.
    "simulator.csm_unholy_bloodshed",
    # Wave 236 — Forgefiend "Daemonic Ordnance": per-activation opt-in; ranged
    # weapons gain [DEVASTATING WOUNDS] and [HAZARDOUS] until end of phase.
    # Grants transient_devastating_wounds + transient_hazardous; Hazardous
    # d6 self-check fires in Unit.attack (ranged mode). Not env-gated (datasheet
    # ability, narrow flag, not a sweep across all CSM). Cited in
    # data/rule_citations.d/keywords_and_mechanics.json.
    "simulator.csm_daemonic_ordnance",
    # CSM wave — Dark Apostle "Dark Zealotry": +1 to Wound roll on melee attacks
    # while the unit is led by a Dark Apostle. Gated SWEG_CSM_ABILITIES.
    # Cited in data/rule_citations.d/leaders.json.
    "simulator.dark_apostle_dark_zealotry",
    # CSM wave — Abaddon the Despoiler "Paragon of Hatred" (Warmaster ability):
    # friendly HERETIC ASTARTES within 6\" re-roll Hit rolls. Army-wide broadcast
    # aura. Gated SWEG_CSM_ABILITIES. Cited in data/rule_citations.d/leaders.json.
    "simulator.abaddon_paragon_of_hatred",
    # Sororitas wave — Triumph of Saint Katherine "Solemn Procession": the
    # round-start Miracle die is fixed at 6 (instead of rolling D6) while the
    # Triumph model is on the battlefield. Gated SWEG_SOROR_ABILITIES.
    # Cited in data/rule_citations.d/adepta_sororitas.json.
    "simulator.triumph_of_saint_katherine",
    # Sororitas wave — Saint Celestine "Miraculous Intervention": once-per-battle
    # self-revive on 2+ when Celestine is destroyed. Gated SWEG_SOROR_ABILITIES.
    # Cited in data/rule_citations.d/adepta_sororitas.json.
    "simulator.celestine_miraculous_intervention",
    # Sororitas — Paragon Warsuits "Righteous Paragons" datasheet ability (10e).
    # +1 to the Hit roll and +1 to the Wound roll when the target has the MONSTER
    # or VEHICLE keyword. Attacker-side gate in Unit.attack; flag set per-unit via
    # data/overrides.json (righteous_paragons=True). Cited in
    # data/rule_citations.d/adepta_sororitas.json.
    "simulator.righteous_paragons",
    # Wave 221 — Chaos Daemons Daemonic Incursion "Warp Rifts" (env-gated
    # SWEG_WARP_RIFTS). Reduces Deep Strike minimum gap from 9" to 6" for
    # Chaos Daemons units arriving under the Daemonic Incursion detachment.
    # Cited in data/rule_citations.d/chaos_daemons.json.
    "simulator.warp_rifts",
    # Wave 232 — Tank Shock dice-faithful ON path (env-gated SWEG_TANKSHOCK_DICE).
    # ON: roll D6 + charger Toughness; on 7+ target takes D3 mortal wounds capped 6.
    # OFF (default): flat 2 mortal wounds (median D3, byte-identical).
    # Verbatim rule text from data/rule_citations.d/stratagems.json
    # "Stratagem.Tank Shock". Cited in data/rule_citations.json.
    "simulator.tank_shock_dice",
    # Wave 223 — 10e core Reserves cap (env-gated SWEG_DEPLOY_AI). Dual cap:
    # no more than half of an army's units AND no more than half of its total
    # points may start in Reserves. Deep Strike and Cult Ambush (a type of
    # Strategic Reserves) both count toward the cap. Enforced in
    # Battle._deploy_armies; the AI choice of WHICH units to reserve is the
    # tactical decision (low-OC alpha-strikers reserved first). Gate OFF
    # leaves the cap unenforced to preserve byte-identical A/B anchor
    # comparability. Cited in data/rule_citations.d/core_reserves.json.
    "simulator.reserves_cap",
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
    # LC-2 — Tactical Secondary Mission deck-draw mechanic. Gates
    # Engage / BEL behind a per-round alternating schedule per side
    # so each side scores at most one Tactical per round, matching
    # real Pariah Nexus 2-of-9 average coverage.
    "simulator.tactical_secondary_deck_draw",
    # M2 (wave 119) — the real 2-card Tactical secondary deck (env-gated
    # SWEG_TAC_DECK). Each army uses ONE track: FIXED (2 kill cards every
    # round) or TACTICAL (a deterministically-seeded 2-card hand with
    # achieve->discard->redraw). Replaces the legacy union-of-~9-11-sources
    # scoring (which trivially exceeded the 40 cap and washed the secondary
    # out). Even-handed track split from unit count; OFF byte-identical.
    # See data/rule_citations.d/secondaries_pariah_nexus.json.
    "simulator.tactical_secondary_deck",
    # Wave 133-135 — secondary dedication PLANNER (env-gated SWEG_SECONDARY),
    # a movement/positioning bias only. The wave-133 scoring gate on the
    # POSITION cards (Engage on All Fronts / Behind Enemy Lines) was REVERTED
    # in wave 135 as unfaithful (positional Secondaries score on presence, not
    # a performed Action); Battle._assign_card_dedication now only biases a
    # spare unit's MOVE toward a card's geography, and Unit.dedicated_card is
    # not read by any scorer. See data/rule_citations.d/secondary_dedication.json.
    "simulator.secondary_dedication",
    # Wave 135 — Action-card cost (env-gated SWEG_SECONDARY). The rules-clean
    # low-unit penalty: performing an Action (Cleanse / Sabotage) costs a unit
    # its shooting and charge for the turn (10e core Actions). A unit may START
    # one only if it passes Battle._unit_can_perform_action (Objective Control
    # > 0, not in Engagement Range, not a productive shooter with a target),
    # and it SCORES only if it completes (survives + not dragged into melee,
    # Battle._action_completes). EMERGENT from unit count — a Knight cannot
    # spare a body and scores 0; no faction / model-count branch. OFF keeps the
    # legacy chaff-selection / still-alive scoring byte-for-byte. See
    # data/rule_citations.d/secondary_dedication.json.
    "simulator.secondary_action_cost",
    # Wave 136 — squad-granularity WHOLLY-WITHIN for Engage / Behind Enemy Lines
    # (user catch): a codex squad counts for a quarter / the enemy DZ only when
    # ALL its models qualify, correcting the one-Unit-per-model over-credit.
    # Env-gated SWEG_SECONDARY; OFF keeps the legacy per-model check.
    "simulator.secondary_wholly_within",
    # Wave 137 — a 10e battle lasts five battle rounds; a one-sided tabling does
    # NOT end it early (only a mutual wipe does). data/rule_citations.d/core_battle_length.json.
    "simulator.battle_length_five_rounds",
    # Challenger cards (Chapter Approved 2025-26 catch-up mechanic, env-gated
    # SWEG_CHALLENGER_CARDS). At the start of a battle round, the side trailing by
    # 6+ victory points draws ONE extra scoring card and scores it through the
    # existing Tactical achievement machinery (Battle._score_one_card); lifetime
    # challenger contribution capped at ~12 VP per side. Even-handed; OFF
    # byte-identical. See data/rule_citations.d/core_challenger_cards.json.
    "simulator.challenger_cards",
    # LC-5 — Warlord designation. First CHARACTER in deploy order is
    # the Warlord; killing it grants +1 Assassination VP per real
    # Pariah Nexus rule.
    "simulator.warlord_designation",
    # SECONDARY-SELECTION-V1 — Pariah Nexus secondary selection. Real
    # 10e rule: each player picks exactly TWO Fixed Secondaries from
    # the four-card pool OR uses the Tactical deck (drawing per
    # round). Implemented in `code/secondaries.py::pick_secondaries`
    # (heuristic on enemy MV count + own FLY/MOUNT count, picks 2
    # Fixed + 2 Tactical); persisted on `Army.chosen_secondaries`;
    # consumed by `code/secondaries.py::score_round_delta` /
    # `score_position_delta` via the `chosen` parameter; threaded
    # through from `code/simulator.py::_score_secondaries`.
    "simulator.secondary_selection",
    # Astra Militarum core battleline special weapons (env-gated
    # SWEG_AM_BATTLELINE_SPECIALS, default OFF). The BSData v10.6.0 mapper drops
    # the up-to-2-special-weapons-per-10-models options from Cadian Shock Troops
    # and Death Korps of Krieg (collapsing both to a lasgun-only model type);
    # when the gate is on, _build_catalog replaces their model_loadouts with a
    # heterogeneous 8 lasgun + 1 plasma gun + 1 meltagun per 10 models so the
    # per-model promotion builds the special-weapon models. Cited in
    # data/rule_citations.d/astra_militarum.json.
    "simulator.am_battleline_special_weapons",
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
    # Live simulator rules whose citations already exist in the shards but
    # were not previously registered in this tuple. Adding them here so the
    # auditor can verify completeness. (A1 block — wave-60 citation audit.)
    "simulator.acts_of_faith",
    "simulator.basket_best_ranged_per_model",
    "simulator.basket_fraction_gating",
    "simulator.beacons_of_rage",
    "simulator.benefits_of_cover",
    "simulator.blessings_of_khorne",
    "simulator.blood_surge",
    "simulator.code_chivalric",
    "simulator.combat_drugs",
    "simulator.dark_pacts",
    "simulator.fights_first_chargers",
    "simulator.fights_first_keyword",
    "simulator.harbingers_of_dread",
    # Wave 232 — Chaos Knights Harbingers of Dread additional Dread abilities
    # (env-gated SWEG_HARBINGERS, default-OFF). Despair and Darkness wired in
    # code/units.py Unit.attack; Dismay and Delirium wired in
    # code/simulator.py _run_battleshock_phase.
    "simulator.harbingers_of_dread_despair",
    "simulator.harbingers_of_dread_darkness",
    "simulator.harbingers_of_dread_dismay",
    "simulator.harbingers_of_dread_delirium",
    # Chaos Knights Harbingers of Dread: Doom (Dread ability 2, env-gated
    # SWEG_CK_DOOM, default OFF). Independent of SWEG_HARBINGERS: enables Doom
    # (+1 to Wound vs Battle-shocked targets) as an additional active Dread pick.
    # Wired in code/units.py Unit.attack. Direction: raises Chaos Knights win rate.
    "simulator.harbingers_of_dread_doom",
    "simulator.multi_profile_weapon_selection",
    # PER-MODEL-LOADOUTS (Stage 3, env-gated SWEG_PERMODEL). One Unit per model,
    # each firing its OWN BSData loadout, so a special-weapon model loses its
    # weapon when it dies and a single-model unit fires only its real gun rack.
    # Faithful representation change (same stats, attributed per model); alt-mode
    # and pistol exclusivity still enforced by the existing picker. See
    # data/rule_citations.d/core_per_model_loadouts.json.
    "simulator.per_model_loadouts",
    # PER-MODEL-LOADOUTS (Stage 4, env-gated SWEG_ROLLDMG). Roll a weapon's real
    # random Damage characteristic (D6, D3+3, 2D6, ...) per shot instead of using
    # its expected-value mean. Tests whether mean-overkill on big single-shot guns
    # inflates the elite / big-gun factions. Only fires on the per-model firing
    # path (the only profiles that carry a raw damage_dice string). See
    # data/rule_citations.d/core_rolled_damage.json.
    "simulator.rolled_damage",
    "simulator.pistol_exclusivity",
    "simulator.primary_vp_no_round_1",
    "simulator.rend_and_tear",
    # Wave 101 — army-level focus fire (env-gated SWEG_FOCUSFIRE). AI tactical
    # heuristic, NOT a 10e game rule: once per Shooting phase the firing army
    # nominates the most dangerous enemy brick it can crack COLLECTIVELY this
    # phase, and every unit that can wound it concentrates fire on it. Does not
    # change combat math; only re-points existing fire onto a target the army
    # can already destroy. The wave-79 SWEG_FOCUS predecessor (points-based, no
    # collective-crack gate) is intentionally NOT cited here — it has no
    # collective-crack guarantee and is being superseded by this layer.
    # See data/rule_citations.d/focus_fire.json.
    "simulator.focus_fire",
    # Fire Overwatch (10e universal core stratagem, env-gated SWEG_OVERWATCH).
    # The defending army may spend 1 Command Point in the opponent's Movement /
    # Charge phase to have one eligible unit (within 24", line of sight) shoot a
    # charging or arriving enemy as if it were its Shooting phase, hitting only
    # on UNMODIFIED Hit rolls of 6. Limited to once per battle round per army.
    # Built as Battle._fire_overwatch + the overwatch path in Unit.attack;
    # hooked at the charge-declaration and reserves-arrival trigger points. Gate
    # unset reproduces the baseline byte-for-byte. See
    # data/rule_citations.d/core_overwatch.json.
    "simulator.fire_overwatch",
    # Necrons Cursed Legion — Relentless Onslaught (Abilities #1). Two simulator
    # gates read Detachment.relentless_onslaught: the +1-to-Hit gate in
    # Unit.attack (NECRONS attacker, target on an objective marker — ranged AND
    # melee, no round restriction) and the [ASSAULT] Advance-lockout exemption in
    # Battle._do_shoot (NECRONS VEHICLE / MOUNTED, excluding TITANIC). The
    # detachment-flag citation CURSED_LEGION.relentless_onslaught is auto-required
    # via RULE_BEARING_FIELDS. Both live in data/rule_citations.d/necrons.json.
    "simulator.relentless_onslaught",
    # Leagues of Votann — Prioritised Efficiency (army rule, current 10e codex,
    # env-gated SWEG_VOTANN_PRIORITISED_EFFICIENCY, default OFF). The +1-to-Hit
    # gate in Unit.attack: a Leagues of Votann attacker (Army.is_votann_army)
    # adds 1 to the Hit roll when the target is within range of an objective
    # marker (target.on_objective) — the Hostile Acquisition clause, the same
    # near-objective shape as simulator.relentless_onslaught above. Re-introduces
    # the army-wide combat buff the codex grants Votann, which was entirely
    # absent after the retired Eye of the Ancestors rule was zeroed. APPROXIMATION:
    # only the Hostile Acquisition state is modelled (not the Yield-Point economy,
    # the Fortify Takeover switch, or the Advance-and-Charge re-roll) — see the
    # notes in data/rule_citations.d/votann.json. Cited there as
    # simulator.prioritised_efficiency.
    "simulator.prioritised_efficiency",
    # SWEG_VOTANN_PE_TARGET_BIAS (default-on 2026-07-01). An AI target-selection
    # heuristic (not a separate rule): the Votann shooting picker prefers
    # on-objective enemy targets (_votann_pe_target_bonus, code/strategy.py, 1.5x
    # score multiplier), concentrating fire where the Prioritised Efficiency
    # +1-to-Hit compounds. Cited in data/rule_citations.d/votann.json.
    "simulator.votann_pe_target_bias",
    # SWEG_VOTANN_RANGED_HOLD (default-on 2026-07-01). AI piloting heuristic (same
    # as simulator.am_advance_discipline / ck_ranged_hold, Votann-scoped): Votann
    # shooting platforms (Hekaton/Sagitaur/Hearthkyn) hold and shoot instead of
    # Advancing and forfeiting their Shooting phase. Overshoots via the durability
    # over-reward but improves the metric via collateral. Cited in votann.json.
    "simulator.votann_ranged_hold",
    "unit.necrodermis",
    # Wave 181 — CA-2025-26 Tactical-track flat kill card VP values.
    # When a TACTICAL-track army (SWEG_TAC_DECK path) draws one of these three
    # kill cards in its hand, it scores a flat per-turn value if one or more
    # qualifying enemy units died, rather than the Fixed per-unit accumulation.
    # No Prisoners keeps its per-unit-capped form in both tracks.
    # Sources: https://wahapedia.ru/wh40k10ed/the-rules/chapter-approved-2025-26/
    "simulator.secondary_assassination_tactical",
    "simulator.secondary_bring_it_down_tactical",
    "simulator.secondary_cull_the_horde_tactical",
    # Wave 249 — 10e core end-of-battle win condition (env-gated SWEG_TABLING_VP,
    # default OFF). When ON, the three survivor-count short-circuits in
    # Battle._decide_winner are skipped; every game (including one-sided tablings)
    # is decided purely by the accumulated VP totals. The run loop already plays
    # out all five rounds on a one-sided tabling, so the VP totals are complete at
    # decision time. Cited in data/rule_citations.d/core_win_condition.json.
    "simulator.win_on_vp_not_tabling",
    # Astra Militarum Grizzled Company — Ruthless Discipline (env-gated
    # SWEG_AM_GRIZZLED, default OFF). Simulator-side gate for the two
    # clauses of the detachment rule: code/orders.py dispatch_orders adds 1
    # to every Officer's per-round Order cap, and code/units.py Unit.attack
    # re-rolls Hit rolls of 1 for both ranged and melee attacks made by a
    # unit stamped `transient_affected_by_order` this round. Detachment-flag
    # citation: GRIZZLED_COMPANY.grizzled_ruthless_discipline. Cited in
    # data/rule_citations.d/astra_militarum.json.
    "simulator.grizzled_ruthless_discipline",
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
