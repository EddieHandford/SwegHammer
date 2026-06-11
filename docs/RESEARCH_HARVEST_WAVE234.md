# Wave 234 research harvest — combined ranked diagnostic queue

Three deep-research agents (meta signatures, under-pole, over-pole) landed 2026-06-10.
This is the compact merged queue. Every "missing mechanic" claim here follows the standing
rule: **code-grounded before build** — status column says where each item stands. Ordering
authority for the live next-three remains `docs/CURRENT_STATE.md`.

## Over-pole candidates (Imperial Knights +15.9 / Adeptus Mechanicus +14.6 / Genestealer +13.1 / Necrons +12.8 / Orks +11.3 / Aeldari +11.0)

| # | Candidate | Est. | Status |
|---|-----------|------|--------|
| 1 | **Necrons fabricated "Command Protocol" army-wide passives** — Hungry Void melee armour-penetration +1 (even rounds), Vengeful Stars Sustained Hits 1 (odd rounds), Eternal Conquerors +1 save (round 3). Orchestrator-verified against BSData (rule id 388f-814a-df25-c988) AND live Wahapedia: the 10e detachment rule is ONLY the led-gated +1 to Hit (already implemented); Hungry Void / Vengeful Stars are stratagems (already implemented — these passives double-count); "Eternal Conquerors" does not exist in 10e. Research agent prescribed a led-gate; correct fix is REMOVAL. | 5–10 | **GROUNDED — fix in flight (wave 234)** |
| 2 | **Adeptus Mechanicus Doctrina Imperatives hit-modifier leg missing the BATTLELINE proximity gate** (`code/units.py` ~2556-2565). The helper `_doctrina_battleline_proximity_met` already gates the other two legs of the same rule; the army-wide approximation comment is stale. Matters more since re-priced seeds flooded lists with non-BATTLELINE Ironstriders/Dragoons. | 3–6 | **GROUNDED — fix in flight (wave 234)** |
| 3 | Aeldari archetype mismatch — sim runs only "Battle Host"/Warhost (nerfed dead December 2025); real meta is Aspect Host Strike Force + Corsair Coterie. List-surface fix (allowed), must be grounded in real list data first. | 5–8 | needs list grounding |
| 4 | Genestealer Cults perfect Cult-Ambush arrival + Orks unimpeded horde approach — terrain/positioning representation. | 5–8 each | **BLOCKED on displacement substrate (active build)** |
| 5 | Necrons Nightbringer (340 points) never seeds at 1000 points (`SEED_FRACTION_BY_FACTION`); Aeldari Yncarne always seeds while the Avatar never does. | 1–3 | needs seed-share diagnostic |
| 6 | SUPPRESSIVE counter-evidence (cuts AGAINST the over-rating — never cite as over-pole cause): Adeptus Mechanicus runs a 50/50 detachment split where Cohort Cybernetica carries no buffs; Orks WAAAGH under-modelled (+1 Strength/+1 Attack and 5+ invulnerable missing); Adeptus Mechanicus Elevated Strider absent. | — | recorded |

## Under-pole candidates (Chaos Space Marines −17.0 / Astra Militarum −16.5 / Adepta Sororitas −16.5)

| # | Candidate | Est. | Status |
|---|-----------|------|--------|
| 1 | **Adepta Sororitas "Blood of Martyrs" detachment rule entirely absent** — `HALLOWED_MARTYRS` is an empty shell in `code/detachments.py`; real rule: +1 to Hit below starting strength, +1 to Wound below half strength. Reuse `_squad_start_count`. | 8–12 | **LANDED wave 234 (`31ba197`)** — cited BSData afa4-169c-3aaa-650, damage-gated on the squad substrate, 23 scoped tests green |
| 2 | Four Hallowed Martyrs stratagems absent — Spirit of the Martyr (2 command points, fight on death) and Righteous Vengeance (1 command point, melee rerolls) are substrate-independent; the other two wait on displacement. | 3–6 | needs grounding |
| 3 | Astra Militarum runs Combined Arms but the real meta is Grizzled Company — Ruthless Discipline (reroll hit rolls of 1 under any Order) + No Retreat (sticky objectives). | 6–10 | needs grounding |
| 4 | Chaos Space Marines cluster: Dark Pacts real coverage 10–20/game vs sim 1/round (**CAVEAT: wave-209 naive expansion was net-negative and REVERTED — only revisit with true Lethal/Sustained Hits flags**); Marks of Chaos crit-on-5+ absent; Legionaries melee attacks 3 vs 3.71 actual; Vashtorr/Red Corsairs absent. | mixed | partially settled (ledger) |
| 5 | Astra Militarum Bullgryns / Rough Riders absent from the archetype lists. | 2–4 | needs list grounding |
| 6 | Morvenn Vahl rerolls 1s only vs full reroll (`code/leaders.py` ~510); Triumph of Saint Katherine not seeded. | 1–3 | needs grounding |

Cross-faction insight (research): all three under-pole factions' identities are **reactive/punish
mechanics** — fight-on-death, attrition-reward, sticky objectives — a class the sim does not model.

## Pricing audit (user-requested 2026-06-11 — the "Ed mistake class", two read-only audit agents + orchestrator era check; toolbox section 6 ground truth, zero simulation runs)

**Fixed (commit `d66ca44`):** ten stale `points_override` entries from old sweg_balance_mc
balancer runs (Lanchester-tainted Stage 2 outputs) priced units in the Stage 1 evaluation at
non-printed costs — forbidden per the 2026-06-02 sim-fidelity ruling, Riptide-removal
precedent. Worst case Aeldari Wraithguard: 240.55/model = 1202.75 per five-model squad vs
printed 160, so the archetype's durable shooting spine NEVER appeared in any evaluation army.
All ten now resolve to BSData printed costs. **Invalidates the wave 233 anchor** (army
composition changes for Aeldari / Adeptus Custodes / Space Marines / Necrons).

**Clean:** derived-price sweep complete (zero enabled units on the Lanchester fallback);
six wave-232 re-enabled seeds canonical; `sweg_points_v1.json` consistent; no budget
re-scaling in army building; leader costs charged once at printed cost; points era aligned
(BSData `main` fetched 2026-05-28 vs the May 2026 target); Greater Daemons price from
printed costs (an audit-agent claim to the contrary was refuted by direct loader check).

**Queued residuals:**

| Item | Note |
|---|---|
| Aeldari archetype decisions made on tainted prices | Falcon was dropped from the template *because* it cost 644 (printed 130); Wraithguard seed-walk comments assume 241/model. Fold into the existing Aeldari list-grounding lever — re-derive the template against real-meta lists at honest prices. |
| Non-linear bracket limit | `parsed.json` stores only the minimum-size bracket cost; per-model linear scaling cannot represent non-linear printed brackets for max-size squads. Known representation limit — most 10e brackets are linear, magnitude small; revisit only if a faction residual localises to max-size fills. |
| Silent fallback hardening | `code/units.py:792` (Lanchester path) and `code/bsdata/loader.py:271` (silent points_listed=0) would let a FUTURE unit slip into derived pricing unnoticed. Fail-loud candidate per CLAUDE.md rule 13: raise or warn when an enabled unit reaches the Lanchester path. |

## Game-shape findings (signatures harness `scripts/diag_signatures.py` — CONFIRMED at N=150, `data/wf_wave234_signatures_full.txt`)

- **Secondary saturation: sim mean 38.3 per player per game vs real 22.7** — nearly every player in
  nearly every game hits the 40-point secondary cap. Secondary scoring is a non-differentiator in the
  sim while in reality it is a major faction axis (Bring It Down averages 14 against vehicle-heavy
  armies). Hypothesis worth testing: saturated secondaries leave primary board-hold as the only
  differentiator, which structurally favours the durable-holder over-pole (Imperial Knights, Necrons,
  Adeptus Mechanicus). Diagnose with `scripts/diag_tacdeck_achieve.py` / `diag_secondary_breakdown.py`
  — which cards over-achieve and why — BEFORE touching any scoring value.
- **Going-first win rate 63.8% vs real ≈49–52%** (Chapter Approved 2025-26: generally better to go
  SECOND). A structural initiative bias — symmetric across factions in the eval pairing so it washes
  out of per-faction win rates, but it distorts game dynamics every round (alpha-strike reward).
- Primary ≈21% hot (35.0 vs ≈29); per-round trajectory FLAT (9.0/8.8/8.9/8.9 rounds 2–5) vs the real
  rising-then-attrition-constrained shape — the sim never shows round-5 attrition constraining scoring.
- Round-1-primary-zero assertion PASSES; margin distribution plausible (median 15, blowouts 3.4%);
  challenger cards not modelled (the only unmeasurable signature).
- Reference values: `docs/REAL_META_SIGNATURES.md`.
