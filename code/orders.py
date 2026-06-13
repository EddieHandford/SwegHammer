"""
Officer Orders — Astra Militarum Voice of Command army rule (iter-14).

10e Astra Militarum's army-wide army rule is "Voice of Command":

    "If your Army Faction is ASTRA MILITARUM, OFFICER models with this
    ability can issue Orders. Each OFFICER's datasheet will specify how
    many Orders it can issue in a battle round and which units are
    eligible to receive those Orders."

Source: https://wahapedia.ru/wh40k10ed/factions/astra-militarum/

Orders are issued during the Command phase. Each Order applies a single
buff to a target REGIMENT or SQUADRON unit within the Officer's range
(typically 6"). Units can only be affected by one Order at a time;
subsequent Orders replace previous ones. Battle-shocked units cannot
receive Orders.

This module implements the Order issuance hook called at the start of
each Command phase by `Battle._run_round` (right after the per-round CP
drip and stratagem dispatch). The simulator picks ONE Order per Officer
per round, gated by `_pick_order_for_target` — greedy heuristic that
picks the highest-value Order for the army's current shape (offensive
units get Take Aim! or First Rank Fire / Second Rank Fire, defensive
bricks get Take Cover!, melee chargers get Fix Bayonets!).

Four Orders are wired (the most-used set per Wahapedia + Goonhammer
May 2026 meta reports):

    * Take Aim!                            (+1 to hit shooting, Take Aim! Order)
    * Fix Bayonets!                        (+1 to wound melee, Fix Bayonets! Order)
    * First Rank, Fire! Second Rank, Fire! (+1 Attack on Rapid Fire weapons)
    * Take Cover!                          (+1 to save, Take Cover! Order)

Move! Move! Move! (+3" movement) and Duty and Honour! (+1 Ld, +1 OC) are
intentionally not modelled — SwegHammer's movement model uses
`effective_move` for one-off boosts and the +1 Ld/OC pair is dominated
by battleshock + objective scoring code paths that don't expose a
per-unit transient slot at present. The codex eligibility table includes
both as valid issuances; the dispatcher skips them and informs the AI
to never pick them.

Effect routing (APPROXIMATION where noted):

    * Take Aim! — `transient_plus_one_to_hit_shooting` on target unit.
      Direct mapping; codex effect is "improve BS by 1" which is
      arithmetically identical to "+1 to hit roll" at every BS bracket.
    * Fix Bayonets! — `transient_plus_one_to_wound_melee` on target unit.
      APPROXIMATION: codex effect is "improve WS by 1" (a hit-roll buff)
      but SwegHammer routes through +1 to wound to capture the offensive
      payoff via a single existing transient flag — same direction
      (more landed melee damage), comparable magnitude on a 4+ wound.
      Notes per CLAUDE.md §10 in `data/rule_citations.d/astra_militarum.json`.
    * First Rank, Fire! Second Rank, Fire! — `transient_frfsrf_active`
      on target unit. Faithful mapping: codex text "Improve the Attacks
      characteristic of Rapid Fire weapons equipped by models in this
      unit by 1." The flag gates a +1 n_attacks uplift in
      Unit.compute_expected_kills for every weapon profile that has
      rapid_fire > 0, unconditionally at all ranges (the rule has no
      range condition). Cited as
      `Order.First Rank, Fire! Second Rank, Fire!`.
    * Take Cover! — `transient_plus_one_save` on target unit. Direct
      mapping; codex effect is "+1 to save (cannot improve better than
      3+)" which lines up exactly with our +1-save flag (the 3+ cap is
      a real-codex restriction that SwegHammer drops; AM REGIMENT
      saves are 5+/4+ so the cap rarely binds anyway).

Eligibility:

    * Issuer: alive, non-Battle-shocked friendly OFFICER (CHARACTER with
      faction == "Astra Militarum"). The codex specifies that each
      OFFICER datasheet caps how many Orders it can issue per round
      (1-3 depending on rank). SwegHammer caps each Officer at 1 Order
      per round; the Flexible Command stratagem (Combined Arms) widens
      this to multiple Officers via the simulator's command-phase
      stratagem dispatch (extra Officers are unaffected since each is
      already at the 1-cap default).
    * Target: alive, non-Battle-shocked friendly REGIMENT or SQUADRON
      unit with faction == "Astra Militarum", within 6" of the issuing
      Officer. The codex REGIMENT and SQUADRON keywords are now tracked
      directly from BSData categoryLinks via the mapper's
      `_TRACKED_UNIT_KEYWORDS` set — no proxy needed. The Flexible
      Command stratagem widens the eligible set for the round (Leman
      Russ etc.) by setting `Army.orders_eligible_squadron_this_round
      = True`.
    * At most one Order per unit per round (subsequent Orders to the
      same unit are skipped — no Order stacking).

Cited per CLAUDE.md §10 as `simulator.voice_of_command_orders` in
`data/rule_citations.d/astra_militarum.json`. Each Order's verbatim
codex text is cited under `Order.<name>`.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Dict, List, Optional, Set, Tuple

if TYPE_CHECKING:
    from .army import Army
    from .units import Unit


# ---------------------------------------------------------------------------
# Lord Castellan two-Order exception gate (wave 248)
# ---------------------------------------------------------------------------
# Ursula Creed's "Lord Castellan" ability (BSData unit id b6b2-9971-ec0c-349e):
# "While this model is leading a unit, that unit can be affected by up to two
# different Orders at the same time."
#
# When SWEG_CREED_TWO_ORDERS=0 (the default) the gate is completely absent from
# the dispatch loop; ordered_squads behaves byte-identically to the pre-248
# code path. When SWEG_CREED_TWO_ORDERS=1 the squad Creed is leading may receive
# a second, DIFFERENT Order (the same Order may not be stacked twice on that
# unit). All other squads remain capped at one Order per round.
#
# Cited as "SWEG_CREED_TWO_ORDERS.lord_castellan_two_orders" in
# data/rule_citations.json.
_CREED_TWO_ORDERS: bool = os.environ.get("SWEG_CREED_TWO_ORDERS", "0") == "1"


# ---------------------------------------------------------------------------
# Order eligibility helpers
# ---------------------------------------------------------------------------

OFFICER_AURA_RANGE: float = 6.0   # 10e canonical (Voice of Command)


# Canonical AM OFFICER datasheets — only these can issue Voice of Command
# Orders. Sourced from Wahapedia AM faction page
# (https://wahapedia.ru/wh40k10ed/factions/astra-militarum/) by reading
# each CHARACTER datasheet's keyword line. The OFFICER keyword is the
# codex gate for issuing Orders; BSData v10.6.0's parsed unit_keywords field
# does not preserve the OFFICER keyword (the bsdata mapper retains only
# INFANTRY / VEHICLE / BATTLELINE / CHARACTER / EPIC HERO / PSYKER / MOUNTED /
# WALKER / MONSTER / SYNAPSE / TRANSPORT / REGIMENT / SQUADRON), so the gate
# has to be applied via an allowlist of unit catalogue keys.
#
# Including a unit in this set requires that its Wahapedia datasheet
# carry the OFFICER keyword on the printed faction-keyword line. Adding
# units that are merely "leaders" or "command-y" is forbidden — that
# was the bug this allowlist exists to fix. The gate uses the unit
# catalogue's display `name` (which the simulator passes through
# untouched from the bsdata mapper) so the allowlist tracks Wahapedia's
# datasheet titles directly.
#
# NOT OFFICERs (and thus excluded — present in the catalogue as
# CHARACTERs but cannot issue Orders per codex): Commissar, Commissar
# Yarrick, Commissar Graves, Ministorum Priest, Tech-Priest Enginseer,
# Primaris Psyker, Nork Deddog, Ogryn Bodyguard, Sly Marbo, "Iron
# Hand" Straken, Sergeant Harker, Gaunt's Ghosts, Hell's Last, Rein
# and Raus, Provisionally Prepared, Quartermaster Cadre Squad,
# Augmented Bone 'Ead, Death Rider Commissar.
AM_OFFICER_NAMES: frozenset = frozenset({
    "Lord Solar Leontus",
    "Cadian Castellan",
    "Cadian Command Squad",
    "Militarum Tempestus Command Squad",
    "Krieg Command Squad",
    "Catachan Command Squad",
    "Lord Marshal Dreir",
    "Ursula Creed",
    "Leman Russ Commander",
    "Rogal Dorn Commander",
    "Sentinel Commander [Crucible]",
    "Front-line Commander [Crucible]",
})

# Per-datasheet Order profiles. Each entry maps an Officer name to a tuple of
# (max_orders: int, target_types: frozenset[str]) sourced verbatim from the
# BSData Library Astra Militarum cat.gz (cached at
# data/bsdata/cache/Imperium - Astra Militarum - Library.cat.gz).
#
# target_types encodes which keyword categories the Officer may issue Orders
# to. Three categories exist in the codex:
#   "REGIMENT"  — unit carries the REGIMENT keyword (from BSData categoryLinks)
#   "SQUADRON"  — unit carries the SQUADRON keyword (from BSData categoryLinks)
#   "TITANIC"   — any unit with the TITANIC keyword
#
# The Flexible Command (Combined Arms, 2 command points) stratagem widens the
# *army-wide* eligible-target set to also include SQUADRON for the round it
# fires; that gate is an OR with per-officer eligibility (if either opens the
# gate, the target is eligible) — see dispatch_orders.
#
# Lord Solar Leontus: "This OFFICER can issue up to 3 Orders to: REGIMENT
# units, SQUADRON units, TITANIC units." — BSData unit id a9d-55c1-3d24-fa25,
# Orders profile id 4768-11ce-3c8b-3ce4. Cross-checked Wahapedia
# https://wahapedia.ru/wh40k10ed/factions/astra-militarum/Lord-Solar-Leontus.
#
# Ursula Creed: "This OFFICER can issue up to 3 Orders to REGIMENT units."
# — BSData unit id b6b2-9971-ec0c-349e, Orders profile id
# 85b7-65b8-1961-50ee.
#
# Lord Marshal Dreir: "This OFFICER can issue up to 3 Orders to REGIMENT
# units" — BSData unit id 9033-d07c-3e1c-f6f0, Orders profile id
# c4eb-5868-02ac-efe3.
#
# Front-line Commander [Crucible]: "This OFFICER can issue up to 2 Orders to
# REGIMENT units." — BSData unit id 4fc5-184d-b305-3551, Orders profile id
# 467f-baf9-5dfd-0f3f.
#
# Cadian Castellan: "This OFFICER can issue 2 Orders to REGIMENT units."
# — BSData unit id 2b49-4d03-aaf5-3532, Orders profile id
# 21e5-4e9-7904-8d96.
#
# Cadian Command Squad: "This unit's OFFICER can issue 1 Order to a REGIMENT
# unit." — BSData unit id 4d28-f2a7-67c1-eb2e, Orders profile id
# 9c13-76b5-43ba-b4f7.
#
# Militarum Tempestus Command Squad: "This unit's OFFICER can issue 1 Order
# to a REGIMENT unit." — BSData unit id 497-36ad-8ecb-f7c7, Orders profile
# id 78c6-15ac-3822-61f2.
#
# Krieg Command Squad: "This unit's OFFICER can issue 1 Order to a REGIMENT
# unit." — BSData unit id fbcd-274b-0196-b4f6, Orders profile id
# 9090-d3fb-61da-29d8.
#
# Catachan Command Squad: "This unit's OFFICER can issue 1 Order to a
# REGIMENT unit." — BSData unit id 7d22-9fb6-a7e0-c21b, Orders profile id
# 5722-8d6d-ae28-d30d.
#
# Leman Russ Commander: "This OFFICER can issue 2 Orders to SQUADRON units."
# — BSData unit id 5430-18e-d7b0-1d54, Orders profile id
# d520-92fd-8c74-ec6e.
#
# Rogal Dorn Commander: "This OFFICER can issue 2 Orders to SQUADRON units."
# — BSData unit id 78b6-f280-bba9-0594, Orders profile id
# 2798-cdef-e114-6795.
#
# Sentinel Commander [Crucible]: "This OFFICER can issue up to 1 Order to
# SQUADRON units." — BSData unit id a040-9715-5d3a-52af, Orders profile id
# f785-4221-70aa-1ae4.
#
# All twelve Officers are listed explicitly here regardless of count. The
# Voice of Command army rule says "Each OFFICER's datasheet will specify how
# many Orders it can issue" — every profile is sourced; none are defaulted.
OFFICER_ORDER_PROFILES: dict = {
    # (max_orders, frozenset of target-type keyword categories)
    "Lord Solar Leontus":                   (3, frozenset({"REGIMENT", "SQUADRON", "TITANIC"})),
    "Ursula Creed":                         (3, frozenset({"REGIMENT"})),
    "Lord Marshal Dreir":                   (3, frozenset({"REGIMENT"})),
    "Front-line Commander [Crucible]":      (2, frozenset({"REGIMENT"})),
    "Cadian Castellan":                     (2, frozenset({"REGIMENT"})),
    "Cadian Command Squad":                 (1, frozenset({"REGIMENT"})),
    "Militarum Tempestus Command Squad":    (1, frozenset({"REGIMENT"})),
    "Krieg Command Squad":                  (1, frozenset({"REGIMENT"})),
    "Catachan Command Squad":               (1, frozenset({"REGIMENT"})),
    "Leman Russ Commander":                 (2, frozenset({"SQUADRON"})),
    "Rogal Dorn Commander":                 (2, frozenset({"SQUADRON"})),
    "Sentinel Commander [Crucible]":        (1, frozenset({"SQUADRON"})),
}

# Backward-compatibility alias: code that reads OFFICER_ORDER_COUNTS directly
# (e.g. test assertions, external scripts) continues to work unchanged.
# Derived from OFFICER_ORDER_PROFILES at import time.
OFFICER_ORDER_COUNTS: dict = {
    name: profile[0] for name, profile in OFFICER_ORDER_PROFILES.items()
}

# Import-time validation: every key in OFFICER_ORDER_PROFILES must name a
# datasheet in AM_OFFICER_NAMES, and every AM_OFFICER_NAMES entry must have
# an OFFICER_ORDER_PROFILES entry. A key that isn't in the allowlist means
# either the allowlist was updated without updating OFFICER_ORDER_PROFILES, or
# the profile was seeded with a typo. Fail loud per CLAUDE.md §13.
for _k in OFFICER_ORDER_PROFILES:
    if _k not in AM_OFFICER_NAMES:
        raise ValueError(
            f"OFFICER_ORDER_PROFILES contains key {_k!r} which is not in "
            f"AM_OFFICER_NAMES. Either add the officer to AM_OFFICER_NAMES "
            f"(if it is a real OFFICER datasheet) or remove the entry from "
            f"OFFICER_ORDER_PROFILES. (code/orders.py import-time validation)"
        )
for _k in AM_OFFICER_NAMES:
    if _k not in OFFICER_ORDER_PROFILES:
        raise ValueError(
            f"AM_OFFICER_NAMES contains {_k!r} which has no entry in "
            f"OFFICER_ORDER_PROFILES. Add a (max_orders, target_types) entry "
            f"sourced from the BSData Library Astra Militarum cache. "
            f"(code/orders.py import-time validation)"
        )
del _k  # don't leak the loop variable into module namespace


def _officer_target_types(officer_name: str) -> frozenset:
    """Return the set of codex keyword categories this Officer may issue
    Orders to, sourced from OFFICER_ORDER_PROFILES.

    Categories: "REGIMENT" (unit carries REGIMENT keyword), "SQUADRON"
    (unit carries SQUADRON keyword), "TITANIC".

    Raises ValueError if `officer_name` is not in OFFICER_ORDER_PROFILES —
    fail loud per CLAUDE.md §13 (no silent .get default).
    """
    if officer_name not in OFFICER_ORDER_PROFILES:
        raise ValueError(
            f"No Orders profile found for officer {officer_name!r} in "
            f"OFFICER_ORDER_PROFILES (code/orders.py). Add a sourced "
            f"(max_orders, target_types) entry from the BSData Library "
            f"Astra Militarum cache."
        )
    return OFFICER_ORDER_PROFILES[officer_name][1]


def _distance(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return (dx * dx + dy * dy) ** 0.5


def _is_am_officer(unit: "Unit") -> bool:
    """True iff the unit is an alive AM OFFICER datasheet.

    Per Wahapedia (https://wahapedia.ru/wh40k10ed/factions/astra-
    militarum/) Voice of Command restricts Order issuance to OFFICER
    models. The codex's OFFICER keyword maps to a specific subset of
    CHARACTER datasheets — not every AM CHARACTER is an Officer.
    Commissar / Commissar Yarrick / Commissar Graves / Ministorum
    Priest / Tech-Priest Enginseer / Primaris Psyker / Nork Deddog /
    Ogryn Bodyguard / Sly Marbo / "Iron Hand" Straken / Sergeant
    Harker / Gaunt's Ghosts / Hell's Last / Rein and Raus /
    Provisionally Prepared / Quartermaster Cadre Squad / Augmented
    Bone 'Ead / Death Rider Commissar all carry CHARACTER but NOT
    OFFICER, so they cannot issue Orders.

    BSData v10.6.0's parsed.json does not preserve the OFFICER keyword
    (the mapper strips it during keyword filtering), so we gate via the
    `AM_OFFICER_KEYS` allowlist — verified against Wahapedia datasheet
    keyword lines.
    """
    if not unit.is_alive:
        return False
    if (unit.profile.faction or "") != "Astra Militarum":
        return False
    return (unit.profile.name or "") in AM_OFFICER_NAMES


def _unit_satisfies_target_type(unit: "Unit", target_types: frozenset) -> bool:
    """True iff the unit's keyword set satisfies at least one of the
    categories in `target_types`.

    Category mapping — real codex keywords, sourced from BSData categoryLinks
    via the mapper's `_TRACKED_UNIT_KEYWORDS` set (wave 243):
      "REGIMENT"  — unit carries the REGIMENT keyword
      "SQUADRON"  — unit carries the SQUADRON keyword
      "TITANIC"   — unit carries the TITANIC keyword
    """
    kw = set(unit.profile.unit_keywords or ())
    if "REGIMENT" in target_types and "REGIMENT" in kw:
        return True
    if "SQUADRON" in target_types and "SQUADRON" in kw:
        return True
    if "TITANIC" in target_types and "TITANIC" in kw:
        return True
    return False


def _is_order_target_eligible(
    unit: "Unit",
    squadron_allowed: bool = False,
    officer_target_types: Optional[frozenset] = None,
) -> bool:
    """True iff the unit is an alive AM unit eligible to receive an Order.

    Eligibility has two independent gates that are OR-ed:
      1. Per-officer target-type gate: the unit satisfies at least one
         category in `officer_target_types` (REGIMENT, SQUADRON, TITANIC).
      2. Flexible Command gate: when `squadron_allowed` is True (set by the
         Flexible Command Combined Arms stratagem), AM SQUADRON units are also
         eligible regardless of the Officer's own per-datasheet restriction.

    When `officer_target_types` is None the per-officer gate is skipped and
    only the army-wide REGIMENT eligibility rule applies (backward-compatible
    default for callers that don't pass officer context).

    The BATTLELINE gate that previously guarded this function has been removed
    (wave 243): REGIMENT and SQUADRON are the real codex eligibility keywords
    sourced from BSData categoryLinks. Keying on BATTLELINE was a proxy that
    blocked Kasrkin, Tempestus Scions, Heavy Weapons Squads, and all SQUADRON
    vehicles from ever receiving Orders.
    """
    if not unit.is_alive:
        return False
    if (unit.profile.faction or "") != "Astra Militarum":
        return False
    kw = set(unit.profile.unit_keywords or ())

    # Gate 1: per-officer target-type restriction.
    if officer_target_types is not None:
        officer_allows = _unit_satisfies_target_type(unit, officer_target_types)
    else:
        # Legacy default: REGIMENT only.
        officer_allows = "REGIMENT" in kw

    # Gate 2: Flexible Command stratagem widens the eligible set to SQUADRON.
    flexible_command_allows = squadron_allowed and "SQUADRON" in kw

    return officer_allows or flexible_command_allows


# ---------------------------------------------------------------------------
# Order definitions
# ---------------------------------------------------------------------------

# Order names exactly as printed in the AM codex (Wahapedia verbatim).
ORDER_TAKE_AIM: str = "Take Aim!"
ORDER_FIX_BAYONETS: str = "Fix Bayonets!"
ORDER_FRFSRF: str = "First Rank, Fire! Second Rank, Fire!"
ORDER_TAKE_COVER: str = "Take Cover!"

WIRED_ORDERS: Tuple[str, ...] = (
    ORDER_TAKE_AIM,
    ORDER_FIX_BAYONETS,
    ORDER_FRFSRF,
    ORDER_TAKE_COVER,
)


def _apply_order(target: "Unit", order: str) -> None:
    """Apply an Order's transient effect to `target`. Idempotent — calling
    twice with the same Order just re-sets the same flag.

    See module docstring for the APPROXIMATION mapping per Order.
    """
    if order == ORDER_TAKE_AIM:
        target.transient_plus_one_to_hit_shooting = True
    elif order == ORDER_FIX_BAYONETS:
        target.transient_plus_one_to_wound_melee = True
    elif order == ORDER_FRFSRF:
        # Faithful mapping: "Improve the Attacks characteristic of Rapid
        # Fire weapons equipped by models in this unit by 1." — sets
        # transient_frfsrf_active; the attack-count uplift is applied in
        # Unit.compute_expected_kills for any weapon with rapid_fire > 0,
        # unconditionally at all ranges (no range condition in the rule
        # text). Cited: `Order.First Rank, Fire! Second Rank, Fire!`
        target.transient_frfsrf_active = True
    elif order == ORDER_TAKE_COVER:
        target.transient_plus_one_save = True
    # Unknown Order — silent no-op so a stale order string in the AI
    # picker doesn't crash the dispatcher.


# ---------------------------------------------------------------------------
# AI gate — pick the best Order for a target
# ---------------------------------------------------------------------------

def _unit_ranged_dpa(u: "Unit") -> float:
    p = u.profile
    return (p.attacks or 0) * (p.hit_probability or 0) * (p.per_shot_damage or 0.0)


def _unit_melee_dpa(u: "Unit") -> float:
    p = u.profile
    return (
        (p.melee_attacks or 0)
        * (p.melee_hit_probability or 0)
        * (p.melee_damage_per_shot or 0.0)
    )


def _unit_has_rapid_fire(u: "Unit") -> bool:
    """True iff the unit carries at least one Rapid Fire ranged weapon —
    primary block, secondary block, or any extra ranged profile.

    This mirrors exactly the set of profiles `Unit.compute_expected_kills`
    buffs under `transient_frfsrf_active` (every profile with rapid_fire > 0),
    so it answers "would First Rank, Fire! Second Rank, Fire! do anything at
    all for this unit?". The codex effect is "Improve the Attacks
    characteristic of Rapid Fire weapons equipped by models in this unit by
    1." — on a unit with no Rapid Fire weapons the Order does literally
    nothing, so the AI picker must never spend an Order slot on it (wave 243:
    widening the eligible pool to SQUADRON vehicles made tanks the
    highest-priority targets, and they were burning their slots on this
    no-op).
    """
    p = u.profile
    if (p.rapid_fire or 0) > 0:
        return True
    if (getattr(p, "secondary_rapid_fire", 0) or 0) > 0:
        return True
    for extra in (p.extra_ranged_profiles or ()):
        if (dict(extra).get("rapid_fire", 0) or 0) > 0:
            return True
    return False


def _pick_order_for_target(
    target: "Unit", hp_frac_lost: Optional[float] = None
) -> str:
    """Greedy: pick the Order that maximises expected value for `target`.

    Heuristic:
      * If the unit has been damaged (>20% HP loss), prefer Take Cover! —
        the +1 save preserves the remaining points.
      * Else if the unit has meaningful melee DPA AND no ranged DPA,
        pick Fix Bayonets! (no shoot-relevant alternative).
      * Else if the unit has real ranged DPA AND carries at least one
        Rapid Fire weapon, pick First Rank Fire / Second Rank Fire
        (matches the codex use case for Cadians / Krieg / Catachan
        Lasgun blocks — the canonical FRFSRF target). The Rapid Fire
        gate matters: the codex effect buffs Rapid Fire weapons only,
        so on a no-Rapid-Fire unit (Leman Russ, Rogal Dorn) the Order
        does nothing — those take Take Aim! instead (wave 243).
      * Else pick Take Aim! (generic +1 to hit shooting).

    Lasgun-heavy REGIMENT squads typically have ranged_dpa > 0 and
    melee_dpa < 0.5; the FRFSRF branch fires on them as intended.
    Bullgryns/Ogryns (melee-only) hit the Fix Bayonets! branch.
    """
    if hp_frac_lost is None:
        # Explicit default (CLAUDE.md rule 13): None means "single-model
        # caller" — derive the damage fraction from this one Unit.
        # dispatch_orders passes the SQUAD-aggregate fraction instead,
        # because the simulator stores one Unit per physical model and
        # casualties are removed whole-model: a squad that has lost half
        # its models is damaged even though every surviving model sits at
        # full health.
        try:
            hp_frac_lost = max(
                0.0, 1.0 - target.current_health / max(1.0, target.profile.health)
            )
        except Exception:
            hp_frac_lost = 0.0

    if hp_frac_lost > 0.2:
        return ORDER_TAKE_COVER

    ranged_dpa = _unit_ranged_dpa(target)
    melee_dpa = _unit_melee_dpa(target)

    if melee_dpa > 0.5 and ranged_dpa < 0.3:
        return ORDER_FIX_BAYONETS

    if ranged_dpa >= 0.5 and _unit_has_rapid_fire(target):
        # FRFSRF is the canonical Lasgun-block Order — pick it on any
        # REGIMENT unit with real ranged DPA (almost every wired AM REGIMENT
        # infantry datasheet qualifies: Cadians, Krieg, Catachan, Kasrkin etc.)
        # — but ONLY when the unit actually carries a Rapid Fire weapon. The
        # codex effect buffs Rapid Fire weapons exclusively, so on a Leman
        # Russ or Rogal Dorn (no Rapid Fire profiles) the Order is a no-op;
        # those fall through to Take Aim! (+1 to hit), the order real players
        # issue to tanks (wave 243 mis-pilot fix).
        return ORDER_FRFSRF

    # Fallback — generic +1 to hit shooting.
    return ORDER_TAKE_AIM


# ---------------------------------------------------------------------------
# Dispatch — called once per army at the start of each Command phase
# ---------------------------------------------------------------------------

def dispatch_orders(army: "Army", battleshocked_uids: set) -> List[Tuple[str, str, str]]:
    """Issue Orders for each AM OFFICER for this Command phase.

    Returns a list of (officer_name, target_name, order_name) triples for
    event-log / verbose printing. Empty list when the army isn't AM,
    has no Officers, has no eligible targets, or no OFFICER is within
    aura range of any eligible target.

    Wahapedia rules respected:
      * Battle-shocked Officers cannot issue Orders (`battleshocked_uids`).
      * Battle-shocked targets cannot receive Orders (`battleshocked_uids`).
      * Each unit can only be affected by ONE Order per phase. The
        simulator stores one Unit instance per physical model, so the
        dispatcher groups model-instances into codex units by `squad_id`,
        applies the Order to every model of the chosen squad, and tracks
        `ordered_squads` to enforce no-stacking at the codex-unit level.
      * Each Officer issues up to its per-datasheet cap (from
        OFFICER_ORDER_PROFILES) per Command phase.
      * Order target must be within 6" of the issuing Officer (canonical
        OFFICER_AURA_RANGE).
      * Order target must satisfy the Officer's per-datasheet keyword
        restriction (REGIMENT / SQUADRON / TITANIC) as recorded in
        OFFICER_ORDER_PROFILES — OR be an AM SQUADRON unit if Flexible Command
        was fired this round (the two gates are OR-ed; the Flexible Command
        stratagem widens the army-wide eligible set independently of each
        Officer's own restriction).

    Cited as `simulator.voice_of_command_orders` in
    `data/rule_citations.d/astra_militarum.json`.
    """
    issued: List[Tuple[str, str, str]] = []
    if not any(
        (u.profile.faction or "") == "Astra Militarum" for u in army.units
    ):
        return issued

    squadron_allowed = bool(getattr(army, "orders_eligible_squadron_this_round", False))

    # Each codex OFFICER datasheet issues its capped Orders per round
    # regardless of how many model-instances share that profile name in the
    # army (Command Squads are multi-model datasheets — Cadian/Catachan
    # Command Squad min_models=5, Krieg Command Squad min_models=6, Militarum
    # Tempestus Command Squad min_models=5). The simulator stores each model
    # as its own Unit instance, so a 5-model squad produces 5 instances all
    # passing _is_am_officer. De-duplicating by profile.name collapses them
    # to ONE Order-issuer per codex datasheet, matching Voice of Command:
    # "each OFFICER [unit] … can issue Orders".
    # Wahapedia: https://wahapedia.ru/wh40k10ed/factions/astra-militarum/
    _seen_officer_names: set = set()
    officers = []
    for u in army.alive_units:
        if not _is_am_officer(u):
            continue
        if u.uid in battleshocked_uids:
            continue
        officer_name = u.profile.name or ""
        if officer_name in _seen_officer_names:
            continue  # already have one instance of this codex Officer unit
        _seen_officer_names.add(officer_name)
        officers.append(u)
    if not officers:
        return issued

    # Army-wide target pool: all alive, non-battle-shocked AM units that carry
    # at least one of REGIMENT, SQUADRON, or TITANIC. Using the real codex
    # keywords (wave 243) means Kasrkin, Tempestus Scions, Heavy Weapons
    # Squads, all Leman Russ variants, Rogal Dorn tanks, Sentinels, and other
    # datasheets that were previously invisible due to the BATTLELINE proxy are
    # now correctly included. Per-officer target-type filtering is applied
    # per-officer below (inside the aura filter) — this pool is a broad
    # pre-filter to avoid scanning every unit in the inner loop.
    all_targets = [
        u for u in army.alive_units
        if (u.profile.faction or "") == "Astra Militarum"
        and u.uid not in battleshocked_uids
        and bool(
            set(u.profile.unit_keywords or ()) & {"REGIMENT", "SQUADRON", "TITANIC"}
        )
    ]
    if not all_targets:
        return issued

    # ONE-UNIT-PER-MODEL CORRECTION (wave 243): the simulator stores one
    # Unit instance per physical model, but a codex Order affects the whole
    # codex unit ("While this unit is affected by an Order …"). The
    # dispatcher therefore groups the eligible pool into codex units
    # (squads, keyed by squad_id): an Order is applied to EVERY model of
    # the chosen squad, the squad counts as ONE target for the no-stacking
    # rule, and the priority heuristic compares squad aggregates. Before
    # this correction an Order buffed a single model — FRFSRF issued to a
    # 10-model Lasgun block improved one lasgun, diluting the Order's
    # value by squad size, while single-model vehicles received the full
    # effect.
    squads: Dict[object, List["Unit"]] = {}
    for t in all_targets:
        sid = getattr(t, "squad_id", -1)
        key: object = ("squad", sid) if sid >= 0 else ("solo", t.uid)
        squads.setdefault(key, []).append(t)

    def _squad_hp_frac_lost(key: object, members: List["Unit"]) -> float:
        """Squad-aggregate damage fraction for the Take Cover! branch.

        Casualties are removed whole-model under the 10e allocation rule,
        so the lost fraction must count ALL instances that ever belonged
        to the squad (alive or dead) — `members` only holds survivors.
        """
        if key[0] == "solo":
            u = members[0]
            try:
                return max(
                    0.0, 1.0 - u.current_health / max(1.0, u.profile.health)
                )
            except Exception:
                return 0.0
        sid = key[1]
        full_hp = 0.0
        cur_hp = 0.0
        for u in army.units:
            if getattr(u, "squad_id", -1) != sid:
                continue
            full_hp += float(u.profile.health or 0)
            if u.is_alive:
                cur_hp += max(0.0, float(u.current_health))
        if full_hp <= 0:
            return 0.0
        return max(0.0, 1.0 - cur_hp / full_hp)

    def _squad_priority(item: Tuple[object, List["Unit"]]) -> float:
        """Squad-aggregate version of the old per-model heuristic: total
        points at stake plus total damage-per-activation. Summing over
        members means a Lasgun block's volume of fire competes honestly
        with a single tank's price tag.
        """
        _key, members = item
        cost = 0.0
        dpa = 0.0
        for m in members:
            try:
                cost += float(m.profile.points_cost)
            except Exception:
                pass
            dpa += _unit_ranged_dpa(m) + _unit_melee_dpa(m)
        return cost + dpa * 10.0

    # ordered_squads: the set of squad keys that have reached their per-round
    # Order cap (1 for all squads, or 2 for the squad Ursula Creed is leading
    # when SWEG_CREED_TWO_ORDERS=1). A squad key is added here once it is full.
    #
    # squad_orders_received: maps each squad key to the set of Order names it
    # has been given this round. Used only when _CREED_TWO_ORDERS is True to
    # enforce "two DIFFERENT Orders" (same Order may not stack twice on the led
    # unit, and all other squads still cap at 1).
    ordered_squads: set = set()
    squad_orders_received: Dict[object, Set[str]] = {}

    # Resolve Creed's led-squad key once, before the officer loop.
    # The led squad is the squad whose members carry a UNIT_CATALOG key listed
    # in Creed's LeaderAbility.host_keys AND that has at least one model within
    # Creed's aura range. If the gate is off, or Creed is absent / dead, this
    # stays None and the logic below is entirely bypassed.
    _creed_led_squad_key: Optional[object] = None
    if _CREED_TWO_ORDERS:
        # Find the Creed officer instance (she may already be in `officers` —
        # find her directly from the alive army units to avoid iterating after
        # de-dup, and to access her position independently of the officers list).
        _creed_unit = next(
            (u for u in army.alive_units if (u.profile.name or "") == "Ursula Creed"),
            None,
        )
        if _creed_unit is not None:
            from .leaders import lookup_ability, _name_to_catalog_keys
            _creed_ability = lookup_ability("Ursula Creed")
            if _creed_ability is not None and _creed_ability.host_keys:
                _host_keys_set = set(_creed_ability.host_keys)
                for _squad_key, _members in squads.items():
                    # Check proximity first (at least one member in aura).
                    if not any(
                        _distance(_creed_unit.position, m.position) <= OFFICER_AURA_RANGE
                        for m in _members
                    ):
                        continue
                    # Check that this squad's members have a catalog key in host_keys.
                    _member_keys = _name_to_catalog_keys(
                        getattr(_members[0].profile, "name", "") or ""
                    )
                    if any(k in _host_keys_set for k in _member_keys):
                        _creed_led_squad_key = _squad_key
                        break  # only one squad can be led at a time

    for officer in officers:
        officer_name = officer.profile.name or ""
        # Per-datasheet caps and target-type restrictions sourced from
        # OFFICER_ORDER_PROFILES (BSData Library Astra Militarum cache).
        # _officer_target_types raises ValueError if the officer is absent —
        # fail loud per CLAUDE.md §13 (the import-time validation above
        # ensures this never fires in normal usage, but guards renames).
        orders_this_officer = OFFICER_ORDER_COUNTS[officer_name]
        officer_types = _officer_target_types(officer_name)

        for _ in range(orders_this_officer):
            # Find eligible squads with at least one alive model within 6" of
            # this Officer, filtered by:
            #   - not already at their per-round Order cap (1 for all squads;
            #     2 for the Creed-led squad when SWEG_CREED_TWO_ORDERS=1),
            #   - satisfies this Officer's per-datasheet target-type restriction
            #     OR falls under the Flexible Command SQUADRON widening (the two
            #     gates are OR-ed per the codex: Flexible Command overrides, it
            #     does not replace, per-Officer limits).
            # Keyword eligibility is per-datasheet, so testing one member
            # covers the squad.
            in_aura = [
                (key, members) for key, members in squads.items()
                if key not in ordered_squads
                and any(
                    _distance(officer.position, m.position) <= OFFICER_AURA_RANGE
                    for m in members
                )
                and _is_order_target_eligible(
                    members[0],
                    squadron_allowed=squadron_allowed,
                    officer_target_types=officer_types,
                )
            ]
            if not in_aura:
                break  # no more eligible squads in aura — stop early

            key, members = max(in_aura, key=_squad_priority)
            order = _pick_order_for_target(
                members[0], hp_frac_lost=_squad_hp_frac_lost(key, members)
            )

            # Gate ON: reject a duplicate Order on the Creed-led squad.
            # The codex wording is "two DIFFERENT Orders at the same time" —
            # issuing the same Order twice does not count as a second slot.
            # When this guard fires the issuance slot is consumed but no buff
            # is applied and the squad is not counted as full (consistent with
            # how a real player would resolve it: they simply cannot issue the
            # same Order again, so a third issuance would be needed, which is
            # outside the Officer's per-round cap anyway).
            if _CREED_TWO_ORDERS and key == _creed_led_squad_key:
                _already = squad_orders_received.get(key, set())
                if order in _already:
                    # Duplicate: mark the squad as full so subsequent
                    # iterations stop trying it.
                    ordered_squads.add(key)
                    continue

            for m in members:
                _apply_order(m, order)

            # Track which Orders this squad has received this round.
            if _CREED_TWO_ORDERS:
                existing = squad_orders_received.setdefault(key, set())
                existing.add(order)
                # Determine this squad's cap: 2 if it is the Creed-led squad,
                # else the normal cap of 1.
                _cap = 2 if key == _creed_led_squad_key else 1
                if len(existing) >= _cap:
                    ordered_squads.add(key)
            else:
                # Gate off: original one-Order cap, byte-identical behaviour.
                ordered_squads.add(key)

            issued.append((officer.profile.name, members[0].profile.name, order))

    return issued


__all__ = [
    "AM_OFFICER_NAMES",
    "OFFICER_ORDER_PROFILES",
    "OFFICER_ORDER_COUNTS",
    "OFFICER_AURA_RANGE",
    "ORDER_TAKE_AIM",
    "ORDER_FIX_BAYONETS",
    "ORDER_FRFSRF",
    "ORDER_TAKE_COVER",
    "WIRED_ORDERS",
    "_officer_target_types",
    "dispatch_orders",
]
