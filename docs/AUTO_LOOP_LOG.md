# Auto-loop log (recent)

Older iter blocks live in `AUTO_LOOP_LOG_archive.md`. Per
`AUTO_LOOP_PROCEDURE.md` §E this file keeps the most recent close + the
in-flight wave only.

## Wave 234 (2026-06-11) — N=80 re-anchor gated 6.02 (7/22 in band, poles deepened) + Blood of Martyrs landed + ten stale price fixes + structural-debt review + queue-debt sweep + Ed's 23 issues triaged

**1. Fresh full N=80 re-anchor on HEAD `31ba197`: gated MAE 6.02** (raw 8.96, **7/22 in band** — up from
5/22). **NEW STANDING ANCHOR: `data/_anchor_wave234_n80_log.json`.** The wave folded in `d66ca44` (ten stale
`points_override` entries corrected — Ed-mistake-class pricing review) and `31ba197` (Adepta Sororitas
Hallowed Martyrs: The Blood of Martyrs detachment rule), both re-pricing/capability changes, so this is a
frame re-base, not a single-mechanic verdict. Surface reshuffle vs wave 233: the middle improved — Adeptus
Mechanicus +14.6 → +10.6 (g6.41), Genestealer Cults +13.1 → +10.2 (g5.57), Orks +11.3 → +6.6 (g3.66),
Tyranids +7.7 → +6.9 (g3.11); World Eaters, Emperor's Children, Grey Knights, Drukhari, Chaos Daemons,
Thousand Sons, Leagues of Votann all in band — but **the poles deepened**:
- **Under-pole:** Chaos Space Marines −19.3 (g16.83), Adepta Sororitas −18.8 (g15.00 — worse despite Blood
  of Martyrs landing), Astra Militarum −17.7 (g14.49, banked structural — displacement).
- **Over-pole:** Aeldari +16.7 (g13.63, NEW top over), Necrons +16.4 (g13.14), Adeptus Custodes +15.8
  (g13.16), Imperial Knights +15.7 (g12.74, banked structural — displacement).

**2. Structural-errors review (user-directed) → `docs/STRUCTURAL_DEBT_REVIEW.md`.** Five-surface audit of
the early approximation era (detachment flags, stratagem dispatchers, leader abilities, secondaries/orders,
simulator gates). Headline finds: five command-point-sink stratagems (army pays, zero effect), five leader
fabrications (Necron Overlord/Trazyn `plus_one_to_hit`, Chronomancer/Plasmancer `fnp=5`, Chaos Lord
`plus_one_to_wound`), the Battle Focus token cadence wrong (flat 4 at battle start vs per-battle-round
scaled grant), Warhost Martial Grace magnitude wrong, plus a catalogued mobility-mechanic-erasure class
tagged to the displacement substrate. Orchestrator cross-verified the Necron leader cluster against the
BSData cache verbatim before any dispatch; live Wahapedia fetch resolved the two open conflicts
(ANNIHILATION_LEGION `reroll_wound_ones` = FABRICATION with a fabricated inline quote; Battle Focus =
per-round grant, Incursion 2 / Strike Force 4 / Onslaught 6).

**3. Queued-never-executed sweep (user-directed) → `docs/QUEUE_DEBT_SWEEP.md`.** Both halves complete:
17-row memory/log-derived table + the docs-layer NE-1..NE-19 / SB-1..SB-6 actionable table with
cross-references. This is now the ranked dispatch source for fix waves.

**4. Ed's 23 GitHub issues triaged conventionally (user-directed).** All bodies snapshot to
`data/_ed_issues_snapshot.json`; two read-only code-state verification agents grounded every disposition;
comments posted on all 23. Closed: #40 (fixed by Ed's own `693751a` on main). Close via pull request 66
closing keywords at the pending body rewrite: #43 #50 #54 #60 #62. Re-scoped and kept open: #61
(pooled-health remnants in ancillary simulator paths), #44 (Battle Focus manoeuvre coverage), #52
(terrain-wall tunnelling → displacement substrate). Framing comments posted where the
2026-06-02 printed-points ruling superseded issue premises (#43 #44 #45 #47). Holds: #46 #48 #49 #51.
Feature requests parked: #55 (first pick for a quiet window) #56 #57 #58 #59. Docs: #63 standing; #53
fulfilled this close (BASELINE.md catalogue count regenerated 1384, date-stamped — the per-unit table the
issue references was removed in the 2026-05 docs reorganisation; noted on the issue).

**5. Stage 0 displacement instrument + game-shape harness landed earlier in the wave** (`c33d8ab` instrument
build; `scripts/diag_signatures.py` + `data/wf_wave234_signatures_full.txt` game-shape snapshot: sim mean
primary ≈ 29.6 victory points vs real ≈ 29 — primary track in range; going-first and secondary spreads
captured for the multi-metric review). Stage 0 run + verdict still pending (SB-1).

**In-flight (wave 235, the overnight fix cluster):** five worktree fix agents off this frame — Necron
leader fabrications (Overlord/Trazyn/Chronomancer/Plasmancer), Battle Focus cadence (landed `10bda6a`,
adjudicated KEEP), Annihilation Legion fabrication (landed `a82c029`, adjudicated KEEP), command-point-sink
stratagem batch (Adaptive Strategy / Plaguesurge / Desecration of Worlds / Vigilance Eternal), World Eaters
Apoplectic Frenzy rewire to true Lethal Hits. Cherry-pick + full suite + N=80 re-anchor next; then the
queue continues (NE-2 First Rank Fire, NE-9 Lord Solar orders, NE-6 Conquering Tyrant, torrent-over-cannon
override batch, hygiene batch incl. #61).


---
*Older waves archived to `docs/AUTO_LOOP_LOG_archive.md`. Decision index: `docs/DECISION_LEDGER.md`.*
