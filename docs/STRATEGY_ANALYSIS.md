# Strategy AI Analysis — IRL Top-Faction Play vs SwegHammer Code

Compared the strategic patterns used by top 10e tournament factions (May 2025
meta) against `code/strategy.py`. Output: gap list + prioritised pickup
list of AI improvements.

## Meta context (May 2025)

Top performers per Goonhammer / Stat Check / Bell of Lost Souls:
- **Deathwatch** ~63% WR (combined-arms gunline + alpha-strike)
- **Thousand Sons** ~62% WR (psychic mortal-wound spam + Rubric durability)
- **Custodes** A-tier (elite control via Shield Host)
- **Necrons** A-tier (Awakened Dynasty objective grind)
- **Death Guard** mid-tier solid (attrition + Plague Marine sticky-hold)
- **Aeldari** variable (Battle Host / Saim-Hann / Aspect Host all see play)
- **T'au** Mont'ka / Retaliation Cadre — alpha-strike gunline

## IRL strategic patterns per top faction

### Necrons (Awakened Dynasty)
- **Game plan**: hold midfield. Reanimation Protocols turns the army into
  an attrition sponge that out-trades any matchup over 5 rounds.
- **Unit roles**: Lokhust Heavy Destroyers backline anti-tank gunline;
  Necron Warriors / Immortals on objectives soaking Reanimation rolls;
  Triarch Praetorians / Lychguard counter-charge; Doomsday Ark indirect
  fire pressure.
- **Tempo**: T1 set up midfield (Scarabs screen, Lokhusts hide in cover).
  T2-T3 damage trades with Reanimation refilling. T4-T5 the army has
  more bodies than the opponent — primary VP gap widens.
- **Anti-pattern**: leaving Reanimation Pool exhausted by spreading thin
  too early.

### T'au Empire (Mont'ka)
- **Game plan**: alpha-strike T2 — drop reserves Crisis Suits + Stealth
  Suits onto an objective + the opposing gunline, delete the highest
  threat in one shooting phase.
- **Unit roles**: Crisis Sunforge for anti-tank, Fireknife for elite
  infantry; Riptide as anchor + DPS; Pathfinders for Markerlights +
  objective contest; Stealth Suits for late flanking; Devilfish for
  Pathfinder delivery.
- **Tempo**: T1 Markerlights stack to T2 alpha strike. T2 alpha. T3
  consolidate primary. T4-T5 reposition for objective secondaries.
- **Anti-pattern**: getting stuck in melee — every T'au unit that's
  engaged misses a shooting phase.

### Aeldari (Battle Host / Saim-Hann)
- **Game plan**: shimmy-step — Move-Shoot-Move, never sit still.
  Battle Focus tokens convert ADVANCE into shoot-after-advance, so
  threat range is M + d6 + range every turn.
- **Unit roles**: Falcon / Fire Prism / Wave Serpent for mobile DPS;
  Wraithguard for objective anchor (D-cannons delete tanks); Striking
  Scorpions for Infiltrator pressure; Howling Banshees for melee
  alpha; Warlocks for psychic + auras.
- **Tempo**: T1 reposition into firing lanes; T2-T4 trade DPS while
  rotating between objectives via mobility; T5 contest enemy home
  objective with reserved Scorpions / Banshees.
- **Anti-pattern**: holding position. Aeldari MUST move every turn or
  they're trading 1-for-1 with armies that have more bodies.

### Custodes (Shield Host)
- **Game plan**: elite control. Few units, each so durable that the
  enemy can't focus-fire them off objectives.
- **Unit roles**: Custodian Guard / Wardens hold objectives (T6 W3
  Sv2+ Inv4+ = absurd EHP); Caladius Grav-tank backline anti-tank;
  Telemon Dreadnought as monster brick; Allarus Custodians deep-strike
  late-game objective steal; Sky Talons as transport.
- **Tempo**: T1 set up the centre. T2-T4 grind on objectives. T5
  Allarus drop on enemy home objective for the secondary points.
- **Anti-pattern**: spreading thin. Every Custodes unit is a focus-fire
  target; isolated units die.

### Death Guard (Plague Company)
- **Game plan**: attrition + screen. Plague Marines stick to objectives
  with FNP 5+ + Disgustingly Resilient. Contagion aura forces enemy
  units to engage at -1 Toughness.
- **Unit roles**: Plague Marines on every objective (10-model squads
  cost ~135pt and are nearly unkillable); Plagueburst Crawlers indirect
  fire; Mortarion as MVP melee; Lord of Contagion / Plague Surgeon
  characters for Lethal Hits + Reanimation-like wound returning.
- **Tempo**: T1-T2 spread Plague Marines onto every objective. T2-T4
  trade in melee where Contagion bites. T5 Plague Marines are still
  alive thanks to FNP 5+ — outscore opponent on primary.
- **Anti-pattern**: leaving objectives to hunt; slow movement means
  abandoned objectives don't come back.

### Thousand Sons (Cult of Magic / Cabal of Sorcerers)
- **Game plan**: psychic mortal-wound spam + Rubric durability. All Is
  Dust (-1 to wound vs D1) makes Rubric Marines tank chip damage on
  objectives.
- **Unit roles**: Rubric Marines / Scarab Occult Terminators sticky-hold;
  Magnus / Ahriman / Infernal Master as psychic engines for Doombolt
  (mortal wound spam) + Twist of Fate (Lethal Hits buff); Tzaangors
  as cheap screens; Cabal Points fuel stratagems.
- **Tempo**: T1-T2 build Cabal Points + cast Doombolt to chip enemy
  threats. T3-T4 leverage stratagems for Lethal Hits volleys. T5 Rubrics
  alive on objectives = primary VP.
- **Anti-pattern**: running out of Cabal Points → no stratagems →
  Rubrics get out-traded.

### Tyranids (Invasion Fleet / Crusher Stampede)
- **Game plan**: mass alpha. Termagant flood for OC and battleshock
  immunity (Synapse auto-pass). Big monsters charge into key targets.
- **Unit roles**: Termagants / Hormagaunts for OC; Genestealers /
  Tyranid Warriors melee; Carnifexes / Hive Tyrants as monster
  pressure; Synapse units (Tyranid Prime, Maleceptor) coordinate
  battleshock.
- **Tempo**: T1 advance everything; T2 alpha strike with monsters +
  Genestealers; T3-T5 outscore via OC swarm.
- **Anti-pattern**: spreading Synapse coverage too thin (units far from
  SYNAPSE units lose battleshock auto-pass).

### Orks (Bully Boyz / Green Tide)
- **Game plan**: horde alpha via WAAAGH! Mass Boyz charge with +1 to
  wound melee for one turn.
- **Unit roles**: Boyz mob (30 models) charge; Trukks / Battlewagons
  deliver melee; Stormboyz / Squighog Boyz for fast objective contest;
  Mek + Warboss for re-rolls + WAAAGH! call.
- **Tempo**: T1 advance everything; T2 declare WAAAGH! and charge
  everywhere; T3-T5 mop up with Mob Rule keeping units in the fight.

## Our AI today (`code/strategy.py`)

| Component | What we model |
|---|---|
| Intent types | HOLD / CAPTURE / STEAL / ENGAGE / REPOSITION / FALL_BACK |
| Objective scoring | `STEAL > CAPTURE > already-scoring`, distance-weighted |
| Role bias | SHOOTY/HEAVY hold in range; MELEE close; DUAL evaluate charge threat |
| Charge target selection | kill_potential + 0.5*ranged_value, threat_against penalty, charge_p multiplier, gunline bonus |
| Wounded retreat | Below-half-HP HORDE/SUPPORT seek obscuring terrain |
| Fall Back | SHOOTY/HEAVY pinned in engagement disengage if a clear destination exists |
| Battle Focus | ASURYANI units bias toward advance when out of range AND tokens available |
| Doctrina | AdMech round-based imperative pick |

## Gaps — what good IRL play does that we don't

### Gap 1 — No faction strategic identity
Our AI applies the same heuristic regardless of detachment. Custodes
should be playing "elite control" not "horde push", Aeldari should
shimmy-step not hold in range, Necrons should be deeply objective-focused.
We treat them all the same role-by-role.

### Gap 2 — No coordinated army-level plan
Each unit picks its activation independently. There's no "army strategy"
deciding "this round we push left", so a 3-unit alpha strike never
materialises — units arrive sequentially.

### Gap 3 — Round-aware tempo missing
We have flat objective scoring across rounds. Real play heavily weights
the FINAL TWO rounds for primary swing (T5 stays-on-objective is worth
2x T2 stays-on-objective). We don't bias.

### Gap 4 — Aeldari shimmy-step not modelled
SHOOTY/HEAVY units in range REPOSITION (nearby cover). Aeldari units
should actively pick a NEW shooting lane each turn — angle of attack,
LoS-block, new flank. We hold them in place.

### Gap 5 — Threat prioritisation ignores support roles
Our charge target scoring is kill_potential / threat ratio. We don't
recognise "kill the leader / buff aura first" — taking out a 95-point
Captain may be worth more than killing 100 points of regular squads.

### Gap 6 — Stratagem timing is reactive, not planned
Stratagems fire on simple triggers. Top players RESERVE CP for known-
to-be-pivotal turns (Counter-Offensive on the alpha-strike turn, +1 to
wound on the WAAAGH! turn). We have no concept of "save CP for later".

### Gap 7 — Screen / bodyguard placement
HORDE units should physically sit between enemies and high-value
friendlies to absorb fire. Our AI moves them toward objectives, not
into bodyguard positions.

### Gap 8 — Deepstrike massing now ✓ (#153 shipped) but no "drop on the
weak flank" detection
The new deepstrike AI clusters mass-drops but picks targets by
threat-DPA, not by flank weakness. Real play drops on the side with
fewest screens.

### Gap 9 — Pre-game deployment patterns
We deploy with a simple algorithm. Top players have detachment-specific
deployment doctrine (Necrons: Lokhusts in cover; T'au: Crisis in
reserves; Aeldari: Wraithguard mid; Custodes: bunker centre).

### Gap 10 — Hammer-and-anvil missing
Real lists deliberately commit melee to one flank and shooting to the
other, forcing the enemy to defend both. Our AI doesn't have flank
awareness.

## Prioritised improvements (pickup list)

| # | Improvement | Effort | Expected MAE impact |
|---|---|---|---|
| **S1** | Faction strategic-posture flag | M | high — every faction calibrates differently |
| **S2** | Round-weighted objective scoring | S | medium-high |
| **S3** | Coordinated activation order (army-level plan per round) | L | high but complex |
| **S4** | Threat-priority bonus for SUPPORT / leader targets | S | medium |
| **S5** | Aeldari shimmy-step (active reposition for shooty mobile units) | M | medium |
| **S6** | Stratagem CP reservation by predicted-pivotal-turn | M | medium |
| **S7** | Screen / bodyguard role bias for HORDE | S | low-medium |
| **S8** | Pre-game deployment patterns per detachment | L | medium |
| **S9** | Flank-awareness for deepstrike + charge target selection | M | medium |

## Recommended next-sprint pickup

1. **S2 (round-weighted scoring)** — small change, large impact. Multiplies
   objective `value` by `1 + 0.2*(round-1)` or similar so late-game
   objective contests dominate.

2. **S4 (support-target priority)** — small change to `_melee_target_score`
   that adds `+30%` for SUPPORT-role units (leaders, buff characters,
   psykers). Real play kills the buff aura first; we don't.

3. **S1 (faction posture)** — add a `STRATEGIC_POSTURE` dict keyed by
   faction (alpha_strike / attrition / objective_hold / horde_push) that
   feeds `pick_move_intent` to bias differently per army. Start with the
   biggest meta divergences.

4. **S5 (Aeldari shimmy)** — small, faction-specific, fixes a known
   eval miss (Aeldari currently +14 over real because they sit still).

5. **S6 (stratagem reservation)** — modify stratagem AI to hold CP
   until the right turn rather than spending on first eligible trigger.

S3 (coordinated activation) is the biggest IRL gap but also the biggest
implementation lift — defer until S1+S2+S5 prove out the simpler ideas.
