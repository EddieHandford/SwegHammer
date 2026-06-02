# Auto-loop log (recent)

Older iter blocks live in `AUTO_LOOP_LOG_archive.md`. Per
`AUTO_LOOP_PROCEDURE.md` §E this file keeps the most recent close + the
in-flight wave only.

## Wave 108 close (2026-06-02) — Go To Ground core stratagem (gated `SWEG_GTG`), watchdog queue P2.2: faithful but the 8th FROZEN-UNDER lever (metric-neutral; refuted the "helps under-shooters" hypothesis)

Branch `claude/sim-calibration-6`. Built the Go To Ground 10e universal core Battle Tactic stratagem
(env-gated `SWEG_GTG`, default-OFF): just after an enemy unit selects a friendly INFANTRY unit as a shooting
target, the defender may spend 1 Command Point to give that unit a **6+ invulnerable save + Benefit of Cover**
until end of phase. Reuses the proven `transient_invuln_4` machinery (new per-Unit `go_to_ground_active` flag,
6++ at the save branch in `Unit.attack`, +1 save via `in_cover` in `_do_shoot`, cleared per round). The
defender heuristic (`Battle._maybe_go_to_ground`) is EVEN-HANDED — INFANTRY keyword + squad model-count +
incoming-threat + Command-Point pool only, NO faction awareness; the Command-Point economy (~1/round) is the
throttle. Verbatim-cited from the captured primary core-rules reference (`simulator.go_to_ground`,
`data/rule_citations.d/core_go_to_ground.json`). Caught + fixed a one-Unit-per-model representation bug in the
build (an absolute per-model wounds floor would have blocked all infantry → switched to a squad model-count
gate). 6 new tests; full suite green (994 passed); audit clean; OFF smoke clean.

**Clean N=40 A/B: OFF gated 4.48 == the wave-107 baseline (zero drift confirmed); ON gated 4.56 (+0.08, within
noise) — METRIC-NEUTRAL.** The hypothesis that an even-handed defensive stratagem would help the fragile
under-shooters (Chaos Daemons get shot off the board crossing to markers) is **REFUTED**: Chaos Daemons got
WORSE (−14.7 → −16.2). The frozen-under law in a defensive form — an even-handed save buff helps whoever
fields fragile infantry UNDER FIRE best (shooty-infantry gunlines), not the specific under-shooters; Daemons,
a melee aggressor, benefit less than their gunline opponents. Per-faction scatter (Genestealer Cults +4.4,
Adeptus Mechanicus +2.9, Chaos Daemons −1.5) is mostly N=40 noise around a neutral headline. **8th faithful
simulator lever to land frozen-under** (terrain, per-model structure, per-weapon dice, focus-fire, deployment,
Fire Overwatch, the anti-tank loadout pin, and now Go To Ground). Kept gated default-OFF (live baseline holds
at 4.48); not flipped (no gain to flip on). Surfaced to the watchdog as LOOP_QA wave-108. The
stats/scoring re-calibration remains THE high-leverage next step (user-gated).

## Wave 107 close (2026-06-02) — built the wave-106 anti-tank fix (watchdog Q18): the diagnosis was wrong on two counts; the IK hypothesis is REFUTED (7th frozen-under lever). Kept the one clear faithful pin (Ravager → Dark Lance), reverted the over-reach (Raider)

Branch `claude/sim-calibration-6`. Built the watchdog's Q18 anti-tank fix and the result materially refined
wave 106:

**(1) It is OVERRIDE-pinned, not a systemic mapper bias.** The clear platforms (Ravager/Raider/Razorwing)
bypass the mapper option-picker entirely — `data/overrides.json` pins them (the DRK-DIAG-5 de-over-arming,
which correctly fires ONE of the two mutually-exclusive cannon mounts but kept the anti-INFANTRY Disintegrator
and discarded the anti-tank Dark Lance). The fix is an override correction, not a mapper change.

**(2) (b) the systemic mapper mix-scoring — BUILT, MEASURED, REVERTED.** Added a target-toughness-mix wound
roll to `expected_damage_through_baseline()` (which had NO Strength-vs-Toughness term). It re-labelled 71
ranged + 48 melee picks with clear OVER-corrections (one-shot Hunter-killer missiles promoted to primary on
~8 Astra Militarum vehicles, Bright Lance → Starcannon, Knight Volcano-lance demoted) because a mix-AVERAGE
rewards high-volume generalists over specialists. Not faithful → reverted; the lone-Marine baseline stays.

**(3) (c) the cited override fix — A/B REFUTES the wave-106 IK hypothesis.** Corrected the Ravager → 3 Dark
Lances and (provisionally) the Raider → Dark Lance, cross-checked against the project's own Skysplinter
archetype (`code/archetypes.py`: 3 Raiders + 1 Ravager, "anti-tank from Ravager triples"). Clean N=40 A/B
(baseline gated 4.13): Imperial Knights +27.3 → +26.6 (−0.7, NOISE — NOT the predicted selective threat,
frozen-under like the prior six levers); Drukhari +4.6 → +9.0 (REAL — the bad anti-infantry loadout was
COMPENSATING for Drukhari being over-tuned; arming it just buffs Drukhari globally). Gated 4.13 → 4.30.

**Disposition.** KEPT the Ravager Dark Lance pin (unambiguously faithful — the list's named anti-tank
platform; kept per the watchdog's "keep faithful regardless of metric direction", though the Ravager-only
confirm showed it too degrades the headline — gated 4.48, Drukhari +11.7 — i.e. it carries re-calibration
debt). REVERTED the Raider pin (a TRANSPORT, not an anti-tank platform; the archetype assigns anti-tank to the
Ravager, not its 3 Raiders — an over-correction). Tests green (the lone equilibrium-phase4 failure was a
CPU-contention timing flake; passes 6.2s alone), smoke clean, audit clean. **This is the 7th lever to confirm
the IK +27 is a STATS/SCORING problem, not reachable by any simulator/loadout lever — the user-gated
re-calibration remains THE next step.** Surfaced to the watchdog as LOOP_QA Q18-OUTCOME (fork: keep the
Ravager now vs bundle the Drukhari loadout correction with the re-calibration). Memory
`project-antitank-picker-bias` rewritten.

## Wave 106 (2026-06-02) — diagnostic (no code change): the "Drukhari zero anti-tank" gap (watchdog hygiene #1) is a SYSTEMIC mapper option-picker bias — and a candidate FIRST non-frozen-under Imperial-Knights lever

Branch `claude/sim-calibration-6`. Per the watchdog's post-floor hygiene re-rank, investigated #1 (Drukhari
anti-tank). The cause is NOT the Strength≥9 tally threshold (the Dark Lance is S12). It is the BSData mapper's
weapon option-picker (`_collect_weapons_for_model`): it resolves a unit's weapon CHOICE groups by highest
expected damage **versus a baseline Marine** (anti-infantry), so anti-tank options lose to high-volume
anti-infantry options. Verified: the Drukhari Ravager — the archetype's literal "anti-tank from Ravager
triples" platform — is catalogued firing a Disintegrator Cannon (S6 D2), NOT a Dark Lance (S12 D6). SYSTEMIC,
not Drukhari-only: across all factions, choice-group units get mis-loadout'd onto anti-infantry guns, so
opponents UNDER-THREATEN vehicles / Monsters / KNIGHTS.

WHY THIS IS POTENTIALLY BIG: it is a candidate FIRST NON-FROZEN-UNDER lever on the IK +27. Unlike the six
even-handed levers (all helped the Knight too), this is a ONE-SIDED data-fidelity correction — giving the
Knight's OPPONENTS their real anti-tank loadouts raises their threat to the Knight WITHOUT helping the Knight
(its own single-model loadout has no such mis-pick). So it could lower IK without the frozen-under offset. It
is ALSO essential pre-re-calibration hygiene (cannot re-fit on lists with silently-absent anti-tank). Recorded
as memory `project-antitank-picker-bias`, surfaced as LOOP_QA Q18 (recommended fix (a): keep BOTH role-distinct
weapon options as fire-able profiles so the per-shot multi-profile picker chooses Dark Lance vs the Knight,
Disintegrator vs infantry — reuses the per-model loadout machinery). NOT band-aided (the systemic fix beats a
one-unit override). NEXT: build the option-picker fix and measure vs IK +27 — the most promising IK angle of
the session.

## Wave 105 close (2026-06-02) — Fire Overwatch core stratagem (gated `SWEG_OVERWATCH`), watchdog queue #3: faithful but REGRESSES at N=80 (frozen-under via Imperial Knights). SIXTH lever → the simulator-AI track is at its FLOOR; the IK +27 needs the RE-CALIBRATION (user's go)

Branch `claude/sim-calibration-6`. Built the missing 10e core Fire Overwatch stratagem (env-gated
`SWEG_OVERWATCH`): out-of-phase reaction shooting at chargers (`_do_charge`) and arriving reserves
(`_arrive_from_reserves`), hitting only on unmodified 6s, 1 Command Point, once per army per round; the AI
only overwatches when it can do meaningful damage (no wasted Command Point). Cited `simulator.fire_overwatch`.
The agent also caught + fixed a real double-Command-Point bug. 989 tests pass (+10 overwatch tests), audit
clean, run.py OK both gate states.

A/B: N=40 OFF 4.13 → ON 3.91 (−0.22), but **N=80 OFF 3.52 → ON 3.69 (+0.17, REGRESSED)** — the N=40
improvement was noise. Driver: **Imperial Knights +27.0 → +30.4 (gated 24.08 → 27.47, +3.4 WORSE)** — the
frozen-under effect: a Knight's big guns overwatch effectively, so IK benefits from punishing chargers far
more than the bled gunline under-shooters benefit. Faithful (a real missing mechanic) → KEPT gated; NOT
flipped (regresses).

**FLOOR REACHED — the session's structural conclusion.** SIX simulator-side levers now — terrain (w97),
per-model weapon structure (w99), per-weapon dice (w100), focus-fire (w101), deployment (w102-104), Fire
Overwatch (w105) — are ALL faithful but FROZEN-UNDER: none moves the Imperial Knights +27 (the dominant
residual, ~half the gated mean absolute error), and most are washes or small regressions on the headline,
because every even-handed improvement helps whoever has the stronger army (the over-shooters). The
simulator / artificial-intelligence calibration track has reached its practical floor for this residual. The
IK +27 is firmly a STATS problem, not a simulator-behaviour problem: it needs the FAITHFUL RE-CALIBRATION
(re-fit the per-faction stats/lists to the now-much-more-faithful sim — the session accumulated a lot of
fidelity the old stats no longer match) or the SCORING / victory-point model. BOTH are USER-GATED. Per the
watchdog's overnight guardrail ("if you run out of clean faithful levers, REPORT it and hold; do NOT cross
into the re-fit/scoring without the user"), the loop is REPORTING the floor and HOLDING for the user's
re-calibration go. The remaining queue levers (#4 trading-up, #5 combined-arms, #6 pile-in) are lower-impact
and expected to be the same frozen-under washes; not worth grinding the thrashed box before the
re-calibration. All the session's fidelity work is committed + gated (default-OFF), so the live baseline
holds; the re-calibration is the high-leverage next step.

## Wave 103 close (2026-06-02) — REFINED the deployment lever (gunlines at the zone midline, not buried): NET-POSITIVE headline (4.13 → 3.75) by un-burying the gunline under-shooters; the wave-102 "Imperial Knights drop" was an ARTIFACT (it buried IK's OWN Knights)

Branch `claude/sim-calibration-6`. Refined wave-102 per watchdog Q16: the high-value gunline group now
deploys at the deployment-zone MIDLINE (legacy single-line position, clear firing lane) instead of buried at
the board edge; the expendable screen stays forward. A/B (N=40, gated `SWEG_DEPLOY`):

| | gated MAE | Imperial Knights | Astra Militarum | Adeptus Mechanicus |
|---|---:|---:|---:|---:|
| OFF | 4.13 | +27.3 | −6.2 | −10.9 |
| crude (w102) | 4.67 | +25.4 | −8.1 | −12.3 |
| **refined (w103)** | **3.75** | +27.5 | −5.8 | **−8.4** |

The refinement flipped the lever to NET-POSITIVE (4.13 → 3.75) by un-burying the guns — the gunline
under-shooters recovered (Adeptus Mechanicus −10.9 → −8.4, BETTER than baseline; Astra Militarum −6.2 →
−5.8). BUT the wave-102 Imperial-Knights drop is GONE (IK back to +27.5 ≈ baseline). THE CORRECTION: the
crude IK-drop was an ARTIFACT, not a screening mechanism — burying the high-value group buried IK's OWN big
Knights at the board edge (slow to objectives), so the Knight army did worse for the wrong reason; restoring
them to the midline restores IK. So deployment is the FIFTH lever that does NOT fix Imperial Knights — but
the REFINED version is a genuine, faithful, NET-POSITIVE headline lever in its own right (a forward screen +
guns in a firing position = real screen-first deployment, helping the gunline under-shooters). KEPT gated;
recommended to the watchdog to confirm at N=80 and flip default-ON. **N=80 (wave 104) confirmed it is a WASH:
OFF 3.52 → ON 3.44 (gain −0.08, inside the noise band) — the N=40 −0.38 was mostly noise, so NOT flipped,
kept gated as a faithful metric-neutral fix; revisit at the re-calibration.** 17 deployment tests pass, audit clean,
run.py OK both gate states. Per the overnight guardrail, the re-calibration / scoring (the real IK fix)
remains the user's morning go.

## Wave 102 close (2026-06-02) — intelligent deployment + SCREENING (gated `SWEG_DEPLOY`), watchdog queue #2: REGRESSES the headline, but is the FIRST lever to move Imperial Knights DOWN (screening denies the Knight) — crude gunline placement hurts the under-shooters

Branch `claude/sim-calibration-6`. Built the watchdog's #2 lever (overnight-appropriate, faithful). The sim
line-deploys every unit on one line (`_deploy_armies`/`_deploy_line`) with no screening. The lever (env-gated
`SWEG_DEPLOY`) role-splits each army: expendable SCREENS / chaff deploy FORWARD (toward mid-board, to control
space + deny the deep-strike bubble + body-block charges), and high-value SHOOTING / durable / character units
deploy at the REAR of the deployment zone, protected. Role split reuses `code/roles.py` classify; even-handed,
cited `simulator.intelligent_deployment` (flagged AI tactic). 977 tests pass (incl. 17 new deployment tests),
audit clean, run.py OK both gate states.

A/B (N=40): gated 4.13 → **4.67** (REGRESSED +0.54). Mixed per-faction:

| | Imperial Knights | Chaos Daemons | Astra Militarum | Adeptus Mechanicus | Genestealer Cults |
|---|---:|---:|---:|---:|---:|
| OFF | +27.3 | −14.5 | −6.2 | −10.9 | +0.1 |
| ON | +25.4 | −11.3 | −8.1 | −12.3 | +3.1 |

THE INTERESTING FINDING: this is the FIRST lever to move Imperial Knights DOWN (+27.3 → +25.4, gated
24.37 → 22.47) — a screen body-blocks the Knight and denies it targets/charges, so SCREENING is a partial,
firepower-independent IK lever (distinct from the four refuted offence/AI levers). It also helped Chaos
Daemons (−14.5 → −11.3). BUT the crude "gunline to the back of the zone" placement HURT the gunline
under-shooters — Astra Militarum (−6.2 → −8.1) and Adeptus Mechanicus (−10.9 → −12.3) got MORE bled, not
less, because burying their guns at the board edge denies them early sightlines — and some deep-strikers got
stronger (Genestealer Cults +0.1 → +3.1). Net headline regressed. So: faithful CONCEPT, CRUDE implementation.
KEPT gated (preserves the IK-down finding); FLAGGED for refinement — screen forward AND keep gunlines with
sightlines (not buried), which might bank the IK-down without the gunline regression. Logged to watchdog.
Per the overnight guardrail: continuing clean faithful levers; the re-calibration / scoring (the real IK
fix) stays for the user's morning go.

## Wave 101 close (2026-06-02) — army-level FOCUS-FIRE targeting (gated `SWEG_FOCUSFIRE`), the watchdog's #1 Imperial-Knights lever: it IMPROVES the headline but makes Imperial Knights WORSE — even focus-fire is frozen-under

Branch `claude/sim-calibration-6`. Built the watchdog's #1 lever for the Imperial Knights +27 (the DEFENCE
half, after the per-model work refuted the offence over-count). Watchdog + user instrumented the root cause:
the per-unit target picker's "won't-crack penalty" makes every unit AVOID a 22-26-wound Knight (no single
unit cracks it) and shoot killable chaff, so opponents kill **0.00** big Knights/game despite carrying the
anti-tank to do it. FIX (`code/simulator.py`, env-gated `SWEG_FOCUSFIRE`): once per Shooting phase the army
nominates the most dangerous enemy brick it can crack COLLECTIVELY this phase (summed expected wounds ≥ 0.85
of its wounds, ≥2 contributing units), and every unit that can wound it concentrates fire. Only nominates a
collectively-crackable brick (no wasted fire on an unkillable target — the wave-79 pathology); a unit that
cannot wound the brick is never redirected. Faithful + even-handed (real tactic, all factions, any brick),
cited `simulator.focus_fire`. 12 tests pass (fixed an unseeded-RNG flake in the agent's harness), audit clean.

THE A/B (N=40 — the N=80 ON run was abnormally slow, ~2× normal, and was killed; the N=40 pattern is clear):

| Eval | gated MAE | Imperial Knights |
|---|---:|---:|
| OFF (baseline) | 4.13 | +27.3 |
| ON (`SWEG_FOCUSFIRE=1`) | **3.85** | **+29.0** |

The headline IMPROVED (4.13 → 3.85, −0.28) but Imperial Knights got WORSE (+27.3 → +29.0). The lever did NOT
crack the Knights — it is the **frozen-under pattern a 4th time**: even-handed focus-fire helps whoever has
the biggest guns, and the Knights HAVE the biggest guns, so a Knight army benefits from focusing ITS targets
more than its opponents benefit from finally focusing the Knight. The headline gain comes from OTHER matchups
(many armies now coordinate fire onto bricks). So: faithful + headline-positive, but NOT the IK lever — every
simulator-side lever tried (terrain, per-model structure, per-weapon dice, now focus-fire) leaves or worsens
IK +27. KEPT gated (faithful, real tactic) — the watchdog decides flip-default-ON vs keep-gated (the headline
gain is within the eval noise band, it worsens the #1 residual, and it carries a ~2× eval-time perf cost;
recommend pairing the flip with the re-calibration). The IK +27 is now structurally confirmed to need the
RE-CALIBRATION (re-fit stats to the faithful sim) or the SCORING / victory-point model — NOT any AI/firepower
lever. Logged to the watchdog (LOOP_QA). NEXT: continue the watchdog queue (#2 deployment/screening) and/or
the re-calibration inflection.

## Wave 100 close (2026-06-02) — Per-model weapon loadouts, STAGE 4: per-weapon Damage-dice ROLLING (gated `SWEG_ROLLDMG`). The OVERKILL half of the hypothesis is REFUTED too — rolling each weapon's real dice does NOT trim the big-gun / elite over-shooters; the Imperial Knights over-rate is durability, triangulated THREE ways

Branch `claude/sim-calibration-6`. Stage 4 of the per-model re-architecture (plan
`graceful-kindling-forest.md`). Now that per-model weapons are in place (Stage 3), Stage 4 rolls EACH
weapon's REAL Damage dice per shot instead of the mean (a Knight's anti-tank gun rolls its big dice, its
anti-horde gun its small dice — no averaging, no mean-overkill). Behind a SEPARATE env gate `SWEG_ROLLDMG`
so the dice effect is isolable from the per-model-structure effect; `roll_damage(dice, mean)` returns the
mean and draws NOTHING when the gate is unset or the weapon has no dice, so OFF and per-model-mean RNG
streams are byte-identical. Cited `simulator.rolled_damage` (10e Inflict Damage). 960 tests pass, audit
clean, run.py OK in all three gate states.

THE THREE-CELL A/B (N=80 — per-model variance needs N≥80):

| N=80 | gated MAE | Imperial Knights | Chaos Knights | Leagues of Votann | Adeptus Custodes |
|---|---:|---:|---:|---:|---:|
| OFF (legacy) | 3.52 | +27.0 | +2.0 | +7.4 | −3.8 |
| per-model, MEAN | 3.79 | +28.3 | +6.1 | +13.4 | −4.4 |
| per-model + DICE | 4.17 | +28.8 | +7.6 | +13.5 | −6.1 |

THE OVERKILL HALF IS REFUTED. Rolling each weapon's real dice (cell 3 vs cell 2) did NOT trim the big-gun /
elite over-shooters — Imperial Knights +28.3 → +28.8, Chaos Knights +6.1 → +7.6, Votann flat — and it
WIDENED the headline 3.79 → 4.17, mostly by adding variance that hurts the low-model elite armies (Custodes
−4.4 → −6.1). So NEITHER half of the user's hypothesis was the lever: not the weapon over-count (Stage 3),
not the mean-overkill (Stage 4). The Imperial Knights over-rate is now triangulated THREE ways (terrain
wave 97 + per-model structure + per-weapon dice) as durability / objective-holding — nothing about a
Knight's GUNS (count, dice, or overkill) moves its win rate, because it wins by sitting on a marker it
cannot be shot off.

What the re-architecture DID deliver is genuine FIDELITY — each model now fires its actual weapons with real
dice, special weapons lost on death, no over-collection, no mean-overkill. But it REGRESSES the headline
3.52 → 4.17 because the per-faction stats are still tuned to the OLD averaged-weapon sim — the expected
fidelity-first debt that the deferred re-calibration (LOOP_QA Q13) absorbs. The re-architecture is committed
and GATED (default OFF); Stage 5 (artificial-intelligence aggregate-isolation) completes it. The real
Imperial-Knights lever remains durability / objective scoring (threat-priority target AI or the
victory-point model), NOT firepower. DECISION on Stage 5 + the re-calibration vs pivoting to the durability
lever is pending the user.

## Wave 99 close (2026-06-02) — Per-model weapon loadouts, STAGES 2 + 3: firing now reads each model's own weapons (gated `SWEG_PERMODEL`). The Knight weapon over-count hypothesis is REFUTED at the metric — per-model is headline-neutral (within noise) and does NOT reduce the Imperial Knights over-rate

Branch `claude/sim-calibration-6`. Two stages of the per-model weapon re-architecture (plan
`~/.claude/plans/graceful-kindling-forest.md`). **Stage 2** (gate-inert) plumbed `model_loadouts` onto
`UnitProfile` (hashable flattened tuple + `_unflatten_model_loadouts`), metric 4.13 unchanged. **Stage 3**
(behavioural, env-gated `SWEG_PERMODEL`) made `Army.add_squad` instantiate one `Unit` per model from the
per-model loadout: each model fires its OWN weapons, a special weapon is lost when its model dies, a pistol
fires at engagement range, and single-model units fire only their actually-equipped guns (the over-count
fix from Stage 1 goes live here). Damage stays at the mean (dice is Stage 4). OFF (gate unset) is the legacy
shared-profile loop verbatim — byte-identical, no extra RNG. Cited `simulator.per_model_loadouts` (10e
Weapons / Making Attacks). 949 tests pass, audit clean, run.py OK in both gate states.

THE A/B (the headline test of the user's Imperial-Knights over-count hypothesis):

| Eval | gated MAE | Imperial Knights | Chaos Knights | Leagues of Votann |
|---|---:|---:|---:|---:|
| OFF N=40 | 4.13 | +27.3 | +1.0 | +6.7 |
| ON N=40 | 4.24 | +27.7 | +7.0 | +12.2 |
| OFF N=80 | 3.52 | +27.0 | +2.0 | +7.4 |
| ON N=80 | 3.79 | +28.3 | +6.1 | +13.4 |

REFUTED at the metric. Same-N comparisons show a small regression (N=40 +0.11, N=80 +0.27), but the gated
MAE itself has LARGE sampling noise — the OFF baseline alone swings 4.13 (N=40) → 3.52 (N=80) — so the
headline move is within noise. The RELIABLE, cross-N-consistent signal is per-faction: per-model firing
HELPS the strong multi-wound elite armies over-shoot MORE (Leagues of Votann +6, Chaos Knights +5) and
leaves Imperial Knights essentially FLAT (+27 → +28). So removing the Knight weapon over-count (a genuine
fidelity win) does NOT reduce the Knight win rate — TRIANGULATED TWICE now (terrain wave 97 + per-model
here): **the Imperial Knights over-rate is durability / objective-holding, not firepower.** Per-model is a
faithful representation upgrade (kept, gated) but it is the frozen-under pattern, not the Knight lever.
METHODOLOGY FINDING: per-model widens per-faction variance — N=40 is inadequate, use N≥80 for per-model
A/Bs (and the gated-MAE noise band is wider than previously treated). Stage 4 (per-weapon dice rolling) is
the UNTESTED other half of the hypothesis (mean-damage overkill of big guns) and sits on this. Decision on
continuing to Stages 4-5 pending the user.

## Wave 98 close (2026-06-01) — Per-model weapon loadouts, STAGE 1 of 5: the mapper preserves per-model loadouts + raw damage dice (DATA ONLY, additive, metric 4.13 unchanged); single-model weapon OVER-COLLECTION diagnosed + fixed in the data

Branch `claude/sim-calibration-6`. The user redirected the per-shot-damage-roll task into a fuller, faithful
re-architecture: move combat from one *averaged* weapon per squad to **per-model weapon loadouts** — each
model fires its own weapons with real damage dice rolled per shot, and loses that weapon when it dies; a
pistol can fire (weakly) at engagement range. The approved plan stages this across five env-gated steps
(`SWEG_PERMODEL`), each of which must keep the OFF eval at the 4.13 baseline; the aggregate
(`weighted_basket_average`) profile is kept unchanged so the whole AI / pricing / test blast radius keeps
working (additive dual representation).

STAGE 1 (data only, nothing reads the new data yet): `code/bsdata/mapper.py` now preserves a structured
`model_loadouts` per unit (each model type: name, count, and its ranged / melee weapons, each carrying the
raw Attacks / Damage **dice strings** alongside the existing means). Crucially, **single-model units now use
the same option-per-choice-group picker that multi-model squads already used** — they previously fell to a
legacy flat weapon-walk that collected EVERY weapon option, including mutually-exclusive arm weapons. The
aggregate is untouched; 1344 units gained `model_loadouts`.

KEY DIAGNOSTIC — this validates the user's Imperial-Knights over-rate hypothesis. **523 of 907 single-model
units were over-collecting weapons.** The Wraithknight dropped from five firing weapons (including BOTH
alternative arm cannons, Suncannon AND Heavy Wraithcannon) to its actual loadout (one arm cannon); the Knight
Castellan / Paladin / Errant shed their mutually-exclusive carapace options. So Knights have been firing guns
they cannot simultaneously equip — the suspected driver of the +27 over-rate the artificial-intelligence and
terrain tracks could not reach. This correction goes LIVE when firing reads the loadout (Stage 3).

The necessary parsed.json regeneration also synced a stale `deadly_demise` field (1 → 5 on 55 large chassis):
the committed parsed.json predated a prior "Deadly Demise D6+2" mapper fix and was never regenerated. Kept
per rule 7 (parsed.json must equal the mapper's output, not a hand-preserved stale value); it is
metric-neutral (4.13 with either value at N=40) and a constant across every per-model A/B, so it does not
confound the staging.

Verification: OFF N=40 gated MAE = **4.13 exactly** (unchanged — proves data-only), Imperial Knights +27.3
unchanged; 933 tests pass (the only failures are the pre-existing Stage-2 equilibrium-solver timing tests),
new `tests/test_model_loadouts.py` green, citation audit clean, `run.py --cli` exits cleanly. Next: Stage 2
(plumb `model_loadouts` onto `UnitProfile`, gate-inert).

## Wave 97 close (2026-06-01) — terrain rebuilt to the competitive Pariah Nexus density (Stream C, P1); FAITHFUL but REGRESSED gated 3.59 → 4.13 and REFUTED the sparse-terrain hypothesis (Imperial Knights got WORSE)

Branch `claude/sim-calibration-6`. Unparked Stream C with the watchdog's supplied competitive-terrain
reference (Q12) and rebuilt every stock map's terrain to the published Pariah Nexus density. KEPT despite
the regression — realistic terrain is faithful by construction (the May-2026 target was played on it), and
the result is an important DIAGNOSIS, not a lever to chase.

BUILT: `code/maps._competitive_terrain(width, height)` — mirrors a seed set of ruins / woods / barricades
through 180-degree rotation about the board centre (EVEN-HANDED by construction, neither deployment zone
favoured), producing ~11 large line-of-sight-blocking RUIN rectangles (about five-to-six inch footprints) +
~6 scatter pieces per map, ~19% coverage (up from the old sparse ~8%), with no clean cross-table sightline
(10% of deployment-zone-to-deployment-zone lines remain clear). Applied to all nine stock maps (the
five-map eval rotation plus four others); objectives left exactly where each mission places them. Cited
`terrain.competitive_pariah_nexus_layout` (Games Workshop Pariah Nexus Tournament Companion + Goonhammer
review).

| Eval (N=40) | MAE_gated | in band | Imperial Knights | Chaos Daemons | World Eaters | Orks |
|---|---:|---:|---:|---:|---:|---:|
| Baseline (wave 96, sparse terrain) | 3.59 | 7/22 | +25.9 | −15.6 | +6.2 | +2.7 |
| **Competitive terrain (LANDED)** | **4.13** | 6/22 | **+27.3** | **−14.5** | +9.8 | +7.7 |

THE HYPOTHESIS IS REFUTED. The watchdog ranked terrain P1-HIGHEST expecting it to crack the Imperial
Knights over-hold (sparse boards letting Knights shoot across the table). The opposite happened: Imperial
Knights got WORSE (+25.9 → +27.3). Chaos Daemons improved slightly as predicted (+1.1 — cover helps melee
advance), but the dominant effect is that realistic terrain HELPS the durable / melee over-shooters: it
shields the unkillable Knight objective-holder from return fire MORE than it limits the Knight's own (now
ruin-blocked) shooting, and it lets melee close (World Eaters, Orks). DIAGNOSIS: the IK over-hold is
durability-as-objective-holder, NOT table-wide shooting; realistic terrain AMPLIFIES it. Terrain is NOT the
IK lever (re-ranked).

KEPT per the prime directive + the watchdog's Q12 ("keep the realism even if it moves the metric the wrong
way"): reverting to sparse boards to protect 3.59 would be choosing a KNOWN INFIDELITY to flatter the
metric. The 3.59-on-sparse figure was a partly-spurious fit on the wrong board; 4.13-on-realistic is the
honest current fidelity. The regression is fidelity-versus-metric debt feeding the planned re-calibration
(Q13: terrain plus the per-shot damage roll land, then re-fit toward real data and land the held
artificial-intelligence Objective-Control fix). 927 tests pass (the Marines-mirror smoke test passes in
isolation; only the pre-existing Stage-2 solver timing test fails), citation audit clean, `run.py --cli`
exits cleanly. Finding logged (LOOP_QA Q14). Session headline gated 5.98 → 4.13 — the honest number on
realistic terrain. Next: P1.5 (per-shot damage roll).

## Wave 96 close (2026-06-01) — core-rules audit quick-fix batch (three parallel worktree streams); LANDED Stream D+E rules-correctness (gated 3.76 → 3.59); HELD Stream A AI-fidelity (frozen-under)

Branch `claude/sim-calibration-6`. Ran the watchdog's core-rules-audit quick-fix batch (per the user's
2026-06-01 parallel-fan-out directive) as THREE file-disjoint concurrent worktree agents, then merged the
faithful winners and held the frozen-under regressor. This wave's value is in the clean split between
rules-correctness (helps the headline) and artificial-intelligence-planning fidelity (regresses it).

LANDED:
- **Stream D+E (rules-correctness — `map.py` / `units.py` / `simulator.py`).** Collapsed cover to a single
  Benefit of Cover (removed the stale 9th-edition −1-to-hit and the Light/Heavy split); corrected Ruins /
  Woods line of sight to current 10e (TOWERING no longer sees through ruins — only AIRCRAFT does; removed
  the stale infantry "shoot through ruin walls" pass, which is movement-only in 10e); added the
  Benefit-of-Cover Armour-Penetration-0 / Save-3+ exception for ALL models (was mis-gated to infantry);
  removed the stale Fall Back FLY exemption (a unit that Fell Back cannot shoot or declare a charge — no
  FLY exception). All re-cited verbatim to the current 10e core rules. Tests rewritten to the new rules,
  not weakened.
- **Stream B1.** Counter-Offensive citation `quoted_text` corrected to current 10e ("has not already been
  selected to fight this phase").

HELD / DEFERRED (honestly, not discarded):
- **Stream A (artificial-intelligence Objective-Control fidelity).** Aligned the planner's Objective-
  Control view with the scorer (the damaged-Knight bracket + battle-shock Objective-Control = 0; plus my
  enemy-snapshot symmetry + `SWEG_DMGOC` gate completions). Genuinely faithful, but it REGRESSED the
  headline and reversed Stream D+E's Imperial-Knights / Drukhari gains — the frozen-under signature. HELD
  in full on branch `held/stream-a-ai-oc-fidelity` (commit `452ce81`), re-queued, and the keep-versus-hold
  fork escalated to the watchdog (`LOOP_QA.md` Q13). Did not bank a headline regression; nothing is lost.
- **Stream B2 (universal Insane Bravery).** Registered + cited but mechanically INERT — the auto-pass needs
  an in-phase hook + a Command-Point spend policy in `_run_battleshock_phase`. Re-queued as a P2 build, NOT
  landed as a live-but-fake rule.
- **Stream C (terrain density).** Parked on the watchdog supplying citable real Pariah Nexus layouts
  (`LOOP_QA.md` Q12); it also correctly sequences after Stream D's line-of-sight fixes, which just landed.

| Eval (N=40) | MAE_gated | in band | Imperial Knights | Drukhari | Chaos Daemons |
|---|---:|---:|---:|---:|---:|
| Baseline (wave 95) | 3.76 | 9/22 | +27.0 | +6.4 | −14.7 |
| Stream A combined (HELD) | 3.89 | 5/22 | +27.8 | +5.7 | −15.3 |
| **Stream D+E + B (LANDED)** | **3.59** | 7/22 | **+25.9** | **+4.7** | −15.6 |

Result: gated 3.76 → **3.59** (−0.17), driven by the two factions the watchdog's D2 (ruin line of sight)
and E1 (no shooting after Fall Back) hypotheses targeted — Imperial Knights and Drukhari. Chaos Daemons
marginally worse (−0.9, its separate combat/positional residual). In band 9 → 7 (the cover / line-of-sight
changes nudged a couple of borderline factions) but the gated mean absolute error — the primary signal —
improved. 928 tests pass (2 pre-existing Stage-2 equilibrium-solver timing failures, unrelated), citation
audit clean, `run.py --cli` exits cleanly. Also unblocked: P1.5 (roll damage per shot) now that Stream D's
`units.py` work landed. Session headline gated 5.98 → 3.59, all faithful.

## Wave 95 close (2026-06-01) — positional re-model Candidate B (idle-unit objective massing) LANDED — gated 4.15 → 3.76, the first positional candidate to work; Chaos Daemons −22.7 → −14.7

Branch `claude/sim-calibration-6`. Built the plan's Candidate B (the move AI massing body-army units
onto markers, the DOMINANT sub-cause). A first aggressive version regressed; a faithful refinement
LANDED. The Q11 positional axis is finally moving — the dominant under-shooter cracked.

THE PROGRESSION (env-gated A/B, SWEG_MASS):
- Aggressive (ALL non-holding units mass, abandoning shooting): gated 4.15 → **6.50** — REGRESSED
  chaotically (T'au +0.9 → +26.7, etc.) because it pulled in-range shooters off their fire-lanes. BUT it
  moved the target axis the RIGHT way (IK +27 → +18.4, Daemons −22.7 → −13.3) — the first candidate to do
  so (geometry w94 helped the wrong factions).
- Faithful refinement (only units OUT of their own firing range mass; in-range shooters keep shooting) +
  arrive-in-cover snap: gated 4.15 → **3.76** — LANDED. In band 8 → 9.

| Eval (N=40) | MAE_gated | in band | Chaos Daemons | Imperial Knights |
|---|---:|---:|---:|---:|
| Baseline (wave 92-94) | 4.15 | 8/22 | −22.7 | +27.0 |
| **Candidate B (landed)** | **3.76** | **9/22** | **−14.7** | +27.0 |

LANDED default-ON (`SWEG_MASS=0` to re-gate). The dominant under-shooter Chaos Daemons improved
−22.7 → −14.7 (+8.0 — its idle Daemons now reach the markers), and Drukhari (+11 → +6.4), T'au, Custodes
eased; a few armies regressed (Astra −4.9 → −8.9, Adeptus Mechanicus, Chaos Space Marines — their idle
units massing is net-negative for them) but the headline NET improved. Imperial Knights unchanged at +27
— the over-shooter half of the axis did NOT move (a Knight can't be shot off and there is no
representation fix for its durability), but the UNDER-shooter half cracked, which is the bigger residual
mass. Faithful: idle out-of-range units play the objectives and take cover — a real tactic, even-handed
across all factions, NOT a per-faction or per-model-count knob, NOT a scoring conversion. Passes every
§5 hard-rail. 927 tests pass; audit clean; run.py OK. Memory `project-ai-frozen-under-mae-first` (the
exception: a faithful AI fix that LANDED because it helps the non-reachers, not the already-strong).
Session headline now gated 5.98 → 3.76, all faithful.

## Wave 94 close (2026-06-01) — positional re-model Candidate A (geometry/clustering) BUILT + A/B'd → REGRESSED (frozen-under), reverted. Candidate B (AI massing, the dominant sub-cause) next

Branch `claude/sim-calibration-6`. Built the plan's lead candidate — the geometry/clustering
correction (`SWEG_CLUSTER`) — A/B'd it, and it REGRESSED. Reverted per the user's "if it washes,
report honestly — do not force, no knob" rule. The result is informative for Candidate B. No net code
change; headline back at gated 4.15.

BUILT (env-gated, reverted): in `Battle._assign_army_oc`, a squad genuinely ON an objective (≥1 model
within the true 3" radius) credited its Objective Control over models within a coherency-extended
footprint (3" + 2" Unit Coherency), modelling that a real unit holding a marker clusters on it rather
than the sim's one-Unit-per-model spread (wave-93: near-marker OC within 6" ≈ 2× within 3"). Even-handed
(a 1-model Knight counts only itself). Cited `simulator.objective_control_clustering` (representation
correction). 927 tests pass, audit clean.

| Eval (N=40) | MAE_gated | in band | IK | Daemons |
|---|---:|---:|---:|---:|
| Cluster OFF | 4.15 | 8/22 | +27.0 | −22.7 |
| **Cluster ON** | **4.30** | 8/22 | +27.0 | −22.7 |

REGRESSED (+0.15) — the FROZEN-UNDER signature. IK unchanged (1-model Knight, correctly unaffected) and
Daemons unchanged (the geometry fix can't reach them — their models are not near markers at all, the
DOMINANT AI-not-massing sub-cause). The worsening came from the OVER-shooters (Custodes +3.1→+4.3, Votann
+11.9→+12.6) — the clustering boost helps multi-model units ALREADY HOLDING markers, which are the
over-shooters, while the under-shooters (Astra −4.9→−5.9) did not benefit. So the geometry fix is
faithful-ish but the WRONG lever: it amplifies whoever already holds markers (the over-shooters), not the
under-shooters whose problem is they do not REACH markers.

THE READ FOR CANDIDATE B. A addressed the SECONDARY sub-cause (near-marker spread) and helped the
already-holders. The DOMINANT sub-cause is AI-not-massing (under-shooters' models are nowhere near
markers). Candidate B (the move AI massing body-army units ONTO markers) pushes the OPPOSITE direction —
it would help the non-reachers (the under-shooters) reach markers, NOT the over-shooters who already
reach. So B is genuinely distinct from A's failure and worth trying, even though it is the contest/deny
class (w81) that washed once. Next (wave 95): build Candidate B (`SWEG_MASS`), env-gated, per-matchup
measured on the IK + Daemons cells; expect a likely wash (the plan's stance) — if it washes, REPORT the
axis as a one-Unit-per-model representation limit that resists faithful fixes, and stop chasing it.

## Wave 93 close (2026-06-01) — positional re-model SCOPED (Q11 plan wave): the body-army on-marker OC gap is geometry/spread (secondary) + AI-not-massing (dominant); plan-first, no code

Branch `claude/sim-calibration-6`. The deck re-alignment is done, so per the user's sequence this wave
plans the Q11 positional re-model (the user mandated plan-first for this high-risk, sharpest-surface
change). Deliverable `docs/POSITIONAL_REMODEL_PLAN.md`. Headline unchanged at gated 4.15.

NEW DIAGNOSTIC (pins the sub-cause). A within-3"-vs-within-6" drill (Imperial Knights vs Chaos Daemons /
Astra / Tyranids) shows the body army's per-marker objective control within 6" is ~2× the within-3":
Daemons 5.8 / 9.4, Astra 4.5 / 8.4, Tyranids 7.7 / 15.6 (army totals ~111 / ~95 / ~185). Two sub-causes:
(1) GEOMETRY/SPREAD (secondary, cleaner lever) — half a body army's NEAR-marker objective control sits in
the 3"–6" band outside the 3" scoring radius (units near a marker are spread by the one-Unit-per-model +
coherency placement; real units cluster on the marker); (2) AI-NOT-MASSING (dominant) — even the within-6"
figure is a tiny fraction of the army total, so most of the army is nowhere near a marker (the regress-prone
AI-positioning class). The within-3" body-army OC (4.5–7.7) is BELOW a big Knight's ~10, so the body army
loses the contest at the marker — a geometry fix recovering the 3"–6" band would roughly DOUBLE on-marker
OC and let body armies out-control a Knight.

PLAN. Candidate A (LEAD, the user's authorised geometry category, least like the washed AI lever): a
clustering correction so a unit on an objective has its models within the 3" scoring radius (A1 real
placement / A2 representation, even-handed, Knight unaffected). Candidate B (the dominant sub-cause but
the washed class): AI massing body-army units onto objectives — build only if A is insufficient, expect a
likely wash. Build env-gated (SWEG_CLUSTER / SWEG_MASS), per-matchup measured (IK + Daemons holding cells,
watch Drukhari/Votann for the frozen-under signature), keep only a clear faithful axis-win; if it washes,
REPORT it as a one-Unit-per-model representation limit — do NOT force, do NOT reach for a knob, do NOT nerf.
Hard-rails self-check in the plan §5. Next (wave 94): build Candidate A1 env-gated.

## Wave 92 close (2026-06-01) — Chapter Approved 2025-26 secondary re-alignment COMPLETE (part 2/2: Bring It Down + Assassination wound-tiers) — metric-flat as predicted (4.10 → 4.15); deck re-align done, positional re-model next

Branch `claude/sim-calibration-6`. Completed the CA-2025-26 deck re-alignment (the user's Q10 ruling)
with the two wound-data cards deferred from wave 91. Metric-flat (cap-wash), kept as the faithful match
to the target deck. Headline gated 4.15 (was 4.10 after part 1 / 4.08 at the floor — all within the
deterministic noise of the secondary cap-wash). The deck re-alignment is now COMPLETE.

BUILT (part 2): threaded destroyed-unit Wounds-characteristic data through the round snapshot (three new
`RoundSnapshot` frozensets: MONSTER/VEHICLE ids at 15+ and 20+ wounds, CHARACTER ids at 4+ wounds — from
`profile.health`, the datasheet max). Then: **Bring It Down** flat-3 → CA-2025-26 **2 +2(15+ total
wounds) +2(20+), max 6/unit, no per-round cap** (a Knight = 6 VP, a Rhino = 2); **Assassination**
flat-3/char → CA-2025-26 **4 VP (4+ wound CHARACTER) / 3 (<4), no per-round cap, no Warlord bonus** (the
Pariah Nexus +1 removed). Three citations rewritten to CA-2025-26 verbatim (Bring It Down, Assassination,
Warlord designation); 3 tests updated + 2 new wound-bracket tests; 927 tests pass; audit clean; run.py OK.

| Eval (N=40) | MAE_gated | in band |
|---|---:|---:|
| Floor (wave 90) | 4.08 | 8/22 |
| CA-2025-26 part 1 (wave 91) | 4.10 | 8/22 |
| **CA-2025-26 part 2 (complete)** | **4.15** | 8/22 |

Metric-flat across both parts (+0.07 total, deterministic but tiny) — the wave-90 cap-wash prediction
holds: both armies max the 40-VP secondary cap, so secondary-value changes barely move the headline.
KEPT as the faithful match to the deck the May-2026 calibration target was played under (fidelity, not
metric — the user's explicit framing). DECK RE-ALIGNMENT COMPLETE (7 cards re-valued: No Prisoners, Cull,
Engage, Behind Enemy Lines, Extend Battle Lines, Bring It Down, Assassination; the 5 board cards — Storm
Hostile Objective, Secure No Man's Land, Area Denial, Defend Stronghold + Extend — confirmed unchanged).
NEXT (wave 93): plan + build the Q11 positional re-model (the one structural axis — IK over-holds /
Daemons under-holds the markers; diagnose-not-nerf, faithful/even-handed/plan-first, NOT a per-faction
objective-control→primary-VP knob; high-risk, may wash — report honestly if so).

## Wave 91 close (2026-06-01) — Chapter Approved 2025-26 secondary re-alignment, part 1/2 (5 cards) — faithful, metric-flat as predicted (4.08 → 4.10, within noise); user Q10/Q11 ruled

Branch `claude/sim-calibration-6`. The user ruled the structural-floor checkpoint (commit 0541e23):
**Q10 = Chapter Approved 2025-26** (re-align the secondary model + re-check Tier A to CA-2025-26,
sourced from ≥2 CA sources, never 40k.app); **Q11 = (c)** authorise the hard positional-representation
re-model (diagnose-not-nerf, faithful/even-handed/plan-first, not a per-faction OC→VP knob). Sequence:
deck re-align first, then the re-model. This wave did part 1 of the deck re-align.

VERIFICATION (the user's ≥2-CA-source requirement). A research agent confirmed the current CA-2025-26
values against wahapedia chapter-approved-2025-26 + the GW Tournament Companion PDF + Goonhammer's CA-2025
review (NOT 40k.app). Five cards changed value, five Tier-A board cards are UNCHANGED from Pariah Nexus
(Storm Hostile Objective, Secure No Man's Land, Area Denial, Defend Stronghold = no action; Extend
Battle Lines dropped 5→4).

BUILT (5 cards, direct value/logic changes — these are the faithful target-deck values, not env-gated):
No Prisoners 3→**2** VP/unit; Cull the Horde 10-model/3 VP → **13-model / 5 VP** (no per-round cap);
Engage on All Fronts 2/3/5 → **1/2/4** at 2/3/4 quarters; Behind Enemy Lines flat-4 → **3** (one unit) /
**4** (two+); Extend Battle Lines 5 → **4**. 5 citations rewritten to CA-2025-26 verbatim text + sources;
8 tests updated; 926 tests pass; audit clean; run.py OK.

| Eval (N=40) | MAE_gated | in band |
|---|---:|---:|
| Wave 90 baseline | 4.08 | 8/22 |
| **CA-2025-26 part 1** | **4.10** | 8/22 |

Metric-FLAT (+0.02, within noise) — exactly the wave-90 cap-wash prediction (both sides max the 40-VP
secondary cap, so secondary-value changes barely move the headline). KEPT because it is the faithful
match to the deck the May-2026 target was played under (fidelity, not metric — the user's explicit
framing). DEFERRED to wave 92 (need destroyed-unit wound-data plumbing in the round snapshot): Bring It
Down flat-3 → **2 +2(15+ wounds) +2(20+ wounds)** per unit; Assassination 3/char → **4** (4+ wound
character) / **3** (<4) + remove the Warlord bonus. THEN (wave 93+): plan + build the Q11 positional
re-model.

## Wave 90 close (2026-06-01) — Chaos Daemons re-diagnosed: POSITIONAL (primary-VP / objective-massing), not combat or attrition; secondary is a CAP-WASH; the residual floor is one structural axis. Strategic checkpoint escalated (no code change)

Branch `claude/sim-calibration-6`. Re-diagnosed the Daemons residual (attrition ruled out wave 88) with a
combat-vs-positional drill (Daemons vs AdMech / Drukhari / Thousand Sons / Astra, survival + primary/
secondary VP split). Two structural findings consolidate the whole remaining residual picture. No code
change; headline gated 4.08. Strategic checkpoint logged `LOOP_QA.md` Q11.

FINDING 1 — Daemons is POSITIONAL, not combat/attrition. Daemons SURVIVE (40–75% of units alive at game
end; not tabled, except vs Drukhari) but LOSE THE PRIMARY race: their primary VP (15–50) trails the
opponent's (20–50) in the losses, while their secondary is capped (see finding 2). So their surviving
bodies do NOT translate to objective control — the same "body army has total Objective Control but does
not mass it onto the markers" gap diagnosed for the under-shooters generally (`project-oc-contest-faithful`).
NOT combat-power (they live), NOT attrition (wave 88 was neutral).

FINDING 2 — secondary VP is a CAP-WASH after Tier A. Both sides generate 80–115 RAW secondary VP, all
clamped to the real 40-VP cap (`_decide_winner`), so secondary contributes ~40 to BOTH and no longer
DIFFERENTIATES — the winner is decided on PRIMARY VP (objectives). Tier A helped (4.95→4.17) by lifting
under-scorers toward the cap, but the secondary layer is now saturated; further secondary work has
diminishing returns because both armies already max it.

THE CONSOLIDATED PICTURE. The dominant remaining residual is ONE structural axis — PRIMARY VP /
objective control: Imperial Knights +27 OVER-holds the markers (durable, uncontestable), Chaos Daemons
−22 UNDER-holds them (survives but does not mass on objectives). Together ≈ half the gated MAE. This is
the one-Unit-per-model positional/representation gap, and the faithful AI levers for it have been
exhausted and REGRESS/WASH (value-targeting w72, focus fire w79, contest/deny w81; the contest is
faithful w84; per `project-ai-frozen-under-mae-first`). So the headline ~4.08 is a STRUCTURAL FLOOR on
the faithful track. The remaining clean lever is the secondary deck re-alignment (Q10, blocked on the
user's ruling, and likely small per finding 2). Strategic checkpoint Q11: rule on Q10 for the small
deck win, and assess whether 4.08 is "substantially converged" vs investing in the hard positional-
representation work (high-risk). Memory `project-faction-residual-rootcause` updated.

## Wave 89 close (2026-06-01) — detachment-fabrication sweep on the over-shooters: NEGATIVE finding — they are already clean; the over-rates are structural, not fabricated buffs (no code change)

Branch `claude/sim-calibration-6`. With Tier B parked (Q10 deck ruling still OPEN) and the Daemons
attrition lever spent, took a different clean deck-independent angle: a detachment-fabrication audit on
the over-shooter factions (memory `project-detachment-fabrication-pattern` — removing a fabricated
always-on buff is faithful AND reduces an over-shoot). Negative-but-useful result; no code change.
Headline unchanged at gated 4.08.

THE FINDING. The over-shooter detachments (Leagues of Votann, Drukhari, Adeptus Custodes, World Eaters,
Adepta Sororitas, T'au, Thousand Sons) are LARGELY CLEAN — the fabricated always-on attack buffs were
already swept in prior waves (Invasion Fleet enemy-Ld, Pactbound reroll-wounds, Sororitas plus-wound,
World Eaters plus-hit, Grand Coven psychic mortals, etc. — all already removed). The audit (BSData-
verified, not just grep) found NO active unconditional fabricated buff on any over-shooter. So the
over-shooter over-rates are STRUCTURAL (positioning / scoring / representation), NOT fabricated
detachment buffs — a useful negative that focuses future work away from this lever.

Two minor flags (neither a clean metric-positive fix, both deferred):
- **Custodes Shield Host `melee_crit_on_5_plus_hits`** was removed earlier citing a Wahapedia 3-bullet
  Martial Mastery; BSData v10.6.0 has it as a real 2-bullet "pick one at battle-round start" rule (crit-
  on-5+ AND AP+1), so the removal cited the wrong source. BUT this is edition-uncertain (BSData 2-bullet
  vs Wahapedia 3-bullet — possible stale-BSData), restoring it WORSENS Custodes (an over-shooter), and it
  needs an even-round-alternation build. Deferred to a careful fidelity pass; not a clean win.
- **Inquisition Task Force `reroll_hit_ones`** (Agents of the Imperium) is a real name+scope fabrication
  (army-wide vs the real CHARACTER-gated Daemon Hunters rule), but Agents is not one of the 22 evaluated
  factions, so it is zero-metric correctness cleanup — deferred.

STRATEGIC STATE. The clean faithful levers are thinning at gated 4.08 (down from 5.98 this session). The
residual mass is now IK +27 (positioning/structural, reported not faithfully fixable) and Daemons −22
(attrition neutral; combat/positional, hard); the biggest remaining clean lever is the secondary
deck-re-alignment, BLOCKED on the Q10 deck ruling. Memory `project-detachment-fabrication-pattern`
updated (over-shooters swept clean).

## Wave 88 close (2026-06-01) — DAEMONIC MANIFESTATION built + landed (real rule, cited), but METRIC-NEUTRAL — it does NOT fix the Chaos Daemons residual; the wave-87 diagnosis over-attributed

Branch `claude/sim-calibration-6`. Built the wave-87-planned fix — the missing friendly half of the
Chaos Daemons army rule. It is a real rule, correctly implemented and cited, and it is KEPT (fidelity),
but the N=40 A/B shows it is **metric-neutral**: it does NOT account for the Daemons −22 residual. An
honest negative result — the wave-87 diagnostic was over-confident.

BUILT: Daemonic Manifestation in `_run_battleshock_phase` (cited `simulator.daemonic_manifestation`,
verbatim BSData text, rule id a312-a2f1-e1c0-30ed). While a Chaos Daemons unit is in its Shadow of
Chaos (proxied as own deployment zone OR within 18" of centre — parity with the existing Daemonic
Terror proxy) it gets +1 to its Battle-shock test, and ON A PASS returns up to D3 destroyed models
(BATTLELINE) / D3 lost wounds via the existing reanimation pulse (`transient_undying_legions_pulse`,
the same plumbing Foetid Resurgence uses; consumed end-of-round by `_apply_undying_legions_pulse`).
Faction-gated to Chaos Daemons (correct — only they have it). Env-gated SWEG_DAEMONIC (default ON).

| Eval (N=40) | MAE_gated | in band | Chaos Daemons |
|---|---:|---:|---:|
| DAEMONIC OFF (=0) | 4.08 | 8/22 | −22.2 (28.6%) |
| **DAEMONIC ON** | **4.08** | 8/22 | **−22.5 (28.3%)** |

Within noise — no real movement. Verified the implementation is NOT a silent no-op (faction matches the
existing Terror check; `_initial_unit_counts` is populated for ALL armies so the revival pulse fires for
Daemons; the pulse is not clobbered between Command-phase set and end-of-round consume). So the rule
genuinely fires but is marginal for the metric. Likely reasons: (1) aggressive Daemons push PAST their
own Shadow into enemy territory, so they are rarely in-Shadow when dying (the own-DZ + 18"-centre proxy
excludes the enemy zone, where the real rule WOULD apply if they hold ≥half the objectives there); (2)
more fundamentally, the −22 residual is not the attrition rule — Daemons lose the firefight / get tabled
before attrition resistance matters, or it is the broader positional/VP-while-alive class. KEPT default-ON
(a real rule the sim was missing — fidelity, metric-neutral, no regression; the damaged-OC precedent),
but the Chaos Daemons residual needs RE-DIAGNOSIS (combat-power / positional, not this rule). 926 tests
pass; audit clean. Memory `project-daemons-manifestation-missing` updated with the negative result.

## Wave 87 close (2026-06-01) — diagnosed the #1 residual (Chaos Daemons −22.2): a real missing rule, DAEMONIC MANIFESTATION; build planned for next wave (no code change)

Branch `claude/sim-calibration-6`. With Tier B parked pending the deck ruling (Q10 still OPEN), did
the clean non-secondary work I committed to: diagnosed the largest residual, Chaos Daemons (sim 28.6%
vs real 50.8%, −22.2). High-confidence, faithful, non-secondary, deck-independent finding. Headline
unchanged at gated 4.08. Build planned for next wave (clean context — it needs a model-revival path,
not a tail-of-session rush; the wave-84/85 lesson).

THE FINDING (BSData-verified myself, not just the sub-agent). The simulator implements only HALF of
the Chaos Daemons army rule "The Shadow of Chaos". The enemy-debuff half, **DAEMONIC TERROR** (enemy
units in the Shadow take Battle-shock at −1 and D3 mortal wounds on a fail), IS implemented
(`_run_battleshock_phase`, cited `simulator.shadow_of_chaos`, proxied as "enemy within 18\" of board
centre while a Daemons army opposes"). The friendly-attrition half, **DAEMONIC MANIFESTATION, is
entirely missing** — grep returns zero hits. BSData cache (`Chaos - Chaos Daemons Library.cat.gz`,
rule id `a312-a2f1-e1c0-30ed`) verbatim: "While a LEGIONES DAEMONICA unit from your army is within
your army's Shadow of Chaos, each time that unit takes a Battle-shock test, add 1 to that test and, if
that test is passed, one model in that unit regains up to D3 lost wounds (if that unit is a BATTLELINE
unit and that test is passed, up to D3 destroyed models can be returned to that unit instead)." The
Shadow itself (verbatim): "Your deployment zone is always within your army's Shadow of Chaos" + No
Man's Land / opponent's zone if Daemons control ≥half the objectives there.

WHY IT IS THE CAUSE. Daemons' battleline (Bloodletters / Plaguebearers / Daemonettes / Pink Horrors —
T3–T5, Sv7+, 5++) is the bulk of every mono-god archetype and is extremely fragile. Daemonic
Manifestation is their core attrition mechanic — it returns D3 models per round a battleline unit
passes Battle-shock in the Shadow, keeping them on objectives. Without it they evaporate under fire 2–3
rounds early and cannot hold the board; this is mechanically why Daemons got WORSE (−18.3 → −22.2) when
board-control secondaries landed (wave 83), and why the residual has been stable since wave 10.

BUILD PLAN (next wave). In `_run_battleshock_phase`: (1) compute `in_daemons_shadow` for a Chaos
Daemons rep — faithful proxy = its OWN deployment zone (the rule GUARANTEES the DZ is in Shadow; clean
y-band like cleanse/sabotage) OR within 18\" of centre (parity with the existing Terror proxy, covering
the forward/objective-holding case); (2) +1 to the test for Daemons units in Shadow (a Ld bonus, same
convention as the existing modifiers); (3) on PASS, for BATTLELINE return up to D3 destroyed models via
the Necron reanimation revival path (`_apply_reanimation` is the model to reuse), else restore D3 lost
wounds to one model. Env-gated A/B, cited `simulator.daemonic_manifestation` from the BSData rule id
above; even-handed (the real Daemons faction rule, applied only to Daemons, like the Knights damaged-OC
bracket). Recorded `project-daemons-manifestation-missing`.

## Wave 86 close (2026-06-01) — Tier B verification surfaced a MISSION-DECK fork (Pariah Nexus 2024 vs Chapter Approved 2025-26); escalated, Tier B parked (no code change)

Branch `claude/sim-calibration-6`. Opening Tier B (kill-card formula corrections), I applied the
wave-84/85 lesson — verify the real values against ≥2 sources before changing — via a Sonnet research
agent. It surfaced a fork I did not know about, which is the wave's deliverable. Headline unchanged at
gated 4.08. Escalated `LOOP_QA.md` Q10; no code change (parking Tier B for a unified pass).

THE FINDING. The 10e secondary-mission values were UPDATED between two decks: **Pariah Nexus (2024)**
(the project's namesake; the sim's current values approximate it plus some Leviathan-era values) and
**Chapter Approved 2025-26** (debuted Adepticon March 2025, the CURRENT tournament standard for all
competitive play since). **The May-2026 Warp Friends calibration target was played under Chapter
Approved 2025-26, not Pariah Nexus 2024** — so the canonical secondary values for matching that data
are arguably the CA-2025-26 ones, but the sim AND the landed Tier A board secondaries (wave 83) were
built from Pariah-Nexus-2024 values. Confirmed deltas (≥2 sources each — Goonhammer Pariah Nexus review
+ Goonhammer Chapter-Approved-2025 review + Bell of Lost Souls):
- Cull the Horde: PN 20+ models / 25+ wounds → CA-2025 **13+ models incl. attached**, both 5 VP (sim: 10+ models, 3 VP — wrong vs both).
- Engage on All Fronts: PN 2/4 @ 3q/4q (no 2q tier) → CA-2025 **1/2/4 @ 2q/3q/4q** (sim: 2/3/5 @ 2/3/4, Leviathan-ish).
- Assassination: PN 4 VP/character → CA-2025 **4 VP (4+ wound char) / 3 VP (<4 wound)** (sim: 3 VP/char cap 4).
- Bring It Down / No Prisoners / Behind Enemy Lines: identical in BOTH decks (BID 2+2+2 max 6; No Prisoners 2+1×units max 5; BEL 3/4) — the sim's flat values are wrong vs both (deck-independent).

WHY ESCALATED, NOT FIXED. Which deck is canonical is a genuine project-scope call: it touches the
landed Tier A and the project's Pariah-Nexus identity, and the calibration data is CA-2025-26. The
sim's current values are a stale Leviathan/Pariah-Nexus mix with per-card wording subtleties, so a
single UNIFIED deck-aligned re-alignment after the ruling is cleaner and lower-risk than piecemeal
edits (and avoids another edition error of the wave-84/85 kind). Recommended (a) align to CA-2025-26;
parked Tier B pending the user's deck ruling. Finding recorded `project-mission-deck-ca-2025`.

## Wave 85 close (2026-06-01) — Knights damaged-OC bracket RE-ADDED as a real rule (gated 4.17 → 4.08); the wave-84 "fabrication" verdict was itself wrong

Branch `claude/sim-calibration-6`. The wave-84 conclusion that the damaged-Objective-Control bracket
was fabricated was REVERSED by the user/watchdog (commits f72a100 / 6135a62 / 6dcccbc): it is a REAL
10e datasheet rule and was re-added this wave, properly sourced and cited. Headline gated 4.17 → 4.08.

THE CORRECTION CHAIN. Wave 84 removed `_effective_oc` after a flawed read suggested Objective Control
does not change on the damage bracket. That read was wrong — both the worker's AND the watchdog's
"BSData shows constant OC" greps hit the wrong lines and never read the damage-table rows. This wave I
extracted the rows CLEANLY from the canonical BSData cache (the proper way): a Questoris Knight carries
"While this model has 1-9 wounds remaining, subtract 5 from this model's Objective Control characteristic
..."; an Armiger / War Dog "1-5 wounds remaining, subtract 3 ..."; Dominus chassis "1-10, subtract 5".
So the rule is real and my original −5/−3 values were correct. (The goal-doc directive expected a codex
−4 for the Questoris; RESOLVED by the watchdog to use the canonical cache −5 — BSData rule-6 governs;
the −4 was an unreliable web summary. ±1 is metric-negligible.) Lesson: `feedback-verify-stats-against-bsdata`
— cross-check ≥2 sources and actually READ the rows before declaring a cited rule fabricated OR building
one; 40k.app serves INDEX data, not codex.

RE-ADDED: `Battle._effective_oc` — Knights-faction-gated (correct: only Knights have this datasheet
rule), reduces a chipped Knight's Objective Control (Armiger −3 at ≤5 wounds, Questoris −5 at ≤9,
Dominus −5 at ≤10), floored at 0, applied in `_oc_within` and `_assign_army_oc`. Env-gated SWEG_DMGOC
(default ON). Cited `simulator.damaged_objective_control_bracket` with the verbatim BSData text (audit
288/288).

| Eval (N=40) | MAE_gated | in band | Imperial Knights | note |
|---|---:|---:|---:|---|
| DMGOC OFF (=0) | 4.17 | 9/22 | +29.2 | identical to wave-83 baseline |
| **DMGOC ON** | **4.08** | 8/22 | **+27.2** | −0.09 headline; IK −2.0 |

Marginal net-positive (a chipped Knight loses Objective Control → easier to contest off a marker), but
small because Knights are durable and rarely enter the bracket while still contested. Chaos Knights
worsen (−1.1 → −4.3) — they ALSO lose Objective Control when damaged, the real rule applied even-handedly
(NOT gated to help the metric). KEPT because it is real (the directive: "keep it because it is real,
regardless"), and it is also net-positive. 926 tests pass; run.py clean. The leftover Imperial Knights
+27.2 re-confirms the wave-84 positioning finding (`project-oc-contest-faithful`): even with the faithful
Objective-Control bracket, the Knight over-controls because body armies do not mass bodies onto markers.
Next: Tier B (kill-card formula corrections), then Tier C / clean under-shooter fixes.

## Wave 84 close (2026-06-01) — objective-control contest verified FAITHFUL; IK over-control is body-army positioning (no code change)

> **PARTIALLY SUPERSEDED by wave 85 (above):** the "damaged-OC bracket is fabricated" conclusion in
> this wave was WRONG — it is a real 10e rule, re-added in wave 85. The summed-OC-contest-is-faithful
> finding below still stands.

Branch `claude/sim-calibration-6`. Investigated the re-aimed Imperial Knights lever (Q8:
objective-takeability / the objective-control contest). A mid-wave MISSTEP and the watchdog
correction are part of this record. Headline unchanged at gated 4.17.

THE MISSTEP (caught + corrected). Mid-wave I built `Battle._effective_oc` — a "damaged Knight
loses Objective Control" rule (Armiger −3 at ≤5 wounds, Questoris −5 at ≤9), gated on the Knight
factions, on the strength of a 40k.app datasheet reading. **This was a fabrication / metric-tuning**
(a faction-gated penalty on the #1 over-shooter, moving the metric the convenient way) and the
watchdog caught it (commit 9f599c0). In real 10e, Objective Control does NOT change on the damage
bracket — BSData (canonical) shows Knight Paladin Objective Control 10 / Armiger 6 in EVERY profile;
the Knights' "Damaged: 1-9 Wounds Remaining" ability grants Lethal Hits / Lance / re-rolls / +1 to
Hit (a damaged Knight gets MORE dangerous, unchanged Objective Control). Reverted entirely (not even
gated-off, no citation). Lesson recorded: `feedback-verify-stats-against-bsdata` — verify stat/rule
claims against BSData before building, and treat "faction-gated AND conveniently moves a residual"
as a hard stop for self-review.

THE FAITHFUL DIAGNOSTIC (the real deliverable). Drilled the summed-Objective-Control contest in
Imperial Knights vs body armies (Astra Militarum, Tyranids), comparing the credited `a_oc`/`b_oc`
(the one-objective-per-squad `_assign_army_oc`) to the RAW summed Objective Control of every alive
model within 3" (the real 10e per-model rule). **Result: credited == raw in every case — the
contest is FAITHFUL.** Each model within 3" contributes its Objective Control; the
one-objective-per-squad modelling does not under-count the body army; a body army that gets bodies
onto a marker DOES out-control a Knight (Tyranids took a marker raw 15 vs the Knight's 6).

THE FINDING (per the watchdog's "if the contest is faithful, report it" branch). The Knight
over-controls because body armies have huge TOTAL Objective Control (Astra ~77 / 49 units,
Tyranids ~159 / 111) but get almost NONE onto the markers (on-marker Objective Control 0–15, often
0 in round 2) while each Knight parks concentrated Objective Control 10 on a marker. The residual is
the body army not MASSING bodies onto objectives — a positioning / one-Unit-per-model representation
gap, NOT an Objective-Control-math bug, NOT a Knight penalty. This is the AI-positioning class that
has historically regressed/washed (wave-81 contest/deny), so it is REPORTED, not chased blindly.
`LOOP_QA.md` Q9; memories `project-oc-contest-faithful`, `project-oc-does-not-bracket`. The scoring
overhaul (wave 83) already cut the headline to 4.17; the leftover IK spike is this positional core.

## Wave 83 close (2026-06-01) — Tier A board-control secondaries BUILT + LANDED (gated 4.95 → 4.17, in-band 6 → 9); sharpens the Imperial Knights finding to objective-over-control

Branch `claude/sim-calibration-6`. First BUILD wave of the scoring-model overhaul (plan Tier A;
watchdog Q7 approved). Added the five real Pariah Nexus objective-holding / board-control
secondaries the sim was missing. Validated as a clear fidelity win and LANDED ON (default-on,
`SWEG_TIER_A=0` to re-gate). Biggest single-wave headline move in a while.

BUILT: `Battle._score_board_secondaries` + `_score_area_denial` + zone helpers (`_obj_in_own_dz`,
`_obj_in_nml`, `_objective_controllers`) + a round-start objective-controller snapshot (for Storm
Hostile Objective). Five cards, scored per the verbatim real text, control = strictly-greater
Objective Control (same test as Cleanse): **Secure No Man's Land** (2/5), **Defend Stronghold**
(3), **Extend Battle Lines** (5), **Storm Hostile Objective** (4 — take an objective the opponent
held), **Area Denial** (2/5 centre). Every army brings the whole package (identical pool + scoring
both sides — even-handed; the asymmetry is purely in COMPLETION), bounded by the existing 40-VP
secondary cap and each card's natural ≤20-VP/game ceiling (the real per-Fixed-mission 20-cap,
honoured by construction). Five citations added to `secondaries_pariah_nexus.json` (audit 288/288).

| Eval (N=40) | MAE_gated | in band | Imperial Knights | note |
|---|---:|---:|---:|---|
| Tier A OFF | 4.95 | 6/22 | +19.1 | baseline (identical to wave 82 — inert keys don't perturb) |
| **Tier A ON** | **4.17** | **9/22** | **+29.2** | **−0.78 headline; IK WORSE** |

Most over-shooters eased hard (Drukhari +18.6 → +9.7, Custodes +7.4 → +2.7, Adepta Sororitas
+8.4 → +2.8, T'au +5.9 → +0.6, World Eaters +7.9 → +1.8, Emperor's Children +5.7 → +2.2) and the
board-control under-shooters rose (Chaos Space Marines −19.2 → −11.3, Chaos Knights −12.3 → −1.1
into band). A few under-shooters worsened (Chaos Daemons −18.3 → −22.2, Necrons, Adeptus Mechanicus,
Genestealer Cults) — they lose the board so their opponents bank the new board VP; their own
positional/AI weakness is a separate diagnosis.

THE SHARPENED IK FINDING (watchdog Q7 pre-authorised this exact scenario — "if Tier A doesn't move
campers, report it as a primary-economy / model-count finding; don't nerf"). Tier A made Imperial
Knights WORSE (+19.1 → +29.2). Mechanism, proven by the delta itself: the only thing Tier A adds is
objective-CONTROL-based scoring, and IK's win rate jumped +10 the moment it was added — so IK
out-controls objectives relative to its opponents and banks the new board secondaries ITSELF. The
IK residual is therefore **objective-OVER-CONTROL** (a durable, high-Objective-Control 9-to-13-unit
army holds the board uncontested — consistent with the wave-81 finding that opponents cannot contest
it off), NOT missing scoring paths. The next IK lever re-aims at objective-takeability / the
Objective-Control contest (does a body army correctly out-Objective-Control a Knight on a shared
marker?), a model-count/representation question — NOT more scoring and NOT a nerf. Tier A kept (clear
faithful aggregate win); IK finding reported to the watchdog (`LOOP_QA.md` Q8). 926 tests pass.

## Wave 82 close (2026-06-01) — scoring / victory-point model overhaul SCOPED (user Q6 ruling); plan wave, no code change

Branch `claude/sim-calibration-6`. First wave of the user-authorised scoring-model phase (Q6
RESOLVED: build the scoring/victory-point overhaul, diagnose-don't-nerf, plan-first). A
diagnosis+plan wave (mirroring wave 73→74 and 78), because the scoring layer is the sharpest
metric-tuning surface in the project and warrants a scoped plan before any code. Headline
unchanged at gated 4.95.

DELIVERABLE: `docs/SCORING_MODEL_OVERHAUL_PLAN.md`. Mapped the current scoring model from the
code (verified): primary is faithful (5/objective, 15/round cap, rounds 2–5, strictly-greater
control); the GAP is the SECONDARY economy — the sim models only 4 tactical secondaries (Engage,
Behind Enemy Lines, Cleanse, Sabotage) of the real ~12-card pool. THE KEY FINDING: the missing
cards are exactly the OBJECTIVE-HOLDING / BOARD-CONTROL family (Storm Hostile Objective, Secure
No Man's Land, Area Denial, Defend Stronghold, Extend Battle Lines, Overwhelming Force) — the
scoring paths a body army uses to out-score a durable camper, which a 9-model Imperial Knights
army physically cannot complete as well. This ALSO explains why wave-81 contest/deny failed:
taking a Knight's objective only denied 5 primary in the sim, but in real play also SCORES 4
(Storm Hostile Objective) — the reward for the anti-camper play was missing from the model.
Real card text sourced + verified against wahapedia pariah-nexus-battles (cross-checked vs the
Goonhammer review); each card a build wave implements gets a verbatim `rule_citations.d` entry.

BUILD SEQUENCE (env-gated, per-matchup Imperial Knights cells + per-faction + headline
before/after, citation before commit): wave 83 = Tier A (add the take-and-hold secondaries +
per-Fixed 20-cap — the targeted lever the ruling named first); wave 84 = Tier B (formula
corrections to the 4 modelled cards — Engage/Behind-Enemy-Lines/Bring-It-Down/No-Prisoners/Cull/
Assassination, correctness, direction mixed); wave 85 = Tier C (primary-economy correctness:
sticky control on ties at any control level — flagged as RAISING Imperial Knights, so isolated +
implemented because-it-is-the-real-rule, never for direction). Hard rails restated in the plan:
cited, even-handed, no per-faction weights, would-it-be-correct-if-it-moved-the-metric-wrong.

## Wave 81 close (2026-06-01) — contest/deny built + tested + REVERTED; the LAST faithful AI lever for Imperial Knights fails → escalated the structural scoring-residual finding (no net code change)

Branch `claude/sim-calibration-6`. Built redesign step #2 (contest/deny positioning) of the
faithful AI track per `docs/MATCHUP_FIDELITY_ANALYSIS.md` and the watchdog's Q5 confirmation.
It barely moved the #1 residual and regressed the headline — the diagnosis-predicted failure.
Reverted. Headline unchanged at gated 4.95. The finding is the deliverable and is escalated.

THE TEST (env-gated `SWEG_CONTEST`). A cheap chaff unit not on an objective moves to CONTEST
the nearest reachable enemy-CONTROLLED objective (deny the durable camper its primary VP),
prioritised over the AI-9 sacrificial enemy-DZ run. Naturally asymmetric: Imperial Knights
carry no chaff, so only their victims gain the contest. N=40 A/B vs baseline 4.95:
- gated **4.95 → 5.14 (REGRESSED +0.19)**; in-band 6/22 → 5/22.
- **Imperial Knights +19.1 → +18.2 (only −0.9; still grossly over-rated at +18.2).**
- The other over-shooters got WORSE: Drukhari +18.6 → +20.6, Votann +13.4 → +14.9, Orks +1.3.

THE FINDING (escalation-grade, `LOOP_QA.md` Q6). Contest/deny was the last faithful AI lever
the diagnosis pointed at for Imperial Knights, and it FAILED. This is the THIRD confirmation
(after wave-72 value-targeting, wave-79 focus fire) of one structural law: **every generic,
faithful AI improvement helps whoever has the better army; the over-shooters HAVE the better
armies; so sharper play WIDENS the headline** (memory `project-ai-frozen-under-mae-first`).
Mechanism for IK: opponents do contest, but a Knight is durable enough to hold/retake, so its
durability converts to held primary VP — the sim's kill-centric scoring under-models how real
tournaments deny primary through the full secondary economy + board tempo. **Imperial Knights
(and the durable over-shooters generally) is a structural VP-vs-durability SCORING residual,
not AI-fixable.** Per the watchdog's Q5 ruling: reported, not nerfed; escalated to the user as
a mission call (Q6: (a) build the scoring/VP-model lever — the real root cause; (b) bank ~4.95
and declare substantial convergence; (c) keep small clean UNDER-shooter fixes meanwhile). My
non-blocking default: (c) now + recommend (a). 926 tests / audit 294/294 expected green
(no net code change — revert restored `code/strategy.py` to baseline).

## Wave 80 close (2026-05-31) — IK Armiger re-fit tested + REVERTED; the AI+re-fit shooting/list routes fail for Imperial Knights (no net code change)

Branch `claude/sim-calibration-6`. Ran the user's AI+re-fit hypothesis on the #1 residual
(Imperial Knights): the faithful list-realism re-fit toward the real Armiger-heavy
tournament-winning list, alone and paired with the wave-79 focus fire. BOTH regress; IK
climbs. Reverted. Headline unchanged at gated 4.95. The finding is the deliverable.

THE TEST. Re-fit the IK archetype from big-Knight-heavy to the real Armiger-heavy list (6
Helverin / 6 Warglaive / Moirax / Canis Rex anchor — the proven competitive shape per the
Goonhammer / Sprues & Brews 2025 reviews). The builder produced a correct ~13-Armiger,
~1970pt list.
- Re-fit ALONE (focus fire off): gated 4.95 → **5.66** — IK UP. The efficient Armigers
  over-perform MORE in the sim (their real-world fragility tax is not modelled).
- Re-fit PAIRED with focus fire: gated **5.90**, **Imperial Knights +39.5 / 88%** — the
  fragile Armigers get focus-removed but they are cheap and many, and both lists' offence
  sharpens. Worst IK result yet.

DIAGNOSIS (firm now): the Imperial Knights over-rate is NOT the list — both the big-Knight
and the Armiger shapes over-perform in the sim (the Armiger one more). It is not the stats
(T11/W26 already current), not the rules (verified 71-72), and not the shooting AI (a Knight
cannot be shot off, so better targeting only sharpens IK's OWN offence — confirmed a 3rd
time). The over-rate is the **objective-HOLDING**: the sim over-rates a durable camper
because opponents do not **deny its primary VP**. Reverted the re-fit (both shapes are
realistic, so the regressing swap is not a clear fidelity win). The remaining faithful lever
is **contest/deny positioning (step #2)** — opponents sacrifice cheap bodies onto the
objectives IK is NOT on / contested ones to deny its primary VP, the real way Knights are
beaten. Logged `LOOP_QA.md` Q5; building step #2 next, env-gated, drilling IK's objective
holding before/after. If it too fails, IK is a structural scoring residual (VP-vs-durability),
not AI-fixable — and that is the finding to report.

## Wave 79 close (2026-05-31) — army focus fire built + tested (env-gated, regresses solo); diagnosis → Armiger re-fit + contest/deny next

Branch `claude/sim-calibration-6`. Built redesign step #1 of the faithful AI track (army-level
focus fire) per `docs/MATCHUP_FIDELITY_ANALYSIS.md`. It regresses solo, exactly the
accept-regression-then-re-fit scenario the user described. Committed env-gated OFF — baseline
gated 4.95 unchanged.

BUILT (env-gated `SWEG_FOCUS`): `Battle._nominate_focus_target` + a `_do_shoot` override. The
army nominates the most valuable durable enemy threat it can hurt (Knight/Monster/Vehicle or
8+ wound model, preferring one on an objective), and its ANTI-ARMOUR weapons only
(`_is_antiarmour_weapon`: damage≥3 / AP≤-2 / Anti-MONSTER-VEHICLE-TITANIC) concentrate on it —
weapon-target matched, so bolters keep clearing chaff. Smoke-confirmed: Chaos Space Marines
focus-fire the Knight Castellan and win a matchup they normally lose 0%.

| Eval | MAE_gated | note |
|---|---:|---|
| Wave 78 baseline | 4.95 | focus fire OFF |
| Focus fire ON (A/B) | **5.41** | regressed +0.46 |

Per-faction: Drukhari +18.6 → +14.2 (HELPED, −4.4 — its fragile Ravagers/Talos get
focus-removed) but Imperial Knights +19.1 → +25.9 (WORSE, +6.8), GSC −5.4 → −15.9, T'au up.

DIAGNOSIS (the user's diagnose-the-over-shoot step): focus fire is the right tool for FRAGILE
high-value threats (Drukhari) but WRONG for the durable Imperial Knights — a Knight cannot be
shot off (T11/W26/5++), so the victims' fire is wasted while IK's own anti-armour sharpens on
the opponents' vehicles/dreadnoughts. Third confirmation (after wave-72 value-targeting) that
better SHOOTING AI sharpens the durable over-shooters. The faithful next steps the regression
exposes: (1) **IK list-realism re-fit** — the sim's big-Knight archetype is OVER-GUNNED vs the
real Armiger-heavy tournament list; rebuild it toward the real list (Armigers are T9/W14, so
focus fire would REMOVE them → IK down). Test: Armiger re-fit PAIRED with focus fire. (2)
**Contest/deny (#2)** — the real IK lever is denying its primary VP (contest the objectives it
is not on; body it off), not killing the Knight. 926 tests pass; audit 294/294. Focus fire
committed env-gated OFF, pending those.

