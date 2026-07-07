# Protocol review — 2026-07-07

A review of the operating protocols used across the Stage-1 calibration
campaign (roughly waves 1–260 plus the 2026-07 sessions), with the changes
shipped alongside it. Written by the Fable session at the owner's request; the
audience is future (Opus) sessions and the owner.

## Evidence base

The decision ledger, EVAL_PROTOCOL.md, PILOT_PROTOCOL.md, CLAUDE.md standing
rules, the auto-memory, and the full 2026-07-04..07 session arc (Daemons pilot
→ list wins → durability investigations → AM deep audit → claim-and-bank →
chase-VP), which exercised every protocol end to end.

## What is working — keep, unchanged

1. **Paired common-random-number evaluation + standing anchors.** The single
   best methodological asset: deterministic, cheap scoped screens, honest
   flip-level verdicts. The "anchor IS the off arm" rule held all session.
2. **Byte-identical-off validation.** Caught real bugs (slots attribute,
   detachment pin) before they contaminated anything. Zero-flip discipline is
   cheap and non-negotiable.
3. **Fidelity-first + mandatory citations (CLAUDE.md §10).** Killed multiple
   phantom rules (turret +1-to-hit, loser-displacement, the stale Flamers
   devastating-wounds memory) before they shipped.
4. **PILOT_PROTOCOL.** Created mid-campaign after three premature "floor"
   verdicts; since then every pole diagnosis that followed it found either a
   real cause or an honest, well-evidenced dead end.
5. **The Principle-2 scoped-lever recipe.** The only piloting pattern with
   repeatable wins (GSC +3.38, CK +11.27, Votann +10.37, AM staging family
   collectively +3.0).
6. **Parallel read-only audit agents + a single eval owner.** The AM deep
   audit (4 agents) produced converging, decision-grade evidence in one
   session — the pattern to reuse.

## Failure modes found — with the fix shipped for each

1. **Family-blind re-derivation (the #1 token sink).** The durability-over-
   reward wall was independently re-proven by ≥6 levers, each built, screened,
   and refuted on schedule. The ledger contained the prediction every time,
   buried in prose. → **Shipped: `docs/LEVER_PROTOCOL.md`** — a mandatory
   family pre-flight table + "state the mechanism difference or don't build".
2. **The measurement frame was never audited.** The metric scores each faction
   from army-A cells only; per-faction A/B positional bias runs to ±5 points.
   On sc57a the gated MAE is 3.08 (A-frame) vs **2.61 (symmetrized)**, and the
   entire Chaos Daemons pole (5.19) was frame artifact (sym 0.23) — days of
   pilot work chased a measurement bias. → **Shipped: `scripts/diag_frame.py`**
   (A/B/sym frames, both gated MAEs, per-opponent detail) + the LEVER_PROTOCOL
   §6 caveat: no pole is "real" until the sym column says so. Frame adoption
   is an owner decision (re-anchor required); the going-second lever family's
   rejections are flagged confounded pending re-screen.
3. **Estimate contamination.** An untested "~+5pp" note in the ledger was
   treated as fact for a week; the first measurement read −0.25. → Rule:
   MEASURED vs ESTIMATE tags (LEVER_PROTOCOL §3).
4. **Small-N verdict flips.** A N=20 "wrong-sign" reading (AM staging +0.65)
   triggered a removal recommendation; N=40 showed it was noise (+0.10). →
   Rule: kill-tests and wrong-sign readings must be re-run at N=40
   (LEVER_PROTOCOL §4).
5. **Operational hygiene.** Recurrences this campaign: two parallel evals
   clobbering scratch paths; the banned `A && B &` pattern used once; agents
   stalled with 0-byte transcripts; 40 stale worktrees; branch 19 at 84
   commits / ~13.6k lines vs the rule-14 checkpoint (~15 commits). →
   **Shipped: a serial-eval lock in `evaluate_vs_meta`** (`data/_eval.lock`,
   refuses while a live run holds it, `SWEG_EVAL_FORCE=1` override, tested
   both paths). Worktree GC and the branch-19 split remain queued below.
6. **Ad-hoc instruments, rewritten every session.** The per-opponent profile
   was hand-written at least three times; orders-utilization, objective-
   presence and kill-conversion instruments lived in throwaway `python -c`
   blobs. → diag_frame / diag_prim_sec_by_faction / diag_attrition are now
   committed; LEVER_PROTOCOL §1 makes "instrument before build" mandatory.
7. **Ledger bloat.** The "one line per item" rule has decayed into 500-word
   essays; the index is hard to scan, which feeds failure mode 1. → Rule:
   ≤3 sentences per entry going forward (LEVER_PROTOCOL §5); a compaction
   pass over old entries is queued.

## Queued decisions (owner)

1. **Adopt the symmetrized frame?** Unbiased estimator of the same target;
   gated MAE would read 2.61 on sc57a. Requires re-anchor + accepting that
   old verdict deltas aren't comparable. Alternative: keep the A-frame and
   instead FIX the positional asymmetry in the sim (real 40k has no ±5-point
   board-side dependence — it is a Stage-1 fidelity bug in its own right);
   fixing it moves the A-frame toward the sym numbers with no frame change.
   Recommendation: do both in order — root-cause the positional artifact
   first; re-anchor after; re-visit the frame question only if an artifact
   remains.
2. **Branch 19 checkpoint.** 84+ commits, ~13.6k insertions — far past rule
   14. Needs a split plan (stacked PRs by subsystem) or an agreed oversize
   merge; new work should start on branch 20 after.
3. **Going-second family re-screen** under the sym lens (OVERWATCH_MOVE is
   faithful, built, held — its +0.40 A-frame rejection is the most likely
   confounded verdict).

## Residual picture under the honest estimator (sc57a, sym frame)

Real poles: Death Guard ~14.0, Astra Militarum ~15.9 (both REAL and larger
than the A-frame showed), Aeldari ~6.4, Imperial Knights ~5.9, Orks ~4.2,
Chaos Knights ~4.0, Emperor's Children ~3.9. Artifact poles now cleared:
Chaos Daemons 0.23, Genestealer Cults 0.0, Custodes 0.59. The productive
queue: Aeldari over-modelling audit (in flight), EC wider-list audit (in
flight), the positional-asymmetry root-cause, and the DG/AM durability
axis (structural, owner fork).
