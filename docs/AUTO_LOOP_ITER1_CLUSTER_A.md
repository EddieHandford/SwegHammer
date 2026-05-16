# Auto-loop iter 1 — Cluster A over-performer diagnostic

Status: diagnosis only. No simulator/AI code changes in this pass.

## Method

`scripts/auto_loop_iter1_cluster_a.py` — N=30 archetype battles per matchup,
1000 pt, vanilla 10e rules. Three opponents per over-performer chosen to
cover the meta diversity (Marines/Tyranids/T'au for melee/swarm/gunline +
Aeldari/Necrons where mirror or counter is informative).

The script captures: damage in/out per round, kills inflicted by each side
per round, VP totals, stratagems fired (with round + name), reanimations.

Baseline gap (iter 0): Death Guard +19.2 / Marines +10.9 / Tyranids +8.1 /
Necrons +6.8 (sim vs real meta WR).

## Headline trace (3-opp slice)

| Faction | Sim avg WR (slice) | Real WR | VP gap | Notable |
|---|---:|---:|---:|---|
| **Death Guard** | 67.8% | 48.0% | +14.1 | Wins despite taking MORE damage than dealing (DG dmg 65.2 / opp dmg 55.8 across slice). Engine = FNP 5+ army-wide + Worldblight sticky objectives. |
| **Marines** | 42.2% (slice) | 48.0% | −4.7 | Slice masks the over-performance — Marines collapse vs Necrons (13.3%) but win vs T'au (60%). The +10.9 headline must come from the unsampled matchups (Aeldari, DG, TSON, Custodes, Votann). |
| **Tyranids** | 52.2% (slice) | 48.0% | +2.6 | Close to real in this slice; the +8.1 headline is pulled by the unsampled cohort (Orks, Votann, TSON). Root cause already documented in `FACTION_T1`. |
| **Necrons** | 87.8% | 53.2% | +32.2 | Catastrophic in the slice. Wins all three matchups by 19-44 VP. RP firing 5.1-5.6 revives / battle. Awakened Dynasty stratagems fire 1.2-1.7x per battle EACH. |

---

## Death Guard (+19.2pt)

### 1. Mechanism trace

DG loses the model-trade arithmetic (dmg dealt 65.2 / dmg received 55.8 vs
Marines/Tyranids/T'au) BUT scores VP +14.1 ahead on average. The driver is
**non-combat scoring through Disgustingly Resilient FNP + Worldblight
sticky objectives** — DG holds primary while opponents bounce off
T5/W2/FNP 5+ Plague Marines.

Stratagem fire rates per matchup (3 opps × 30 battles = 90 battles):
- Overwhelming Generosity: 86-97 fires (~1.0/battle, +1 to hit/reroll approx)
- Creeping Blight: 78-85 fires (~0.9/battle, reroll hits shooting)
- Putrid Detonation: 13 fires (Deadly-Demise auto-success)
- Disgustingly Resilient (the stratagem, on top of the faction rule): 2-10
- Leechspore Eruption: 6-12 fires

So DG armies fire ~2 transient-hit-buff stratagems per battle on top of
the always-on FNP 5+. The hit-buff stratagems both grant reroll-hits-shooting
which composes with no diminishing return.

### 2. Wahapedia rule gap audit

**G-DG-1 — Disgustingly Resilient scope wrong.** Real rule (Wahapedia:
https://wahapedia.ru/wh40k10ed/factions/death-guard/#Disgustingly-Resilient)
says it applies to "this unit … each time a model in this unit would lose
a wound" with the army rule keyword on **specific datasheets** — Plague
Marines, Deathshroud, Blightlord Terminators, Typhus, Death Guard
CHARACTER infantry. It is NOT on Plagueburst Crawler (VEHICLE), Foetid
Bloat-Drone (VEHICLE), Mortarion (he has it as a separate ability), or
Poxwalkers. Our simulator gates on `profile.faction == "Death Guard"` →
every DG model gets FNP 5+, including the Plagueburst Crawler. Verbatim:
"Each time an attack is allocated to this model, subtract 1 from the
Damage characteristic of that attack." Note: the real DR is **−1 to
Damage**, not FNP 5+ — we approximate it as FNP 5+. Both directions are
defensive but FNP 5+ on a W12 Crawler is FAR stronger than −1 to damage
(−1 Damage from a D2 lascannon → 1; FNP 5+ on a D2 lascannon → 0.67 EV
saved per wound, applies to D6+1 too).

**G-DG-2 — Opponents have no Anti-DG counter-tool.** Real meta uses
weapons with `[ANTI-INFANTRY 2+]` (Pulse Blastcannon, Stalker Bolt Rifle
under doctrine), `[DEVASTATING WOUNDS]` (Tyranid Neurotyrant, Custodes
Misericordia, Eldar Bright Lance), and `[MORTAL WOUNDS]` payloads — none
of these bypass FNP 5+ (FNP applies to mortal too), but they bypass the
T5/W2 wall via auto-wounds. Our weapon DB has `devastating_wounds=False`
on the standard Marine Eradicator melta, the Custodes Misericordia (which
has DW on Wahapedia datasheet), and on most Aeldari psychic weapons.
Result: simulated opponents fire bolters into a T5/2+/FNP 5+ wall and
deal half-EV damage where real-meta opponents would route to DW weapons
or anti-infantry profiles.

**G-DG-3 — Worldblight stickiness over-locks.** Real rule (Wahapedia:
https://wahapedia.ru/wh40k10ed/factions/death-guard/#Virulent-Vectorium)
verbatim: "If you control an objective marker at the end of your Command
phase and a DEATH GUARD unit from your army (excluding Battle-shocked
units) is within range of that objective marker, that objective marker
remains under your control until your opponent's Level of Control over
that objective marker is greater than yours at the end of a phase." We
model this correctly per simulator.py:482. But the Battleshock-exempt
clause is meaningful in real play: a Battle-shocked DG unit cannot
lock. Our FNP 5+ army-wide rule keeps DG models alive, and the same
DG models pass Battleshock automatically because Ld 7 + auto-pass at
half-wounds. Combined, DG locks objectives perma-effectively.

**G-DG-4 — Contagions of Nurgle stacks too easily.** Wahapedia:
https://wahapedia.ru/wh40k10ed/factions/death-guard/#Contagions-of-Nurgle.
"While an enemy unit is within Contagion Range of any DEATH GUARD models
from your army, that unit is subjected to the Contagion that is in
effect." Contagion Range starts at 3" and only grows to 6" at R3+ via
Plaguesurge. We model the radius as 6" army-wide from `units.py:81`
(`_is_near_enemy_dg_model(radius=6.0)`) — too big in R1-R2. Effect: -1 to
hit on opponents in R3+ projects to the entire DG screen.

### 3. Strategy AI gap audit

**A-DG-1 — Opponents shoot through the FNP wall instead of around it.**
Universal AI gap: target priority doesn't downweight defenders with
high FNP. A T'au Crisis suit firing at a Plague Marine reads kill-potential
high (T5, W2, 3+ save) but ignores the FNP 5+ → real EV is 33% lower.
The score doesn't apply an FNP haircut. Faction-neutral fix: in
`code.strategy._durability`, multiply effective HP by `(6/(7-fnp))` so a
4+/T5 unit with FNP 5+ reads as 1.5x as durable per attacker DPA.
**Faction-neutral** — applies to any FNP defender (DG, Drukhari with Pain
Tokens, TSON via stratagem, Eldar Aspect Warriors with Lightning-Fast
Reactions, etc.).

**A-DG-2 — Opponents don't focus-fire to clear DG bodies in one
activation.** DG bricks survive chip-damage because every attack
re-rolls a wound through FNP 5+; one Eradicator can't clean a 5-model
Plague Marine squad. Real meta groups Eradicators + Hellblasters
together. Our AI activates one unit at a time without coordinating fire.
Faction-neutral fix: when picking ranged targets, prefer the target that
the just-activated friendly's DPA can overkill given pre-committed
friendly fire this round. Already partially handled by COUNTER plan; not
implemented as a per-activation lookahead. **Faction-neutral**.

### 4. Ranked fix list (Death Guard)

| # | Type | Fix | Wahapedia | Scope | Expected Δ MAE |
|---|---|---|---|---|---|
| F-DG-1 | RULE_FIX | Restrict Disgustingly Resilient to DG `INFANTRY` keyword + CHARACTER; remove from VEHICLE / MONSTER. Replace FNP 5+ with `transient_minus_one_damage_taken`. | https://wahapedia.ru/wh40k10ed/factions/death-guard/#Disgustingly-Resilient | medium (keyword gate + flag swap) | **−3.0 to −5.0 pt** |
| F-DG-2 | RULE_FIX | Restrict Contagions of Nurgle radius to 3" in R1-R2, 6" only in R3+. | https://wahapedia.ru/wh40k10ed/factions/death-guard/#Contagions-of-Nurgle | low (one line in `_is_near_enemy_dg_model`) | **−1.5 to −2.5 pt** |
| F-DG-3 | AI_IMPROVE | Faction-neutral: `_durability` haircut for FNP (multiply by 6/(7-fnp)). Improves opponent target priority against any FNP defender. | https://wahapedia.ru/wh40k10ed/the-rules/core-rules/#Feel-No-Pain | low (one function in strategy.py) | **−1.0 to −2.0 pt** |
| F-DG-4 | RULE_ADD | Worldblight: gate the sticky-objective claim on the DG unit passing a Battleshock check (already in simulator.py:511, but no actual Battleshock test fires on DG units because they auto-pass at full HP). Force a BS test for the lock. | https://wahapedia.ru/wh40k10ed/factions/death-guard/#Virulent-Vectorium | low (already wired; just gate harder) | **−0.5 to −1.0 pt** |
| F-DG-5 | STAT_FIX | Audit DG stratagem firing gates: Creeping Blight and Overwhelming Generosity fire 0.9-1.0x per battle each = ~2 CP/battle when DG only banks 8 CP/game. Tighten triggers to prevent both firing same shooting phase. | n/a (AI tuning) | low | **−0.5 to −1.5 pt** |

Cumulative: fixes likely interact (F-DG-1 + F-DG-3 both reduce DG
durability and would compose). Headline +19.2 → target −10 to −15 pt of
reduction = land at +4 to +9, a major win.

---

## Adeptus Astartes (+10.9pt)

### 1. Mechanism trace

Marines in the 3-opp slice **under-perform** (42.2% avg WR). Per matchup:
- vs Necrons: 13.3% WR — Marines burn shooting on a reanimated wall.
- vs Tyranids: 53.3% WR — close to real.
- vs T'au Empire: 60.0% WR — Marines comfortably beat the gunline.

The headline +10.9 must come from unsampled matchups (Aeldari, DG,
Custodes, TSON, Votann, Orks). The 3-opp slice average dmg dealt is 75.8
vs 53.3 received — Marines win the model-trade everywhere, but VP
scoring lags vs Necrons specifically (RP keeps Necron OC alive).

Stratagems: heavy `Command Re-Roll` (98-176 fires per matchup) +
`Heroic Intervention` (12-74). No detachment-specific stratagems wired
for Gladius Task Force (Combat Doctrines is the only headline).

### 2. Wahapedia rule gap audit

**G-AA-1 — Oath of Moment damage is uncapped.** Real rule (Wahapedia:
https://wahapedia.ru/wh40k10ed/factions/space-marines/#Oath-of-Moment):
"At the start of the battle round, select one enemy unit … each time a
unit from your army … makes an attack against that enemy unit, you can
re-roll the Hit roll, and you can re-roll the Wound roll." We model
this correctly in simulator.py:3182. The mechanic itself is per rule;
the gap is that the AI picks the **highest-points target each round**
without considering revival (RP) or sticky-objective control. The real
rule is correctly cited — no rule gap; AI gap covered below.

**G-AA-2 — Gladius Task Force stratagem set is missing.** Real
Gladius has 6 detachment stratagems (Wahapedia:
https://wahapedia.ru/wh40k10ed/factions/space-marines/#Gladius-Task-Force):
Adaptive Strategy, Storm of Fire, Honour the Chapter, Only in Death Does
Duty End, Armour of Contempt, Bolter Discipline. None are wired in
`code/stratagems.py`. Result: Marines get Combat Doctrines + 4 universal
stratagems only; opponents with their full detachment sets out-pace them
on CP. This is a structural gap on the Marines side that REDUCES sim
Marine WR (so fixing it would INCREASE the over-performance gap — but the
right thing is to wire the real stratagems and let the eval rebalance).

**G-AA-3 — Combat Doctrines wound-roll boost is mode/round-correct but
not target-gated.** Real doctrine rule: Devastator (ranged), Tactical
(both), Assault (melee) — applies the wound boost to ALL Astartes
attacks in the matching mode. We model this correctly per units.py.
No gap.

### 3. Strategy AI gap audit

**A-AA-1 — Oath of Moment target picker ignores reanimation /
respawn.** simulator.py:3182 picks the highest-points enemy unit. Against
Necrons, that's almost always a Canoptek Doomstalker (240 pts) — but a
killed Doomstalker doesn't reanimate (it's a VEHICLE/MONSTER, not
Reanimation Protocols), so this is the right pick. The issue is that the
Marine's reroll-everything Oath bonus over-kills the chosen unit, and
spillover damage is wasted while the rest of the Necron army reanimates
chaff. Faction-neutral fix: track "expected reanimation" as a
durability multiplier in target priority — bias toward targets that
won't return. **Faction-neutral** (applies to any opposing reanimation/
sticky-respawn faction; relevant only to Necrons today but generalises).

**A-AA-2 — Marines' Eradicator/Hellblaster squads fire independently.**
Real meta groups Eradicator + Hellblaster fire on a single anvil. Our
strategy picks one target per activation; the resulting damage chunks
into per-unit kills. Faction-neutral focus-fire fix already mentioned in
A-DG-2.

### 4. Ranked fix list (Adeptus Astartes)

| # | Type | Fix | Wahapedia | Scope | Expected Δ MAE |
|---|---|---|---|---|---|
| F-AA-1 | RULE_ADD | Wire the 6 Gladius Task Force detachment stratagems (Adaptive Strategy, Storm of Fire, Honour the Chapter, Only in Death Does Duty End, Armour of Contempt, Bolter Discipline). | https://wahapedia.ru/wh40k10ed/factions/space-marines/#Gladius-Task-Force | medium (6 new stratagem entries + dispatchers) | **+1.0 to +2.0 pt** (increases Marine WR — diagnostic-correct direction once over-perform from other factions is squeezed out) |
| F-AA-2 | AI_IMPROVE | Faction-neutral: Oath of Moment target picker reads opponent's `reanimate_per_round > 0` flag and avoids low-W/high-respawn targets when an unrespawnable VEHICLE/MONSTER is in range. | https://wahapedia.ru/wh40k10ed/factions/space-marines/#Oath-of-Moment | low | **−0.5 to −1.0 pt** (cleaner Marine play vs Necrons specifically) |
| F-AA-3 | AI_IMPROVE | Faction-neutral focus-fire: when a friendly unit just shot a target and didn't kill it, the next friendly activation in this round biases (+1.5x score) toward finishing the same target. | n/a (AI tuning) | medium | **−0.5 to −1.5 pt** |
| F-AA-4 | RULE_FIX | Gladius's "+1 wound roll" doctrine in our sim is round-rotating BUT does not consume CP / is always-on. Real rule: detachment passive (no CP cost). Already correct. No fix needed. | n/a | — | 0.0 pt |

Cumulative: F-AA-1 and F-AA-2 partially cancel (F-AA-1 buffs Marines,
F-AA-2 nerfs vs Necrons). Net delta on MAE ~ −1.0 to −2.0 pt; the better
play is to fix the Cluster A factions and let Marines settle naturally.

---

## Tyranids (+8.1pt)

### 1. Mechanism trace

Tyranids in the 3-opp slice average 52.2% — close to real. Per matchup:
- vs Marines: 43.3% WR — Marines win the model-trade decisively (dmg 67.9
  inflicted / 49.2 dealt; kills 9.0 to 6.1).
- vs T'au: 53.3% WR — Tyranid melee tags T'au gunlines as expected.
- vs Aeldari: 60.0% WR — Aeldari can't break the chaff OC.

The +8.1 headline therefore comes from the unsampled cohort (Orks,
Votann, TSON, Custodes). The root cause is already documented in
`FACTION_T1_TYRANIDS_VANILLA.md`: **OC dominance via Synapse Imperative
auto-pass Battleshock**. Tyranid VP gap +2.6 in this slice; the gap is
likely much larger in unsampled matchups where the opponent has no
ranged DEVASTATING WOUNDS or low Anti-Infantry firepower.

### 2. Wahapedia rule gap audit

**G-TYR-1 — Synapse Imperative auto-pass radius.** Real rule (Wahapedia:
https://wahapedia.ru/wh40k10ed/factions/tyranids/#Synapse) verbatim:
"Each time a Battle-shock test is taken for a TYRANIDS unit while it is
within 6\" of one or more friendly TYRANIDS SYNAPSE units, that Battle-
shock test is automatically passed." We currently auto-pass globally
army-wide (not range-gated to 6"). Effect: Termagant chaff 30" away from
the Hive Tyrant still gets the auto-pass shelter. **The +1.5x SYNAPSE
target priority (S7) can't override this gap because the chaff is too
spread to actually all be in 6" of one Tyrant.**

**G-TYR-2 — Shadow in the Warp scope.** Real rule (Wahapedia:
https://wahapedia.ru/wh40k10ed/factions/tyranids/#Invasion-Fleet) is
ONCE-per-battle at the start of one chosen battle round, all enemy units
take a Battleshock test. We model it as always-on -1 Ld (army-wide).
Already flagged APPROXIMATION in detachments.py:222. Direction-correct
but always-on is far stronger; the always-on -1 Ld effectively battle-
shocks low-Ld bricks every round.

**G-TYR-3 — Endless Multitude / Termagant respawn.** Real rule: when a
TERMAGANT/HORMAGAUNT unit is destroyed, on a 4+ at end of phase it
returns. We don't model this. Direction: would BUFF Tyranids slightly —
not relevant to fixing the over-performance.

### 3. Strategy AI gap audit

**A-TYR-1 — Faction-neutral chaff focus.** Already partly addressed by
S6 `_is_screen_target` (1.4x bonus for OC≥2 + health≤5 / HORDE). The
bonus stacks multiplicatively with S7 Synapse bonus. But against the
seeded Invasion Fleet roster (2× Termagants squads + 1× Hormagaunts +
1× Gargoyles ≈ 40 chaff bodies), the multiplicative bias still doesn't
land enough damage because attackers split fire across MANY chaff
candidates. Faction-neutral fix: when an OC-bearing chaff target is
within first-shot kill-range of a single attacker, lock the attacker
onto that one target (avoid spreading damage across multiple Termagant
squads). **Faction-neutral** — improves all anti-horde play.

**A-TYR-2 — Battleshock checks don't fire on Tyranid chaff.** Because
of G-TYR-1, the per-round simulator BS test never runs on out-of-
Synapse-range Termagants. Fixing G-TYR-1 would enable BS tests to
trigger and lower chaff OC by ~33% per failed test.

### 4. Ranked fix list (Tyranids)

| # | Type | Fix | Wahapedia | Scope | Expected Δ MAE |
|---|---|---|---|---|---|
| F-TYR-1 | RULE_FIX | Gate Synapse Imperative auto-pass to 6" range from a SYNAPSE friendly model. Termagants out-of-range take normal BS tests. | https://wahapedia.ru/wh40k10ed/factions/tyranids/#Synapse | medium (distance check in BS test logic) | **−2.0 to −4.0 pt** |
| F-TYR-2 | RULE_FIX | Replace Shadow in the Warp always-on -1 Ld with a once-per-battle army-wide BS test at the start of round 1. Drop the `enemy_ld_penalty=1` flag. | https://wahapedia.ru/wh40k10ed/factions/tyranids/#Invasion-Fleet | low (flag swap + one BS pulse hook) | **−0.5 to −1.5 pt** |
| F-TYR-3 | AI_IMPROVE | Faction-neutral focus-fire: when a friendly attacker can wipe a single chaff squad in one activation, lock onto it instead of spreading. | n/a (AI tuning) | medium | **−0.5 to −1.5 pt** |
| F-TYR-4 | STAT_FIX | Audit Hive Tyrant + Zoanthropes stats — current `T9 W12` for Hive Tyrant matches BSData; no fix needed. | n/a | — | 0.0 pt |
| F-TYR-5 | RULE_ADD | Endless Multitude (TERMAGANT/HORMAGAUNT respawn 4+). Adding it would buff Tyranids further — DEFERRED. | https://wahapedia.ru/wh40k10ed/factions/tyranids/#Endless-Multitude | high (new mechanic) | +1.0 pt (deferred) |

Cumulative: F-TYR-1 + F-TYR-2 compose multiplicatively (range-gating
Synapse + once-per-battle Shadow). Headline +8.1 → target −3 to −5 pt
reduction = land at +3 to +5.

---

## Necrons (+6.8pt)

### 1. Mechanism trace

Necrons over-perform massively in this slice (87.8% avg WR). Per matchup:
- vs Marines: 80% WR — wins despite Marines doing 85.5 dmg / Necrons 70.4.
  Reanimation: 5.6 revives / battle.
- vs Aeldari: 90% WR — Necrons crush Aeldari OC despite even kill counts (13.3/13.2).
- vs T'au: 93.3% WR — alpha-strikes T'au (R1 dmg 11.9) and snowballs.

Necron stratagems fire heavily per matchup (1.2-1.7 fires / battle each):
- Protocol of the Hungry Void: 37-52 (~1.5/battle, +1 wound roll melee)
- Protocol of the Sudden Storm: 34-36 (~1.2/battle, [ASSAULT] this round)
- Protocol of the Conquering Tyrant: 18 (~0.6/battle, reroll hits shooting)
- Protocol of the Undying Legions: 18 (~0.6/battle, extra reanimation)

That's ~3-4 stratagems per battle from the detachment pool alone, on top of
~3 Command Re-Rolls. Necrons spend 6-10 CP per battle vs the 6-CP cap.

### 2. Wahapedia rule gap audit

**G-NEC-1 — Reanimation Protocols revive count is wrong.** Real 10e RP
(Wahapedia: https://wahapedia.ru/wh40k10ed/factions/necrons/#Reanimation-Protocols)
verbatim: "At the start of your Command phase, this unit's models are
healed and any destroyed models are returned to the unit until that unit
is at Starting Strength. While doing so, you can reanimate a number of
wounds in total up to D3+1 (or 3+D3 if it is a CHARACTER unit). Then if
your army's Faction is NECRONS and that unit is on the battlefield, it
also regains D3 wounds (or 3+D3 if it is a CHARACTER unit)." So real RP
restores wounds, not whole models, and the dice are D3+1 NOT D3.
Our sim caps at 2 (median D3) per profile per round; real meta median
is D3+1 = ~3 wounds = often 1 multi-W model, OR 1-2 single-W models.
For W1 Warriors, our model is roughly correct; for W2 Immortals, real
RP brings back 1 Immortal where ours brings back 2. **Direction-correct,
slight over-reanimation for high-W models.**

**G-NEC-2 — RP fires even when squad lost 0 models this round.** Already
flagged in `FACTION_N1_NECRONS_VANILLA.md` recommendation. The
simulator.py:1846 `_apply_reanimation` compares `initial_count` vs
`alive_now`, but doesn't gate on "models lost THIS round". Result: a
squad that lost models in R1 and survived R2 with no losses STILL revives
D3=2 at R2 end (because alive_now < initial_count). Over multiple
rounds, this drains the dead pool unrealistically.

**G-NEC-3 — Command Protocols always-on `bonus_to_hit_when_led=True`.**
Real rule: "While a NECRONS CHARACTER model is leading this unit, each
time a model in this unit makes an attack, add 1 to the Hit roll." We
gate correctly on leader-led (leaders.py:362). No rule gap.

**G-NEC-4 — Awakened Dynasty stratagem firing rate excessive.** Hungry
Void + Sudden Storm fire ~3x per battle combined. Real meta uses 1-2 of
these per battle (CP economy ceiling 6-8 CP/game). Audit `should_fire_stratagem`
gates for the Necron Protocols.

### 3. Strategy AI gap audit

**A-NEC-1 — Opponents don't downweight Necron defenders for
reanimation.** A T'au Crisis suit shooting a Necron Warrior squad reads
kill-potential 5/5 (T4, W1, 4+ save) but real EV is 5/5 minus 1-2
revives per round = effective 60% efficiency. Faction-neutral fix:
multiply `_durability` by `(1 + reanimate_per_round / wounds_per_model)`
for targets in an army with active Reanimation Protocols. **Faction-
neutral** — generalises to any "respawn / revive" detachment.

**A-NEC-2 — Stratagem firing greed: Hungry Void + Sudden Storm both fire
same Command phase.** simulator.py:687-700 dispatchers walk the
stratagem list and fire any whose trigger green-lights. Real meta picks
ONE Protocol per round (the codex limits each stratagem to once per
phase, not per turn). Faction-neutral fix: in `_try_protocol_*`
dispatchers, gate on "no other detachment stratagem fired this Command
phase". **Faction-neutral** if applied as a generic "at most one
detachment stratagem per Command phase" rule.

### 4. Ranked fix list (Necrons)

| # | Type | Fix | Wahapedia | Scope | Expected Δ MAE |
|---|---|---|---|---|---|
| F-NEC-1 | RULE_FIX | Gate Reanimation Protocols on "squad lost at least one model THIS round". Track `previous_round_alive_count` per profile. | https://wahapedia.ru/wh40k10ed/factions/necrons/#Reanimation-Protocols | medium (new per-round counter in Battle) | **−2.0 to −3.0 pt** |
| F-NEC-2 | AI_IMPROVE | Faction-neutral: `_durability` haircut/boost for targets in armies with `reanimate_per_round > 0` — adds (reanimate_per_round / wounds_per_model) effective HP per round remaining. | https://wahapedia.ru/wh40k10ed/factions/necrons/#Reanimation-Protocols | low | **−1.0 to −2.0 pt** |
| F-NEC-3 | AI_IMPROVE | Faction-neutral: cap detachment stratagem firing at one per Command phase per army. Forces Necron AI to pick Hungry Void OR Sudden Storm, not both. | https://wahapedia.ru/wh40k10ed/the-rules/core-rules/#Command-Phase (general CP economy) | low (one gate in `_apply_stratagems`) | **−1.0 to −2.0 pt** |
| F-NEC-4 | RULE_FIX | Reduce RP revive count from `min(destroyed, 2)` → `min(destroyed, 1)` for W>=2 profiles, keep 2 for W=1. Mirrors D3+1 wounds → 1 multi-W model. | https://wahapedia.ru/wh40k10ed/factions/necrons/#Reanimation-Protocols | low | **−0.5 to −1.0 pt** |
| F-NEC-5 | STAT_FIX | Audit Awakened Dynasty stratagem ctx gates — Hungry Void's "friendly_necrons_unit_about_to_fight" is firing on every fight; tighten to "within engagement AND target has >=2 wounds". | https://wahapedia.ru/wh40k10ed/factions/necrons/#Awakened-Dynasty | low | **−0.5 to −1.0 pt** |

Cumulative: F-NEC-1 and F-NEC-4 compose (both nerf RP); F-NEC-2 and
F-NEC-3 are AI changes that compose orthogonally. Headline +6.8 → target
−5 to −7 pt reduction = land at 0 to +2.

---

## Combined ranked fix list (sorted by expected MAE Δ, highest first)

For the loop's next dispatch step. Each row notes parallelism risk —
which fixes can ship simultaneously without conflict and which need to be
sequenced.

| Rank | Fix | Faction | Type | Scope | Δ MAE | Parallel-safe? |
|---:|---|---|---|---|---|---|
| 1 | **F-DG-1** Restrict DR to DG INFANTRY + flag swap FNP 5+ → -1 damage | DG | RULE_FIX | medium | **−3.0 to −5.0** | YES — units.py only, no overlap with #2-#7 |
| 2 | **F-NEC-1** Gate RP on "lost a model this round" | Necrons | RULE_FIX | medium | **−2.0 to −3.0** | YES — simulator.py:1846 only |
| 3 | **F-TYR-1** Range-gate Synapse Imperative to 6" | Tyranids | RULE_FIX | medium | **−2.0 to −4.0** | YES — units.py + simulator BS pass |
| 4 | **F-DG-2** Contagions of Nurgle 3" R1-R2 / 6" R3+ | DG | RULE_FIX | low | **−1.5 to −2.5** | YES — `_is_near_enemy_dg_model` only |
| 5 | **F-NEC-3** Cap detachment stratagem at 1/Command phase | Necrons | AI_IMPROVE | low | **−1.0 to −2.0** | YES — applies to `_apply_stratagems` flow |
| 6 | **F-NEC-2** Faction-neutral durability haircut for RP targets | Necrons | AI_IMPROVE | low | **−1.0 to −2.0** | YES — strategy.py `_durability` only |
| 7 | **F-DG-3** Faction-neutral durability haircut for FNP defenders | DG | AI_IMPROVE | low | **−1.0 to −2.0** | **CONFLICTS with #6** — both touch `_durability`; merge into single PR |
| 8 | **F-AA-2** OoM picker avoids low-W/high-respawn targets | Marines | AI_IMPROVE | low | **−0.5 to −1.0** | YES — `_pick_oath_target` only |
| 9 | **F-TYR-2** Shadow in the Warp → once-per-battle BS test | Tyranids | RULE_FIX | low | **−0.5 to −1.5** | YES — detachment flag swap |
| 10 | **F-NEC-4** RP revive 1 for W>=2 profiles | Necrons | RULE_FIX | low | **−0.5 to −1.0** | CONFLICTS with #2 (same code path) — sequence after #2 |
| 11 | **F-DG-5** Tighten DG stratagem firing gates | DG | STAT_FIX | low | **−0.5 to −1.5** | YES — strategy.py stratagem gates |
| 12 | **F-TYR-3** Faction-neutral focus-fire on chaff | Tyranids | AI_IMPROVE | medium | **−0.5 to −1.5** | YES — strategy.py target picker |
| 13 | **F-NEC-5** Tighten Hungry Void ctx gate | Necrons | STAT_FIX | low | **−0.5 to −1.0** | YES — strategy.py |
| 14 | **F-DG-4** Worldblight harder BS gate | DG | RULE_ADD | low | **−0.5 to −1.0** | YES — simulator.py only |
| — | F-AA-1 Wire 6 Gladius stratagems | Marines | RULE_ADD | medium | +1.0 to +2.0 | DEFERRED — would worsen MAE before it improves |
| — | F-TYR-5 Endless Multitude | Tyranids | RULE_ADD | high | +1.0 | DEFERRED — would buff Tyranids |

**Top-5 parallel-safe ship list (expected cumulative −7 to −12 MAE pt):**

1. F-DG-1 (DR scope + flag swap) — independent
2. F-NEC-1 (RP this-round gate) — independent
3. F-TYR-1 (Synapse 6" gate) — independent
4. F-DG-2 (Contagions range gate) — independent
5. F-NEC-3 + F-DG-3 + F-NEC-2 — single PR (all touch strategy.py `_durability` + stratagem dispatch caps; merge to avoid conflicts)

These five can ship in **5 parallel agent worktrees** (#1-#4 each
independent; #5 combines three small AI changes into one PR). The
expected combined MAE reduction lands the loop near MAE ≤ 1.5 pt
(baseline 6.72 minus 5-10 pt of compositive reductions, with the caveat
that under-performers — Orks −6.6, Aeldari −4.4 — will need separate
diagnostics to close the bottom half of the gap).

---

## Out of scope

- No code changes were made in this pass (diagnostic only — per task
  constraint).
- No archetype seed changes (per task constraint; per CLAUDE.md the seed
  templates are locked).
- No `overrides.json` edits.
- The under-performer cohort (Orks, Aeldari, T'au) needs a separate
  Cluster B diagnostic — symmetric methodology but different leverage
  (their AI/rule deficits make them lose, not their over-priced units).
