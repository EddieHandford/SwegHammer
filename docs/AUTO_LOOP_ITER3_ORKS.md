# iter 3 — Orks deep diagnostic (-4.3pt under-perform)

Resumed after API rate-limit reset. Vanilla 10e, N=30/matchup vs DG, Marines,
Necrons, archetypes ON, 1000pt. Driver: `scripts/iter3_orks_deep_diag.py`.

## Headline numbers

| Matchup | Sim WR | Diff vs real (44.9%) | Ork charge succ% | Ork:Opp kill ratio |
| --- | --- | --- | --- | --- |
| Orks vs Death Guard | 23.3% | -21.6 | 54.0% | 0.38 |
| Orks vs Adeptus Astartes | 33.3% | -11.6 | 50.9% | 0.37 |
| Orks vs Necrons | 6.7% | -38.2 | 55.9% | 0.81 |
| Cross-matchup avg | 21.1% | -23.8 | 53.6% | 0.52 |

Eval-vs-meta cumulative shows Orks -4.3pt; this diag isolates 3 worst matchups
where the gap is much wider, which is where mechanism deltas are loudest.

## Mechanism trace

### 1. War Horde stratagems — five of six fire as designed

Per battle, across the 3 matchups (N=90 battles total):

| Stratagem | fires/battle | CP/battle | status |
| --- | --- | --- | --- |
| Insane Bravery | 0.00 | 0 | confirmed no-op (no battleshock-immunity infra) — `simulator.py` L749-751 |
| Power Of The WAAAGH! | 4.99 | 5.0 | fires every fight phase (1 CP, both rounds 1-5) |
| Mob Up | 0.11 | 0.1 | rarely fires — only fires when an Ork is `_most_vulnerable_unit` |
| Big Krumpin' | 0.61 | 1.2 | fires when a high-DPA Ork has a heavy target |
| Tellyporta | 0.06 | 0.1 | almost never fires — vulnerable-target gate rarely satisfied |
| Da Biggest Boss | 1.26 | 1.3 | fires routinely on Warlord Character |

CP burn rate is healthy; Power Of The WAAAGH! eats most of the budget.
Insane Bravery confirmed as catalogued-but-no-op APPROXIMATION (correct).

### 2. WAAAGH! impact — declared R3, but Orks die under it

WAAAGH! round distribution (across all 90 battles): R3 = 83/90 (92%), R2 = 2,
R4 = 5. The first-charge trigger in `strategy.should_declare_waaagh` correctly
overlaps WAAAGH! with the round Orks reach engagement (R3 with archetype
deployment).

`Army.waaagh_round_unlocked` is set and `Unit.attack` reads it for the
+1-to-wound-melee gate (`units.py` L779-786).

**+1 to charge roll leg — MISSING IN CODE.** The iter 1 B4 commit (`36660c0`)
updated `data/rule_citations.d/keywords_and_mechanics.json` and the docstrings
in `units.py` to claim +1-to-charge is implemented, but `simulator._do_charge`
(L3339) still does plain `random.randint(1, 6) + random.randint(1, 6)` —
no WAAAGH! adder. Empirical charge success rate is 53.6%, statistically
indistinguishable from the bare-2D6 vs ~7" gap baseline (~58%). With +1 it
would be ~63%.

**5++ vs melee leg — STILL MISSING.** On the WAAAGH! turn alone, Orks lost
96 models to enemy melee strikes across the 3 matchups. A 5+ invulnerable
save vs melee attacks would have saved ~32 models in expectation (1/3 of
melee deaths). Cross-matchup avg of ~10.7 models saved per matchup per 30
battles — a non-trivial defensive uplift on the round Orks expect to be in
range and getting punched back.

**Advance-counts-as-Charge leg — MISSING IN CODE.** Not measured directly
(no event), but the simulator's `_advanced_this_round` set still blocks
charges for advanced units (`simulator._do_charge` L3326-7), with no Ork-
WAAAGH! exemption.

### 3. Charge resolution post-C2

C2 (iter 2 won't-crack penalty) is firing — Orks charge less futilely than
before. But raw success rate sits at 53.6% across the 3 matchups, with
opponents at 52.4% — Orks no longer have a charge-success disadvantage,
but they don't have any structural advantage either despite WAAAGH! being
declared on the same round.

### 4. Boyz mob + Mob Up

Mob Up fired 10 times across 90 battles. Reanimation pulses on Ork units:
only 3 (DG: 1, Marines: 2, Necrons: 0). The `_most_vulnerable_unit`
selector rarely picks Orks INFANTRY because Necron / DG / Marine high-AP
shooting deletes them outright before they register as "wounded but alive".
Mob Up is functionally near-dead in the meta-realistic matchups. Real-codex
Mob Up needs INFANTRY unit selection logic that includes "below half
starting models" rather than current-HP heuristic — but the model-count
SwegHammer carries (1 Unit per model) makes that read-out trivial.

### 5. Get Stuck In [SUSTAINED HITS 1]

Flag `melee_sustained_hits_army_wide` is set on `WAR_HORDE` (`detachments.py`
L520) and read by `Unit.attack` on every Ork melee strike (`units.py`
L1005-1016). N=90 battles produced 990 Ork melee strikes — every one of
them ran through the +1 sustained-hits adder. Math: a 5+ to-hit Ork melee
weapon's nat-6 rate is 1/6, so SUSTAINED HITS 1 adds ~16.7% more hits on
average. The flag is working.

Kill ratio 0.52 means even with Get Stuck In, Orks deal half as many
casualties as they take. Get Stuck In is not the bottleneck.

## Wahapedia gap

WAAAGH! (`https://wahapedia.ru/wh40k10ed/factions/orks/#WAAAGH`) full rule
modelled vs implemented:

| Leg | Implemented? | Notes |
| --- | --- | --- |
| +1 to Wound (melee) | YES | `units.py` L779-786 |
| +1 to Charge rolls | **NO** | docstring claims "yes" but `_do_charge` has no adder |
| Advance counts as Charge | **NO** | `_advanced_this_round` still blocks charges |
| Army-wide 5+ invuln vs melee | **NO** | no transient flag wired |

## AI gap

`strategy.should_declare_waaagh` is firing on the right round (R3 = first-
charge round for Ork archetypes). No AI-side issue with WAAAGH! timing.

## Top fix proposal (single highest-MAE-leverage)

**Implement WAAAGH! army-wide 5++ vs melee leg** on the declaring turn.
Add a transient defensive flag (e.g. `army.waaagh_round_unlocked == cur_round`
gate in `Unit.attack`'s save-roll block — same shape as the existing +1-to-
wound gate) that lets every Ork model take a 5+ invuln save vs melee attacks
on the declared turn (only if the model doesn't already have a better
invuln).

**Expected MAE delta (informational)**: 32 models / 90 battles = ~0.35
saved models per Ork-battle on the WAAAGH! turn. That maps to roughly
0.5-1.5pt of Ork WR uplift (kills-prevented translates to fewer Ork units
falling below the 50%-strength break point during the critical R3 melee
exchange). Best-case projection if the 5++ keeps Boyz blocks alive into R4
where they continue to threaten objectives: **−0.4 to −0.8pt MAE delta**.
Mid-range estimate **−0.5pt**.

**Wahapedia citation**: https://wahapedia.ru/wh40k10ed/factions/orks/#WAAAGH

> "Once per battle, in your Command phase, you can declare a WAAAGH! is in
> effect for that turn. While a WAAAGH! is in effect for your turn: [...]
> Each model in your army has a 5+ invulnerable save against melee attacks."

Existing `simulator.waaagh` citation already quotes the full rule and flags
the 5++ leg as APPROXIMATION (`data/rule_citations.d/keywords_and_mechanics.json`).
No new citation entry needed — flipping the citation note to "modelled" is
the only docs change at implement-time.

## Honorable mentions (NOT picked)

- **+1-to-Charge leg** — also missing, but a +1 on 2D6 only shifts success
  from ~58% to ~63%, ~5pp lift on Ork charges. Smaller per-Ork-battle
  impact than the 5++.
- **Mob Up profile-name match** — re-target the dispatcher to select Ork
  INFANTRY at <50% starting model count rather than `_most_vulnerable_unit`.
  Low-effort but the +2 reanimation pulse only saves ~2 HP / battle in
  expectation. Skip.
- **Faction-neutral AI** — no obvious AI bug surfaced in this trace; charge
  picker post-C2 is sane, WAAAGH! timing is sane, stratagem firing is sane.
  Nothing to propose here.

## Don't-implement note

Per task gating: this is diagnostic only. No code change in this iter 3
slice. Next iter dispatch picks up the 5++ vs melee fix.

## Tests

`python -m unittest discover -s tests` — 644 tests, 1 failure pre-existing
(`test_archetypes.test_archetype_fallback_when_no_curated`, unrelated to
this script — no diag changes touch test paths).
