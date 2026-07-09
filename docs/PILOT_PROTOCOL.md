# Pilot protocol — what a piloted run MUST include

Read this before running or dispatching a manual pilot, and before ever writing the
words "structural" or "floor" about an under-pole. It is the diagnostic counterpart of
[`EVAL_PROTOCOL.md`](EVAL_PROTOCOL.md) (which governs *measuring*): this governs
*diagnosing a pole by piloting*. It exists because the same shortcut has been made
twice and buried real Stage-1 headroom both times.

## Why this exists (the mistakes it prevents)

A "manual pilot" that is only the automated tactic battery (`scripts/pilot_manual.py`)
plus a glance at the objective-control text is **not a diagnosis** — it is a filter.
Three times a *flat* quick screen said "structural floor" and was **wrong**:

- **Thousand Sons** read as a durability floor across four play-quality pilots — until
  reading the board showed the army was missing Magnus (a list gap). +6.70 when fixed.
- **Orks** read as structural from a flat single-lever (Ghazghkull) screen — until the
  board showed inert Killa Kans and no mobility (a list gap). +4.86 when reshaped.
- **Chaos Daemons** read as a floor from the battery + objective text — until reading
  the round-by-round board showed the Khorne melee force **abandoning held objectives
  in the scoring round to make futile charges into a Toughness-12 brick**, throwing a
  tied game. A specific decision error the battery could not see.

The lesson, now a rule: **the tactic battery is necessary but NOT sufficient. Reading
the board and trying to win the game is MANDATORY. "Floor" requires that BOTH the
battery AND the hands-on board-reading find no fixable cause.**

## The mandatory steps (all of them, in order)

1. **Per-opponent loss profile.** Compute the faction's win rate against every opponent
   from the standing anchor (the DG-matchup / Ork-matchup script pattern). Is it a deep
   crater in a few matchups, or a broad shallow bleed? The shape tells you where to look
   and which seeds to read.

2. **The tactic battery (rate-faithful, necessary filter).** Run `scripts/pilot_manual.py`
   for the worst matchup(s): baseline win rate + each pre-set tactic's win-flip delta.
   This is deterministic and rate-faithful, but it only tests the *fixed* tactics wired
   into the harness — it cannot see a misplay no existing tactic expresses (objective
   abandonment, a movement error, a missing unit). A flat battery is a prompt to look
   harder, **never** a verdict of "floor."

3. **READ THE BOARD, ROUND BY ROUND, ON ACTUAL LOSS SEEDS — MANDATORY.** Render real
   losing games (`scripts/diag_pilot_am_vs_ik <seed> "<under>" "<over>"`) and **open the
   per-round board IMAGES with the Read tool** — not just the objective-control text.
   Prefer a *close* loss (a tied-then-thrown game is the most diagnostic). Narrate, per
   round: where each unit goes, what it shoots/charges, who holds which objective, what
   dies, and — critically — **the decisive round** (where the game is actually lost).
   Watch specifically for: units abandoning held objectives; premium/melee units futile-
   charging bricks they cannot crack; a chunk of the army sitting inert; fire scattered
   into targets it cannot hurt; the late-game objective flip.

4. **Try to win it.** From the board, name the specific misplays and reason about what a
   human would do differently to flip *this* game. If a clear human line wins the game
   the AI lost, the pole is NOT a floor — there is a fixable cause (a lever or a list).

5. **Check list composition against the real sourced list.** Census the archetype
   (20+ builds): detachment, centerpiece, unit mix, mobility. Compare to the real
   May-2026 competitive list (source it). Is the faction under-built — missing a
   centerpiece (Magnus), a whole detachment (Emperor's Children Coterie), or the right
   army shape (Orks mobile War Horde vs a Kan wall)? A gated env flag that *looks* off
   may already be default-on (verify the code, not the comment — the Be'lakor gate's
   "default OFF" comment was stale).

6. **Only then conclude.** "Structural / durability floor / Stage-2 pricing" is
   permitted ONLY when steps 2–5 all come back empty: no tactic helps, the board shows
   no fixable decision error, no human line wins, and the list matches the real one.
   Otherwise name the fixable cause (lever direction or list correction) and build it.

## Guardrails carried from EVAL_PROTOCOL and the ledger

- A flat single-lever N=20 screen is NOT a diagnosis (it hid Magnus and the Ork reshape).
- Harness seeds diverge from the eval pair-seed scheme — pilot renders are
  **mechanism evidence only, never rate evidence**. Rates come from `pilot_manual`
  (faithful winner determination) or a scoped eval screen.
- Respect the standing lever rejections (WAAAGH-timing, melee-caging, blanket
  charge-blocking, objective-blind kiting, weak-body-holds) — do not re-derive them.
- The precedent-aligned lever directions are target-economics / focus-fire, scoped
  ranged-holds, staging, and objective-CONTEST-when-behind; a "don't charge / hold the
  objective" lever must be narrowed (a target-quality or held-objective gate), never a
  blanket block.
