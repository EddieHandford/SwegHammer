# Chaos Daemons −14.7 under-shoot — the diagnosis (wave 112, 2026-06-02)

Per the watchdog steer, instrumented the Chaos Daemons default under-shoot the
way wave 109 instrumented the Imperial Knights over-shoot. Daemons are side A.
Instrumentation: `scripts/diag_daemons_wave112.py` (throwaway). The conclusion is
that the Daemons under-shoot and the Imperial Knights over-shoot are the **same
single residual** — primary board-control / mission fidelity — at opposite ends.

## Finding 1 — Daemons do NOT die before they arrive; they are never tabled

| opponent | Daemon win | Daemon tabled | tabled opp | Daemon survivors | rounds |
|---|---|---|---|---|---|
| Adeptus Astartes | 10/25 | 0 | 0 | 37% | 5.0 |
| T'au Empire | 10/25 | 0 | 0 | 45% | 5.0 |
| Astra Militarum | 12/25 | 0 | 0 | 58% | 5.0 |
| Necrons | 16/25 | 0 | 0 | 52% | 5.0 |
| Adeptus Custodes | 11/25 | 0 | 0 | 36% | 5.0 |
| Imperial Knights | 7/25 | 0 | 0 | 44% | 5.0 |
| Aeldari | 7/25 | 0 | 0 | 35% | 5.0 |
| Tyranids | 10/25 | 0 | 0 | 57% | 5.0 |

Daemons are tabled 0 times in 200 games, keep 35–58% of their units, and every
game runs the full five rounds. **The "shot off the board before they arrive"
hypothesis is refuted** — Daemons survive fine.

## Finding 2 — the loss is PRIMARY victory points (secondary is a capped wash)

Averaged: Daemon primary 27–36 vs opponent primary 30–41 — Daemons **lose primary
by ~6 to ~12** to almost every opponent (worst vs Imperial Knights −11.8 and
Aeldari −12.4; roughly even only vs Necrons). Both sides' raw secondary exceeds
the 40/game cap, so secondary cancels. **The under-shoot is entirely a primary
board-control deficit** — the mirror image of the Imperial Knights diagnosis.

## Finding 3 — Daemons have surviving bodies but they are not on the markers

Probe (48 games vs shooty/elite opponents):
- **Only 22% of alive Daemon units are within 3" of any objective marker.** 78% are
  off in combat or moving — the army is committed to fighting, not holding.
- When Daemons ARE on a marker, the Objective Control contest is roughly **even**
  (summed Objective Control 2.7 Daemon vs 2.9 opponent) — not a low-OC loss per se.
- 46 of 71 Daemon models (the whole army, essentially) DEEP-STRIKE, with low
  per-model Objective Control (~2). The deep-strike arrival logic
  (`_pick_arrival_point`) already scores landing points by objective proximity,
  but weights it LOW for melee-leaning armies (`objective_w = 0.7` versus 1.6 for
  shooty armies; a late-game ×3 objective boost exists), so the AI deep-strikes
  the melee Daemon army toward enemies to CHARGE rather than onto open objectives.

## Conclusion — the Daemons under-shoot is the SAME residual as the Knight over-shoot

Both are the **primary board-control / mission-fidelity gap**: the simulator
decides games too much on combat and under-models how board control is won. The
durable Imperial Knight over-converts its survival into held markers (over-shoot);
the mobile Daemon army has surviving bodies that fight instead of holding markers
(under-shoot). Same root, opposite ends. Specifically for Daemons:

- It is NOT a survival / arrival deficiency (never tabled).
- It is NOT a missing Daemon-specific board-control RULE: Shadow of Chaos's
  combat / Battle-shock half is modelled (`simulator.shadow_of_chaos`,
  `code/detachments.py`); the real Daemon army rule has no objective-control
  buff to add; the on-marker Objective Control contest is even.
- It IS the same mission/board-control fidelity gap, with the proximate cause
  being the AI committing the melee deep-strike army to combat over objectives —
  the AI-objective-positioning class that has already washed (SWEG_MASS), and the
  scoring-timing model that needs the user-escalated (iii) un-interleaving.

The one buildable-now sub-lever — raising the melee deep-strike `objective_w` so
Daemons deep-strike onto objectives more — is an AI-tuning knob, not a clear
fidelity bug (0.7 for early-game melee deep-strike is defensible; the late-game
×3 already prioritises objective steals), so it is NOT pursued (it would be
metric-tuning per the prime directive).

**Net: this UNIFIES the two biggest residuals (Imperial Knights +27, Chaos Daemons
−14.7) as one root cause — primary board-control / mission fidelity — and so
STRENGTHENS the case for (iii) un-interleaving (real per-player turns +
per-Command-phase scoring), which would address BOTH ends at once. (iii) remains
FOUNDATIONAL and user-escalated; no faithful, separable, buildable-now Daemon-only
lever was found. Reported to the watchdog (LOOP_QA wave-112).**
