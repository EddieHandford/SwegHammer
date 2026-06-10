# Auto-loop log (recent)

Older iter blocks live in `AUTO_LOOP_LOG_archive.md`. Per
`AUTO_LOOP_PROCEDURE.md` §E this file keeps the most recent close + the
in-flight wave only.

## Wave 232 (2026-06-10) — five verified gates flipped DEFAULT-ON + weapon-keyword parity (ungated) + clean N=80 re-anchor: NEW STANDING FRAME gated 5.79 (was 5.99)

Hygiene-and-flip wave. Two code deliverables plus the serial A/B queue and the re-anchor:

**1. Weapon-keyword parity for non-primary profiles (`dc4f63c`, ungated — a mapper data-correctness fix, verifier PASS).**
The mapper only carried `indirect_fire` / `one_shot` / `hazardous` / `precision` onto the PRIMARY weapon profile; secondary
and extra-melee profiles silently dropped them. Fixed: 21 profiles gained indirect_fire, 55 one_shot, 29 hazardous,
5 precision across 523 multi-profile units; parsed.json regenerated deterministically. Ungated default-config change →
all prior anchors invalidated as pairing bases; a fresh full-default N=40 run (gated 6.34) served as the OFF anchor for
every A/B below.

**2. Serial A/B queue (paired/Common-Random-Numbers where valid; N=40 vs the fresh OFF anchor) — all five gates adjudicated KEEP:**
| gate | aggregate gated MAE delta | decisive movers | note |
|---|---|---|---|
| `SWEG_TANKSHOCK_DICE` (Tank Shock rolls Toughness-many D6, 5+ = 1 mortal wound, cap 6) | −0.13 | Astra Militarum +0.61 toward target (decisive) | replaces the flat-2 proxy |
| `SWEG_ROLLOFF_ONCE` (first-turn roll-off once per battle, not per round) | −0.36 | — (aggregate compare; gate re-randomizes the stream so pairing is invalid) | retires a fake free-double-turn mechanic |
| `SWEG_SITW_TEST` (Shadow in the Warp forces Battle-shock tests) | −0.06 | Tyranids +2.11 toward target | cross-faction "movers" in the scoped run were re-randomization artifacts (gate adds dice draws), not effects |
| `SWEG_HARBINGERS` (Chaos Knights Harbingers of Dread Dread abilities) | −0.21 | **Chaos Knights +7.42 toward target (decisive, 200 flips)** | the biggest single-faction win of the wave |
| `SWEG_SOROR_ABILITIES` (Sororitas character abilities) | flip per the wave-231 N=80 evidence (+0.81 faithful) | Adepta Sororitas | that commit's own message deferred the flip to this re-anchor |

**3. The flip (`f35346c`):** 10 environment-read sites across `simulator.py` / `units.py` / `leaders.py` changed from
default `"0"` to default `"1"` (`=0` stays the explicit escape hatch), ~16 comment/docstring sites + 5 citation prose
sites updated, 5 test files converted (OFF tests now set `"0"` explicitly; unset-parity tests assert unset == explicit
`"1"`). Full suite 1304 passed / 1 skipped / 1 xfailed, audit clean, `run.py --cli` exit 0. (Box note: the full pytest
sweep needs `PYTHONHASHSEED=0` preset on this Windows machine, same as the evals — without it the suite produces empty
output with exit 0.)

**4. Clean full N=80 re-anchor at the new defaults: gated MAE 5.99 → 5.79 (raw 9.20, 4/22 in band).
NEW STANDING ANCHOR: `data/_anchor_wave232_n80_log.json`.** Movers vs the wave-228 frame: Chaos Knights −9.0 → −5.1
(Harbingers, now gated 1.81), Adepta Sororitas −15.3 → −13.5, Emperor's Children +15.2 → +11.6, T'au +10.6 → +9.4,
Death Guard +8.7 → +7.5. Worsened: **Imperial Knights +17.2 → +20.2** (banked structural) and **Adeptus Mechanicus
−4.8 → −8.2** — both plausibly the ungated keyword-parity redistribution (one_shot added to 55 profiles cuts their
output); the Adeptus Mechanicus move is flagged for a scoped follow-up diagnostic. Tests green, audit clean, cli 0.


---
*Older waves archived to `docs/AUTO_LOOP_LOG_archive.md`. Decision index: `docs/DECISION_LEDGER.md`.*
