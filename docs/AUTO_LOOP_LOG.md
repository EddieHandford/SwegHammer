# Auto-loop log (recent)

Older iter blocks live in `AUTO_LOOP_LOG_archive.md`. Per
`AUTO_LOOP_PROCEDURE.md` §E this file keeps the most recent close + the
in-flight wave only.

## Wave 233 (2026-06-10) — post-merge N=80 re-anchor (NEW FRAME gated 5.74, surface reshuffle) + Adeptus Mechanicus diagnostic closed + keyword-parity COMPLETION kept + displacement substrate GREENLIT

**1. Mandatory fresh full N=80 re-anchor on the post-merge catalogue (pull request #65's 38-unit disable + six
archetype seeds re-priced canonical): gated MAE 5.79 → 5.74** (raw 8.93, 5/22 in band). **NEW STANDING ANCHOR:
`data/_anchor_wave233_n80_log.json`.** Big surface RESHUFFLE from the re-priced seeds (Carnifexes 90, Ironstrider
Ballistarii 85, Sydonian Dragoons 65 — previously over-priced Lanchester-derived, starving their lists):
**Tyranids flipped −13.0 → +7.7 OVER** and **Adeptus Mechanicus −8.2 → +14.6 OVER**; Chaos Daemons into band.
Under-pole now: Chaos Space Marines −17.0 (g14.5), Astra Militarum −16.5 (g13.3), Adepta Sororitas −16.5 (g12.8).
Over-pole: Imperial Knights +15.9 (g13.0, banked structural), Adeptus Mechanicus +14.6 (g10.4), Genestealer +13.1,
Necrons +12.8, Orks +11.3, Aeldari +11.0.

**2. Adeptus Mechanicus wave-232 worsening (−4.8 → −8.2) diagnostic CLOSED with ZERO evals.** Per-gate paired
decomposition on the existing wave-232 logs accounts for the full −3.4 as faithful opponent buffs (Shadow in the
Warp −20 win-rate points in the Tyranids matchup ≈ −1.0 overall; roll-off-once −1.2; Tank Shock −0.6; Sororitas
−0.5; harbingers 0). The one-shot-parity hypothesis was FALSIFIED by audit: Adeptus Mechanicus has zero `one_shot`
assignments, and all 55 one-shot gains are genuine (Hunter-killer missiles ×48, Seeker missiles ×5, Hekaton
warhead ×1). The post-merge frame then superseded the question entirely (Adeptus Mechanicus is now +14.6 OVER —
the pre-merge under-read was dominated by its over-priced seed units).

**3. Keyword-parity COMPLETION (`8e8a060`) adjudicated KEEP.** Secondary-profile `one_shot` / `hazardous` /
`indirect_fire` / `precision` now flow end-to-end (mapper → loader → UnitProfile + sec_swap + per-model secondary
reset; 15/34/8/11 changed units; extra-melee serializer gained one_shot+hazardous), clearing the wave-232 backlog
items (sec_swap keyword inheritance, extra-melee serializer drops). 11 new tests; full suite **1315 passed / 1
skipped / 1 xfailed** (the earlier "2 timing failures" were CPU-contention flakes — suite green on the
uncontended box). Paired N=40 vs the wave-233 anchor: aggregate −0.08, decisive movers **Genestealer Cults −0.55
and Imperial Knights −0.33, both over-pole moving TOWARD target**, nothing cratered. Faithful data-correctness →
KEEP.

**4. Displacement substrate GREENLIT (user-gated → authorized).** The user greenlit the avenue-2 build contingent
on a final-pass review against the rules and online strategy advice. Both reviews completed: the strategy review
confirmed every plan assumption and added two amendments (Stage 2 must evaluate the swarm contest against the
FULL stacked Objective Control of the defending cluster, not the lone holder; Battle-shocked units trivially pass
the Stage 1 no-control-consequence test, scoring at the end of each player's own Command phase); the rules review
confirmed six of seven axes and found one real contradiction — **FLY does NOT bypass the Fall Back shoot/charge
lockout** (it exempts only Desperate Escape tests) — plus a Stage 3 precision (consolidation's objective-marker
fallback fires only on cleared positions). All amendments folded into `docs/DISPLACEMENT_SUBSTRATE_PLAN.md`
(`601fc42`) with a six-item ranked future-candidates section, including the NEW visual-diagnostic finding:
late-game markers sit at 0/0 Objective Control — empty — and no unit ever re-tasks to claim the free victory
points. Visual diagnostic script `scripts/diag_render_displacement.py` committed (renders confirm: Knights
blob-hold their markers; body armies scatter midfield off-marker). Meta-signatures research captured in
`docs/REAL_META_SIGNATURES.md` (real reference values: mean primary ≈29 victory points, going-first win rate
≈49–52%, mean secondary ≈22.7; per-marker control data does NOT exist publicly — Stage 0 will be its first
measurement).

**In-flight (wave 234):** Stage 0 `SWEG_DISPLACE_INSTR` fight-outcome instrument (Opus worktree build) +
`scripts/diag_signatures.py` game-shape harness (Sonnet) + under-pole / over-pole deep-research agents to
harvest into the ranked diagnostic queue.


---
*Older waves archived to `docs/AUTO_LOOP_LOG_archive.md`. Decision index: `docs/DECISION_LEDGER.md`.*
