# Auto-loop log (recent)

Older iter blocks live in `AUTO_LOOP_LOG_archive.md`. Per
`AUTO_LOOP_PROCEDURE.md` §E this file keeps the most recent close + the
in-flight wave only.

## Wave 246 (2026-06-12, CLOSED) — second batch-screen wave on `claude/sim-calibration-11`: Drukhari Power from Pain ADOPTED (the last missing army rule among the competitive factions), squad-level pre-game embark REJECTED and DELETED, squad-aware Fall Back escape WASH-KEPT — and the keeper-set default flip exposed a squad-membership predicate bug that the wave-236 displacement rail tests caught before it shipped. Eighty-battle re-anchor: gated 5.73, new best honest frame.

**1. Lever 1 — Drukhari Power from Pain: ADOPTED.** The held build (`4ad801a` off
`held/pain-tokens`, gated `SWEG_PAIN_TOKENS`) cherry-picked after its three pick-time review items
cleared: fixed-seed demonstration-battle byte-comparison proved the obsolete per-Unit `pain_tokens`
removal neutral on the gate-unset frame, citation source fields re-pointed at the BSData cache path
plus rule id `5e02-2ddc-f55-e6dd` (Wahapedia was unreachable at build time), and the transient
lethal-hits spend scope verified per-round with attached-squad dedup. Army-level Pain-token pool:
command-phase, enemy-destroyed, and battle-shock-failure accrual; greedy
highest-damage-per-activation spend granting transient Lethal Hits (documented approximation — the
codex activates per-datasheet Pain abilities; the simulator collapses Empowering to the dominant
offensive uplift). Paired forty-battle screen against the shared `data/wf_w245_solar_n40.json`
anchor: gated 6.75 → 6.69 (−0.06), Drukhari +1.03 ± 0.90 the sole decisive mover, toward target,
all others flat.

**2. Lever 2 — squad-level pre-game embark: REJECTED and DELETED** (revert `6cb1883`). The
`SWEG_EMBARK_SQUAD` screen read gated 8.36 (+1.61) with decisive wrong-direction movers across six
factions — T'au −9.48, Drukhari −8.85, Leagues of Votann −6.28 further under; Chaos Space Marines
+6.63, Tyranids +6.07, Orks +5.04 further over. Whole-squad embark denies first-round shooting and
board presence with no disembark-timing intelligence to recover the tempo. It is a piloting policy,
not a codex rule, so fidelity-first protection does not apply; gate and code deleted at close per
the housekeeping prevention rule. The transport lever family (one-passenger simplification was the
wave-245 queue entry) is closed as measured-rejected on this frame.

**3. Lever 3 — squad-aware Fall Back escape: WASH-KEEP, default flipped ON.** A genuine multi-model
squad surrounded by three or more enemies now accepts per-squad Desperate Escape losses (about 1.67
expected models on a five-model squad) to recover its shooting instead of dying in place
(`SWEG_SQUAD_ESCAPE`, `code/strategy.py` `_displace_fall_back_buys_something`). Screen: gated 6.73
(−0.02), every faction flat, World Eaters −2.07 ± 2.13 toward target grazing zero. Kept on the
officer-follow / solar-squadron wash-adoption precedent: the piloting is faithful and the suppression
it relaxes was an artefact of the lone-model heuristic.

**4. The predicate bug — the wave's major find.** The combined keeper-set screen (gated 6.69,
−0.06, Drukhari +2.43 ± 2.36 decisive toward) passed, but the build agent's squad-membership test
was `squad_id >= 0` — and `Army.add_unit()` makes EVERY lone unit a one-model squad with its own
squad_id (`code/army.py:680`), so the flipped gate would have let every surrounded non-titanic unit
fall back, a far broader behaviour than the screened lever. The two wave-236 displacement rail
tests caught it at the post-flip full-suite run (both asserted STAY for a lone surrounded unit and
got FALL_BACK). Predicate corrected to count ALIVE members sharing the unit's squad_id via
`unit.army_ref` (more than one alive member = genuine squad; one-model squads, last survivors, and
hand-built units without `army_ref` keep the conservative lone-model suppression). Flip and fix
landed as one commit (`2c08406` — the flip alone leaves the suite red, so they cannot be split),
with the gate-unset tests across three test files converted to explicit `="0"` kill-switch tests.
Suite 1661 green, demonstration battle clean.

**5. Corrected keeper-set re-screen (defaults ON, plain run against the same anchor): gated 6.75 →
6.78 (+0.03, wash), Drukhari +1.29 ± 1.00 the sole decisive mover, toward target, zero
wrong-direction movers.** Half the buggy-predicate Drukhari win was lone-model escapes; the
corrected, genuinely-squad-scoped lever keeps the faithful half. Method note banked: a keeper set
measured with a broader-than-intended behaviour must be re-screened after the correction, never
argued away.

**6. Fold, re-anchor, diagnostics.** origin/main folded at close (`4250949` — pull requests 75/76,
pure `scripts/archive/` renames, zero behaviour-relevant files, anchors stay valid). Eighty-battle
re-anchor on the corrected flipped frame: **gated 5.73, raw 8.99, 3/22 in band —
`data/_anchor_sc11b_n80_log.json` promoted as the standing anchor, best honest frame to date
(−0.06 vs sc11a).** Paired join against sc11a (36,960 matched games): Drukhari +1.01 ± 0.97 toward
target (the wave's intended effect, confirmed at eighty battles) and Grey Knights −0.15 ± 0.13
toward (over-pole shrinking); all twenty other factions flat. Fall Back diagnostic negative
findings recorded so they are not re-litigated: the FLY Fall Back lockout is correct as modelled,
Desperate Escape is already modelled at the displacement gate, the screening gap and the absence of
overextension punishment are real but deferred, consolidation-targeting examined and deprioritized.
An eval-wall-clock read-only diagnostic triaged the Astra Militarum twenty-point under-pole into
five citation-backed candidates (Born Soldiers REGIMENT proxy at `code/units.py:3524` the
highest-estimate; orchestrator spot-verified the top two against source) — banked as the wave-247
lever list in `docs/CURRENT_STATE.md`.
