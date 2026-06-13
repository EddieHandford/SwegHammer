# Auto-loop log (recent)

Older iter blocks live in `AUTO_LOOP_LOG_archive.md`. Per
`AUTO_LOOP_PROCEDURE.md` §E this file keeps the most recent close + the
in-flight wave only.

## Wave 247 (2026-06-13, CLOSED) — third batch-screen wave, first on `claude/sim-calibration-12`: rolling damage default-flipped after one hundred forty-seven waves dormant (fidelity-first), Born Soldiers REGIMENT keyword gate adopted, Cadian Castellan Senior Officer sustained-hits grant adopted — ALL THREE ADOPTED. Eighty-battle re-anchor gated 5.78 with every faction paired-flat against the previous frame and the in-band count up to four.

**1. Lever 1 — Born Soldiers REGIMENT keyword gate: WASH-KEEP.** Cherry-picked `d3f8576`
(`SWEG_BORN_REGIMENT`). The army-rule Lethal Hits leg now gates on the codex-literal REGIMENT
keyword (31 datasheets — Kasrkin, Heavy Weapons Squads, Tempestus Scions, Field Ordnance, Rough
Riders and the rest) instead of the legacy BATTLELINE proxy (3 datasheets). Paired forty-battle
screen against the shared `data/wf_w246_keeperset_fixed_n40.json` anchor (gated 6.78): 6.75
(−0.03), every faction flat; Astra Militarum +0.31 ± 1.91 on 55 flipped games (the faction-scoped
gate flips almost only its own games). Codex-literal rule replacing a proxy — kept on fidelity, the
solar-squadron precedent.

**2. Lever 2 — Cadian Castellan Senior Officer sustained hits: WASH-KEEP.** Cherry-picked
`1a4a229` (`SWEG_CASTELLAN_SH`). The Castellan now grants [SUSTAINED HITS 1] to the led unit's
ranged weapons per the BSData ability text (Abilities profile id `a7f5-adb8-d1c9-2a2d`); the
registry entry's old "no such dataclass field" comment was stale. Screen: 6.75 (−0.03), every
faction flat; Astra Militarum +0.33 ± 0.36 on six flipped games, a whisker from decisive-toward.

**3. Lever 3 — rolling damage default flip: KEEP per fidelity-first.** `SWEG_ROLLDMG` — the
user-approved wave-100 build (each weapon's REAL Damage characteristic rolled per shot on the
per-model firing path, cited `simulator.rolled_damage`) had never been default-flipped and no eval
invocation set the gate, so every production anchor to date was an expected-value-damage frame; the
wave-100 default-off choice predates the fidelity-first ruling. Screen-only lever (no build):
gated 6.92 (+0.14, wash-grade); sole decisive mover Chaos Space Marines +5.84 ± 4.30 away. One
decisive away-mover at a wash headline is not the embark-class decisive rejection — the faithful
core mechanic is adopted.

**4. Combined keeper set: PASS → defaults flipped.** Gated 6.78 → 6.86 (+0.08), the exact sum of
the three solo screens; sole decisive mover Chaos Space Marines +6.27 (the rolling-damage
signature); Astra Militarum nets +1.21 toward target. All three defaults flipped ON in one commit
(`67d124a`), every gate keeping `"0"` as a working kill-switch; the three test files converted to
the kill-switch convention (gate-unset asserts the adopted behaviour, explicit-`"0"` pins the
legacy path). Full suite 1674 green with the flipped defaults, demonstration battle clean.

**5. Diagnostic adjudication — flip-count forensics as the inertness oracle (method note
banked).** A deep-dive agent dispatched on the Chaos Space Marines screen response concluded the
rolling-damage gate was "functionally inert" (top-level `damage_dice` empty catalogue-wide plus a
stale GATE-INERT comment at `code/units.py:724`) and the +5.84 a statistical false positive.
REFUTED from evidence already in hand: a truly inert gate gives byte-identical arms and ZERO
flipped games in the deterministic paired join — the near-inert Born and Castellan screens showed
zero-to-seven flips for most factions, while the rolling-damage screen flipped roughly two hundred
games per faction. The contrast is the oracle, and the end-to-end variance test passed in the same
suite run. Post-flip coverage verification closed the agent's one open question: per-model
promotion defaults ON (`code/army.py:701`), all 1384 catalogue entries carry `model_loadouts` with
a `damage_dice` string in every weapon block, and 499 units field at least one variable-damage
weapon — coverage adequate, no "wire damage dice for non-promoted paths" lever exists because no
non-promoted firing path exists in production. Salvaged from the agent: Chaos Space Marines carries
the field's highest dice-damage-weapon density (77 dice weapons across 112 loadout slots, 17.4
percent) — the faithful explanation for its outsized screen response. The stale comment at
`code/units.py:724` is queued as a trivial comment-only fix.

**6. Fold, re-anchor.** origin/main folded mid-wave (`71c9fbf` — pull requests 77 and 78 merged by
Ed; housekeeping files only, anchors stayed valid). Eighty-battle re-anchor on the flipped frame:
**gated 5.78, raw 9.14, 4/22 in band — `data/_anchor_sc12a_n80_log.json` promoted as the standing
anchor** (the honest rolled-damage frame; +0.05 vs sc11b, authorized fidelity cost). Paired join
against sc11b (36,960 matched games): ALL twenty-two factions flat — the three-lever flip is
metric-neutral at eighty battles, and the Chaos Space Marines watch item largely dissolves (+1.38
± 3.18 at eighty vs +5.84 ± 4.30 at forty — an edge-of-interval forty-battle read regressing to
the mean; the watch stays open at low priority). Non-decisive toward-movers: World Eaters −3.01,
Imperial Knights −2.75, Emperor's Children −2.27. Non-decisive away: Death Guard +3.03 — now the
top over-pole at 14.90. Adepta Sororitas enters the noise band.
