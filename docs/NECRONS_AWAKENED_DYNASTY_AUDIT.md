# Necrons Awakened Dynasty — Command Protocols Audit

**Wave:** 57 (2026-05-29)
**Branch:** claude/sim-calibration-6
**Auditor:** Claude Sonnet 4.6 (agent)
**Task:** Investigative audit — per-model amplification pattern check

---

## Context

Necrons sim 50.4% vs real 53.2% (-2.84 gated, noise 3.22) at wave-56 close.
The faction is in-band (just inside). This audit checks whether the
per-model amplification pattern (`[[project-one-unit-per-model-amplification]]`,
7 instances catalogued) applies to the Awakened Dynasty Command Protocols
`bonus_to_hit_when_led` path.

---

## Stage A — Baseline (20-battle archetype eval)

Setup: Necrons (Overlord + Necron Warriors + Immortals, Awakened Dynasty
detachment) vs Space Marines (Intercessor Squad + Assault Intercessor Squad).

Result: **Necrons 0/20 wins (0.0%)** — unexpected; see findings below.

`is_actually_led` call distribution across all 20 battles:

| Attacker | Total calls | True (buff fired) | False (buff blocked) |
|---|---:|---:|---:|
| Overlord | 243 | 0 | 243 |
| Necron Warriors | 116 | 0 | 116 |
| Immortals | 97 | 0 | 97 |

**100% False** — the `bonus_to_hit_when_led` buff did NOT fire once in 20 battles.

Root cause: `in_range_leaders()` returned empty for all calls. Tracing unit
positions during battle showed the Overlord placed at approximately (11", 14")
and Necron Warriors at (29", 13") — about 18" apart, well outside the Overlord's
6" aura range. The simulator's deployment logic spreads all units to distinct
positions at battle start; the Overlord and the Warriors are independent
Unit objects that move toward the nearest enemy, not toward each other.

In real 40k, a Leader formally attached to a unit moves inside the unit's
coherency; they are always within engagement distance. The simulator does not
model this — there is no "attached leader" data structure, only proximity
approximation with `aura_range = 6.0"`.

---

## Stage B — Targeted Checks

### B1 — Per-codex-unit gate: does each Warrior model's attack independently trigger the buff?

**Finding: NO amplification.** `effective_buffs()` is called ONCE at the top of
`Unit.attack()` (line 1099 in `code/units.py`) and the result is cached per unit
uid via `_buffs_cache`. The `is_actually_led()` call inside `effective_buffs`
therefore fires once per unit activation, not once per model. `n_attacks =
int(p.attacks)` is the squad-total attack count from the mapper — not per-model
to be multiplied. The for-loop `for _ in range(n_attacks)` iterates the shared
`plus_one_to_hit` boolean. No per-model amplification of the gate call exists.

### B2 — Multi-leader stacking: does two Overlords 0" from Warriors stack the +1?

**Finding: No stacking.** The `_merge_bool` helper uses OR-assignment. Two
Overlords within 6" both set `buffs["plus_one_to_hit"] = True`, which is
idempotent. The modifier cap at `hit_mod_clamped = max(-1, min(1, hit_mod_delta))`
(line 2157 in `code/units.py`) further constrains any path. No numeric stacking.

### B3 — Proximity check uses leader aura_range, not hardcoded 6"?

**Finding: Correct.** `in_range_leaders()` checks `ability.aura_range` (line
1122 in `code/leaders.py`), not a hardcoded constant. The Overlord's
`aura_range = 6.0` is sourced from the `LeaderAbility` dataclass entry.

### B4 — Detachment gate + leader host_keys compose cleanly?

**Finding: Correct.** Both paths use the same `_name_to_catalog_keys` reverse
lookup. Warriors, Immortals, and Lychguard resolve to host keys that match the
Overlord's `host_keys` tuple. Non-leadable units (Lokhust Heavy Destroyers,
Canoptek Wraiths, C'tan Shards — which have no catalog key) correctly fail the
gate and never receive the buff.

### B5 — Reanimation Protocols per-codex-unit gate regression check

**Finding: No regression.** `_apply_reanimation()` in `code/simulator.py`
(line 4424) operates per `profile.name` bucket, reviving at most
`min(destroyed, deaths_this_round, 1)` models per profile per round — the
per-squad gate that wave 28/49 verified. The SOROR-pattern regression cannot
have occurred here: reanimation fires in the end-of-round cleanup pass, not
inside the per-model attack loop.

---

## Stage C — Decision

### Is the per-model amplification pattern present?

**No.** The `bonus_to_hit_when_led` buff gate is called once per unit
activation (not per model), stores the result in a per-uid cache, and uses
boolean OR-merge. No amplification shape exists.

### Is there a different bug?

**Yes — the buff is effectively dead code in sim battles.** Because the
simulator places each Unit at an independent board position, the Overlord
and Warriors are never within 6" of each other during combat. The
`is_actually_led` proximity approximation, which was designed to approximate
the "formally attached" codex rule, fails systematically because attached
Leaders and their bodyguard squads do not co-locate in the simulator's
positional model.

**Effect on Necron metric:** The `bonus_to_hit_when_led` buff has been
contributing ZERO uplift in actual sim battles. Necrons' 50.4% simulated
win rate is achieved without this buff firing. The real-meta 53.2% Necron
rate is partially sustained by the Command Protocols led-unit bonus in
real games. This structural gap is a candidate explanation for the -2.84 pt
residual — but the residual is within noise (3.22 pt).

### Fix decision: PARK

A rule-correct fix would require implementing a proper "leader attached to
unit" registry so the Overlord and its bodyguard squad co-locate during
the sim. That is a simulator architecture change, not a targeted calibration
tweak. The current metric position (in-band, -2.84 gated vs 3.22 noise) does
not justify a structural change now.

A simpler proxy fix — changing `aura_range` to 0 (army-wide) for the Necron
Overlord — would push Necrons OVER their current position (buff now always
fires) without the host_keys gate being meaningful. That would over-correct.

**Decision: PARK with this note.** The `bonus_to_hit_when_led` proximity
approximation does not work in the current positional model. The correct fix
is an explicit leader-attachment registry (out-of-scope for wave 57).
The Necron metric should be tracked for improvement opportunities that do NOT
require changing this structural approximation.

---

## Test Results

```
76 passed, 1 xfailed in 0.51s
```

All tests passing. No code changes made.

---

*Generated by wave-57 audit agent. Top commit at audit time: 2588076.*
