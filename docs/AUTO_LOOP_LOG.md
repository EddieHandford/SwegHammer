# Auto-calibration loop log

Started 2026-05-16. Hands-off iteration toward MAE-vs-real-meta ≤ 1.0pt
or 3 consecutive iterations with Δ < 0.1pt.

## Rules

- Every rule addition cites Wahapedia (CLAUDE.md §10).
- AI improvements must benefit all factions equally — no faction-specific picker biases.
- Regressing fix batches get reverted, logged in "Parked" with reason, continue loop.
- Cumulative MAE delta is the metric — individual fix predictions are informational.

## Baseline

- Iter 0: MAE-vs-real **6.72pt**, MAE-vs-Sweg 6.78pt (commit `053e352`).
- Per-faction (Sim% / Real% / Diff):
  - Marines 58.9 / 48.0 / +10.9
  - Necrons 60.0 / 53.2 / +6.8
  - Aeldari 40.0 / 44.4 / −4.4
  - Tyranids 56.1 / 48.0 / +8.1
  - Orks 38.3 / 44.9 / −6.6
  - T'au 51.1 / 54.5 / −3.4
  - DG 67.2 / 48.0 / +19.2
  - Custodes 50.0 / 48.0 / +2.0
  - TSON 52.8 / 54.6 / −1.8
  - Votann 50.0 / 46.0 / +4.0

## Iteration log

(Each iteration: cluster diagnostics → per-faction synthesis → fix dispatch → merge → eval → commit-or-park.)
