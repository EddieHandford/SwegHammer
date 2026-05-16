# Auto-loop iter 3 — Aeldari deep diagnostic (-3.8pt under-perform)

Base: HEAD `a4881cc` on `claude/bsdata-stats-import` (iter 2 cumulative
MAE 5.66pt). 644 tests green.

Source: `scripts/iter3_aeldari_deep_diag.py`, 30 N=30 vanilla battles
per matchup at 1000pts.

## 1. Raw mechanism trace (per matchup, N=30)

| Matchup       | win% | dmg dlt | dmg tkn | burst R1-2 dlt | late R4-5 dlt | burst R1-2 tkn | 1st death R | units start→end | adv/btl | charges (fail) | tokens start→end (spent) |
|---------------|------|---------|---------|----------------|---------------|----------------|-------------|------------------|---------|----------------|----------------------------|
| vs Death Guard| 26.7%| 56.3    | 75.0    | 22.5           | 18.2          | 24.7           | 1.23        | 18.0 → 6.0       | 24.9    | 4.7 (2.3)      | 5.0 → 2.1 (2.9)            |
| vs Marines    | 20.0%| 46.5    | 81.8    | 17.4           | 15.9          | 27.4           | 1.70        | 17.4 → 4.7       | 20.6    | 3.7 (2.0)      | 5.0 → 2.5 (2.5)            |
| vs Necrons    | 6.7% | 61.9    | 93.0    | 24.4           | 21.5          | 29.7           | 1.17        | 15.8 → 3.7       | 20.8    | 4.6 (2.3)      | 5.0 → 2.1 (2.9)            |

Mean win% across opponents: **17.8%** (real-meta Aeldari ≈ 44.4%).

## 2. Mechanism findings (the four cohorts)

### Cohort A — Battle Focus token economy
- Tokens issued: **5.0/battle** (Warhost +1, otherwise 4). One-shot pool,
  no per-round refresh.
- Tokens spent: **2.5–2.9/battle**, i.e. ~50% utilisation.
- Real Aeldari uses **8–12 Agile Manoeuvres per battle** (4 tokens
  refreshed at start of EACH round x 5 rounds = ≤20 token-events). The
  simulator is short by a factor of **3–4x** on token throughput, and
  only the "Star Engines" advance+shoot leg is modelled — the **other
  5 manoeuvres (Swift as the Wind, Flitting Shadows, Sudden Strike,
  Opportunity Seized, Fade Back) are not modelled at all**.
- `advances/battle` = 20.6–24.9 confirms the AI is willing to Advance,
  so the throttle is **token supply, not AI intent**.

### Cohort B — Stratagem firing
- Aeldari-named stratagems fire **0.7–1.7 per battle** total. Real
  expected: 4–6.
- Lightning-Fast Reactions 0.33–0.57, Feigned Retreat 0.43–1.17,
  Skyborne Sanctuary 0.17–0.20, Webway Tunnel 0.07–0.13.
- **Fire and Fade / Blitzing Firepower: ~0.0/battle** (Fire and Fade
  fired exactly once across 90 battles). Both gate on
  `atk_cost >= 150.0` AND `_is_heavy_target` AND `tgt_hp_frac > 0.15`
  — the conjunction is empirically unreachable because the 150pt floor
  excludes Fire Dragons (120pt), Dire Avengers (90pt), Warp Spiders
  (95pt). Iter-1 cluster B already flagged this; not fixed.
- Aeldari's CP is being burnt on universal Command Re-Roll
  (3.3–4.9/battle) instead of named warhost plays.

### Cohort C — Damage output
- Burst R1-2 dealt (22.5 / 17.4 / 24.4) is roughly equal to late R4-5
  dealt (18.2 / 15.9 / 21.5). **There is no alpha spike**, despite
  Aeldari being the canonical melta/Fusion alpha army (Fire Dragons,
  Wraithguard D-scythes, Crimson Hunters). Damage profile is flat.
- The reason: by R1.17–1.70 the Aeldari has already lost its first
  unit (alpha-strike vulnerability — see Cohort D). With no Fate dice
  to lock in a 6+ save, the high-cost Fusion squad dies before it
  delivers its burst.
- Cumulative damage taken outpaces dealt by **1.33x–2.0x**.

### Cohort D — Survival
- **First death round 1.17–1.70**. Aeldari dies on Necron / DG turn 1
  in >80% of battles. Units start 15.8–18.0, end 3.7–6.0 — **65–77%
  attrition**. Without a save-rerolling mechanic this is structural.
- Real-Aeldari survival is propped up by **Strands of Fate**: 6D6 Fate
  dice spent to replace a failed save (or fix a critical hit-roll).
  The dice are army-wide and effectively give Aeldari ~6 free "you
  don't die this turn" tokens per battle.

## 3. Is Strands of Fate worth implementing now?

**Yes — it is the highest-leverage single fix available.**

- Wahapedia text: "At the start of the battle, before the first turn,
  roll 6D6; the values of those dice are your **Fate dice**. Each time
  you make a Hit roll, Wound roll, saving throw, Damage roll, charge
  roll, Advance roll or Battle-shock test… you can replace the result
  of that roll with the result of one of your Fate dice." Source:
  https://wahapedia.ru/wh40k10ed/factions/aeldari/#Strands-of-Fate
- Infra cost: **medium** (not high as previously feared). Concrete
  shape:
  1. `Army.fate_dice: list[int]` seeded at setup_battle by rolling
     6D6 for ASURYANI armies (gate on the same `any("ASURYANI" in kw)`
     check used for Battle Focus).
  2. Hook points (no new mechanism — substitute the rolled value):
     - `Unit.attack` failed-hit branch (use a high Fate die ≥ hit
       threshold to convert miss → hit).
     - `Unit.take_damage` failed-save branch (use a high Fate die to
       convert fail → pass; gate on `save_threshold` + invuln).
     - `Battle._charge_roll` / `_advance_roll` (substitute when the
       roll would fail).
  3. AI gate: a single faction-neutral helper `_should_burn_fate_die`
     that fires when the substitution flips a fail → success on a unit
     whose loss costs > 100pts, or a hit/wound that would have killed
     a model.
- Citation: add `data/rule_citations.d/aeldari.json` entry
  `AELDARI.strands_of_fate` per CLAUDE.md §10.
- Expected MAE delta: **-1.5pt to -2.5pt** on Aeldari alone (alpha
  survival fix; pushes first-death R from 1.17–1.70 to ~2.0+, lets the
  Fusion burst land; closes -3.8 → ~-1.5pt). Cross-faction effect
  should be near-zero because every Aeldari opponent already eats
  Aeldari shots — what changes is the Aeldari unit surviving long
  enough to swing back.

## 4. Alternatives considered (rejected as lower leverage)

- **Per-round token refresh** (Cohort A fix only): would push tokens
  spent from 2.9 → ~10 but only powers the Star Engines branch
  (advance+shoot) — the other 5 manoeuvres still aren't modelled.
  Expected delta -0.5 to -1.0pt. **Lower** than Strands.
- **Lower `atk_cost >= 150` floor to 100** (Cohort B fix): unblocks
  Fire and Fade / Blitzing Firepower for real 100pt Aeldari bricks.
  Expected delta -0.3 to -0.8pt. Useful but doesn't fix the alpha
  death; pair with Strands later.
- **Faction-neutral AI: alpha-strike screening preference**
  (move cheaper screen-units between high-cost Fusion bricks and
  enemy LoS in deployment): would benefit Aeldari but also Tyranids
  (Gargoyles screening Carnifex) and Orks (Grots screening Boyz).
  Expected delta -0.4 to -0.7pt for Aeldari specifically. Decoupled
  benefit; can be a future C-track item.

## 5. Top single fix (recommended for iter 3 dispatch)

| # | Type     | Fix                                                                                           | Type infra | Expected MAE delta (Aeldari) | Wahapedia URL |
|---|----------|-----------------------------------------------------------------------------------------------|------------|------------------------------|---------------|
| 1 | RULE_ADD | Strands of Fate — 6D6 Fate dice at start, substitute roll on hit/wound/save/charge/advance.    | medium     | -1.5 to -2.5pt               | https://wahapedia.ru/wh40k10ed/factions/aeldari/#Strands-of-Fate |

## Files

- `scripts/iter3_aeldari_deep_diag.py` (new)
- `docs/AUTO_LOOP_ITER3_AELDARI.md` (this file)
