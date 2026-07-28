# Astra Militarum: the infantry never fires its guns

**Date:** 2026-07-25
**Frame:** standing anchor `data/_anchor_sc67a_n80_log.json`. Astra Militarum
33.8 percent against a real 45.3 — residual −11.5, the second-deepest under-pole
after Tyranids (−12.5) and ahead of Emperor's Children (−11.4).
**Instruments (all read-only, all added by this investigation):**
`scripts/_am_unit_audit.py`, `_am_infantry_probe.py`, `_am_target_probe.py`,
`_am_lockout_probe.py`, `_am_intent_probe.py`, `_chaff_sweep.py`.

---

## 1. The observation

A per-unit contribution audit of the built Astra Militarum army, sixteen games
against Genestealer Cults, Adepta Sororitas, Necrons and Death Guard:

| datasheet | points/game | shooting activations | wounds dealt/game | survive to end |
|---|---|---|---|---|
| Cadian Shock Troops | 146 | 46.6 | **0.4** | **3%** |
| Death Korps of Krieg | 49 | 15.9 | **0.0** | **0%** |
| Kasrkin | 28 | 7.4 | 0.2 | 8% |
| Attilan Rough Riders | 30 | 8.8 | 0.1 | 32% |
| — Rogal Dorn Battle Tank | 260 | 4.4 | 27.1 | 75% |

The army's ninety-one wounds a game come almost entirely from five tank
datasheets. Its entire infantry corps — roughly fifty of fifty-seven models, the
army's model count, its Order recipients and the carrier of its army rule —
contributes under one wound a game between them. Death Korps of Krieg dealt
damage on zero of two hundred and fifty-four activations.

That is not dice and it is not a stat error: the profiles are correct (lasgun,
one attack, Strength 3, no armour penetration, damage 1, twenty-four inches,
Rapid Fire 1), and Tempestus Scions firing the same way land damage on 15.7
percent of activations, which is exactly what one Strength 3 shot should do.

## 2. The chain, measured end to end

**Weapon range and line of sight are not the problem.** 74.1 percent of Cadian
Shock Troops activations have a legal target inside weapon range with line of
sight. Only 1.0 percent deal damage.

**Nine tenths of legal shooting never reaches the dice.** Of roughly 358
activations that clear the range and line-of-sight gate, 34 reach `Unit.attack`.

**The lockout is Advance.** Attributing every activation to the first gate in
`Battle._do_shoot` that stops it:

| datasheet | ADVANCED | free to shoot |
|---|---|---|
| Cadian Shock Troops | **82.2%** | 5.4% |
| Death Korps of Krieg | **92.9%** | 6.7% |
| Kasrkin | 53.4% | 39.0% |

Under 10e core rules a unit that Advances cannot make ranged attacks with
non-`[ASSAULT]` weapons. Astra Militarum's infantry Advances nine turns in ten,
so it never shoots.

**The Advance is not reached by the advance-suppression family**, because the
family only applies when `intent in ("CAPTURE", "STEAL")` and the infantry is
not carrying either intent:

| datasheet | SACRIFICIAL | CAPTURE / STEAL |
|---|---|---|
| Cadian Shock Troops | **77.8%** | 15.4% |
| Death Korps of Krieg | **83.9%** | 15.3% |

**The root cause is AI-9, the sacrificial-chaff heuristic**
(`strategy._sacrificial_chaff_target`). It sends any unit under fifteen points
per model that is not standing on an objective into the enemy deployment zone to
score the position secondaries. Every Astra Militarum infantry datasheet
qualifies — Guardsmen and Death Korps at 6.5, Kasrkin at 11.0, Scions at 14.0 —
so the heuristic consumes the whole battleline.

Its one safety gate asks whether a friendly is **already standing** in the enemy
deployment zone. Nothing is standing there for the first several rounds: a Move
6" infantry unit needs four or more rounds to cross a Pariah Nexus table, and
until it lands every other chaff unit passes the same gate and receives the same
intent. The army marches, forfeits its Shooting phase to the Advance, and dies —
three percent and zero percent of the two battleline datasheets survive.

**It is pure waste on the simulator's own scoring table.**
`secondaries.score_position_delta` pays Behind Enemy Lines three victory points
for one unit in the enemy deployment zone and four for two or more. The second
body is worth one point; the third is worth nothing. The simulator commits
roughly half the army.

## 3. Why this is specifically an Astra Militarum defect

The sacrificial-chaff share does **not** correlate with the residual across the
field (Pearson −0.164; Death Guard runs 47 percent chaff and is the biggest
*over*-pole). The share is the wrong measure — what matters is *what* is being
sacrificed:

- Death Guard's chaff is Poxwalkers: no guns, genuinely expendable bodies. Their
  sacrifice costs Death Guard nothing.
- Astra Militarum's chaff **is the army**. Three faction rules pay out only on a
  ranged attack the unit never makes: **Born Soldiers** grants `[LETHAL HITS]`
  to REGIMENT units' ranged attacks; **First Rank, Fire! Second Rank, Fire!** and
  **Take Aim!** are 86 percent of every Order the army issues, with Cadian Shock
  Troops their single largest recipient at 35 percent; and the **Rapid Fire 1**
  lasgun wants to be stationary inside half range.

An army whose army rule, whose Orders and whose weapons all reward standing and
shooting cannot be piloted to Advance nine turns in ten. The Order-economy
finding in `docs/AM_ORDER_COVERAGE_FINDINGS.md` compounds with this one: the
simulator issues shooting buffs to units that then forfeit their Shooting phase.

## 4. The three corrections

All default-off, all byte-identical off (the deterministic twelve-battle
event-log digest is unchanged at `db13417fb7e3b2d47cef9867`), `audit_rules`
clean, `run.py --cli` exits zero individually and combined.

**`SWEG_CHAFF_COMMIT_CAP`** (`code/strategy.py`) — cap the number of units
committed to the enemy deployment zone at `_CHAFF_COMMIT_CAP = 2`, counting
units **en route** and not merely those that have arrived. Two because the
simulator's own Behind Enemy Lines table pays nothing for a third. Faction
neutral: it fires for whoever over-commits.

**`SWEG_AM_INFANTRY_FIRE`** (`code/simulator.py`) — admit Astra Militarum
REGIMENT infantry to the existing advance-suppression family, which the
`rDPA >= 2.0` floor was written to exclude. Distinct from the rejected
`SWEG_ADVANCE_HORIZON`, which moved the generic decision horizon for every
faction and destabilised fifteen of them: this adds one faction-scoped entry
point and leaves the family's downstream can-actually-damage guard in force.

**`SWEG_SQUAD_DAMAGE_FLOOR`** (`code/simulator.py`) — make that guard's 0.5
expected-damage floor squad-aware. The simulator stores one `Unit` instance per
model, so the guard measured one model's shooting against a floor calibrated for
single-model platforms: twenty Cadian Shock Troops into Poxwalkers is 3.33
expected wounds, but each model computes 0.167 and fails, so **no multi-model
squad in the catalogue can ever pass it**. In the rules a shooting activation
belongs to the codex unit, so the codex unit is the right unit of account.
Single-model platforms have a squad of one and are byte-identical either way.

## 5. Measured effect (behavioural, not yet win-rate)

| | off | all three on |
|---|---|---|
| Cadian Shock Troops SACRIFICIAL intent | 77.8% | **9.8%** |
| Death Korps SACRIFICIAL intent | 83.9% | **2.5%** |
| Cadian Shock Troops ADVANCED | 82.2% | **24.5%** |
| Death Korps ADVANCED | 92.9% | **26.8%** |
| Cadian Shock Troops wounds/game | 0.4 | **8.4** |
| Death Korps wounds/game | 0.0 | **1.5** |
| Cadian Shock Troops wounds per 100 points | 0.26 | **5.73** |
| army wounds/game | 91.0 | **98.9** |

Survival barely moves (3 → 6 percent) — the infantry still dies, it now shoots
first, which is the faithful behaviour.

## 6. Status

**First win-rate verdict is in, and it is decisive.** A matchup-scoped N=80 arm
over Astra Militarum's row and column carrying `SWEG_AM_INFANTRY_FIRE` together
with `SWEG_ORDER_AURA_BASEEDGE`, joined by `paired_delta --scoped` against
`data/_anchor_sc67a_n80_log.json`:

```
Astra Militarum   33.8 -> 37.6   pairedD +3.76   ci95 3.14   334 flips   UP*
gated mean absolute error: OFF 2.76 -> ON 2.56  (-0.20)
```

Every other faction flat. This is a **lower bound on the package**: that arm
carried neither `SWEG_SQUAD_DAMAGE_FLOOR` (without which the advance-suppression
guard still rejects every multi-model squad) nor `SWEG_CHAFF_COMMIT_CAP` (the
gate that actually collapses SACRIFICIAL intent from 77.8 to 9.8 percent and
takes Cadian Shock Troops from 0.4 to 8.4 wounds a game). Both are faction
neutral, so they cannot be matchup-scoped and need the full matrix; that arm —
all four gates together — is running.

Nothing is committed.

### Victory-point validation (the trade the win rate would hide)

The chaff cap stops the army throwing bodies at the enemy deployment zone, which
is precisely what the position secondaries reward — so the package could have
bought shooting with victory points. It did not. Same twelve games (Astra
Militarum's four hardest matchups), all four gates off versus on:

| | off | on |
|---|---|---|
| Astra Militarum victory points | 31.2 | **33.8** |
| — secondary | 7.3 | **8.2** |
| — primary | 23.9 | **25.6** |
| opponent victory points | 54.0 | **51.8** |
| margin | −22.8 | **−18.0** |

Both halves of the ledger move the right way. (The win rate in that sample went
16.7 → 8.3 percent, but that is two wins versus one in twelve games of the worst
cells — not readable; the margin is the signal at this N.)

### First full-matrix screen — the lift is real, the first cap was buggy

All four gates, N=80 full matrix, paired against `sc67a`:

```
Astra Militarum   33.8 -> 38.7   pairedD +4.93   ci95 4.03   UP*
gated mean absolute error: OFF 2.76 -> ON 3.11  (+0.35, WORSE)
```

The target moved further than any lever in the campaign's history on this pole,
but the frame got worse, and the collateral named the cause: **Tyranids −6.39,
Adeptus Mechanicus −4.43, Adepta Sororitas −4.01, Genestealer Cults −3.38** —
the horde and chaff-heavy factions, whose deployment-zone push is correct play.

The cause was a defect in `SWEG_CHAFF_COMMIT_CAP` itself, and it is the very trap
this document diagnoses elsewhere: `friendly_alive` holds one `Unit` instance per
physical MODEL, so counting it directly capped each army at two **models** — a
fraction of a single squad — while Behind Enemy Lines scores for a **unit** in
the enemy deployment zone. Every horde faction had its position secondaries
strangled.

Corrected to count distinct `squad_id` groups, with a committed squad allowed to
keep going so the first model of a squad cannot claim the slot and turn the rest
of its own models back. Chaff share after the correction is reduced rather than
strangled (Tyranids 50.8 → 18.7 percent of move decisions, against 50.8 → far
lower before). Re-screen running.

### Corrected-cap re-screen — the best frame of the investigation

All four gates with the squad-counted cap, N=80 full matrix, paired against
`sc67a` (`data/_scr_ampkg2_log.json`):

```
gated mean absolute error:  OFF 2.76  ->  ON 2.51   (-0.25)
Astra Militarum   33.8 -> 37.6   +3.82  UP*
Aeldari           51.8 -> 48.5   -3.31  DOWN*   toward real 41.5
Adeptus Astartes  48.7 -> 51.1   +2.40  UP*     away from real 47.0
```

The collateral is gone: Tyranids −6.39 → −1.78, Adeptus Mechanicus −4.43 →
−0.68, Adepta Sororitas −4.01 → −1.49, Genestealer Cults −3.38 → +0.05,
Emperor's Children −2.39 → +0.73, all inside noise. **The model-versus-codex-unit
defect owned essentially all of it.**

THE DECOMPOSITION THIS HANDS US FOR FREE. The scoped pair alone gave Astra
Militarum +3.76 at gated 2.56; all four gates give +3.82 at gated 2.51. So:

* the Astra Militarum lift is **almost entirely** `SWEG_ORDER_AURA_BASEEDGE` +
  `SWEG_AM_INFANTRY_FIRE` (+3.76 of +3.82);
* the two faction-neutral gates contribute ~nothing to Astra Militarum (+0.06)
  and instead move OTHER factions — Aeldari 3.31 toward real, Adeptus Astartes
  2.40 away — netting −0.05 on the frame.

That splits the recommendation cleanly. The scoped pair is the Astra Militarum
fix and is worth adopting on its own evidence. The faction-neutral pair is a
separate, smaller, cross-cutting question that happens to help the frame; it
should stand or fall on its own screen, not ride the Astra Militarum result.

### Collateral attribution is NOT clean — do not assume the chaff cap owns it (superseded)

*Superseded by the re-screen above: after the model-versus-codex-unit correction
the collateral vanished, so the cap did own it. The reasoning below is kept
because the caution was correct at the time — the evidence then available did not
support the attribution, and acting on it would have meant scoping or discarding
a gate that turned out to be sound.*

Correlating each faction's sacrificial-chaff share against its delta in the first
full-matrix package screen (Astra Militarum excluded) gives a Pearson correlation
of only **−0.280**. The decisive counter-example: **Emperor's Children −2.39 on a
0.0 percent chaff share** — the cap cannot have touched it, and neither can
`SWEG_SQUAD_DAMAGE_FLOOR`, because none of the advance-suppression entry gates is
default-on for Emperor's Children, so that whole block is skipped for them.

Two honest explanations for the residue, neither yet separated:

* **second-order** — a faction's win rate moves because its OPPONENTS' piloting
  changed, not its own (Astra Militarum plays better, so everyone loses their
  Astra Militarum cell; Tyranids plays worse, so everyone gains theirs);
* **multiple comparisons** — at 95 percent confidence across 22 factions one or
  two spurious decisive calls are expected, and Emperor's Children was marginal
  (−2.39 against a 2.20 interval).

The only way to settle it is the decomposition below. Do not scope or discard a
gate on this evidence.

### RESOLVED — the probe defect was the missing side roll-off, and the fixed
### answer is that primary and secondary are EQUAL halves

`SWEG_SIDE_ROLLOFF` is **default-on** in `scripts/evaluate_vs_meta.py`: it flips
which faction occupies slot A on a per-game coin flip keyed on `pair_seed ^
0x51DE` and re-orients the winner, so every evaluated cell is a both-sides
average. `scripts/_am_vp_probe.py` always built Astra Militarum as slot A, so it
measured a one-sided frame. Seeds, map rotation and mission selection were
already identical — the roll-off was the whole discrepancy.

With the roll-off implemented the probe reproduces the frame: package-off Astra
Militarum reads **35.7 percent over 42 games against the anchor's 33.8** — inside
noise. The instrument is now trustworthy.

**The corrected decomposition (fair spread, all twenty-one opponents, package
off):**

| | Astra Militarum | opponent | deficit |
|---|---|---|---|
| primary | 29.3 | 34.9 | **5.6** |
| secondary | 8.9 | 14.2 | **5.3** |
| total | 38.2 | 49.1 | 10.9 |

**Primary and secondary are essentially EQUAL halves of the remaining gap.** Both
of this document's earlier claims were wrong and are retracted: "the deficit is
primary, not secondary" was an artefact of the one-sided frame, and the "17.6
primary deficit" was an artefact of sampling only the four worst matchups. The
earlier sessions' focus on the secondary economy was not misplaced — it was half
the story, and the primary half is the part that was never separately measured.

### Superseded: the probe does not reproduce the evaluation frame

Re-running the decomposition across a FAIR spread (all twenty-one opponents, one
seed each) instead of the four worst cells:

| | package off | package on |
|---|---|---|
| Astra Militarum primary | 35.6 | 32.9 |
| Astra Militarum secondary | 8.5 | 9.5 |
| opponent primary | 37.1 | 39.6 |
| opponent secondary | 13.0 | 14.0 |
| probe win rate | 42.9% | 33.3% |

Two things fall out, both of which qualify the section below.

**1. The primary deficit is 6.7, not 17.6.** On a fair spread primary is 32.9
against 39.6 and secondary 9.5 against 14.0. Primary remains the larger channel
but by a modest margin, not "more than double". The 17.6 figure was an artefact
of sampling Astra Militarum's four worst matchups.

**2. The probe does not reproduce the evaluation's world, so its absolute numbers
are not calibrated.** Its package-off baseline win rate is 42.9 percent where the
`sc67a` anchor puts Astra Militarum at 33.8 percent. Same faction, same nominal
2000 points, wildly different rate — so `scripts/_am_vp_probe.py` is building a
different distribution of games than `scripts/evaluate_vs_meta.py` (orientation
handling and the seed schedule are the likely divergence). Its probe-level win
rate also moved the OPPOSITE way to the authoritative N=80 paired screen
(42.9 → 33.3 here against 33.8 → 37.6 there), which at twenty-one games is
simply noise — nine wins versus seven.

**Standing rule from this: the paired N=80 screens are the verdict. Every
victory-point figure in this document is indicative of CHANNEL (is the gap in
primary or secondary?), never of magnitude, and never of direction at these
sample sizes.** The same caution retroactively applies to the twelve-game
"margin improved 4.8" figure recorded earlier.

### The next thread: the remaining deficit is PRIMARY, not secondary (magnitudes superseded above)

With the package on, the victory-point ledger splits like this (twelve games):

| | Astra Militarum | opponent |
|---|---|---|
| primary | **23.2** | **40.8** |
| secondary | 7.6 | 15.4 |
| total | 30.8 | 56.2 |

The primary deficit is 17.6 points a game, more than double the secondary gap —
so the secondary economy, which every previous investigation treated as the
Astra Militarum problem, is the SMALLER half.

**Caveat, and it matters: these twelve games are Genestealer Cults, Adepta
Sororitas, Necrons and Death Guard — three of Astra Militarum's four worst cells,
chosen while hunting the damage defect.** This is the deficit in its hardest
matchups, not its average one. Re-measure across a fair opponent spread before
sizing anything from it.

Ruled out already as the cause:

* **Objective control values are correct.** Cadian Shock Troops and Death Korps
  read OC 2, matching 10e, and the army's total starting objective control is
  111 — the HIGHEST of those four opponents (Necrons 110, Sororitas 102, and
  Genestealer Cults 122 from 87 models). Astra Militarum does not start short.
* **The Cadian sticky objective is live**, not dead code: all twenty Cadian Shock
  Troops models carry `sticky_objective`, and 0.67 sticky markers a game are
  still held by Astra Militarum at the end of the battle.

So the objective control is present at deployment and dies. Infantry survival to
end of battle is 3 percent before the package and 6 percent after — the package
makes the infantry shoot, it does not make it live. Whether that is a faithful
consequence of Toughness 3 bodies or the durability over-reward seen from the
under-pole side is the open question, and it is the same wall the Death Guard
investigation hit from the opposite direction.

### Target economics REJECTED on the new frame (task #23) — hypothesis falsified

The pre-flight argument was that `SWEG_TARGET_ECONOMICS`'s held verdict
("recovers only 1 game in 40") was measured on a frame where Astra Militarum's
infantry never fired, so a target-CHOICE gate had nothing to redirect. That
argument was legitimate under the lever-protocol family pre-flight, and it is
empirically WRONG. Screened on top of the package, paired against
`data/_scr_ampkg2_log.json`:

```
gated mean absolute error:  2.51 -> 2.90   (+0.40, WORSE)
Astra Militarum   37.6 -> 36.8   -0.80  flat — no benefit whatsoever
Aeldari +2.58 UP (over-pole further away); Tyranids -1.87, Orks -1.76,
T'au -1.73, Chaos Daemons -1.35 (under-poles deeper)
```

With the infantry now firing, target economics still does nothing for Astra
Militarum. The original held verdict stands, re-confirmed on a better frame.

### The package does NOT trade objective control for shooting

A real risk in `SWEG_AM_INFANTRY_FIRE`: a suppressed Advance is a shorter move,
so the infantry could reach objectives later and give back in primary what it
gains in shooting. Measured with the existing read-only over-score instrument
(`SWEG_OVERSCORE_INSTR`), fair spread, side roll-off applied:

| | package off | package on |
|---|---|---|
| Astra Militarum objective markers won / game | 13.07 | 12.71 |
| share of all markers won | 44.1% | 43.9% |

Unchanged within noise — the infantry keeps its markers AND gains its shooting.

Incidental finding worth its own thread: **84 percent of Astra Militarum's marker
wins are UNCONTESTED** (mean winning objective control 6.2 against a loser's
0.4). It wins the markers nobody stands on and loses the contested ones — the
same bodies-die root cause, seen from the primary side.

### DECOMPOSITION COMPLETE — the measuring bug carries 87 percent of the lift

| configuration | Astra Militarum | gated mean absolute error | arm log |
|---|---|---|---|
| anchor `sc67a` | 33.8 | 2.76 | — |
| `SWEG_ORDER_AURA_BASEEDGE` **alone** (scoped) | **37.1  (+3.33)** | 2.59 | `_scr_auraonly_log.json` |
| + `SWEG_AM_INFANTRY_FIRE` (scoped) | 37.6  (+3.76) | 2.56 | `_scr_amfire_scoped_log.json` |
| + `SWEG_CHAFF_COMMIT_CAP` + `SWEG_SQUAD_DAMAGE_FLOOR` (full) | 37.6  (+3.82) | **2.51** | `_scr_ampkg2_log.json` |

Marginal contributions to Astra Militarum: **order aura +3.33**, infantry fire
+0.43, the faction-neutral pair +0.06 (their real contribution is elsewhere —
Aeldari 3.31 toward real, Adeptus Astartes 2.40 away, netting −0.05 on the frame).

**The single largest contributor is the measuring defect, not any piloting
heuristic.** Correcting one range test from centre-to-centre to base-edge — the
10e core rule this repository already cites in
`data/rule_citations.d/keywords_and_mechanics.json` and already applies to
Engagement Range and objective control — is 87 percent of the whole result. The
three behavioural gates together supply the remaining 13 percent.

### The remaining gap, investigated — four hypotheses tested, three falsified

**Secondary half is dominated by one card.** Per-card decomposition
(`scripts/_am_secondary_cards.py`, fair spread, side roll-off applied):

| card | Astra Militarum/game | opponents/game | gap |
|---|---|---|---|
| **assassination** | 0.24 | 3.14 | **+2.90** |
| bring_it_down | 0.57 | 1.86 | +1.29 |
| secure_no_mans_land | 0.90 | 1.57 | +0.67 |

Assassination alone is ~55 percent of the 5.3-point secondary deficit. Astra
Militarum out-scores its opponents on a_tempting_target, establish_locus and
overwhelming_force, so the deficit is concentrated, not general.

**FALSIFIED — "Astra Militarum wins only uncontested markers."** Its
contested-win share is 18 percent, dead middle of a 7-to-27 percent field. Not an
anomaly; winning markers uncontested is how the simulator plays for everyone.

**PARTIAL — marker control explains some of the residual structure, not most.**
Across all 22 factions, correlation(markers won per game, residual) = **+0.463**
and correlation(contested-win share, residual) = **−0.384** — real but moderate
(~21 percent of variance), with hard outliers (Tyranids wins an above-median
15.83 markers a game and is still −12.5). Do not treat marker control as the
master key.

**FALSIFIED — "Astra Militarum's infantry dies too fast."** Cheap Toughness 3
infantry death rates: **Astra Militarum 92 percent, Adepta Sororitas 97 percent,
Genestealer Cults 99 percent.** Astra Militarum's bodyguards actually survive
BETTER than two near-target factions. Cheap infantry evaporating is universal in
this simulator and is not an Astra Militarum defect.

**FALSIFIED (pre-empted) — "a 5-model Cadian Command Squad scores Assassination
once per MODEL."** That is exactly the one-Unit-per-model trap this document
found twice elsewhere, but prior work already fixed it:
`SWEG_SECONDARY_PER_UNIT` is default-on (adopted 2026-07-13) and a CHARACTER unit
counts as destroyed only when all its models die.

**WHAT SURVIVES.** Leader attachment is working — Astra Militarum characters are
attached at **99 percent**, HIGHER than opponents' 75 percent. Yet they die at
**61 percent against 17 percent**, on comparable bodyguard attrition. Attachment
protects a character only while its host squad keeps a living bodyguard, so the
protection lapses; but since the bodyguard death rate is not anomalous, the
distinguishing factor must be elsewhere.

The standing candidate, unbuilt and unscreened: **Astra Militarum's characters
are the only ones in the game under a POSITIONAL OBLIGATION.** Voice of Command
requires an Officer within 6 inches of the unit it orders, so
`SWEG_OFFICER_FOLLOW` (and the coverage hook) pull them toward the firing line,
where other factions' characters are free to sit back. That is a real tension in
10e as well — but a real Guard player answers it by standing the Officer at the
FAR edge of its aura, behind the squad and out of line of sight, rather than at
the squad's centroid. A "safe end of the aura" refinement to
`_maybe_officer_coverage` is the natural next lever; it is NOT built.

### SWEG_OFFICER_STANDOFF — built, cited, HELD (fails its behavioural bar)

Order from the back of the aura instead of the squad's centroid, taking the
largest backward step that still keeps every ordered model in range. Measured
over eighteen games on top of the package:

| | standoff off | standoff on |
|---|---|---|
| Astra Militarum character death rate | 57% | 58% |
| Orders issued per round | 4.01 | 4.19 |

**No survival benefit.** The reason is structural: `SWEG_OFFICER_FOLLOW` only
fires on the DRIFT case (Officer already outside the aura), so most activations
never reach the standoff at all, and the Officers die from being near the front
generally rather than from the follow hook's specific target. Held default-off;
it does not earn a screen slot.

**The session's pattern is now unambiguous: four piloting heuristics
(`SWEG_OFFICER_COVERAGE`, `SWEG_OFFICER_STANDOFF`, and the two faction-neutral
gates on their own Astra Militarum contribution) are marginal or inert, against
ONE measuring fix worth +3.33.** Look for measurement defects, not better play.

### Decomposition still owed (remaining)

The package has four gates and only one paired arm so far. Owed, each against the
package-on arm rather than `sc67a` so the marginal contribution is isolated:

1. `SWEG_CHAFF_COMMIT_CAP` alone — faction-neutral, the largest behavioural
   mover, and the one with cross-faction risk (T'au 56.5 percent of move
   decisions SACRIFICIAL, Tyranids 50.8, Death Guard 47.0). Needs the full matrix.
2. `SWEG_ORDER_AURA_BASEEDGE` versus `SWEG_AM_INFANTRY_FIRE` — the +3.76 scoped
   arm carried both and did not separate them.
3. `SWEG_SQUAD_DAMAGE_FLOOR` alone — it admits multi-model squads to the
   advance-suppression family for *every* faction, so it is not scopeable.

### Evaluation execution note

Two full-matrix runs launched as harness background tasks were killed with no
artifacts. Evaluations must be launched **detached** (PowerShell `Start-Process`
with redirected output) with a separate background waiter armed on the output
file; the scoped arm completed cleanly that way.

Registered alongside, from the same measuring-rule family and not folded in:
weapon range eligibility and the Rapid Fire / Melta half-range trigger are also
measured centre-to-centre rather than base-edge, costing Death Guard 18.6 percent
and Adeptus Astartes 15.9 percent of their in-range target pairs against Astra
Militarum's 9.5 — faithful to fix, but it favours the over-poles, so it needs its
own screen (`scripts/_range_measure_probe.py`).
