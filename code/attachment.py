"""10e Leader / Attached-unit protection (gate: SWEG_LEADER_ATTACH).

Real 10e rule (Wahapedia core rules, "Leader"): a CHARACTER attaches to a
Bodyguard unit to form an Attached unit. When that unit is attacked, attacks
**must be allocated to Bodyguard models** while any remain — the Character
cannot be allocated wounds until the bodyguards are destroyed — UNLESS the
attack was made with a [PRECISION] weapon, which may be allocated to the
Character. Once the bodyguards are gone, the Character is a normal target.

SwegHammer models every physical model as its own `Unit` (one-Unit-per-model;
see the ground-truth note in DECISION_LEDGER), so there is no intra-unit
wound-allocation step to model. The faithful equivalent in this representation:
while a leader's bound host squad still has a living non-CHARACTER (bodyguard)
model, the leader cannot be SELECTED as the target of an attack (ranged or
melee) — the enemy's fire lands on the separate bodyguard squad instead, the
identical outcome. [PRECISION] bypasses. When the host squad is dead the leader
becomes a normal target (then Lone Operative / normal rules apply).

This REPLACES the fabricated "Look Out, Sir" gate (deleted 2026-07-13; not a real
10e rule — it grafted Lone Operative's 12" clause onto a rule name that does not
exist in the 10e core rules).
Lone Operative is a separate, correct ability handled in
`army.can_target_for_ranged`.

Multi-leader hosts are allowed (e.g. Necron Cryptek + Overlord on one squad,
Cryptek + Cryptothralls): binding does not cap the number of leaders per squad.

Cited: LEADER.attached_unit_allocation + LEADER.precision_bypass in
data/rule_citations.d/core_targeting.json.
"""
from __future__ import annotations

import functools
import json
import os
from typing import Dict, Iterable, Optional, Tuple

_NON_ATTACH_KW = frozenset({"MONSTER", "VEHICLE", "TITANIC"})

# Max Leaders a single bodyguard unit can carry. 10e allows one, with specific
# rules permitting a second (Necron Cryptek + a Noble; several stacking clauses).
# Two is the faithful upper bound; excess leaders stay unattached (exposed).
_MAX_LEADERS_PER_SQUAD = 2

# Catalog-key attach map (data/leader_attach_targets.json): {leader UNIT_CATALOG
# key: [host UNIT_CATALOG keys]}. Keyed by CATALOG KEY (unique per faction) so it
# is immune to the cross-faction substring collisions in `lookup_ability`
# (Sorcerer x3, Master of Executions x2, the Space Marines Captain/Chaplain/
# Librarian variants). Populated from the BSData-validated gap-fill (four agents,
# 2026-07-12; see docs/LEADER_ATTACHMENT.md). Consulted FIRST by bind_leaders,
# ahead of the name-substring registry. This map only drives ATTACHMENT — it
# never touches the aura-buff `host_keys` gate in leaders.py, so it is
# calibration-neutral for the aura system.


@functools.lru_cache(maxsize=1)
def _attach_targets() -> Dict[str, Tuple[str, ...]]:
    """Load + cache the catalog-key attach map. Silently empty if the data file
    is absent (the mechanic falls back to the registry host_keys)."""
    import os.path as _p
    path = _p.join(_p.dirname(_p.dirname(_p.abspath(__file__))),
                   "data", "leader_attach_targets.json")
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        return {}
    return {k: tuple(v) for k, v in raw.items() if isinstance(v, list) and v}


def attachment_enabled() -> bool:
    """SWEG_LEADER_ATTACH gate. DEFAULT-ON (adopted 2026-07-13). The fabricated
    "Look Out, Sir" gate it replaced has been deleted, so `SWEG_LEADER_ATTACH=0`
    is a kill-switch meaning NO character protection (for A/B / debugging), not a
    revert to Look Out Sir."""
    return os.environ.get("SWEG_LEADER_ATTACH", "1") != "0"


def _squad_dedupe_enabled() -> bool:
    """SWEG_LEADER_SQUAD_DEDUPE gate. DEFAULT-ON (adopted 2026-07-13: paired N=40
    vs sc64a improved gated MAE 2.41→2.22 A-frame / 2.83→2.73 symmetrized, AM
    +1.9pp; promoted anchor sc65a). `SWEG_LEADER_SQUAD_DEDUPE=0` reverts to the
    legacy per-model binding (byte-identical to sc64a) for A/B / debugging.

    Fixes a BSData sub-model keyword-promotion bug: a handful of multi-model
    LEADER units (Cadian / Krieg / Catachan / Militarum Tempestus Command
    Squads, Dark Apostle, Dark Commune, Brôkhyr Iron-master, Grimnyr,
    Hyperadapted Raveners, Ravenwing Command Squad, Rogue Trader Entourage,
    Traitor Enforcer — Wahapedia-verified 2026-07-13) carry the CHARACTER
    keyword on ALL models when only the single embedded commander is a
    CHARACTER. Because every one of those models then reads as an attachable
    leader, the squad hogs N of a host's `_MAX_LEADERS_PER_SQUAD` slots and
    crowds the army's REAL single-model characters out of a host (they go
    unbound = unprotected = Assassination-exposed). When ON, a character squad
    that shares one squad_id binds to a host as ONE leader entity (one slot,
    all its models pointed at the same host), never once per model.
    See docs/LEADER_ATTACHMENT.md."""
    return os.environ.get("SWEG_LEADER_SQUAD_DEDUPE", "1") != "0"


def _is_attachable_character(profile) -> bool:
    """A CHARACTER that can attach as a Leader — excludes MONSTER / VEHICLE /
    TITANIC characters (Knights, Greater Daemons, C'tan) which never attach."""
    kw = set(profile.unit_keywords or ())
    return "CHARACTER" in kw and not (kw & _NON_ATTACH_KW)


def _resolve_attach(profile, amap) -> Tuple[str, ...]:
    """Attach-target UNIT_CATALOG keys for a leader profile: the catalog-key map
    (`amap`) FIRST (unique keys, no substring collisions, includes gap-fill
    leaders absent from the registry), then the registry's attach_keys/host_keys
    as fallback. Empty tuple = not a leader / army-wide aura with no attach
    target. `amap` values are guaranteed non-empty by `_attach_targets`."""
    from .leaders import lookup_ability, _name_to_catalog_keys
    for ck in _name_to_catalog_keys(profile.name):
        if ck in amap:
            return amap[ck]
    ability = lookup_ability(profile.name)
    if ability is not None:
        return (ability.attach_keys if ability.attach_keys is not None
                else ability.host_keys)
    return ()


def bind_leaders(army) -> None:
    """Deploy-time hard bind: assign each attachable leader a host squad_id.

    Sets `unit._attach_host_squad_id` on every unit (None = unattached / exposed).
    A leader binds to a squad whose bodyguard models' UNIT_CATALOG key is in the
    leader's `LeaderAbility.host_keys`. Prefers the least-loaded legal squad so
    leaders spread 1-per-squad when possible, and multiple leaders share a squad
    only when there are more leaders than legal hosts (multi-leader allowed).
    Idempotent. No-op behaviourally unless `attachment_enabled()` is read later.

    With `SWEG_LEADER_SQUAD_DEDUPE` ON, a multi-model LEADER unit (a character
    squad sharing one squad_id) binds as ONE leader entity — one host slot, all
    its models pointed at the same host — instead of once per model. Default OFF
    reproduces the per-model binding byte-identically (see `_squad_dedupe_enabled`).
    """
    from .leaders import _name_to_catalog_keys

    # Map squad_id -> the set of UNIT_CATALOG keys of its non-CHARACTER models.
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
    load: dict = {}  # squad_id -> leaders already bound (for least-loaded spread)

    def _bind_group(members: list) -> None:
        """Bind one leader ENTITY (a lone character, or all models of a
        character squad) to one least-loaded legal host, or leave it exposed.
        A bodyguard unit takes at most `_MAX_LEADERS_PER_SQUAD` leaders (10e
        allows one, occasionally two — e.g. Necron Cryptek + Overlord); a leader
        with no free legal host stays UNATTACHED / exposed."""
        attach = _resolve_attach(members[0].profile, amap)
        if not attach:
            return  # not a leader / army-wide aura with no attach target
        legal = [sid for sid, keys in squad_keys.items()
                 if load.get(sid, 0) < _MAX_LEADERS_PER_SQUAD
                 and any(k in attach for k in keys)]
        if not legal:
            return  # no free legal host present -> unattached (exposed)
        sid = min(legal, key=lambda s: load.get(s, 0))
        for m in members:
            m._attach_host_squad_id = sid
        load[sid] = load.get(sid, 0) + 1

    if not _squad_dedupe_enabled():
        # LEGACY per-model binding (byte-identical off): every attachable
        # CHARACTER model-Unit binds independently — so a multi-model leader
        # squad (all models CHARACTER-tagged) consumes N host slots.
        for u in army.units:
            u._attach_host_squad_id = None
            if _is_attachable_character(u.profile):
                _bind_group([u])
        return

    # DEDUPE: group attachable-character model-Units by squad_id (a multi-model
    # leader squad shares one squad_id; each lone character has its own), then
    # bind each GROUP as a single leader so a squad claims only one host slot.
    groups: dict = {}
    order: list = []
    for u in army.units:
        u._attach_host_squad_id = None
        if not _is_attachable_character(u.profile):
            continue
        sid = getattr(u, "squad_id", None)
        key = sid if isinstance(sid, int) and sid >= 0 else ("lone", id(u))
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(u)
    for key in order:
        _bind_group(groups[key])


def _host_squad_has_bodyguard(defender_units: Iterable, squad_id) -> bool:
    """True iff squad `squad_id` still has a living non-CHARACTER (bodyguard)
    model among `defender_units`."""
    for u in defender_units:
        if getattr(u, "squad_id", None) != squad_id:
            continue
        if not getattr(u, "is_alive", False):
            continue
        if "CHARACTER" not in set(u.profile.unit_keywords or ()):
            return True
    return False


def is_attachment_protected(target, defender_units: Iterable) -> bool:
    """True iff `target` is an attached leader whose host squad still has a
    living bodyguard model — i.e. it cannot be allocated wounds (selected as a
    target) yet. The [PRECISION] bypass is applied by the caller. Returns False
    when the gate is off, so callers stay byte-identical in the legacy path."""
    if not attachment_enabled():
        return False
    sid = getattr(target, "_attach_host_squad_id", None)
    if sid is None:
        return False
    return _host_squad_has_bodyguard(defender_units, sid)
