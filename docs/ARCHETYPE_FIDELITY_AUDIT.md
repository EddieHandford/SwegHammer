# Archetype fidelity audit — is the "structural durability over-reward" real? (2026-07-01)

The owner challenged the standing "structural durability over-reward" conclusion and asked
for a run-through of the archetypes. Eight parallel read-only audits ran: seven comparing
each big-residual faction's archetype in `code/archetypes.py` against sourced March–June
2026 competitive tournament lists, and one enumerating every concrete delta between the
simulator's scoring and the real Chapter Approved 2025-26 rules.

## Verdict

**The owner is right: there is no distinct "structural durability over-reward" mechanism.**
Every time the claim is drilled into, it resolves into named, individually fixable things:

1. **Archetype-layer infidelity (the biggest single family).** Three mechanisms, all in
   `code/archetypes.py`:
   - **Template curation**: the deterministic seed walk anchors on whichever unit is most
     expensive, which force-seeds unplayed flagship monsters into 100% of games — Angron
     (World Eaters; real 2026 lists are Khârn-anchored), Fulgrim (Emperor's Children,
     17% of army points; zero real-list appearances), Canis Rex (Imperial Knights; real
     lists run Cerastus-class chassis the template does not even contain), a
     Mortarion + Typhus double stack (Death Guard; Typhus and Foul Blightspawn appear in
     zero sourced lists).
   - **Random fill**: ~55–70% of every build's points are drawn UNIFORMLY from the whole
     faction catalogue, not the curated template — Chaos Predators / Land Raiders /
     Heldrakes that essentially no real list fields, ~35% off-god contamination in every
     "mono-god" Chaos Daemons army, and a wrecker-cap formula (`template_count = 0` for
     any MONSTER/TITANIC unit absent from the template) that makes real-meta staples
     ARCHITECTURALLY IMPOSSIBLE to field (Death Guard Daemon Prince, Be'lakor / Kairos /
     Skarbrand, every Cerastus/Acastus Knight).
   - **Detachment picker**: decoupled from list identity (a Khorne army gets the Khorne
     detachment ~20% of the time), and real top-meta detachments are missing entirely —
     Emperor's Children runs NO detachment (the "Slaaneshi Excess" label is inert),
     Astra Militarum lacks Grizzled Company (the real 2026 top performer), Leagues of
     Votann lacks Hearthband / Needgaârd Oathband (~80% of its real meta).
2. **One confirmed catalogue data bug sitting on top**: Canis Rex fielded as TWO permanent
   26-wound TITANIC combatants (BSData folds the ejected-pilot Sir Hekhtur in as a second
   model slot) in every Imperial Knights game — plausibly a large share of the Imperial
   Knights over-pole AND the Imperial-vs-Chaos-Knights asymmetry (the Chaos anchor has no
   such bug). Fixed this session (`SWEG_IK_CANIS_SINGLE`, screening at the time of writing).
3. **Three concrete scoring deltas, not a structural wall** (scoring audit, file:line +
   verbatim rule evidence):
   - Round-5 second-player end-of-turn scoring is missing (known; the faithful fix was
     REJECTED at the 4.86-era frame because it helped durables more — a deliberate
     load-bearing compensating error).
   - A secondary-scoring gate mismatch (`secondaries._tac_deck_enabled()` defaults OFF
     while `simulator.Battle._tac_deck_enabled()` defaults ON) scores the full ~11-card
     legacy union uncapped every round: sim ~39 secondary points/player/game vs real 22.7.
     Currently props up Astra Militarum (the faithful 2-card cap cratered it at the
     4.86-era frame).
   - **NEW, previously uncatalogued, never measured: the wave-67 one-marker-per-squad
     Objective Control clamp** (`code/simulator.py` `_assign_army_oc`) credits a squad's
     summed Objective Control to AT MOST one marker per round. The real rule has no such
     cap (a model within 3 inches of two markers counts toward both). A no-op for
     single-model durables; forecloses a real horde tactic. The one candidate that is
     mine to build and screen without any list-zone decision.
   - (Also: two stale tests + a docstring still assert the pre-wave-252 `SWEG_TABLING_VP`
     default — documentation/test drift, runtime is correct.)
4. **Stale verdicts**: the compensating-error rejections above were measured against the
   4.86 / 3.26 frames. The frame now sits at 2.02 with Astra Militarum at ~38 (not ~27) —
   whether those two infidelities are still load-bearing is an open, re-testable question.
5. **The honest counter-cases** (the claim is not uniformly wrong):
   - **Astra Militarum**: its archetype IS mis-composed (65% of points in a one-of-each
     tank toolbox, one reliable infantry squad, matching no real list) — but the corrected
     infantry-heavy list (`SWEG_AM_REALISM`+`SWEG_AM_RECON`, built + cited) screened
     WORSE at N=80 on the 4.20-era frame. List identity alone does not close the
     under-pole. (That screen is also frame-stale now, and the World Eaters auditor found
     the same gate family has a random-fill leak — see below — so a clean re-screen on
     the current frame is cheap and worth it.)
   - **Leagues of Votann**: composition is roughly in-range (sim Hekaton count is LOW vs
     real); its overshoot is not a list artifact.
   - **Death Guard**: real lists are AT LEAST as durable-share-heavy as the sim's — the
     durable-share axis itself does not discriminate. The deltas are which units carry it
     and the missing screening bodies (~34 sim models vs ~48-58 real).
6. **Implementation bug found in the held list gates**: `SWEG_WE_REALISM`'s seed-phase
   Angron drop never propagates to `_random_fill`, so Angron re-enters ~27% of "fixed"
   builds — the wave-250 "list fix didn't help" screen was measuring a leaky gate.

## Per-faction summary (sim vs real, field-weighted residual from sc33a)

| Faction | Residual | Archetype finding | Direction of faithful fix |
|---|---|---|---|
| World Eaters | +10.1 | Angron force-seeded (real: Khârn-anchored, no Angron); durable share ~50% vs ~33% real; held fix gate leaks | Down (toward real) |
| Emperor's Children | +10.6 | Fulgrim force-seeded 100% (zero real lists); no detachment wired at all; Defiler unreachable from template | Down, despite missing real buff |
| Death Guard | +7.8 | Typhus+Blightspawn phantoms 100%; Daemon Prince architecturally blocked; Blight-hauler disabled (0 points); ~14 models thin | Down (body-count + phantom removal) |
| Chaos Daemons | +7.8 | Be'lakor/Kairos/Skarbrand absent from all templates; ~35% off-god fill contamination; detachment picker god-blind | Ambiguous (real meta is bimodal) |
| Imperial Knights | +7.5 | Canis Rex double-model BUG (fixed this session); real Cerastus/Defender chassis unfieldable; Canis Rex in zero real lists | Down (bug fix + curation) |
| Chaos Knights | +4.7 | Same missing-chassis gap; sim under-seeds Despoiler (real top pick) whose sim output is HIGHER than the Tyrant's | Flat or up — accept per fidelity-first |
| Leagues of Votann | +6.0 | Composition in-range; missing Hearthband/Needgaârd detachments (~80% of real meta) | Not a list artifact |
| Astra Militarum | −12.3 | Genuinely mis-composed, but the corrected list screened WORSE (frame-stale, leaky-gate caveats); real top detachment Grizzled Company unimplemented | List alone insufficient |

## Decision menu (owner-reserved — nothing below applied)

**List zone (per-faction template corrections, each cited to sourced lists in the agent
reports):** World Eaters Khârn re-anchor (plug the `_random_fill` leak first); Emperor's
Children template overhaul (drop Fulgrim/Keeper/Daemonettes, raise Lord Exultant / Noise
Marines / Defiler); Death Guard template fixes (drop Typhus/Blightspawn, add Daemon
Prince + Lord of Contagion, more bodies, re-enable the Myphitic Blight-hauler at its
cited 100 points); Chaos Daemons fifth "Be'lakor's Court / Scintillating Legion"
archetype; Imperial + Chaos Knights missing-chassis menu additions.

**Mechanism zone (one change fixes all factions at once — arguably higher value than any
single list):** weight or scope the `_random_fill` pool (per-god scoping for Daemons; a
curated-pool-only or meta-weighted draw generally), and fix the wrecker-cap formula so
off-template MONSTER units are cappable-but-not-impossible.

**Rules zone (mine to build unless vetoed):** the Objective Control one-marker clamp
faithful fix (new, unmeasured); re-screen the round-5 scoring timing and the secondary
2-card cap on the CURRENT 2.02 frame (both already built + gated, so each is one arm);
re-screen the AM realism list gates on the current frame after plugging the leak.

**Detachment builds (Stage-1 rules work, but switching an archetype's detachment is a
list-identity call):** Astra Militarum Grizzled Company (+1 Order per officer + re-roll
economy — the top real AM detachment, fully absent); Votann Hearthband; a real Coterie
of the Conceited for Emperor's Children.

## Sources

Full per-faction reports with list citations were produced by the audit agents in this
session (transcripts under the session task directory); scoring-delta evidence is
file:line against the current tree plus live Wahapedia fetches. Prior sourced-list data:
`docs/WAVE250_LIST_REALISM.md`. The scoring deltas cross-reference
`docs/DURABILITY_OVERREWARD_INVESTIGATION.md`, whose "RESOLVED — structural" banner
should be read as superseded by this audit.
