# Per-unit-vs-per-model mechanics audit (2026-05-31)

A systematic sweep (four parallel read-only audits) for 10th-edition rules that are
**per unit** but applied **per model**, because the engine models one `Unit` object
per physical model. `squad_id` (added this session: `Unit.squad_id`, `Army.add_squad`,
`Army.squads()`) is now the fix key for almost all of them.

**Already fixed this session** (not findings): normal damage-allocation spillover,
mortal-wound spillover, Deadly Demise per-unit, Blast squad-scoping.

**Correctly handled (verified, no fix needed):** per-model saves / invuln / Feel No
Pain rolls (10e rolls these per model), Engage on All Fronts / Behind Enemy Lines
(set/quadrant occupancy, not model count), Contagions of Nurgle (boolean proximity),
Blood Tithe (last-model dedup), Power from Pain token award (squad-deduped),
Miracle/Fate dice generation (army pool), Rapid Fire / Melta distance (shared squad
position), Twin-Linked, Anti-X basket fraction, Hazardous, WAAAGH! +1-wound flag.

---

## Ranked backlog (severity × MAE relevance; all squad_id-keyable unless noted)

### HIGH

1. **Deployment spreads a squad's models across the whole board** —
   `simulator.py:_deploy_line` (~4732) spaces every model-Unit evenly across the
   table width, so a 10-model squad starts spread ~44". Each model then contests a
   different objective from round 1, independently qualifies for position secondaries,
   and approaches the nearest enemy on its own. Over-rates multi-model armies; the
   starting condition that compounds findings 2, 6, 7. Fix: cluster each `squad_id`
   into one coherency bubble at one slot. (Part of the coherency wave.)

2. **Objective Control double-dipping** — `_score_objectives` (~657) sums OC per
   model, so one scattered squad contests several objectives at once (illegal in 10e:
   coherency pins a unit to ~one marker). Over-rates hordes' board control — a large
   slice of the remaining Drukhari +30 / horde over-shoot. Fix: count each squad's OC
   once per objective (nearest model), or enforce coherency. (Coherency wave.)

3. **No Prisoners secondary counts killed MODELS, not killed UNITS** —
   `secondaries.py:score_round_delta` (~261). Killing 2 of a 10-model squad scores VP
   where the codex scores 0 (unit not destroyed). Corrupts secondary VP every game and
   is the root of the elite-vs-horde scoring-cap tuning pressure already noted in
   `secondaries.py:57-66`. Fix: last-model / squad_id dedup (Blood Tithe template).

4. **Reanimation Protocols & Undying Legions pool by `profile.name`** —
   `simulator.py:4555-4587` and `3746-3762`. A fully-wiped Necron Warriors squad
   revives off a *different* same-datasheet squad's "alive" guard, violating "squad
   wiped → Reanimation cannot fire." Over-rates Necron survivability (note: Necrons
   drifted +0.6→+4.2 this wave). Fix: group the alive/dead buckets by `squad_id` and
   gate "alive_now == 0" per squad.

5. **Stratagem transient buffs land on ONE model, not the squad** — ~30 sites in
   `simulator.py` set `transient_*` (Disgustingly Resilient, Lightning-Fast Reactions,
   Fire and Fade, Arcane Genetic Alchemy, Dark Pacts, …) on a single model-Unit, so
   the other N-1 models never benefit. Under-rates every faction's squad-targeted
   stratagems by ~1/N. Fix: after each `target.transient_X = True`, propagate to alive
   `squad_id` siblings.

### MEDIUM

6. **Synapse / battleshock tested per model** — `simulator.py:5196` runs the
   below-half + battleshock test per model-Unit, so a 10-model Tyranid squad takes 10
   tests (each 3D6 under Synapse) instead of 1 → over-battleshocks. Fix: one test per
   `squad_id`, mark the whole squad.

7. **Battleshock "below half-strength" uses per-model health, not squad model count**
   — `simulator.py:5196-5197` (`u.current_health < u.profile.health/2`). Should be
   "fewer than half the squad's starting models." Needs a per-squad starting-count
   snapshot at battle start + `squad_id` grouping.

8. **Mob Rule (Orks) pools by `profile.name`** — `simulator.py:5129-5131,5200`: two
   5-model Boyz squads sum to 10 and both falsely auto-pass battleshock. Fix: squad_id
   count.

9. **Oath of Moment targets one model uid, not the unit** — `simulator.py:7145`;
   gate `units.py:2397`. Melee / multi-attacker fire on non-nominated models of the
   target squad miss the re-roll. Fix: store `oath_target_squad_id`, gate on it.

10. **Cull the Horde secondary** — same per-model kill-count issue as No Prisoners
    (`secondaries.py:274`), partially masked by the 3-VP cap.

11. **Shadow in the Warp "forces a test on every enemy unit" half missing** —
    `simulator.py:5079-5092` (documented omission); only below-half units test. Missing
    rule, not amplification — and Tyranids over-shoot, so leaving it is conservative.

### LOW / re-key for correctness / known-stub

- **profile.name once-per-unit gates that should be squad_id** (merge two squads of
  the same datasheet → *under*-count): Acts of Faith (`aof_squad`), Strands of Fate
  (`_fate_*_names_used_this_round`), Miracle-die-on-death, Markerlight emission, Pain
  Token award. Re-key to `squad_id` (fall back to `profile.name` for squad_id < 0).
- **Blood Surge** moves only the targeted Berzerker model, not the squad
  (`simulator.py:6544`). Fix: move all squad siblings.
- **Beacons of Rage below-half** per-model health (`units.py:1825`) — never fires vs
  1-wound infantry. Fix: squad headcount.
- **Leader aura coverage** partial across a spread squad (`leaders.py:1152`) — Low,
  coherency-dependent (deployment/coherency wave resolves most of it).
- **Movement intent** decided per model (`simulator.py:6114`) — Low, coherency wave.
- **WAAAGH! 5+ invuln-in-melee leg missing** (`units.py:1912`) — missing rule, Orks
  under-shoot so it's MAE-relevant but separate from per-unit framing.

---

## The two structural clusters worth their own waves

- **Coherency** (findings 1, 2, and most Low items): cluster squads at deployment and
  keep them coherent in movement, so OC reflects one objective per unit. This is the
  most likely remaining lever on the horde board-control over-shoot (Drukhari +30).
- **Per-unit VP scoring** (findings 3, 10): make secondaries count destroyed *units*.
  Directly removes the elite-vs-horde scoring distortion the cap is papering over.

Everything else is a contained `squad_id` re-key following the existing Blood Tithe /
last-living-model dedup template.
