# 10th-edition core-rules implementation audit (2026-05-31)

> Supersedes the earlier stale version (HEAD `945c840`), whose "MISSING" items
> (Death Guard Feel No Pain, All Is Dust, Deadly Demise, Fall Back, Look Out Sir)
> have all since been implemented, and which wrongly listed Heroic Intervention
> and the 3-start/6-cap Command Point economy as correct.

Rule-first audit: every rule in the Warhammer 40,000 10th-edition Core Rules table
of contents (Wahapedia, fetched 2026-05-31) was checked **into** the simulator —
so completely-missing rules are caught, not just the ones the code happens to show.
Six parallel read-only verifiers each owned a section; every BUG / MISSING /
FABRICATION below was then personally re-read in the code before being recorded.

Verdict key: **PASS** (correct) · **APPROX** (deliberate simplification, acceptable)
· **BUG** (wrong vs the rule) · **MISSING** (rule absent) · **FABRICATION** (sim
implements something with no rules basis).

Files: `code/simulator.py` (phase engine), `code/units.py` (`Unit.attack`,
`receive_damage`), `code/map.py` (terrain/LoS), `code/army.py`, `code/leaders.py`.

---

## TOP PRIORITY — actionable findings (verified personally)

> **Resolution status (wave 68, 2026-05-31):** findings #1-6, #9, #10 are FIXED
> (rules-correct). #7 (Command Point economy) left pending live mission-pack
> verification; #8 (movement coherency) deferred to its own wave. See the
> wave-68 close in `docs/AUTO_LOOP_LOG.md`.

### 1. Heroic Intervention is a FABRICATION — `simulator.py:8047` `_do_heroic_intervention` — **FIXED (removed)**
10th edition has **no** universal Heroic Intervention rule (it was removed from 9e).
The method's docstring cites the Wahapedia Charge-phase page and quotes 9e wording;
the page contains no such rule. It fires **free, automatically, for every defending
CHARACTER within 6″ of a charger** (`_do_charge` calls it), giving a free 6″ (3″
WALKER) move into engagement. This systematically over-rates every army that runs
melee Characters (Custodes, Space Marines, Chaos, Daemons, Tyranids…). **Fix: delete
it** (or gate to the handful of datasheets that have a *named* Heroic Intervention
ability + cite each). Same class as the AURIC_CHAMPIONS fabrication removed in wave 62.

### 2. Fall Back always rolls Desperate Escape — `simulator.py:6342`
The test fires on **every** Fall Back for non-TITANIC/non-FLY units, destroying a
model on a 1-2 (~1/3 of the time). The 10e rule only requires the test when the unit
is **Battle-shocked** or **moves over/through enemy models**. A clean Fall Back into
open space should take **no** test. This over-penalises Fall Back by ~33% per model —
directly taxing the tactic the wave-61 AI fall-back fix made central. **Fix: gate the
test on `is_currently_battle_shocked` OR a path-crosses-enemy heuristic.**

### 3. Indirect Fire is missing two of its three effects — `units.py:2105`
Implemented: the −1 to Hit, and "no Critical Hits". **Missing:** (b) the target
automatically gains **Benefit of Cover**, and (c) an **unmodified Hit roll of 1-3
always fails**. Effect (c) is the big one: a BS2+ indirect weapon should cap at 50%
hits, but the sim only applies −1 (misses on 1 only). Indirect/artillery is
systematically over-powered. **Fix: add `if indirect_fire_attack and unmodified_roll
<= 3: continue` and grant cover to the target.**

### 4. In-engagement shooting can target any unit — `simulator.py:6536`
When a unit shoots while within Engagement Range (Pistols, or Big Guns Never Tire
Monsters/Vehicles), 10e restricts targets to **units it is engaged with**. The sim
applies no such filter — a pistol/BGNT shooter picks the juiciest target anywhere in
range. Over-values both mechanics. **Fix: restrict the candidate list to enemies
within ER when `shooting_in_engagement`/pistol.**

### 5. Blast can target units in Engagement Range — `units.py:1684`
The "+1 attack per 5 models" half is correct (now squad_id-scoped). The rule
"**cannot target a unit within Engagement Range of the bearer**" is absent. **Fix:
gate Blast target selection.**

### 6. Unmodified 6 can miss under a −1 modifier — `units.py:3044`
`if roll < hit_target: continue` with `hit_target` clamped to 7 means a base-6+
profile under −1 (target 7) treats a rolled 6 as a miss. 10e: **an unmodified 6 always
hits (Critical Hit)**; same for the Wound roll (unmodified 6 always wounds). Narrow
(needs a 6+ characteristic AND a −1 modifier) but a true rules violation. **Fix:
short-circuit `unmodified_roll == 6` to a hit/wound before the threshold compare.**

### 7. Command Point economy — `stratagems.py:1581` `STARTING_CP=3, CP_CAP=6`
10e matched play does not start armies at 3 CP or cap at 6 (these read as 9e Strike
Force values). Likely should be a 0 start with +1 per Command phase and no 6-cap.
**Symmetric across both armies, so low calibration impact**, but a rules deviation —
verify against the current mission pack before changing.

### 8. Movement coherency still not enforced — `_do_move`
Task #23 clustered squads **at deployment** and made Objective Control per-unit, but
did **not** add the "keep coherent during movement" half despite the task title.
Models still drift apart across activations with no coherency check or
remove-models-to-restore-coherency consequence. Feeds the residual horde-spread issue.

### 9. Disembark can place a unit within Engagement Range — `simulator.py:7722`
The placement loop checks only impassable terrain, not enemy proximity, so a
disembarking unit can be placed adjacent to an enemy and then fight for free. Low
practical impact (mid-game embark/disembark is barely modelled). **Fix: skip
candidate points within 1″ of any enemy.**

### 10. Battle-shock Fight-phase ordering — MISSING — `simulator.py:6194`
A Battle-shocked unit must be selected to fight at the **start of the Remaining
Combats step**. `_fight_priority` only tiers chargers + Fights First; shocked units
get no special ordering. Low impact.

---

## MISSING rules (known gaps, not yet built)

- **Strategic Reserves** — all reserves route through the Deep Strike 9″ path
  (`_pick_arrival_point`); no "within 6″ of a board edge, >9″ from enemy", no
  per-round edge unlocking. (`simulator.py:5048`)
- **Universal stratagems — 6 of 10 absent:** Fire Overwatch, Go to Ground, Grenade,
  Rapid Ingress, Smokescreen, Epic Challenge. Present: Command Re-roll (wound rolls
  only), Counter-Offensive, Tank Shock; Insane Bravery is catalogued but a **no-op**.
- **Reserves auto-destroyed if still in reserve end of Round 3** — not enforced by the
  engine (currently masked by the strategy layer force-dropping at Round 3).
- **TITANIC / TOWERING line-of-sight + cover** — open as task #3. (`map.py`)
- **Multi-target charges** — only single-target charges modelled (`_do_charge`).
- **"Can't move within Engagement Range of a non-target during a charge"** — no path
  check (`simulator.py:6964`).

---

## APPROXIMATIONS (deliberate, documented, acceptable for Stage 1)

- **Distance** measured centre-to-centre (point models, zero base radius) — `_distance`.
- **Fight phase alternation:** the active player fights all their units, then the
  defender fights in their own turn (no within-phase alternation). Documented.
- **Pile In / Consolidate / "which models fight":** the one-Unit-per-model
  representation collapses the 2″-of-a-friendly-in-ER clause; 3″ moves are correct.
  Squad *grouping* is faithful, though: every model shares a squad_id, so
  per-unit economies fire once per squad (one Advance/charge roll, battle-shock
  by surviving model count, Blast by target model count, once-per-unit
  stratagems). The Streamlit app's preset, Faction-vs-Faction, and army-list
  battles all field full squads (max-size by default for presets), so they are
  no longer amplified by the legacy one-model-per-instance build that fielded
  each model as its own unit.
- **Transport capacity** hardcoded at 12; **Firing Deck** uses the passenger's
  ballistic skill not the transport's; only pre-game embark modelled.
- **Look Out Sir** omits the "Wounds ≤ 9" gate (no current datasheet exceeds it →
  zero practical impact). (`army.py`)
- **Benefit of Cover** caps INFANTRY at 3+ correctly, but a non-INFANTRY 3+-save model
  still gains cover vs AP0 (10e denies it). (`units.py:2264`)
- **Command Re-roll** exposed only on failed wound rolls (highest-value trigger).
- **Heavy** keys on `moved_this_round` (Advance/Fall Back blocked upstream anyway);
  **Hazardous** rolls one die per activation not per weapon, no invuln on self-damage;
  **Precision** also strips cover (not a real effect, minor).
- **Pistol exclusivity** (can't fire pistols + other weapons same phase) — correct;
  the in-ER targeting restriction is finding #4 above.
- **Leader attachment** modelled as proximity + host-key proxy (no formal attach; a
  leader can be targeted; auras apply to all eligible units in range). Documented.
- **Scouts / Infiltrators** placement is heuristic (the >9″ constraints aren't
  explicitly verified, but the board geometry makes them hold in practice).

---

## PASS — verified correct

Core dice: re-roll-once, modifier cap ±1 (`units.py:2213`), unmodified-1-always-fails
on hit/wound/save (by `max(2,…)` clamp). **Wound roll S-vs-T table** exact
(`units.py:28`). Saving throw best-of armour/invuln, invuln unaffected by AP, cover
+1. Allocate Attack + normal-damage spillover + excess-lost (wave 65). Inflict Damage.
Feel No Pain per-wound. **Weapon abilities:** Assault, Rapid Fire, Ignores Cover,
Twin-linked, Torrent, Lethal Hits (crit auto-wound, not a crit-wound), Lance (charge
melee), Melta (half-range +D), Sustained Hits, Extra Attacks, Anti-X (unmodified
threshold → crit wound), Devastating Wounds (save-bypass normal hit, excess lost —
current 10e). **Shooting gates:** Advanced/Fell Back/engagement eligibility,
Big Guns Never Tire −1, Lone Operative 12″, Look Out Sir 12″ proximity + Precision
bypass. **Charge:** 2D6 roll, ends in ER, charged → Fights First. **Fight:** Fights
First step then Remaining Combats (vanilla), Pile In 3″, melee via `attack(mode=
"melee")`, Consolidate 3″. **Objectives:** OC 3″ + strictly-greater, battle-shocked
OC 0. **Battle-shock:** below-half by model count, 2D6 vs Ld, OC 0 + no stratagems.
**Terrain:** true line of sight, Ruins INFANTRY/BEAST/SWARM LoS, cover types. **Core
abilities:** Deadly Demise (per-unit, wave 66), Deep Strike 9″ + Round-2 gate, Scouts,
Infiltrators, Stealth (−1 ranged hit), Firing Deck, Feel No Pain, Fights First.

---

## Recommended fix order (rules-correct, measure each per the MAE-first gate)

1. **Remove Heroic Intervention** (#1) — clearest fabrication, melee-wide impact.
2. **Gate Fall Back Desperate Escape** (#2) — un-taxes a central tactic.
3. **Indirect Fire 1-3 auto-fail + cover** (#3) — de-powers over-strong artillery.
4. **In-engagement / Blast targeting restrictions** (#4, #5).
5. **Unmodified-6-always-hits** (#6), **disembark ER guard** (#9), battle-shock fight
   order (#10) — small correctness cleanups.
6. Larger builds: movement coherency (#8), Strategic Reserves, the missing universal
   stratagems — scope as their own waves.
