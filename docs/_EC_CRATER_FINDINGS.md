# Why Astra Militarum craters against Emperor's Children

Read-only diagnostic, Stage 1 calibration. Scratch scripts:
`scripts/_ec_crater_replay.py` (reconstructs and re-runs every Astra
Militarum vs Emperor's Children game from the standing anchor and verifies
the replay against the recorded winner), `scripts/_ec_crater_analyze.py`
(aggregates the loss mechanism across all replayed losses), and
`scripts/_ec_crater_narrative.py` (replays one named game with a full
round-by-round move log and optional per-round renders). No production code
was changed; no levers were built.

## The anomaly, restated

On the standing anchor (`data/_anchor_sc48a_n80_log.json`, one hundred and
sixty games — eighty with Astra Militarum on side A against Emperor's
Children on side B, and eighty with the sides reversed), Astra Militarum
wins only twenty-nine of one hundred and sixty games against Emperor's
Children (18.1 percent), its worst cell by far. Astra Militarum's real-meta
win rate is 45.1 percent and Emperor's Children's is 47.9 percent; the real
head-to-head between them should sit close to 47 to 48 percent for Astra
Militarum. Earlier pilot-harness games (a different, smaller-scale seed
schedule) did not reproduce a crater this deep, which is why this
investigation replays the evaluation path's own recorded seeds rather than
a fresh pilot seed.

## Reproduction verification (the mandatory gate)

`scripts/_ec_crater_replay.py` reconstructs each of the one hundred and
sixty games exactly as `scripts/evaluate_vs_meta.py`'s `_run_battle_job`
builds it: seed the global random module with the pair seed
`(faction_index_a * 1000 + faction_index_b) * 100 + seed`, build each side
with `build_faction_random_army(..., use_archetype=True)` using its own
seeded `random.Random` instance, pick the map with `_pick_rotation_map`,
pick the primary mission with `_pick_primary_mission`, and run a vanilla
(`rules=None`) `Battle`.

**Result: one hundred and sixty of one hundred and sixty replayed winners
matched the anchor's recorded winners exactly (160/160).** Every downstream
number below is computed on this verified-faithful replay, with a full
event-log subscriber attached to each game.

Astra Militarum's record in the replayed cell: **29 wins / 128 losses / 3
draws** (18.1 percent), matching the anchor exactly.

## Loss-mechanism breakdown (the 128 losses)

### It is a scoring loss, not an attrition wipeout

Every one of the 128 losses ran the full five battle rounds — zero mutual
wipes and zero one-sided tablings. The win condition is decided by the
capped victory-point standing (primary capped at 50, secondary capped at
40, per the Pariah Nexus rules the simulator already implements), not by
board wipeout. This rules out "Astra Militarum gets tabled early" as the
mechanism outright.

### The margin is a blowout, and it grows every round

- Mean capped victory-point margin in the 128 losses (Emperor's Children
  minus Astra Militarum): **24.35** (median 21.0, range 1 to 56).
- Split: mean primary-track margin 11.95, mean **secondary-track margin
  14.46** — the secondary track contributes slightly more to the gap than
  the primary board-holding track does.
- Contrast with the 29 wins: when Astra Militarum wins this matchup, the
  mean margin is only **11.31** (median 7.0) — a close game. Astra
  Militarum's wins are narrow; its losses are blowouts. That asymmetry (not
  simply "the average is bad") is itself a clue: something snowballs once
  Emperor's Children gets ahead, and Astra Militarum's own good games never
  build a comparable lead.
- Objective control at rounds 2, 3, and 4 (how many of the 128 losses each
  side is ahead on board-held objectives at that round's end-of-round
  snapshot): round 2, Emperor's Children ahead in 62 games vs Astra
  Militarum ahead in 19 (47 tied); round 3, 74 vs 12 (42 tied); round 4, 85
  vs 15 (28 tied). **The board-control gap widens every round** — this is a
  snowball, not a fixed handicap set in deployment.

### Attrition is heavy on both sides, but heavier for Astra Militarum

Across the 128 losses, Astra Militarum starts 6,144 units total and ends
with 1,453 survivors — a 76.4 percent casualty rate. Emperor's Children
starts 5,749 and ends with 1,697 — 70.5 percent. Both armies are ground
down hard; Astra Militarum's casualty rate is about six points worse.

Casualties by round (summed across all 128 losses): round 1 — 28 units;
round 2 — 543; round 3 — 932 (the peak); round 4 — 630; round 5 — 410.

### Astra Militarum's shooting DOES meaningfully engage Emperor's Children

Total damage dealt is almost perfectly symmetric: Emperor's Children deals
16,620 damage to Astra Militarum across the 128 losses; Astra Militarum
deals 16,617 back. This directly rules out "Astra Militarum's artificial
intelligence never fires" as the mechanism — both sides output essentially
identical raw damage. Astra Militarum's own top damage dealers are exactly
the units the fire-support-hold and advance-discipline levers are built to
protect: Rogal Dorn Battle Tank (4,520 damage), Leman Russ Demolisher
(3,294), Leman Russ Battle Tank (2,773), Taurox Prime (1,550), Manticore
(1,253), Basilisk (1,106).

What differs is the **conversion** of that damage into kills and board
control, not the raw output.

### Kill attribution: which Emperor's Children unit does the damage

Emperor's Children unit credited with killing an Astra Militarum unit,
summed across all 128 losses (attribution: the most recent shooting or
fighting event against that unit's identifier before its kill event):

| Emperor's Children unit | Kills | Damage dealt |
|---|---:|---:|
| Noise Marines | 679 | 2,827 |
| Defiler | 610 | 7,148 |
| Sorcerer | 250 | 1,110 |
| Daemon Prince of Slaanesh with Wings | 194 | 1,526 |
| Lord Kakophonist | 189 | 679 |
| Tormentors | 151 | 328 |
| Chaos Rhino | 126 | 355 |
| Maulerfiend | 85 | 859 |
| Flawless Blades | 47 | 595 |
| Lord Exultant | 42 | 658 |
| Infractors | 32 | 109 |
| Lucius the Eternal | 18 | 360 |
| Chaos Spawn | 9 | 66 |

(Total attributed kills: 2,432 of 4,691 actual Astra Militarum deaths — the
remainder is spread across deaths this simple "most recent attacker"
heuristic does not cleanly attribute, for example stacked-damage kills
inside a single activation or battleshock/morale losses.)

The Defiler alone accounts for 43 percent of all Emperor's Children damage
output (7,148 of 16,620) — this is the sourced "triple Defiler" monster
pillar named in the Emperor's Children list-realism correction
(`SWEG_EC_REALISM`), and it is doing exactly the job that correction
intended. The Noise Marines get more raw kills (679) at much lower total
damage (2,827) than the Defiler — consistent with a durable, high-output
monster grinding down whatever it can reach while the army's own
battleline mops up already-weakened Astra Militarum squads.

## Three representative games, read in full

### 1. The median-margin loss (margin 21) — Emperor's Children (side A) vs Astra Militarum (side B), seed 4, map Search and Destroy

Final: Emperor's Children 73 capped (primary 45, secondary 28) vs Astra
Militarum 52 capped (primary 40, secondary 12). Round-by-round capped
victory points (Emperor's Children – Astra Militarum): round 1, 0–7 (Astra
Militarum ahead); round 2, 12–17 (still ahead); round 3, 34–37 (still
narrowly ahead); **round 4, 61–47 (Emperor's Children swings 14 points
ahead in a single round)**; round 5, 73–52 (final gap 21).

Astra Militarum actually leads or is close through three rounds. The swing
happens in round 4: Emperor's Children's Noise Marines hold one objective
continuously across rounds 3 to 5 while shrugging off Astra Militarum's
return fire (several Noise Marine models die each round but the squad
keeps re-establishing control), and a pair of Defilers each land two
attacks in the same activation for double-digit damage (one hits for 6 and
7, the other for 6 and 8 against separate targets). Astra Militarum's Rogal
Dorn Battle Tank and Lord Solar Leontus (its effective warlord) both die in
round 4. Astra Militarum's own light infantry (Kasrkin, Cadian Heavy
Weapons Squads) die repeatedly in the same rounds having moved up without
landing meaningful damage of their own — they contribute to the casualty
count but not to the scoreboard.

### 2. The blowout (margin 56, the widest in the cell) — Astra Militarum (side A) vs Emperor's Children (side B), seed 18, map Tipping Point

Final: Astra Militarum 15 capped (primary 15, secondary 0) vs Emperor's
Children 71 capped (primary 45, secondary 26). Round-by-round: round 1,
0–0; round 2, 5–10; round 3, 10–22; **round 4, 10–51 (Astra Militarum
gains nothing, Emperor's Children gains 29 in one round)**; round 5,
15–71.

By round 3, most of Astra Militarum's light-infantry screen (Cadian Shock
Troops, Taurox Prime, three Kasrkin squads) is already dead, several
without having acted that round at all — killed before their own
activation came up. Round 4 is the collapse: Emperor's Children's melee
and character elements consolidate on the survivors simultaneously —
Flawless Blades repeatedly charging the Basilisk and a Leman Russ Battle
Tank, a Defiler dealing 25 damage to a Cadian Command Squad in one hit,
Lucius the Eternal and a Sorcerer both piling onto the Rogal Dorn Battle
Tank — and Emperor's Children takes four of the five objectives outright
in that round. By round 5, Astra Militarum's last three vehicles are still
shooting, but the game is already decided. Renders saved to
`data/_pilot_crater_astra_v_emperor's_s18_r1.png` through `..._r5.png`.

### 3. The near-miss (closest loss, margin 1) — Astra Militarum (side A) vs Emperor's Children (side B), seed 17, map Hammer and Anvil

Final: Astra Militarum 64 capped (primary 40, secondary 24, challenger 0)
vs Emperor's Children 65 capped (primary 40, secondary 18, **challenger
7**). Both sides tie the primary track exactly at 40. Astra Militarum
actually *wins* the secondary track, 24 to 18. The entire one-point margin
is the Chapter Approved 2025-26 challenger-card catch-up mechanic:
Emperor's Children banks 7 challenger victory points because it fell
behind by six or more points at some point in the game and drew a
challenger card; Astra Militarum never falls behind by that much and so
never draws one of its own. This is the single cleanest illustration in
the sample that the crater is not purely a list-power or attrition gap —
this specific game shows Astra Militarum's own play was strong enough to
tie primary and lead secondary, and it still lost to a scoring-mechanic
asymmetry that only fires for the side that falls behind first.

## Ranked hypotheses

**1. List-shape mismatch: numbers versus quality (strongest evidence).**
Astra Militarum's archetype-built list is a large count of comparatively
fragile, cheap squads (Cadian Shock Troops, Kasrkin, Tempestus Scions,
several Cadian Heavy Weapons Squads). Emperor's Children's sourced
`SWEG_EC_REALISM` template is a small count of very tough, very efficient
units (three Lord Exultant, two Defilers, two Noise Marines squads as the
core, plus whatever random-fill adds). The total damage output of the two
sides across the 128 losses is almost exactly equal (16,620 vs 16,617), but
Astra Militarum still loses more of its own units (76.4 percent casualties
versus 70.5 percent) and falls further and further behind on objective
control every round (19/62 at round 2 widening to 15/85 by round 4). That
combination — equal raw damage output, unequal conversion into kills and
board control, and a gap that widens rather than holds steady — is the
signature of a durable, high-per-model-value army grinding down a numerous,
low-per-model-value army over an attrition war. This may be a faithful
reflection of how an elite daemon-engine list actually performs against a
horde Guard list in real 10e, but the magnitude here (an 81.9 percent loss
rate and a 24-point average blowout margin) looks too extreme against a
real head-to-head that should sit near 47 to 48 percent for Astra
Militarum — so the *degree* of the mismatch, not its direction, is the
open question.

**2. A piloting gap in Astra Militarum's light-infantry commit discipline
(strong evidence).** The existing advance-discipline and fire-support-hold
levers (`SWEG_AM_ADVANCE_DISCIPLINE`, `SWEG_AM_FIRE_SUPPORT_HOLD`) are both
default-on in this replay and are working exactly as designed for Astra
Militarum's real gunline (tanks, artillery, heavy-weapons squads correctly
hold position and shoot instead of Advancing — visible throughout every
game's log). Those levers deliberately exclude weak-shooting bodies (their
own comment: "Guardsmen, rDPA ~0.5 ... SHOULD advance to grab objectives"),
and it is exactly those excluded units — Kasrkin, Tempestus Scions, Cadian
Shock Troops — that repeatedly show "ADVANCED; DIED" in the same round they
arrive, contributing zero shooting and zero held ground before dying. Once
that screen is gone (visible concretely in the round-3-to-4 transition of
the blowout game), Emperor's Children's melee and character elements
consolidate on the remaining Astra Militarum units in the same round,
producing the observed one-round scoring swings of 14 to 29 points. Real
Guard doctrine screens with cheap bodies from behind cover or out of charge
range rather than sprinting them into a durable opponent's engagement
envelope; the current carve-out treats "should advance to grab objectives"
as unconditional, without checking whether the opposing side can kill the
advancing unit before it holds anything.

**3. Secondary and challenger-card scoring may structurally favor an elite
list (moderate evidence).** The secondary-track margin (14.46 mean) is
larger than the primary-track margin (11.95 mean) across the 128 losses,
and the near-miss game shows the challenger-card catch-up mechanic handing
Emperor's Children 7 points that Astra Militarum had no equivalent
opportunity to win. Whether this is a genuine modelling asymmetry (kill-
count secondaries and the catch-up card rewarding whichever side happens to
fall behind briefly, which an elite list with fewer, tougher activations
may do less often) or simply a downstream consequence of hypothesis 1 and 2
already in motion is not yet separated apart in this diagnostic; it would
need its own isolated instrumentation to resolve.

## Candidate lever directions (named only, not built, per the brief)

- **Astra Militarum light-infantry stage-before-commit.** Extend the
  existing `SWEG_AM_STAGING` / advance-discipline family to Astra
  Militarum's excluded weak-shooting bodies: instead of an unconditional
  "should advance," stage them behind the enemy's live threat envelope
  (the same envelope math `_precompute_staging_envelope` already computes
  for the gunline) until support is in range, rather than sprinting solo
  into a durable opponent's kill zone.
- **Emperor's Children list-realism re-audit at the durability/output
  ratio.** Re-check whether the `SWEG_EC_REALISM` triple-Defiler-plus-
  Lord-Exultant template, combined with the simulator's general durability
  treatment of multi-wound models (already flagged as an "over-reward" in
  the Chaos Knights and Leagues of Votann ranged-hold comments elsewhere in
  `code/simulator.py`), is running unusually hot for this specific
  faction's toughness/save profile rather than reflecting the sourced
  list's real-world efficiency.
- **Secondary and challenger-card audit for elite-versus-horde
  matchups.** Isolate the secondary-track and challenger-card contribution
  to the Astra Militarum versus Emperor's Children margin specifically (a
  paired instrument that zeroes each track in turn) to determine whether
  kill-count secondaries and the catch-up card are a material, separable
  contributor to the crater or merely a downstream artifact of the
  attrition and piloting gaps above.
