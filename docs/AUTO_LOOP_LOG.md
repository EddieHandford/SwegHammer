# Auto-loop log (recent)

Older iter blocks live in `AUTO_LOOP_LOG_archive.md`. Per
`AUTO_LOOP_PROCEDURE.md` §E this file keeps the most recent close + the
in-flight wave only.

## Wave 238 (2026-06-11) — re-anchor on the defender-allocation frame: NEW STANDING FRAME gated MAE 5.83 + displacement Stage 2 recovered, verified, harvested (paired A/B in flight) + simulator modularization Stage A pull request 71 opened.

**1. Upstream pickup (procedure §H, first live exercise).** Ed merged pull request 69 (defender wound
allocation — the defending player allocates wounds, scoring candidates by on-objective / distance /
health, `SWEG_DEFENDER_ALLOC` default-ON) and pull request 70 (follow-up: wounds reach out-of-range
models, finish wounded models first, plus a 188-line test file). Both are behaviour-changing, so both
in-flight anchors were killed stale-on-arrival and the merges folded at wave boundaries (`8e81bde`,
`0550475`), each validated with the full suite before relaunch.

**2. Fresh full N=80 re-anchor on `0550475`: gated MAE 5.83** (raw 8.78, 5/22 in band).
**NEW STANDING ANCHOR: `data/_anchor_sc7c_n80_log.json`** (record `data/_anchor_sc7c_n80.txt`). Against
the wave-237 frame (5.71 on `4f9cce3`) the headline moved +0.12 — re-base churn on a frame change, not a
keep/reject signal. The shape moved the right way for the defender-allocation mechanic: the over-pole
softened (Adeptus Custodes +17.7 → +15.6 g12.98, Necrons +15.2 → +12.5 g9.26, Imperial Knights
+16.0 → +15.4 g12.48) — consistent with defenders now protecting objective-holders — while the
under-pole deepened slightly (Chaos Space Marines −18.0 → −19.3 g16.82) and Aeldari (+15.4 g12.33) /
Adeptus Mechanicus (+13.3 g9.12) worsened. In band (5): Thousand Sons, Leagues of Votann, Chaos
Daemons, Grey Knights, Drukhari (Death Guard g1.72 and Chaos Knights g1.42 close behind).

**3. Displacement Stage 2 recovered and harvested.** The build agent died mid-task leaving uncommitted
work in its worktree; a recovery agent preserved it (`475c3c8`, 222 lines in `code/strategy.py` + a
330-line test file), and a continuation agent verified the build complete against all rails: the
`SWEG_DISPLACE_SWARM` gate (default-OFF) reads in exactly one place and the unset path is byte-identical;
the contest decision sums the FULL CLUSTER's stacked objective control on both sides; a unit that cannot
at least tie the defending cluster contributes zero contest value (no-suicidal-feed); the score injection
mirrors the tarpit-pin pattern. Six tests green. Cherry-picked onto the calibration branch as `724252e`;
full suite + citation audit + demo validation, then the paired eighty-battle A/B
(`SWEG_DISPLACE_SWARM=1` versus the 5.83 anchor) — IN FLIGHT at wave close. Targets the Adeptus
Custodes / Imperial Knights over-hold.

**4. Simulator modularization Stage A shipped for review.** On the user's explicit go, pull request 71
opened: `code/sim/constants.py` + `code/sim/geometry.py` extracted from `code/simulator.py` by pure code
motion, facade re-imports keep every call site working, behaviour identity proven by the new
fingerprint harness `scripts/sim_motion_proof.py` (base and branch hash identical, 1477 tests passed).
Later stages (per-phase engines, then decision layers) follow the same protocol after Ed merges.

**5. Operational incident, logged for the procedure.** A spurious empty `Get-Process python` read plus
0-byte buffered output files led to a false "anchor dead" diagnosis and a redundant duplicate N=80
launch (violating the no-redundant-evaluations rule and oversubscribing cores). Caught one tick later
from the CPU-time-bearing process listing; the duplicate was killed and the original anchor completed
cleanly. Lesson: 0-byte output files mid-run are normal (stdout buffering); declare an evaluation dead
only from a full process listing showing no accumulating processor time.

**NEXT (wave 239):** (1) Stage 2 paired A/B keep/reject; (2) Acts of Faith `SWEG_AOF_PER_PHASE=1`
paired A/B versus the same anchor; (3) Chaos Space Marines −19.3 positional re-diagnosis (the
displacement own-marker direction per the mark-grants REDIRECT) + Adepta Sororitas findings 2–7
re-rank. Checkpoint pending with the user: the calibration branch is past the size caps
(8 commits / ~1,550 reviewable lines) and has NO open pull request — asked whether to open it for Ed.
