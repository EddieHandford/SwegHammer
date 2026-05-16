# Auto-loop iter 1 — Cluster B (under-performer diagnostic)

Scope: three under-performing factions per iter-0 baseline (`AUTO_LOOP_LOG.md`).
Diagnostic source: `scripts/auto_loop_iter1_cluster_b_diag.py` — 30 archetype
battles per matchup at 1000 pts, 3 representative opponents per faction.

| Faction | Sim% | Real% | Diff   |
|---------|------|-------|--------|
| Orks    | 38.3 | 44.9  | -6.6pt |
| Aeldari | 40.0 | 44.4  | -4.4pt |
| T'au    | 51.1 | 54.5  | -3.4pt |

---

## 1. Orks (-6.6pt)

### Mechanism trace

| Matchup           | win% | dmg dealt/taken | 1st death R | charges (fail) | WAAAGH R | 1st charge R |
|-------------------|------|-----------------|-------------|----------------|----------|--------------|
| vs Custodes       | 23%  | 26 / 90         | R2.10       | 17.5 (7.3)     | 3.03     | 2.37         |
| vs T'au           | 77%  | 60 / 50         | R1.40       | 17.8 (9.2)     | 2.90     | 2.34         |
| vs Necrons        | 10%  | 51 / 103        | R1.33       | 16.6 (7.4)     | 3.03     | 2.77         |

**Dominant losing mechanism**: WAAAGH! fires mean R3.03 but mean first-charge
round is R2.37-2.77 - the +1-to-wound melee buff is declared AFTER 50%+ of Ork
charges have already resolved (the existing `scripts/orks_waaagh_diag.py`
output confirms `waaagh_after_charge` = 13-17/30). Boyz die before the buff
turns on (first death R1.33-2.10). Plus: 40-55% of charge attempts fail (no
+1-to-charge implementation), and there is currently NO Orks detachment
mapped (`DEFAULT_BY_FACTION["Orks"] = ""`, `FACTION_DETACHMENTS["Orks"] = ()`)
- the army goes naked while every other faction stacks a detachment passive.

### Wahapedia rule gap audit

1. **War Horde detachment (NONE wired)**. Detachment rule "Get Stuck In, Ladz":
   "While an OUTRIDE OBJECTIVE CONTROL marker that an INFANTRY unit from your
   army is within range of is controlled by your army, each time a model in
   that unit makes a melee attack, that attack has [SUSTAINED HITS 1]." Plus 6
   real stratagems (Insane Bravery, Power Of The WAAAGH!, Mob Up, Big Krumpin',
   Tellyporta, Da Biggest Boss). Source:
   https://wahapedia.ru/wh40k10ed/factions/orks/#War-Horde

2. **WAAAGH! full bundle (only +1-to-wound melee modelled)**. Real text grants
   on the declared turn: +1 to wound melee AND +1 S AND +1 A on melee weapons
   AND army-wide 5+ invuln AND Advance-counts-as-Charge AND +1 to charge rolls.
   `code/units.py:765-770` says verbatim: "we model only the +1-to-wound leg".
   The +1-to-charge leg directly explains the 40-55% failed-charge rate. Source:
   https://wahapedia.ru/wh40k10ed/factions/orks/#WAAAGH

3. **Mob Rule (no Battleshock penalty currently for Orks)**. Real text: "Each
   time a Battle-shock test is taken for an OUTRIDE OBJECTIVE CONTROL INFANTRY
   unit from your army, instead of taking that test using that unit's
   Leadership characteristic, take it using the highest Leadership
   characteristic of any OUTRIDE OBJECTIVE CONTROL INFANTRY unit from your
   army within 9" (including itself)." Maps onto auto-pass when a Warboss is
   nearby. Source: https://wahapedia.ru/wh40k10ed/factions/orks/#Mob-Rule

4. **Dakka 3+ on Shoota weapons not exposed**. The Boyz `Shoota` profile in
   `parsed.json` carries `hit_probability: 0.333` (BS5+) with no sustained.
   Real Shoota is 18", Assault, Rapid Fire 1 with no upgrade — current model
   is fine. (Not a real gap; rejected.)

### Strategy AI gap audit

- `should_declare_waaagh` declares at R3 because the "first-charge-round
  trigger" gates on `_has_chargeable_target` checking `<= 12"`, but most Ork
  units start outside that range and don't close until movement R2-3. The
  ordering counter (`waaagh_after_charge`) shows the AI consistently fires
  the buff after the unit it should be helping has already swung. Fix is
  faction-neutral if reformulated as "fire on the turn a melee unit declares
  its first charge" rather than a separate Command-phase declaration.
- No Ork stratagems fired at all in 30-battle samples (only Universal
  Core Stratagems: Command Re-Roll, Heroic Intervention, Tank Shock,
  Counter-Offensive). Direct consequence of (1) above.

### Ranked fix list (Orks)

| # | Type      | Fix                                                                 | Expected MAE delta |
|---|-----------|---------------------------------------------------------------------|--------------------|
| 1 | RULE_ADD  | Add War Horde detachment + 6 stratagems (Wahapedia citation above)  | -1.5pt to -2.5pt   |
| 2 | RULE_FIX  | Add +1-to-charge-roll leg to WAAAGH!                                | -1.0pt to -1.5pt   |
| 3 | AI_IMPROVE| Move WAAAGH! declaration to the turn a melee unit STARTS its charge phase (compute right before the charge step rather than command-step prediction). Faction-neutral framing: AI decides army-rule timers in lockstep with the consuming phase. | -0.5pt to -1.0pt |
| 4 | RULE_ADD  | Wire +1 S, +1 A, Advance-counts-as-Charge legs of WAAAGH!           | -0.5pt to -1.0pt   |

---

## 2. Aeldari (-4.4pt)

### Mechanism trace

| Matchup        | win% | dmg dealt/taken | 1st death R | charges (fail) | 1st charge R |
|----------------|------|-----------------|-------------|----------------|--------------|
| vs Custodes    | 13%  | 26 / 94         | R1.70       | 5.9 (2.5)      | 2.75         |
| vs Death Guard | 3%   | 42 / 93         | R1.17       | 4.7 (2.8)      | 3.28         |
| vs Necrons     | 3%   | 51 / 97         | R1.23       | 5.2 (3.2)      | 2.76         |

**Dominant losing mechanism**: Catastrophic alpha-strike vulnerability. First
death round R1.17-1.70 (Aeldari dies first turn against Death Guard / Necrons).
Damage taken (93-97) outpaces damage dealt (26-51) by 1.8-3.5x. Warhost
stratagems fire 0.07-0.67 times per battle - the "wounded brick" gate is too
restrictive (Fire and Fade requires >150pt attacker AND target softened, but
the attacker is dead before turn 3). The Aeldari Battle Focus army rule is
modelled as a one-shot pool of 4 tokens (not the real per-round refresh) and
only spent for the Star Engines Advance+shoot manoeuvre - the army misses the
"shoot then move" Fade Back leg entirely.

### Wahapedia rule gap audit

1. **Battle Focus full ruleset (5 of 6 manoeuvres missing)**. Real text grants
   6 named Agile Manoeuvres triggered by token spend: Star Engines (modelled),
   Swift as the Wind, Flitting Shadows, Sudden Strike, Opportunity Seized,
   Fade Back. Fade Back ("shoot then move out of LoS") is the canonical
   alpha-protect mechanic that Aeldari uses to survive turn 1. Source:
   https://wahapedia.ru/wh40k10ed/factions/aeldari/#Battle-Focus
   Citation already exists: `data/rule_citations.d/keywords_and_mechanics.json:250`
   (verbatim) - marked APPROXIMATION.

2. **Per-round token refresh missing**. Real text: "at the start of each
   battle round, you receive a number of Battle Focus tokens (4 at Strike
   Force)" - SwegHammer issues 4 once-per-battle. Verified at
   `code/simulator.py:298-305`: `army.battle_focus_tokens = base_tokens`
   runs only at battle setup, not at round start.

3. **Strands of Fate (army-rule layer above Battle Focus)** - NOT YET MODELLED.
   Real text: "At the start of the battle, before the first turn, roll 6D6;
   the values of those dice are your Fate dice. Each time you make a Hit roll,
   Wound roll, save... you can replace the roll with one of your Fate dice."
   This is the single biggest Aeldari mechanic missing - it powers the
   guaranteed-crit-on-Fire-Dragons / guaranteed-save-on-Wraithguard plays.
   Source: https://wahapedia.ru/wh40k10ed/factions/aeldari/#Strands-of-Fate

4. **Asuryani INFANTRY 4+ invuln vs Psychic / ranged not exposed**. Real text
   for Striking Scorpions / Howling Banshees: 4+ invulnerable vs ranged
   attacks; for Banshees: 5+ invuln + always-strike-first. Both datasheets are
   in `parsed.json` with `invuln_save: 7` (none). Source:
   https://wahapedia.ru/wh40k10ed/factions/aeldari/#Striking-Scorpions
   and #Howling-Banshees

### Strategy AI gap audit

- Aeldari Warhost stratagem gates are intentionally tight (the comments cite
  "Aeldari already over-rates by +7.5 vs the meta") but that was iter-0 BEFORE
  the diagnostic data showed Aeldari now UNDER-rates by -4.4pt. The thresholds
  at `code/strategy.py:1967-2075` (`cost >= 150.0`, `hp_frac > 0.4`) deny CP
  to canonical 100-pt Aeldari bricks (Fire Dragons 120pt, Dire Avengers 90pt,
  Wraithguard 240pt only at the high end).
- Faction-neutral re-framing: the "hp_frac" gate is reasonable but the
  "atk_cost >= 150" floor is excessive - real meta lists average 100pt squads.
  Lowering the floor in the picker would benefit any faction with sub-150pt
  HEAVY squads (Tyranid Zoanthropes 90pt, T'au Sunforge Crisis 142pt, etc.).

### Ranked fix list (Aeldari)

| # | Type      | Fix                                                                  | Expected MAE delta |
|---|-----------|----------------------------------------------------------------------|--------------------|
| 1 | RULE_ADD  | Strands of Fate - implement Fate dice (6D6 pool at battle start, spendable as substitute for hit / wound / save / charge / advance / battleshock rolls). High infra. | -1.5pt to -2.5pt |
| 2 | RULE_FIX  | Refresh battle_focus_tokens at start of each round (move L298-305 from setup_battle into `_run_round` Command-phase block).                                          | -0.5pt to -1.0pt |
| 3 | AI_IMPROVE| Lower `atk_cost >= 150` floor on Warhost stratagem gates to `>= 100` so the AI spends CP on real meta squad sizes. Faction-neutral because the gate is per-stratagem-name and the same `atk_cost` threshold appears across many factions - lowering the floor benefits Aeldari now without changing other factions' branches. | -0.3pt to -0.8pt |
| 4 | RULE_ADD  | Add Striking Scorpions / Howling Banshees 4+ invuln overrides in `data/overrides.json`.                                                                              | -0.2pt to -0.5pt |

---

## 3. T'au Empire (-3.4pt)

### Mechanism trace

| Matchup       | win% | dmg dealt/taken | 1st death R | early/late dmg | 1st charge R |
|---------------|------|-----------------|-------------|----------------|--------------|
| vs Custodes   | 27%  | 25 / 80         | R1.73       | 19.8 / 4.9     | 2.94         |
| vs Tyranids   | 33%  | 42 / 77         | R1.77       | 27.4 / 14.8    | 3.19         |
| vs Necrons    | 10%  | 66 / 81         | R1.33       | 42.1 / 23.6    | 3.25         |

**Dominant losing mechanism**: Damage front-loads in rounds 1-3 (Mont'ka
`army_wide_assault_rounds_1_3` is active), then collapses to 25-35% of
early output once the assault window closes. The shooting army with no
charge counterplay then has nothing to do rounds 4-5 while the enemy
trades into the gunline. Plus: Markerlight / Guided mechanic completely
unimplemented (`code/detachments.py:127-129`, `code/detachments.py:378-381`
both say "lethal_hits_on_guided NOT YET READ"), so the Killing-Blow detachment
rule loses half its codex text.

### Wahapedia rule gap audit

1. **Markerlight / Guided keyword (entire mechanism missing)**. Real text:
   "Each time a model in your army with the SPOTTER MARKERLIGHT weapon hits
   a target with one of its attacks, until the start of your next Command
   phase, you can Guide that target for one of your units." Guided units
   gain BS+1 to hit the target and (under Mont'ka) Lethal Hits. The Stormsurge
   / Riptide / Broadside spine of the May-2026 meta list is built around
   feeding Guided buffs to the heavy weapons - which currently do nothing.
   Source: https://wahapedia.ru/wh40k10ed/factions/t-au-empire/#Markerlights

2. **For The Greater Good (saviour protocols defensive)**. Real text:
   "Each time a ranged attack targets a TAU EMPIRE unit from your army, if
   that unit is within 6" of a FIRE WARRIORS unit, that FIRE WARRIORS unit
   can elect to intercept the attack." Maps onto Fire Warrior screens
   absorbing alpha-strike on Crisis suits - directly addresses the R1-2
   battlesuit deaths visible in the trace. Source:
   https://wahapedia.ru/wh40k10ed/factions/t-au-empire/#For-the-Greater-Good

3. **Kauyon alternate detachment missing**. Real Kauyon (the patient hunter
   detachment) rotates Hit re-rolls onto a tagged target over rounds 1-2
   then `Sustained Hits 1` army-wide rounds 3-5. The simulator only has
   Mont'ka (rounds 1-3 assault) - which alone leaves rounds 4-5 dead. Adding
   Kauyon as a second detachment lets the builder picker choose based on
   composition (heavy-shooter rosters tilt Kauyon, mobile rosters tilt
   Mont'ka). Source:
   https://wahapedia.ru/wh40k10ed/factions/t-au-empire/#Kauyon

### Strategy AI gap audit

- Mont'ka stratagem `cost >= 150` floor (`code/strategy.py:2265-2276`) gates
  out the same squad-cost issue as Aeldari (see Aeldari item 3 - same
  faction-neutral lowering would also benefit T'au).
- `_GUNLINE_ATTACKER_FACTIONS = frozenset({"T'au Empire"})` (strategy.py:297)
  explicitly excludes T'au from the gunline-charge defensive bias - good for
  symmetry but means T'au's own melee escorts (Stealth Battlesuits, Vespid)
  never get the prioritise-the-gunline target uplift even when fighting
  another shooty army.

### Ranked fix list (T'au)

| # | Type      | Fix                                                                  | Expected MAE delta |
|---|-----------|----------------------------------------------------------------------|--------------------|
| 1 | RULE_ADD  | Implement Markerlight / Guided keyword (per-unit guided-target uid + +1 to hit + Mont'ka Lethal Hits on Guided units). New infrastructure. | -1.0pt to -1.5pt |
| 2 | RULE_ADD  | Add Kauyon detachment (alternate to Mont'ka) so builder picks based on composition - rotates re-roll-hits R1-2 onto Oath-target then Sustained 1 R3-5. | -0.5pt to -1.0pt |
| 3 | RULE_ADD  | Saviour Protocols / For the Greater Good intercept rule (Fire Warriors within 6" of a targeted T'au unit redirect a fraction of incoming attacks). Mid infra. | -0.3pt to -0.8pt |
| 4 | AI_IMPROVE| Same `atk_cost >= 150` -> `>= 100` cross-faction floor reduction as Aeldari fix #3 (benefits Mont'ka stratagems on 140pt Crisis Sunforge / Fireknife). | -0.2pt to -0.5pt |

---

## Combined ranked fix list (top 5 by expected cumulative MAE delta)

| # | Faction | Fix                                          | Type       | Scope  | Expected MAE delta |
|---|---------|----------------------------------------------|------------|--------|--------------------|
| 1 | Orks    | War Horde detachment + 6 stratagems          | RULE_ADD   | medium | -1.5 to -2.5pt    |
| 2 | Aeldari | Strands of Fate (6D6 Fate dice pool)         | RULE_ADD   | high   | -1.5 to -2.5pt    |
| 3 | T'au    | Markerlight / Guided keyword + Mont'ka tie-in | RULE_ADD   | high   | -1.0 to -1.5pt    |
| 4 | Orks    | +1-to-charge-roll leg of WAAAGH!             | RULE_FIX   | low    | -1.0 to -1.5pt    |
| 5 | T'au    | Kauyon alternate detachment                  | RULE_ADD   | medium | -0.5 to -1.0pt    |

Cumulative-delta caveat: fixes 1+4 are both Orks - apply together they likely
yield -2.5 to -3.0pt total (not the additive -2.5 to -4.0pt) because both
target the same melee-output deficit. Fix 5 only counts if Mont'ka is
preserved alongside (composition-driven picker) - the two detachments
combined have an upper-bound delta of -1.5pt rather than the literal sum.
Fix 2 (Strands) is the highest-effort single-faction change and the only
"high infra" item in the top 5; can be parked for iter 2 if iter 1's
4 lower-infra items already close the MAE.

---

## Files

- `scripts/auto_loop_iter1_cluster_b_diag.py` - diagnostic script (new)
- `docs/AUTO_LOOP_ITER1_CLUSTER_B.md` - this analysis doc (new)
