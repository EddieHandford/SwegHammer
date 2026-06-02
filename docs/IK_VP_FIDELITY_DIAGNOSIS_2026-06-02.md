# Imperial Knights +27 — the victory-point fidelity diagnosis (wave 109, 2026-06-02)

Following the user ruling (the "re-fit stats" path is killed; the gap is
simulation fidelity in how the game is WON), this is the diagnostic-first probe
of WHY the simulator's Imperial Knights win the +27 over-rate. No code change —
this is the diagnosis that the next build works from. Instrumentation:
`scripts/diag_ik_vp_wave109.py` (throwaway), Imperial Knights versus seven broad
armies, archetype lists, the real map rotation.

## Finding 1 — the Knight wins on VICTORY POINTS, not combat / tabling

| opponent | IK win | IK tables opp | opp tables IK | opp survivors | rounds |
|---|---|---|---|---|---|
| Tyranids | 16/25 | 1 | 0 | 31% | 5.0 |
| Astra Militarum | 22/25 | 1 | 0 | 25% | 5.0 |
| Necrons | 21/25 | 0 | 0 | 27% | 5.0 |
| Orks | 21/25 | 0 | 0 | 28% | 5.0 |
| Chaos Daemons | 19/25 | 0 | 0 | 37% | 5.0 |
| Adeptus Mechanicus | 24/25 | 0 | 0 | 27% | 5.0 |
| Genestealer Cults | 17/25 | 2 | 0 | 29% | 4.9 |

The Knight tables the opponent in only 0–2 of 25 games; the opponent never
tables the Knight; every game runs the full five rounds; the broad army keeps a
quarter to a third of its units. **The Knight does not win by killing the
opponent off the board.** The "the sim decides games on combat" hypothesis is
refuted at the tabling level — the win is decided on victory points.

## Finding 2 — the differential is PRIMARY victory points; secondary is a capped wash

Averaged victory-point composition (per game): Imperial Knights primary ~44,
secondary raw 55–75; opponents primary ~26–35, secondary raw 46–108. The
decision uses `primary + min(secondary, 40)`:

- **Secondary is a wash.** BOTH sides' raw secondary exceeds the 40-per-game cap,
  so both contribute exactly 40 to the decision — it cancels. (Secondary
  selection, per-card caps, and the Cleanse / Sabotage action secondaries are
  already live and already pulled the Knight down once — wave 74; the residual is
  not a missing secondary.)
- **Primary is the whole gap:** Knight ~44 vs opponent ~30, a **+14** primary
  lead that is the entire victory-point margin.

## Finding 3 — the Knight's primary lead COMPOUNDS; the broad army's board control COLLAPSES

Per-round primary victory points (game rounds 2–5; primary correctly does not
score round 1, `simulator.primary_vp_no_round_1`), averaged over 48 IK-vs-broad
games:

| round | Imperial Knights | opponent | IK − opp |
|---|---|---|---|
| 2 | 11.8 | 8.4 | +3.3 |
| 3 | 9.4 | 8.2 | +1.1 |
| 4 | 10.8 | 7.8 | +3.0 |
| 5 | 12.0 | 5.9 | **+6.0** |

The Knight's marker-holding is steady-to-growing (peaks in the final round); the
broad army's board control **collapses under attrition** (8.4 → 5.9). The
unkillable Knight holds its concentrated Objective Control reliably while the
broad army's marker-holders are ground down and not sustained. **This is the
one-Unit-per-model gap the user named: the sim over-rates the Knight's elite
combat (it clears and holds markers) and under-rates the broad army's model-count
board control (its huge total Objective Control never converts to held markers
because its bodies die / do not re-flood).**

## The mechanism, and why the obvious fixes are blocked

The Knight wins because it converts durability into sustained, growing PRIMARY
board control that a broad army should out-contest but cannot sustain. Candidate
faithful fixes and their status:

1. **Positional AI (move the broad army's bodies onto / massed on markers)** —
   tried (`SWEG_MASS`, waves 94-95) and **washed**. Making the AI position better
   did not move the axis: the bodies that reach the marker are then killed.
2. **Secondary economy** — already faithful (selection + caps + live Cleanse /
   Sabotage); it is a 40-cap wash, not the lever.
3. **Command-phase primary-scoring timing** (the cleanest new idea): real 10e
   scores each army's primary at ITS OWN Command phase (turn start), so a broad
   army that floods a marker on its turn banks the victory points even if the
   Knight clears it on the following turn. The sim scores primary **once per
   round, at end of round, after all combat** — crediting only the army left
   controlling (the durable Knight that cleared the contesters). This single
   end-of-round check structurally over-rewards the survivor. **BUT it is blocked
   by the alternating-activation round model** (`_run_round_alternating`): units
   from both armies interleave sub-phase by sub-phase, so there are no clean
   per-player Command phases to score at. Restoring per-turn scoring would mean
   un-interleaving the round — a large structural change to a SwegHammer rule-mod.

## So what is the specific missing mechanic?

The residual is **primary board-control fidelity under attrition**: a broad
army's transient marker control (it floods a marker, it is cleared next turn) is
never credited, because the sim scores primary once per round on the post-combat
survivor. The two natural fixes are tried-and-washed (positional AI) or
structurally blocked (per-command-phase scoring under alternating activations).

The promising untried direction that fits the alternating model: **credit
objective control for a unit that CONTESTS a marker during the round even if it
is destroyed before the end-of-round score** — i.e. score primary on PEAK
in-round control rather than only round-end survivor control, or check control
at the START of the round (before that round's killing) so a marker flooded last
round is banked before it is cleared. Both are faithful to "you hold the
objective at your Command phase" and even-handed (they credit whoever contested,
Knight or horde). This is surfaced to the watchdog (LOOP_QA wave-109) for the
build-direction steer before touching the scoring surface — the sharpest
metric-tuning surface in the project, where a plan-first, env-gated A/B is
mandatory.
