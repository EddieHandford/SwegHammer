# Lever protocol — before proposing, building, or screening ANY lever

This is the third standing protocol, beside [`EVAL_PROTOCOL.md`](EVAL_PROTOCOL.md)
(how to measure) and [`PILOT_PROTOCOL.md`](PILOT_PROTOCOL.md) (how to diagnose a
pole). This one governs **how to decide what to build** and **what a verdict
means**. It exists because the 2026-07 protocol review found the single largest
token sink of the campaign was re-deriving already-settled conclusions: the
durability-over-reward wall was independently "discovered" by at least six
different levers (melee-hold, scoped staging, clear-holder, shoot-holders,
claim-and-bank, chase-VP), each built and screened to a verdict the family
table below would have predicted in one paragraph.

## 1. Instrument BEFORE you build

No lever gets built until a cheap measurement shows its mechanism actually
occurs at a frequency that could matter. Cadia Stands! was built before anyone
measured that Cadian Shock Troops stand on controlled objectives ~4% of
unit-rounds — the flat screen was predictable from that one number. Standard
instruments (run these first, they read the anchor or a handful of games):

- `scripts/diag_frame.py <anchor> [--faction X]` — A-frame vs symmetrized win
  rates, per-faction A/B positional bias, gated MAE under both, per-opponent
  craters. **Always check the sym column before declaring a pole real: on
  sc57a, the entire Chaos Daemons "under-pole" (gated 5.19) was A-frame
  positional artifact (sym: 0.23).**
- `scripts/diag_prim_sec_by_faction.py` — primary/secondary VP shape per faction.
- `scripts/diag_attrition.py [curve|byfac]` — kill curves, survival at round 5.
- `scripts/diag_signatures.py` — game-shape vs real (going-first, VP levels,
  round trajectory).
- `scripts/pilot_manual.py` — rate-faithful tactic battery (a FILTER, not a
  diagnosis — see PILOT_PROTOCOL).

## 2. Family pre-flight — predict the verdict before building

Look your proposal up in this table. If the family is settled, you must state
the specific mechanism difference that makes your lever escape the family
verdict — or don't build it. "It's a bit narrower" is not a difference; the
clear-holder lever was the narrower variant of shoot-holders and met the same
end.

| Family | Standing verdict | Anchor evidence |
|---|---|---|
| List-composition fidelity (missing centerpiece / detachment / army shape) | **REPEAT WINNER — audit first, always** | Magnus +6.70, Orks reshape +4.86, EC detachment +3.34 |
| Datasheet / rules fidelity (stats, keywords, invulns, loadouts) | Adopt when verified (fidelity-first) — but faithful ≠ lift; measure | Magnus stats; BATTLELINE_SPECIALS was faithful yet −0.25 |
| Scoped piloting (Principle-2, per-faction gate) | Works ONLY for a genuine piloting gap matching the faction's real playstyle | GSC +3.38, ck_ranged_hold +11.27, votann +10.37; AM exhausted ×5 channels, Daemons ×2 |
| Faction-NEUTRAL piloting / target bias | Washes or feeds the durable side (closed-matrix symmetry) — do not build unscoped | tau_guided, focus-fire family, staging, persistent nomination |
| Going-second / tempo mechanics | All rejected **under the A-frame** — verdicts confounded by frame bias; re-screen under `diag_frame` sym before treating as settled | OVERWATCH_MOVE +0.40, KITE +1.12, PROBE_RESERVE +1.67 |
| Durability / scoring-rule knobs | **FORBIDDEN** (tune-to-win-rate; the scoring is the real Pariah Nexus rule) | no-knobs ruling |
| OC / loser-displacement inventions | **FORBIDDEN** (not a real 10e rule) | ground-truth correction 2026-06-21 |
| "Chase VP" / play-to-score weights | Built (SWEG_AM_CHASE_VP, held): raises VP, does not convert to wins under the durability wall | ledger 2026-07-07 |

## 3. Claims hygiene — MEASURED vs ESTIMATE

Every number written into the ledger is tagged **MEASURED** (with N and frame)
or **ESTIMATE**. An ESTIMATE must never be load-bearing: the ledger carried
"`SWEG_AM_BATTLELINE_SPECIALS` ~+5pp" for a week as if real; the first actual
screen read −0.25. If you find an untagged number in an old entry, treat it as
ESTIMATE until re-measured.

## 4. Minimum-N and verdict discipline

- A scoped N=20 screen is a smoke test, not a verdict. Kill-tests and
  wrong-sign readings at N=20 MUST be re-run at N=40 before acting
  (SWEG_AM_STAGING read +0.65 "wrong-sign" at N=20 and +0.10 flat at N=40).
- Use `decide_stop` semantics: a verdict needs the CI clear of zero (decisive)
  or |delta|+ci below threshold (decisively neutral). Anything else says
  "extend seeds", not "flat".
- Verdict taxonomy, exactly one per lever: **ADOPTED** (default-on, kill-switch)
  / **HELD-faithful** (built, default-off, concrete reopen condition) /
  **REJECTED-empirical** (measured harmful) / **REFUTED-hypothesis** (the
  mechanism claim was wrong) / **PARKED** (needs named new information).
  A reopen condition must be checkable ("after the A/B positional artifact is
  fixed", not "later").

## 5. Eval + agent hygiene (operational rules that keep being broken)

- **One evaluation at a time, across the whole session including background
  agents.** `evaluate_vs_meta` now takes a lock file (`data/_eval.lock`) and
  refuses to start while another live run holds it (`SWEG_EVAL_FORCE=1`
  overrides). Orchestrator owns evals, or names exactly one eval-owner agent.
- Module form, serial, never `A && B &` (detaches the chain; evals die silently).
- Every run logs to a UNIQUE `data/_<tag>.json` — two agents once clobbered the
  same scratch path and one "found" the other's output.
- NEVER import `scripts.evaluate_vs_meta` (even for FACTIONS) in a shell without
  `PYTHONHASHSEED=0` — its self-relaunch guard re-execs the module and silently
  runs a FULL default evaluation, seizing the lock.
- Sub-agents are read-only unless the brief says otherwise; a briefing states
  the exact gates and their defaults; worktree agents verify their base branch
  (CLAUDE.md rule 8).
- **CPU budget (2026-07-09, after a 100 percent freeze of the owner's box):**
  every evaluation runs with `SWEG_WORKERS=8` (half the 16-core box), and only
  ONE compute lane runs at a time — agents must NOT run battle batteries or
  validation battle loops while an evaluation holds `data/_eval.lock`; treat
  the lock as covering ALL battle-running compute, not just evaluate_vs_meta.
- Ledger entries: at most ~3 sentences (the "one line per item" rule has
  decayed into 500-word essays; the index is becoming unreadable). Long
  narrative goes in the archives or a dated doc.

## 6. The frame caveat (2026-07-07)

The standing metric scores each faction from its army-A cells only. On sc57a
the per-faction A/B positional bias runs to ±5 points and moves the gated MAE
from 3.08 (A-frame) to 2.61 (symmetrized). Until the frame decision is settled
(owner call — a frame change requires a re-anchor):

- report `diag_frame`'s sym numbers alongside any screen whose lever touches
  tempo, going-first, deployment, or a faction with |A/B bias| > 2; and
- do not declare a pole "real" (or spend a pilot on it) without checking the
  sym column first.
