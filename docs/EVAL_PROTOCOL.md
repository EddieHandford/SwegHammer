# Eval protocol — read before any eval, screen, or re-anchor

This is the pre-flight checklist for **running** a calibration evaluation: the
execution discipline that the headline metric depends on. It is separate from
*what* to build (`docs/AUTO_LOOP_PROCEDURE.md`, the standing rules in `CLAUDE.md`)
and *what has already been tried* (`docs/DECISION_LEDGER.md`). Those tell you which
lever to make; this tells you how to measure it without wasting a run or reading a
false delta.

Every rule below has cost a real mistake at least once. The first one is the most
expensive and the most recently re-learned, so it is first.

---

## 1. Reuse the standing anchor as the OFF arm — never re-run an OFF arm

The common-random-number paired evaluation is **deterministic**: two identical
current-code, gates-off runs flip **zero of 36,960 games** (confirmed repeatedly,
most recently the wave-260 both-off validation). So the standing anchor log **is**
the OFF arm for any gate that is byte-identical off. Do not run a fresh OFF arm to
pair against — pair the ON arm directly against the anchor:

```
python -m scripts.paired_delta data/_anchor_<frame>_n80_log.json <ON-arm>.json
```

A full eighty-battle (N=80) arm is **~64 minutes** on this box, so a needless OFF
run doubles the wall-clock of every screen. Run a fresh OFF arm **only** when:

- you are doing a true **re-anchor** (establishing a new production default frame), or
- the anchor is **stale** (see rule 3) and must be regenerated against current code.

> This is the rule the previous session forgot — it ran a redundant OFF arm and the
> owner caught it. It is first here so it cannot be missed again.
> (Source: `docs/CURRENT_STATE.md` wave-252 eval-integrity note; `docs/DECISION_LEDGER.md`
> "Paired / Common-Random-Numbers eval mode".)

## 2. Validate every new gate byte-identical-off (the both-off check)

A new default-off gate must reproduce the standing anchor **exactly** — zero of N
flips with the gate off. That single check does double duty: it proves the new code
path is byte-identical when the gate is off (so the anchor is still a valid OFF arm
for it, per rule 1), and it re-confirms the anchor still reproduces against current
code (rule 3). If it does **not** reproduce to zero flips, either the gate leaks when
off or the anchor is stale — stop and resolve before screening anything.

## 3. An anchor must reproduce against current code — watch for staleness

An anchor goes stale when code or the archetype lists change underneath it. The
retired `sc12a` anchor was found to flip forty-one percent of games versus a fresh
current-code gates-off run — it predated the then-current code. The both-off check
(rule 2) is the staleness probe. Per `AUTO_LOOP_PROCEDURE.md` section H: if a merge
of `origin/main` changes simulator behaviour or the archetype lists, **every standing
anchor is stale** and a fresh full N=80 re-anchor is mandatory before any keep or
reject decision. A documentation-only or tooling-only merge keeps the anchor.

## 4. Anchor-promotion, not re-run

When a measured ON arm becomes the new production default, **promote that exact log**
as the standing anchor — do not re-run it. Its configuration already equals the new
default, so re-running only spends sixty-four minutes to reproduce a file you already
have (the Acts-of-Faith promotion at wave 239 and `sc17a` at wave 260 are the
precedent).

## 5. Sample size, and the serial-queue constraint

- An **all-faction** gate is screened at full **N=80** (~64 min/arm).
- A **faction-scoped** lever is screened at **N=40**, reusing the wave's single
  shared off-arm anchor.
- Screens run **serially** — this box is the binding constraint, one arm at a time.
  Do **not** try to parallelise screens; fill the evaluation wall-clock with build
  and diagnostic agents instead (`AUTO_LOOP_PROCEDURE.md` section I).

## 6. Batch screens, single re-anchor — the wave shape

Build every lever gated and default-off; screen each independently against the one
shared baseline; run **one** combined N=40 of the keeper set before flipping, because
levers do **not** compose additively; flip all adopted defaults together at wave
close; then pay for exactly **one** N=80 re-anchor and promote it as the new standing
anchor (`AUTO_LOOP_PROCEDURE.md` section I).

## 7. Flip-count forensics is the inertness oracle

In the deterministic paired join, an inert or never-fired gate flips **zero** games;
a gate that fires flips many. Use the flip count — never a stale code comment — to
decide whether a gate is byte-identical-off (zero flips) or actually firing. The
wave-247 lesson: an agent's "gate inert" claim, argued from a stale comment plus an
empty-but-never-fired field, was refuted by ~200 flipped games per faction. The
corollary saves runs: gates that each flip zero compose to zero, so a combined arm of
all-zero-flip gates is byte-identical to the anchor already in hand — skip it as
provably redundant (wave 248).

## 8. Do not re-burn settled levers

Before proposing or building, check the Reverted / Rejected / Forbidden sections of
`docs/DECISION_LEDGER.md` and the current handover. A lever listed there as refuted or
parked is not fresh work. Re-running one wastes a screen slot on a settled result
(tarpit valuation, the wave-94 clustering geometry, round-five going-second scoring,
the standalone secondary fix, fight-alternation, and the five exhausted on-table
artificial-intelligence levers are all already screened and reverted).

## 9. Forbidden zone — the fidelity guardrails

These bound every lever; the full statement is `DURABILITY_OVERREWARD_INVESTIGATION.md`
section 5, and they are enforced by `CLAUDE.md` rules ten and thirteen.

- **Never nerf a faithful durability statistic** — toughness, wounds, saves,
  invulnerable saves, feel no pain. The combat damage model is a closed faithful floor.
- **No Objective-Control-to-victory-point knob** — corrections move models, they do not
  multiply a model's contribution.
- **No faction or model-count branch** — a correction that fires only for one faction or
  only for low-model armies is fitting the list, not modelling the rule.
- **No rate dial without an external real-meta reference.** Going-first win rate is the
  lone exception (published real target forty-nine to fifty-two percent).
- **Cite every rule** (`CLAUDE.md` rule ten) — if no canonical citation exists, stop and
  ask the user; do not approximate or invent.
- **Fail loud on missing data** (`CLAUDE.md` rule thirteen) — no silent defaults.

---

## Where this is surfaced

So this checklist cannot be missed at the moment an evaluation starts:

- **`.claude/hooks/eval_guard.py`** — a `PreToolUse` guard prints the headline rules
  whenever a command running `scripts.evaluate_vs_meta` or `scripts.paired_delta` is
  about to execute (through either the Bash or the PowerShell tool).
- **`.claude/skills/sweg-wave/SKILL.md`** — links here from the cherry-pick-and-eval step.
- **`CLAUDE.md`** and **`docs/AUTO_LOOP_PROCEDURE.md`** (section I) — link here as the
  eval-execution layer.
