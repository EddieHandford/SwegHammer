# Wave 250 — melee-cluster archetype list-realism (HANDOVER, in progress)

**Status as of 2026-06-13 ~23:45 UTC. Branch `claude/sim-calibration-13` @ `71e270b` (pushed).
PR #79 merged to main and folded in (`f15e552`). The standing anchor
`data/_anchor_sc12a_n80_log.json` (gated 5.78) is unchanged and valid.**

This wave corrects the archetype LISTS for the four over-rated melee factions to match
real May-2026 competitive tournament lists. The melee over-pole (Death Guard 14.90, World
Eaters 14.24, Emperor's Children 11.94, Chaos Daemons 11.19) was localized in wave 249 to
archetype-composition fidelity after four other mechanisms were ruled out (see the wave-249
block in `AUTO_LOOP_LOG.md`). The fix is metric-direction-NEUTRAL and faithful (matches the
cited real list), in the wave-174/175 list-realism tradition — NOT win-rate tuning.

## User decision (2026-06-13)
- **Scope: all four factions, sourcing first.** Source real lists before rebuilding each.
- **World Eaters: anchor swap only** (minimal — stop always-fielding Angron; anchor on Khârn).
- Each rebuild is gated default-off, screened (N=40 paired vs the keeper-set anchor
  `data/wf_w247_keeperset_n40.json`, gated 6.86), and reported before any default flip.

## Lever 1 — World Eaters (BUILT, SCREENING)
- **Commit `71e270b`, gate `SWEG_WE_REALISM`, default-off.** `code/archetypes.py`
  `_instantiate_template`: when on + faction World Eaters, drops `world_eaters_angron` from
  the template and force-seeds `world_eaters_kh_rn_the_betrayer` (Khârn) so the build is
  Khârn-anchored. 5 tests (`tests/test_we_realism_wave250.py`), 67 archetype tests green,
  both demo arms exit, off-path byte-identical. Citations in the code comment.
- **Screen DONE** (N=40, `SWEG_WE_REALISM=1`, `data/wf_w250_werealism_n40.*`, paired vs
  `data/wf_w247_keeperset_n40.json`): **gated 6.86 → 6.96 (+0.10, mild adverse wash).** World
  Eaters itself +0.64 but with a ±5.13 CI on **273 flipped games** — a large behavioural change
  whose net effect on World Eaters is INDETERMINATE at N=40 (high variance), point estimate UP
  (away). Decisive movers are all OTHER factions drifting up (Adeptus Custodes +0.95, Chaos
  Daemons +0.84, Adeptus Mechanicus +0.83) — cross-contamination, mildly worse frame.
- **READ:** the anchor-swap is faithful and clearly does something (273 flips), but it does NOT
  reduce World Eaters' over-rating — swapping the 340-pt Angron for Khârn frees points that
  become more cheap bodies, which the per-model representation over-rates just as much. This
  CORROBORATES the standing finding that the melee over-pole is the per-model activation
  representation wall, not the specific list composition.
- **DISPOSITION:** lever KEPT built + gated default-OFF (faithful, reversible, user-approved).
  NOT flipped (mild adverse + WE itself indeterminate). A clean WE read needs N=80. **STRATEGIC
  QUESTION FOR THE USER before the EC/DG/Daemons rebuilds: if faithful list-realism does not move
  the melee over-pole (representation wall), is it worth rebuilding the other three — which are
  bigger reshapes — for fidelity alone (metric-neutral-to-adverse expected)?** The EC/DG/Daemons
  rebuilds are sourced and ready either way; the decision is whether the payoff justifies them.
- Real lists (3, Best Coast Pairings via Grimhammer): Khârn-anchored, **no Angron**. Core:
  Khârn 1, Slaughterbound 1, Khorne Berzerkers 3+ squads, Exalted Eightbound 1-2, Jakhals
  1-2 squads of 9, Chaos Spawn 2 squads, Rhino 1-2. ~67 models (sim ~61 — model count was
  NOT the issue; composition/anchor is). URLs in the `71e270b` code comment.

## Lever 2 — Emperor's Children (SOURCED, REBUILD QUEUED)
- **Dominant detachment = Coterie of the Conceited** (~half of EC games, ~60% win rate;
  John Lennon 1st at Warhammer Open Edmonton 250+, AC Champions Cup; Goonhammer detachment
  focus). The sim's archetype names a **non-existent** detachment "Slaaneshi Excess".
- **Real Coterie core (NO Fulgrim, NO Keeper of Secrets, NO Daemonettes/Seekers/Fiends, NO
  Chaos Terminators, NO Chaos Spawn, NO Heldrake):** 2× Daemon Prince of Slaanesh with
  Wings, 3× Noise Marines (6-model), 2-3× Infractors (5), 2× Tormentors (5), 2-3× Lord
  Exultant, 1× Lucius the Eternal, 1× Lord Kakophonist, 2× Maulerfiend, 2-3× Chaos Rhino.
  ~43-49 models.
- Sources: spikeybits.com (AC Champions Cup 2025; Warhammer Open Edmonton 1st/250+),
  gmpwt.blog (Court of the Phoenician battle report, Feb 2026, Fulgrim variant).
- REFINEMENT to the wave-249 note: the Slaanesh daemons ARE legal EC datasheets, but real
  competitive Coterie lists don't run them — dropping them is list-realism, not a
  faction-boundary fix.
- **Build plan:** replace the `code/archetypes.py` "Emperor's Children" → "Slaaneshi Excess"
  template with the Coterie core above (rename to "Coterie of the Conceited"), gated
  (e.g. `SWEG_EC_REALISM`), default-off. EC current keys live ~line 919.

## Lever 3 — Death Guard (SOURCED, REBUILD QUEUED — opposite direction: sim UNDER-counts)
- Real "Virulent Vectorium" (3 lists, Grimhammer Jul/Oct/Nov 2025): Daemon Prince of Nurgle
  1, Lord of Contagion 1-2, Deathshroud 2 squads, Foetid Bloat-Drone 3-4, Myphitic
  Blight-Haulers 2, Poxwalkers 2-3 squads of 10. Mortarion in 2/3. **NO Typhus, NO Foul
  Blightspawn.** ~48-58 models — sim builds ~39, so DG needs MORE bodies (more Poxwalkers).
- **Build plan:** correct the DG archetype to drop Typhus + Foul Blightspawn and increase
  Poxwalker / Deathshroud / Bloat-Drone weighting toward the real counts; gated, default-off.

## Lever 4 — Chaos Daemons (SOURCED, REBUILD QUEUED — wrong detachment)
- Real dominant = **Be'lakor Scintillating Legion (Tzeentch)**, NOT the sim's four mono-god
  sub-archetypes. 4 lists (Grimhammer Jan/Dec 2025/Mar 2026): Be'lakor 1, Kairos / Lord of
  Change 2-3, Daemon Prince of Chaos, Flamers, Screamers, Nurglings, Blue/Pink Horrors.
  ~25-43 models (sim ~52 mono-god = over + wrong archetype).
- **Build plan:** add a Scintillating Legion sub-archetype (Be'lakor-anchored Tzeentch) as
  the dominant build; bigger reshape; gated, default-off. (Lowest priority of the four —
  smallest over-pole, biggest reshape.)

## Open levers carried into / parked before wave 250 (do not lose)
- `SWEG_TABLING_VP` (wave 249, `f59930f`) — faithful, near-inert, built-and-held; run with
  the gate on at the next N=80 re-anchor (free) and decide the flip.
- Three wave-248 Astra Militarum gates (Creed / Reinforcements / Fix Bayonets) — built-and-held,
  byte-inert; reopen conditions in `DECISION_LEDGER.md`.
- Astra Militarum 19.89 under-pole = per-model activation representation (structural wall).
- `units.py:724` stale GATE-INERT comment (trivial, bundle with any units.py edit).

## Resume checklist
1. Read the World Eaters screen verdict (`data/wf_w250_werealism_n40.txt` + paired_delta vs
   `data/wf_w247_keeperset_n40.json`). If WE moved toward target cleanly, the anchor-swap
   approach is validated → proceed with the EC/DG/Daemons rebuilds above.
2. Build EC → DG → Daemons rebuilds (gated, default-off, A/B screened, cite the lists in the
   archetype comment — `code/archetypes.py` is NOT in the citation-audited set).
3. Combined keeper-set screen → flip the adopted defaults → N=80 re-anchor (fold the held
   `SWEG_TABLING_VP` on into that re-anchor for its free confirm) → close wave 250.
