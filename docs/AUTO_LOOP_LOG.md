# Auto-loop log (recent)

Older iter blocks live in `AUTO_LOOP_LOG_archive.md`. Per
`AUTO_LOOP_PROCEDURE.md` §E this file keeps the most recent close + the
in-flight wave only.

## Wave 245 (2026-06-12, CLOSED) — first wave on `claude/sim-calibration-11`: three levers screened against the standing sc10a anchor — fight-alternation variant (b) REJECTED decisively (gate and code path deleted), Lord Solar SQUADRON reach adopted as a fidelity wash, Heavy Weapons Squad mortar flags kept as a measured-inert data correction. Eighty-battle re-anchor on the flipped frame in flight.

**1. Housekeeping opener (standing element).** The first vibe-code cleanup checklist item executed
at the branch roll: forty stale one-shot diagnostic scripts moved to `scripts/archive/` as pure
renames (commit `672d81a`, own branch off main, pull request 76 opened merge-ready). Checklist
item annotated done in `docs/research/vibe_code_cleanup_research.md`.

**2. Lever 1 — fight-alternation variant (b): REJECTED, decisively.** Round-scoped once-per-round
melee alternation (cherry-picked `348a7b9`, gated `SWEG_FIGHTALT` default-off). Paired forty-battle
screen against the anchor: gated 6.77 → 7.96 (+1.19), with every decisive mover wrong-direction —
World Eaters +5.89, Imperial Knights +6.58, Adeptus Custodes +5.41, Chaos Space Marines +4.62 all
further over; Drukhari −6.46 further under. Extra fight activations inflate a melee surface the
simulator already over-rewards; the bounding argument the adoption needed is exactly backwards on
this frame. Both variants are now measured rejections — (a) at waves 166/168, (b) here on a frame
sixty waves fresher — so the fight-phase lever is closed, not merely parked: per the housekeeping
prevention rule the gate and code path were DELETED at this close (`_run_fight_alternation`, the
`_fought_this_round` tracker, `tests/test_fight_alternation.py`, and the now-orphaned
`simulator.fight_alternation` citation file). The four pre-existing Astra Militarum citation-debt
fixes bundled in the cherry-pick are kept (they cite live code in `data/rule_citations.d/astra_militarum.json`).
The queue-debt-sweep row for the re-test is closed as executed-and-rejected.

**3. Lever 2 — Lord Solar SQUADRON order reach: WASH-KEEP on fidelity, default flipped ON.**
Five SQUADRON artillery/tank catalog keys appended to Lord Solar's stay-near host set behind
`SWEG_SOLAR_SQUADRON` (`75781ff`, `code/leaders.py`). Paired forty-battle screen: gated 6.77 → 6.75
(−0.02); Astra Militarum +0.68 ± 3.82 with 157 flipped games — his three orders per round now
reach the artillery and churn its games without net direction; only decisive mover Adeptus
Mechanicus +0.96. Kept because the mechanic is faithful (the orders were verifiably wasted every
round before) and adopted default-on at this close (`SWEG_SOLAR_SQUADRON=0` is the kill-switch).

**4. Lever 3 — Heavy Weapons Squad mortar flags: measured EXACTLY inert, kept as a top-level data
correction, and the diagnostic's behavioural claim corrected.** The overrides-only restore of the
mortar's "Blast, Heavy, Indirect Fire" keywords (`c4e0c15`) read gated 6.77 → 6.77 with literally
zero flipped games across 18,480 paired games — byte-identical outcomes. Explained by code, not
anomalous: the squad is per-model promoted, and `_loadout_entry_to_weapon_fields`
(`code/units.py` ~4585) rebuilds the firing block from the per-model loadout dicts, which already
carry the mortar with both flags true — the simulator was never firing this unit
line-of-sight-gated, and the mapper's majority-vote flag loss is real but confined to the unused
top-level aggregate block. Override and notes corrected to state this; kept so the catalogue
matches BSData verbatim. Diagnostic lesson recorded: a per-model-promoted unit's behaviour cannot
be diagnosed from the catalogue top-level flags; the majority-vote bug only has behavioural reach
on units NOT on the per-model path.

**5. Combined keeper-set run SKIPPED as provably redundant (no-redundant-runs directive).** The
keeper set is solar (gated) plus the HWS override (proven byte-inert: zero flips on 18,480 paired
games, and the inertness is frame-independent — per-model promotion replaces the overridden block
unconditionally). The combined configuration is therefore game-for-game identical to the solar
screen already on disk: `data/wf_w245_solar_n40.json` IS the combined result. The §I combined-run
rule exists for non-additive lever composition; composition with a proven null is the identity.

**6. Flip, delete, re-anchor.** `SWEG_SOLAR_SQUADRON` default flipped to "1"; fight-alternation
gate and code deleted (the gate-off path was byte-identical, so the deletion is behaviour-neutral
on the unset frame); full test suite green (1636 passed) and demonstration battle clean
post-surgery. Eighty-battle re-anchor on the flipped frame: **gated 5.79, raw 9.08, 3/22 in band
— `data/_anchor_sc11a_n80_log.json` promoted as the standing anchor, best honest frame to date
(−0.11 vs sc10a).** The paired join against sc10a (36,960 matched games) upgrades the solar
verdict from wash to a REAL toward-target win: Astra Militarum +2.74 ± 2.65 on 330 flipped games
(gated 22.97 → 20.22) — the forty-battle screen's +0.68 ± 3.82 was under-powered, the orders
reaching artillery do convert games; the only other decisive mover is Adeptus Mechanicus +0.55
(small, away), and all twenty other factions are flat, confirming the rest of the wave was
byte-neutral as designed. Wave-246 lever 1 is
already built and held per the pipelining rule: Drukhari Power from Pain (`4ad801a` on
`held/pain-tokens`, gated `SWEG_PAIN_TOKENS`), with three review items queued at pick time
(byte-identity proof for the obsolete per-Unit `pain_tokens` removal, citation source fields to
the BSData cache path + rule id `5e02-2ddc-f55-e6dd`, transient lethal-hits flag scope).
