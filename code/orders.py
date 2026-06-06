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
    * First Rank, Fire! Second Rank, Fire! — `transient_plus_one_to_hit_shooting`
      on target unit. APPROXIMATION: codex effect is +1 Attack on Rapid
      Fire weapons (a per-weapon attack-count uplift). SwegHammer has no
      transient attack-count buff, so the value is routed through +1 to
      hit shooting — same direction (more landed hits on shooting),
      magnitude is comparable on a Lasgun (1A) target where +1 hit on
      RF 1 closes a 4+ to a 3+, matching the doubled shot count's
      expected hits.
    * Take Cover! — `transient_plus_one_save` on target unit. Direct
      mapping; codex effect is "+1 to save (cannot improve better than
      3+)" which lines up exactly with our +1-save flag (the 3+ cap is
      a real-codex restriction that SwegHammer drops; AM BATTLELINE
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
    * Target: alive, non-Battle-shocked friendly BATTLELINE INFANTRY
      with faction == "Astra Militarum", within 6" of the issuing
      Officer. SwegHammer doesn't model the codex REGIMENT keyword
      directly; we map REGIMENT → BATTLELINE INFANTRY (the codex
      eligible-target set for Voice of Command). The Flexible Command
      stratagem widens this to also include VEHICLE BATTLELINE for the
      round (Leman Russ etc.) by setting `Army.orders_eligible_squadron
      _this_round = True`.
    * At most one Order per unit per round (subsequent Orders to the
      same unit are skipped — no Order stacking).

Cited per CLAUDE.md §10 as `simulator.voice_of_command_orders` in
`data/rule_citations.d/astra_militarum.json`. Each Order's verbatim
codex text is cited under `Order.<name>`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, Tuple

if TYPE_CHECKING:
    from .army import Army
    from .units import Unit


# ---------------------------------------------------------------------------
# Order eligibility helpers
# ---------------------------------------------------------------------------

OFFICER_AURA_RANGE: float = 6.0   # 10e canonical (Voice of Command)


# Canonical AM OFFICER datasheets — only these can issue Voice of Command
# Orders. Sourced from Wahapedia AM faction page
# (https://wahapedia.ru/wh40k10ed/factions/astra-militarum/) by reading
# each CHARACTER datasheet's keyword line. The OFFICER keyword is the
# codex gate for issuing Orders; BSData v10.6.0's parsed unit_keywords
# field does not preserve it (the bsdata mapper retains only INFANTRY /
# VEHICLE / BATTLELINE / CHARACTER / EPIC HERO / PSYKER / MOUNTED /
# WALKER / MONSTER), so the gate has to be applied via an allowlist of
# unit catalogue keys.
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


def _is_order_target_eligible(unit: "Unit", squadron_allowed: bool = False) -> bool:
    """True iff the unit is an alive AM BATTLELINE INFANTRY unit (REGIMENT).

    When `squadron_allowed` is True (set by Flexible Command, Combined
    Arms stratagem), AM BATTLELINE VEHICLE units (SQUADRON) are also
    eligible.
    """
    if not unit.is_alive:
        return False
    if (unit.profile.faction or "") != "Astra Militarum":
        return False
    kw = set(unit.profile.unit_keywords or ())
    if "BATTLELINE" not in kw:
        return False
    if "INFANTRY" in kw and "VEHICLE" not in kw:
        return True
    if squadron_allowed and "VEHICLE" in kw:
        return True
    return False


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
        # APPROXIMATION: +1 Attack on Rapid Fire weapons → +1 to hit
        # shooting (same single-flag transient slot as Take Aim!).
        target.transient_plus_one_to_hit_shooting = True
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


def _pick_order_for_target(target: "Unit") -> str:
    """Greedy: pick the Order that maximises expected value for `target`.

    Heuristic:
      * If the unit has been damaged (>20% HP loss), prefer Take Cover! —
        the +1 save preserves the remaining points.
      * Else if the unit has meaningful melee DPA AND no ranged DPA,
        pick Fix Bayonets! (no shoot-relevant alternative).
      * Else if the unit has rapid-fire ranged DPA, pick First Rank
        Fire / Second Rank Fire (matches the codex use case for Cadians
        / Krieg / Catachan Lasgun blocks — the canonical FRFSRF target).
      * Else pick Take Aim! (generic +1 to hit shooting).

    Lasgun-heavy BATTLELINE squads typically have ranged_dpa > 0 and
    melee_dpa < 0.5; the FRFSRF branch fires on them as intended.
    Bullgryns/Ogryns (melee-only) hit the Fix Bayonets! branch.
    """
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

    if ranged_dpa >= 0.5:
        # FRFSRF is the canonical Lasgun-block Order — pick it on any
        # BATTLELINE INFANTRY with real ranged DPA (almost every wired
        # AM BATTLELINE infantry datasheet qualifies).
        return ORDER_FRFSRF

    # Fallback — generic +1 to hit shooting.
    return ORDER_TAKE_AIM


# ---------------------------------------------------------------------------
# Dispatch — called once per army at the start of each Command phase
# ---------------------------------------------------------------------------

def dispatch_orders(army: "Army", battleshocked_uids: set) -> List[Tuple[str, str, str]]:
    """Issue one Order per AM OFFICER for this Command phase.

    Returns a list of (officer_name, target_name, order_name) triples for
    event-log / verbose printing. Empty list when the army isn't AM,
    has no Officers, has no eligible targets, or no OFFICER is within
    aura range of any eligible BATTLELINE INFANTRY.

    Wahapedia rules respected:
      * Battle-shocked Officers cannot issue Orders (`battleshocked_uids`).
      * Battle-shocked targets cannot receive Orders (`battleshocked_uids`).
      * Each unit can only be affected by ONE Order per phase (the
        dispatcher tracks `ordered_uids` to enforce no-stacking).
      * Each Officer issues at most one Order this Command phase (the
        codex caps higher-rank Officers at 2-3; SwegHammer caps at 1
        as the per-Officer baseline — Flexible Command stratagem doesn't
        widen the per-Officer cap, only the eligible-target set).
      * Order target must be within 6" of the issuing Officer (canonical
        OFFICER_AURA_RANGE).
      * Order target must be AM BATTLELINE INFANTRY (REGIMENT) — or AM
        BATTLELINE VEHICLE (SQUADRON) if Flexible Command was fired this
        round (the `Army.orders_eligible_squadron_this_round` flag).

    Cited as `simulator.voice_of_command_orders` in
    `data/rule_citations.d/astra_militarum.json`.
    """
    issued: List[Tuple[str, str, str]] = []
    if not any(
        (u.profile.faction or "") == "Astra Militarum" for u in army.units
    ):
        return issued

    squadron_allowed = bool(getattr(army, "orders_eligible_squadron_this_round", False))

    # Each codex OFFICER datasheet issues ONE Order per round regardless of
    # how many model-instances share that profile name in the army (Command
    # Squads are multi-model datasheets — Cadian/Catachan Command Squad
    # min_models=5, Krieg Command Squad min_models=6, Militarum Tempestus
    # Command Squad min_models=5). The simulator stores each model as its
    # own Unit instance, so a 5-model squad produces 5 instances all
    # passing _is_am_officer. De-duplicating by profile.name collapses them
    # to ONE Order-issuer per codex datasheet, matching Voice of Command:
    # "each OFFICER [unit] … can issue one Order".
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

    # Eligible target pool (AM BATTLELINE INFANTRY, plus VEHICLE if Flexible
    # Command is active). Exclude battle-shocked units.
    targets = [
        u for u in army.alive_units
        if _is_order_target_eligible(u, squadron_allowed=squadron_allowed)
        and u.uid not in battleshocked_uids
    ]
    if not targets:
        return issued

    ordered_uids: set = set()
    for officer in officers:
        # Find eligible targets within 6" of this Officer.
        in_aura = [
            t for t in targets
            if t.uid not in ordered_uids
            and _distance(officer.position, t.position) <= OFFICER_AURA_RANGE
        ]
        if not in_aura:
            continue

        # Greedy: prioritise the target whose chosen Order has the
        # highest expected swing (cost × applicability). We use a coarse
        # heuristic — pick the highest-DPA target in aura, then assign
        # the best Order for that target. This biases toward
        # FRFSRF on big Lasgun blocks (their DPA dominates) which
        # matches real-meta usage.
        def _target_priority(u: "Unit") -> float:
            try:
                cost = float(u.profile.points_cost)
            except Exception:
                cost = 0.0
            dpa = _unit_ranged_dpa(u) + _unit_melee_dpa(u)
            return cost + dpa * 10.0

        target = max(in_aura, key=_target_priority)
        order = _pick_order_for_target(target)
        _apply_order(target, order)
        ordered_uids.add(target.uid)
        issued.append((officer.profile.name, target.profile.name, order))

    return issued


__all__ = [
    "AM_OFFICER_NAMES",
    "OFFICER_AURA_RANGE",
    "ORDER_TAKE_AIM",
    "ORDER_FIX_BAYONETS",
    "ORDER_FRFSRF",
    "ORDER_TAKE_COVER",
    "WIRED_ORDERS",
    "dispatch_orders",
]
