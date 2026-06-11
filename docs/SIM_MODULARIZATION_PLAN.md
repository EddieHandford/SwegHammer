# Simulator modularization plan

## Goal

`code/simulator.py` is a single module of about 13,400 lines. Everything from
the battle result data class, through the geometry helpers, the win condition,
the secondary and primary scoring, the per-faction stratagem dispatchers, the
deployment and reserves logic, the per-phase move / shoot / charge / fight
engines, and the transport and command-point machinery lives in one file. A
file this large is slow to load into a reader's head, slow to search, and a
constant source of merge conflicts when several calibration waves touch it at
once.

This plan splits the module into a `code/sim/` package by **pure code motion**.
The public import surface does not change: `code/simulator.py` stays as the
import that the rest of the code base and the tests use, and re-exports every
public name from the new package, so nothing downstream breaks. Over the course
of the staged extractions it shrinks from a 13,400-line module to a thin facade
over the package.

This is calibration scaffolding (Stage 1 in the project's two-stage pipeline
sense — it touches the simulator's structure, not the points equation), but it
deliberately changes **no behaviour at all**. It is a refactor, not a rule
change.

## The hard constraint: provable determinism

The calibration loop relies on paired common-random-number evaluations and on
reusing a saved evaluation as an anchor for the next comparison. Both die if the
random number generator call order shifts even slightly between two trees that
are supposed to be equivalent. Therefore every extraction step in this plan must
be **provably behaviour-identical**.

"Pure code motion" here means exactly that, with no latitude:

- zero logic edits — not even a rename, a reordered argument, or a "while I am
  here" tidy;
- zero reordering of dictionary or set construction or iteration (iteration
  order is observable through `PYTHONHASHSEED=0`-pinned set traversal, which the
  simulator's trackers rely on);
- zero change to the order in which random rolls happen;
- zero change to import side effects or to when module-level code runs.

If something looks like it should be fixed while moving it, it is **not** fixed
in a motion commit. It is recorded as a follow-up and left exactly as found.

## Proof protocol — run after every single commit

1. **Full test suite**, single process (no parallel workers, because an
   expensive evaluation may be running on the same machine):
   `PYTHONHASHSEED=0 python -m pytest -q`. The pass / skip / xfail counts must
   not change.
2. **Motion-proof fingerprint**: `python scripts/sim_motion_proof.py`. The
   printed `FINGERPRINT sha256=...` line must equal the recorded baseline byte
   for byte. A different fingerprint means the motion changed behaviour; find it
   and fix it before committing — never re-record a new baseline to make a
   changed hash "pass".
3. **Rule-citation audit**: `python -m scripts.audit_rules` must stay clean
   (exit zero — no missing or malformed citations). The audit derives its
   required rule set from the imported `Detachment` / `LeaderAbility` /
   `Stratagem` / enhancement registries and from a hard-coded list of simulator
   gate key strings; it does not scan the simulator source text by file, so
   moving code between files does not change what it checks. No audit
   configuration change is needed for the Stage A extractions.
4. **Command-line demo**: `PYTHONIOENCODING=utf-8 python run.py --cli` exits
   zero (it imports and runs through the facade, so it catches a broken
   re-export).

### Baseline (recorded on the unmodified tree, commit `b3195f9`)

- Motion-proof fingerprint:
  `df0fef4a0be5ec50fee8aa2da0c7ec7b786ab85081099027f9eb7937f7ceabc0`
- Test suite: 1473 passed, 1 skipped, 1 xfailed.
- Rule-citation audit: clean (all active rules cited and well-formed).

Note on the command-line demo: `run.py --cli` is itself **not** deterministic
across consecutive runs, because the demo battle does not seed the global random
number generator before running. That is exactly why the motion proof is a
separate, explicitly seeded harness rather than a comparison of two
command-line runs.

## Facade strategy

`code/simulator.py` remains the single import surface. After each extraction it
imports the moved names back from the new package module, using explicit import
lists (not wildcard imports) so the re-exported surface is auditable. Three
properties matter:

- **Name availability.** Both `from code.simulator import Name` and
  `simulator.Name` (attribute access through `import code.simulator`) must keep
  resolving. An explicit re-import at the top of the facade satisfies both.
- **Object identity for mutated module globals.** Several instrument
  dictionaries (for example `OCFLIP_STATS`, `BOARDCONTROL_STATS`,
  `DELIVERY_STATS`, `OVERSCORE_STATS`, `SHOOTLOSS_STATS`,
  `PATHFIND_STAGE0_STATS`, `REACH_STATS`) are mutated in place from outside the
  module — the board-control and reach diagnostic scripts call `.clear()`,
  `.update(...)`, and read them back. Re-importing a name binds the same object,
  so `simulator.OCFLIP_STATS is code.sim.constants.OCFLIP_STATS` and a
  diagnostic that resets one sees the same dictionary the geometry helper
  mutates. The extraction must preserve this single-object identity; it does,
  because a plain `from ... import OCFLIP_STATS` rebinds the name to the same
  dict.
- **No new import cycles.** The package is layered so lower modules never import
  higher ones (see the dependency note under Stage A).

## Module map of `code/simulator.py`

Approximate line ranges on the `b3195f9` tree (they will shift as extractions
land; this is the starting map).

| Lines | Section | Target module | Stage |
|---|---|---|---|
| 1–84 | Module docstring and imports | facade keeps its own imports | n/a |
| 91–119 | `BattleResult` data class | `code/sim/result.py` | B (data classes) |
| 126–127 | `_distance` geometry helper | `code/sim/geometry.py` | **A** |
| 130–195 | `_OccupantGrid` spatial hash | `code/sim/geometry.py` | **A** |
| 198–217 | `_collision_pos_legal` | `code/sim/geometry.py` | **A** |
| 220–271 | `_enemy_path_cap_t` | `code/sim/geometry.py` | **A** |
| 274–309 | `_fan_to_goal` | `code/sim/geometry.py` | **A** |
| 312–445 | `_move_toward` | `code/sim/geometry.py` | **A** |
| 455–461 | Round / coherency / command-point constants | `code/sim/constants.py` | **A** |
| 463–539 | Instrument statistics dictionaries and pathfinding threshold | `code/sim/constants.py` | **A** |
| 542–560 | `_bc_model_radius_in` (read-only footprint helper) | `code/sim/geometry.py` | **A** |
| 563–615 | `RulesConfig` frozen data class | `code/sim/config.py` | B (data classes) |
| 618–862 | `Battle.__init__` and battle-instance setup | `code/sim/battle/core.py` | last (high coupling) |
| 866–1142 | `Battle.run` public entry point | `code/sim/battle/core.py` | last |
| 1143–1694 | Win condition: objectives, attrition, points, primary scoring | `code/sim/scoring/primary.py` | scoring/missions |
| 1695–2417 | Action cards: cleanse, sabotage, burn, terraform | `code/sim/scoring/actions.py` | scoring/missions |
| 2418–2630 | Tactical-secondary pursuit layer | `code/sim/scoring/secondaries.py` | scoring/missions |
| 2631–2888 | Secondary dedication planner and action-cost contract | `code/sim/scoring/secondaries.py` | scoring/missions |
| 2889–3375 | Board secondaries, tactical deck, secondary scoring | `code/sim/scoring/secondaries.py` | scoring/missions |
| 3376–3510 | Reanimation protocols, detachment stratagem dispatch entry | `code/sim/engines/command.py` | command/battle-shock |
| 3511–6440 | Per-faction stratagem dispatchers (every `_try_*` method) | `code/sim/stratagems/` | artificial-intelligence / decision layer |
| 6444–6720 | Cabal of Sorcerers rituals (Thousand Sons) | `code/sim/engines/command.py` | command |
| 6722–7530 | Per-army-rule appliers: daemonic ordnance, dark pacts, combat drugs, bondsman, blessings of khorne, psychic phase, cult ambush resurgence, reanimation | `code/sim/engines/command.py` | command |
| 7535–7915 | Deployment and reserves: assign UIDs, deploy, screen split, deploy line | `code/sim/engines/deployment.py` | reserves/deployment |
| 7916–8358 | Scout phase, reserves arrival, arrival-point picking | `code/sim/engines/deployment.py` | reserves/deployment |
| 8359–9075 | Battle-shock: per-squad test, shadow-in-the-warp, battle-shock phase, battle-focus tokens | `code/sim/engines/battleshock.py` | command/battle-shock |
| 9076–9754 | `_run_round` round logic | `code/sim/battle/core.py` | last |
| 9755–10126 | Round alternation, vanilla turns, relentless carnage | `code/sim/battle/core.py` | last |
| 10127–10416 | Coherency enforcement, make-way / clear-lane planner | `code/sim/engines/movement.py` | movement |
| 10417–10635 | `_do_move` movement engine | `code/sim/engines/movement.py` | movement |
| 10636–11059 | Threat / focus-fire / split-fire target heuristics, defender allocation | `code/sim/engines/shooting.py` (and decision helpers) | shooting / AI |
| 11060–11674 | `_do_shoot` shooting engine and blood surge | `code/sim/engines/shooting.py` | shooting |
| 11675–11924 | Charge intent, go-to-ground, fire overwatch | `code/sim/engines/charge.py` | charge |
| 11925–12059 | `_do_charge` charge engine | `code/sim/engines/charge.py` | charge |
| 12060–12303 | Fight alternation and `_do_fight` fight engine | `code/sim/engines/fight.py` | fight |
| 12304–12837 | Event emission, markerlight phase, oath / machine-vengeance target pick, blood tithe / miracle die / judgement token / deadly demise awards | `code/sim/engines/` (split by phase) | shooting / command |
| 12838–13173 | Transports: embark, disembark, destroyed-transport, firing deck | `code/sim/engines/transport.py` | movement/shooting adjacent |
| 13174–13399 | Command-point award, stratagem firing, command re-roll, tank shock, counter-offensive | `code/sim/engines/command.py` | command |

The large `Battle` class itself is the deepest coupling problem: most of the
rows above are methods on one class that read and write a great deal of shared
instance state (`self._reserves`, `self._advanced_this_round`,
`self._squad_*`, and so on). Extracting them is not a simple cut-and-paste of a
free function; it needs either a mixin decomposition (the `Battle` class
inherits from several phase mixins, each in its own module) or free functions
that take the battle as their first argument. That work is later in the
sequence, by design. Stage A deliberately takes only the material that is
already free of `Battle` instance state.

## Staged extraction sequence

The sequence runs lowest coupling first, because each later stage can rely on
the earlier ones already being in place, and because the lowest-coupling
material is the safest place to prove the proof protocol itself works.

1. **Stage A — constants, dice, geometry (this stage).** Module-level constants
   and static data tables; pure dice and probability helpers; pure geometry
   helpers that are free of battle state. The lowest-coupling material in the
   file. Detail below.
2. **Stage B — data classes.** `BattleResult` and `RulesConfig`. These are
   plain dataclasses with no `Battle` coupling; they move next, into
   `code/sim/result.py` and `code/sim/config.py`.
3. **Per-phase engines, one subsystem per commit, in this order:** movement,
   shooting, fight, charge, command and battle-shock, scoring and missions,
   reserves and deployment. Each engine is a coherent group of `Battle` methods;
   they are extracted as phase mixins (or battle-first free functions) so the
   instance state they share is threaded explicitly. Each is one commit, each
   re-proved against the fingerprint.
4. **Artificial-intelligence and decision layers last.** The per-faction
   stratagem dispatchers and the target-selection heuristics churn most under
   the calibration loop and have the widest coupling to the rest of the battle,
   so they move last, when the surrounding structure is already settled.

## Stage A detail

Stage A creates the `code/sim/` package and extracts, one module per commit:

### `code/sim/constants.py`

The module-level constants and the instrument statistics dictionaries:

- `MAX_ROUNDS`, `CP_BONUS_DIVISOR`, `CP_BONUS_CAP`, `COHERENCY_INCHES`;
- `_PATHFIND_BIG_RADIUS_IN`;
- the read-only / instrument dictionaries `OCFLIP_STATS`, `OVERSCORE_STATS`,
  `DELIVERY_STATS`, `SHOOTLOSS_STATS`, `BOARDCONTROL_STATS`,
  `PATHFIND_STAGE0_STATS`, `REACH_STATS`.

These have no dependency on anything else in the simulator, so the module is a
leaf. The facade re-imports each name. Identity is preserved for the
externally-mutated dictionaries (see the facade strategy section), so the
board-control, delivery, over-score, shoot-loss, objective-control-flip,
pathfinding-stage-zero, and reach diagnostics keep resetting and reading the
same objects.

### `code/sim/dice.py`

**Empty for Stage A — recorded, not forced.** A scan of `code/simulator.py`
found no module-level pure dice or probability helper functions to extract. All
random rolls in the simulator are done inline inside `Battle` methods (direct
`random.randint(1, 6)` / `random.random()` calls), and the one reusable pure
dice helper that does exist in the code base, `roll_damage`, already lives in
`code/units.py`, not in the simulator. There is therefore nothing for a
`code/sim/dice.py` to hold in Stage A. Rather than invent a module with no
content, this stage does **not** create `dice.py`. If a future stage factors the
inline rolling into named helpers, that is the moment to create it — and that
would be a logic-touching change, out of scope for pure motion.

### `code/sim/geometry.py`

The pure geometry helpers, all of which are free of `Battle` instance state —
they take positions, a map, and an occupant list as plain arguments:

- `_distance`;
- `_OccupantGrid` (the per-mover spatial hash);
- `_collision_pos_legal`;
- `_enemy_path_cap_t`;
- `_fan_to_goal`;
- `_move_toward`;
- `_bc_model_radius_in` (a read-only model-footprint helper; it reads only a
  profile's base dimensions, so it is battle-state-free and belongs with the
  geometry group rather than with the constants).

Dependency note for `geometry.py`: these helpers import `Map` from `code.map`
and `find_path` from `code.pathfind` (both already external to the simulator),
and they read and mutate the instrument dictionaries `PATHFIND_STAGE0_STATS` and
`REACH_STATS` plus the threshold `_PATHFIND_BIG_RADIUS_IN`. Because the
constants land first, `geometry.py` imports those names from
`code/sim/constants.py`. This keeps the layering clean: `constants` is a leaf,
`geometry` depends only on `constants` (within the package) plus the already-
external `code.map` and `code.pathfind`. The facade re-imports the geometry
names so `from code.simulator import _distance, _move_toward, _OccupantGrid,
_collision_pos_legal, _enemy_path_cap_t` (used by tests and the melee /
collision diagnostics) keeps resolving.

### What Stage A deliberately leaves behind

Every geometry-adjacent helper that touches `Battle` instance state stays in the
`Battle` class for a later stage. In particular the make-way / clear-lane /
ring-slot planner (`_make_way`, `_clear_lane`, `_ring_slots`, `_make_way_slot`,
`_make_way_target`) reads `self` state and is part of the movement engine, not
the pure geometry layer, so it is not in Stage A. Coherency enforcement
(`_enforce_squad_coherency`) is likewise a `Battle` method and stays for the
movement-engine stage.

## Things noticed but deliberately not changed

Pure motion means leaving these exactly as found; they are recorded here so the
observation is not lost:

- The geometry helpers reach for the environment with `__import__("os")` inline
  (for example the `SWEG_PATHFIND_STAGE0` / `SWEG_REACH_INSTR` /
  `SWEG_PATHFIND` / `SWEG_REACH_FIX` gates inside `_move_toward`) rather than
  using the module-level `import os`. This is a stylistic wart, not a bug, and
  rewriting it would be a logic-touching edit, so it is preserved verbatim
  through the move.
- `_move_toward` and `_fan_to_goal` do `import math as _m` inside the function
  body. Same reasoning: preserved as-is.
- The instrument dictionaries carry long explanatory comments inline. They move
  with the code unchanged, comments included.
