# Auto-loop log (recent)

Older iter blocks live in `AUTO_LOOP_LOG_archive.md`. Per
`AUTO_LOOP_PROCEDURE.md` §E this file keeps the most recent close + the
in-flight wave only.

## Wave 235 (2026-06-11) — overnight fix cluster LANDED (five structural-debt fixes + Apoplectic Frenzy corrected) + Stage 0 displacement GO + N=80 re-anchor gated 5.96. NEW STANDING FRAME.

**1. The full overnight fix cluster is landed and anchored.** Seven fidelity commits closed the wave:
Battle Focus per-round cadence (`ecc925f`), Annihilation Legion fabrication removal (`d89ab89`),
command-point-sink stratagem batch (`d8e0aed` — Adaptive Strategy / Plaguesurge / Desecration of Worlds /
Vigilance Eternal now carry their real effects), Necron leader fabrications removed (`79546fb` + `aa8211c`
— Overlord/Trazyn hit auras, Chronomancer/Plasmancer feel-no-pains; Plasmancer's real Harbinger of
Destruction parked pending a ranged-critical-threshold aura field), **Apoplectic Frenzy corrected**
(`1321799` — the fabricated melee-buff paraphrase replaced by the verbatim advance-and-charge rule via a
new `transient_charge_after_advance` flag in the existing advance-lockout exemption chain; 8 new
regression tests), and **NE-6 Conquering Tyrant scope** (`05c080f` — full hit re-roll when a character
leads, re-roll-ones otherwise, the two-branch codex rule).

**2. Fresh full N=80 re-anchor on HEAD `05c080f`: gated MAE 6.02 → 5.96** (raw 8.99, 5/22 in band —
World Eaters g0.50 and Emperor's Children g0.18 slipped just outside, both near-zero). **NEW STANDING
ANCHOR: `data/_anchor_wave235_n80_log.json`.** Fidelity fixes trended the right factions toward target:
Necrons +16.4 → +14.8 (g13.14 → g11.61), Aeldari +16.7 → +16.0 (g13.63 → g12.86), Imperial Knights
+15.7 → +14.8 (g12.74 → g11.87). **Chaos Space Marines worsened to −20.3 (g17.84, NEW top under)** — the
command-point-sink batch gave its opponents' factions real effects too; Chaos Space Marines is now the
single deepest residual and the next diagnostic target (Pactbound Zealots no-op shell is the named queue
item). Astra Militarum −17.9 (g14.69) and Adepta Sororitas −19.1 (g15.31) hold the rest of the under-pole;
Adeptus Custodes +16.0 (g13.34) now tops the over-pole.

**3. Stage 0 displacement instrument RUN + VERDICT: GO.** Addressable pool 10–25 primary victory points
per game per side, over-pole dominant; the Imperial Knights signature (24.25 uncontested-hold vs 0.75
tarpit) confirms the swarm hypothesis. Full table `docs/DISPLACEMENT_SUBSTRATE_PLAN.md` §5, raw records
`data/wf_wave235_displace_instr_stage0.txt`. Displacement Stage 1 (`SWEG_DISPLACE_FALLBACK`,
fall-back-only-when-wasted rails) is now unblocked.

**4. Wave-236 queue work cherry-picked after the anchor** (post-anchor, so the 5.96 frame predates them):
**NE-2 First Rank, Fire! Second Rank, Fire!** (`ea46aef` — the wrong-stat plus-one-to-hit proxy replaced
by the faithful +1 Attacks on rapid-fire weapons at all ranges via `transient_frfsrf_active`; citation
flipped to approximation false; 281-line test file), **Farseer Branching Fates removal** (`d29fcee` —
the always-on `reroll_wound_ones` aura had no codex support; the real rule is once-per-phase
set-one-roll-to-6, no simulator field exists; removal on the Autarch/Avatar iter21 standard; Aeldari is
the top over-pole so this is suppressive AND faithful), **Chaos Lord Lord of Chaos removal** (`2e7643b` —
`plus_one_to_wound` was a flavour proxy for a once-per-battle-round stratagem command-point discount;
host routing also corrected from the dormant traitor-guardsmen key to Legionaries + Chosen per BSData).
All two-source verified (Wahapedia + BSData v10.6.0 ability ids in the commit messages). Full suite
**1411 passed / 1 skipped / 1 xfailed**, citation audit clean, command-line demo exit 0 at `2e7643b`.
**Anchor caveat: the three wave-236 commits change behaviour (Astra Militarum, Aeldari), so the next
keep/reject comparison must re-anchor rather than reuse `_anchor_wave235_n80_log.json` as an OFF arm.**

**In-flight (wave 236):** NE-9 Lord Solar order count (unblocked by NE-2 landing — resolve the exact
order count from Wahapedia + BSData, stop on conflict), then the queue: Chaos Space Marines −20.3
diagnostic (Pactbound Zealots H1#6), torrent-over-cannon override batch, hygiene batch (issue #61
pooled-health remnants, `cult_ambush_pending` clear, NE-16 citation filing, reserves off-by-one,
Punisher override #104), SWEG_FIGHTALT paired re-test, Battle Focus manoeuvre coverage (#44),
displacement Stage 1. Parked for a wave boundary: merge `origin/main` (pull request 67) + the Warp
Friends target refresh decision; Plasmancer Harbinger of Destruction rebuild; mapper extract_fnp
structural fix.


---
*Older waves archived to `docs/AUTO_LOOP_LOG_archive.md`. Decision index: `docs/DECISION_LEDGER.md`.*
