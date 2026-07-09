# List-fidelity audit — Death Guard: is the simulator fielding a stronger-than-real army? (2026-07-03)

Read-only audit. Base branch `claude/sim-calibration-19`, top commit `5b00fc8`.
Standing anchor `data/_anchor_sc52a_n80_log.json`. Scratch scripts:
`scripts/_list_audit_dg_census.py`, `scripts/_list_audit_dg_real.py`,
`scripts/_list_audit_dg_attrib.py`. Windows discipline: `PYTHONIOENCODING=utf-8`,
`PYTHONHASHSEED=0` on replays.

## The question

Real Death Guard wins about 46.1 percent at May-2026 tournaments; the simulator now
has rules audited faithful to print (the durability and secondary-economy waves) yet
Death Guard wins 68.6 percent (sc52a, plus 22.5 over real, the top over-pole). The
durability audit (`docs/_DURA_AUDIT_D_DEATHGUARD.md`) proved the over-pole is
scoring-shaped survivor-uptime, not a defensive-statistic error. The remaining
Stage-1 list-zone suspect: if the simulator fields a MORE durable-per-point Death
Guard army than real tournament lists, faithful rules will correctly over-reward it.
This audit quantifies the simulator's Death Guard durability-per-point and compares it
to the real May-2026 meta, unit for unit.

## Headline verdict

**List-fidelity is NOT the answer for Death Guard. The simulator's Death Guard army is
durability-per-point FAITHFUL to the real meta — in fact marginally BELOW it.** On the
primary intensive metric, wounds-per-point, the simulator's army sits 5 to 7 percent
UNDER the sourced real competitive lists. Its durable-share (fraction of points in
durable platforms) matches the Mortarion-brick real list within one point and is 8 to 9
points BELOW the vehicle-swarm real list. The one genuine composition divergence — the
template force-seeds Mortarion into 100 percent of builds where real lists field him in
roughly half — pushes durability-per-point DOWN, not up, because Mortarion is the most
durability-EXPENSIVE unit in the codex (0.042 wounds per point against an army average of
0.075). The fill no longer leaks durable phantoms: across 105 reproduced anchor games only
1.2 percent of Death Guard models are off-template, and every one of those is a cheap
support character (Nurglings, Noxious Blightbringer, Malignant Plaguecaster), never a
durable platform. The simulator wins its Death Guard games with exactly the units the real
list fields. **The residual is the pricing floor / scoring representation, not the army
list.**

---

## 1. Build census (N = 80, seed versus fill split)

`build_archetype_army("A", "Death Guard", 2000, use_archetype=True)`, sampled over 80
deterministic seeds. The census harness (`build_split`) is validated **byte-identical**
to the production `build_faction_random_army(use_archetype=True)` path (matching model
counts, points, and per-unit composition across seeds 0, 5, 42, 123, 10000, 10005) — the
production path consumes one `rng.choice` archetype-pick draw even for a single-archetype
faction, which the census now replicates.

The effective template (default-on `SWEG_DG_REALISM`, `code/archetypes.py`
`_effective_template`): Mortarion 1, Foetid Bloat-drone 2, Plague Marines 2, Poxwalkers 2,
Deathshroud Terminators 2, Plagueburst Crawler 1, Daemon Prince of Nurgle 1, Lord of
Contagion 2, Myphitic Blight-hauler 1 — Typhus and the Foul Blightspawn dropped. The seed
fills roughly the first 1115 points; `_random_fill` (default-on `SWEG_FILL_TEMPLATE_POOL`,
template-pool-first) supplies the remaining ~870.

| Metric | Whole army | Seed (template) | Fill (random) |
|---|---|---|---|
| models | 50.6 | 22.0 | 28.6 |
| points | 1983.9 | 1115.0 | 868.9 |
| total wounds | 149.4 | 74.0 | 75.4 |
| **wounds per point** | **0.0753** | 0.0664 | 0.0868 |
| average Toughness (wound-weighted) | 7.93 | 8.49 | 7.41 |
| invulnerable-save coverage | 67.9% of wounds | 73.0% | 63.9% |
| feel-no-pain coverage | 28.5% of wounds | 35.1% | 21.0% |
| save 2+ coverage | 47.2% of wounds | 59.5% | 36.3% |
| Toughness 10+ models | 3.0 | 2.0 | 1.0 |
| 15+ wound models | 1.0 | 1.0 | 0.0 |
| durable-share (points) | 81.7% | 85.7% | 76.6% |
| vehicle/monster-share (points) | 55.2% | 60.5% | 48.3% |

Per-unit, averaged per build (models / points / seed-models / fill-models / percent of
builds present):

| unit | models | points | seed | fill | in% |
|---|---|---|---|---|---|
| Mortarion | 1.00 | 380 | 1.00 | 0.00 | 100 |
| Daemon Prince of Nurgle | 1.55 | 302 | 1.00 | 0.55 | 100 |
| Deathshroud Terminators | 5.40 | 288 | 3.00 | 2.40 | 100 |
| Lord of Contagion | 1.79 | 215 | 1.00 | 0.79 | 100 |
| Plague Marines | 10.00 | 190 | 5.00 | 5.00 | 100 |
| Foetid Bloat-drone | 1.86 | 186 | 1.00 | 0.86 | 100 |
| Poxwalkers | 26.75 | 174 | 10.00 | 16.75 | 100 |
| Myphitic Blight-hauler | 1.25 | 125 | 0.00 | 1.25 | 52 |
| Plagueburst Crawler | 0.47 | 100 | 0.00 | 0.47 | 40 |
| (off-template support) | <0.5 total | <25 | 0 | <0.5 | ≤12 each |

**Key reading of the split.** The fill's wounds-per-point (0.0868) is HIGHER than the
seed's (0.0664), the opposite of the "over-durability creeps in through the fill" prior.
That is because `SWEG_FILL_TEMPLATE_POOL` (adopted default-on) now draws the fill from the
curated template pool first, so the fill is mostly extra Poxwalkers (+16.75 models),
Plague Marines (+5), and Deathshroud (+2.4) — cheap, high-wounds-per-point bodies — rather
than the whole-catalogue durable junk (Chaos Predators, Land Raiders, Defilers) the
2026-07-01 archetype-fidelity audit flagged. Those durable phantoms are now architecturally
absent (see attribution). The seed carries the durable pillars (Mortarion, Daemon Prince,
Bloat-drone, Deathshroud); the fill dilutes durability-per-point downward toward bodies.

---

## 2. The sourced real list(s)

Web decklist hosts (Best Coast Pairings, Grimhammer, Bell of Lost Souls, tabletopbattles,
Goonhammer, listengine) were attempted but are JavaScript-rendered or return HTTP 403 to
the fetcher, so exact points tables could not be pulled live. Per the brief this falls back
to the sources already cited in the repository and reasons from BSData points. Two real
competitive Death Guard archetypes define the May-2026 meta, and BOTH are heavily durable:

**Real-A — Virulent Vectorium, Mortarion durability-brick.** Structure from
`docs/WAVE250_LIST_REALISM.md` (three Grimhammer lists, July/October/November 2025) plus
the tabletopbattles Detachment Focus: the Daemon Prince of Nurgle "shows up in most, if not
all, competitive Virulent Vectorium lists"; "at least two units of Deathshroud"; Mortarion
in two of three lists; NO Typhus, NO Foul Blightspawn; roughly 48 to 58 models. Concrete
~2000-point reconstruction: Mortarion 1, Daemon Prince of Nurgle 1, Lord of Contagion 1,
Lord of Virulence 1, Deathshroud 2 squads, Foetid Bloat-drone 3, Myphitic Blight-hauler 2,
Poxwalkers 3 squads of 10, Plague Marines 2 squads of 5 (55 models).

**Real-B — Mortarion's Hammer, "cheap hulls" vehicle-swarm.** This is the actual Warhammer
Open Tacoma winner (Steve Trimble). Structure from the spikeybits placings extraction: 2
Lord of Contagion + 1 Lord of Virulence, 3 Deathshroud squads, 3 Foetid Bloat-drones, 2
Myphitic Blight-haulers, **3 Plagueburst Crawlers**, 3 Poxwalkers squads — no Mortarion, no
Plague Marines, no Daemon Prince: a pure durable-hull swarm (eight vehicles). The source
describes "the sheer efficiency of the cheap hulls" as "one of the strongest builds going".

Both real lists were priced on the SAME BSData/simulator catalogue as the census (identical
points and defensive statlines on both sides) so any gap is pure composition, not pricing.

| Metric | SIM (N=80) | Real-A (Mortarion brick) | Real-B (vehicle-swarm, 2000) | Real-B (full Trimble) |
|---|---|---|---|---|
| models | 50.6 | 55 | 47 | 50 |
| points | 1984 | 2000 | 1985 | 2145 |
| **wounds per point** | **0.0753** | **0.0810** | **0.0796** | 0.0793 |
| average Toughness (wound-weighted) | 7.93 | 7.74 | 7.75 | 7.69 |
| invulnerable coverage | 67.9% | 69.1% | 81.0% | 82.4% |
| feel-no-pain coverage | 28.5% | 28.4% | 19.0% | 17.6% |
| save 2+ coverage | 47.2% | 38.3% | 49.4% | 52.9% |
| Toughness 10+ / 15+ wounds | 3.0 / 1.0 | 2.0 / 1.0 | 3.0 / 0.0 | 3.0 / 0.0 |
| durable-share (points) | 81.7% | 80.8% | 90.2% | 90.9% |
| vehicle/monster-share | 55.2% | 53.8% | 56.9% | 52.7% |

A pricing signal falls out of the table: the full Trimble list costs 2145 SIMULATOR points,
so it does not fit inside a 2000-point budget when priced with the simulator's catalogue.
The simulator prices the durable hulls ABOVE Games Workshop (for example Plagueburst Crawler
210 simulator points against roughly 170 in the current dataslate). At equal simulator
points the simulator therefore fields LESS durable tonnage than a real Games-Workshop-pointed
list, not more — a Stage-2 pricing-floor observation, not a list-composition one.

---

## 3. The unit-for-unit diff and the durability-per-point gap

**Durability-per-point gap (simulator minus real):**

- Wounds per point: simulator 0.0753 versus Real-A 0.0810 (simulator **−7.0%**), Real-B
  0.0793–0.0796 (simulator **−5.0% to −5.4%**). The simulator is LESS durable per point.
- Durable-share: simulator 81.7% versus Real-A 80.8% (**+0.9 points**, a match) versus
  Real-B 90.2–90.9% (simulator **−8.5 to −9.2 points**; the real vehicle-swarm is more
  durable-share-heavy than the simulator).
- Vehicle/monster-share: simulator 55.2% versus Real-A 53.8% (+1.5) versus Real-B
  52.7–56.9% (roughly level).
- Average wound-weighted Toughness: simulator 7.93 versus real 7.69–7.75 (simulator +0.2,
  the only metric where the simulator runs slightly hot).

**Unit-for-unit divergences (simulator versus real):**

1. **Mortarion over-fielded.** Simulator: 100 percent of builds (force-seeded flagship).
   Real: Virulent Vectorium runs him in about two of three lists, Mortarion's Hammer
   vehicle-swarm runs zero. This is the single clearest composition divergence — but it
   REDUCES durability-per-point, because Mortarion returns 16 wounds for 380 points
   (0.042 wounds per point) against the army average of 0.075. Removing the force-seed and
   letting some builds run the Trimble no-Mortarion swarm would RAISE the simulator's
   wounds-per-point toward real, not lower it.
2. **Plagueburst Crawler under-fielded.** Simulator: present in 40 percent of builds, 0.47
   per build (the `SWEG_DG_REALISM` seed was thinned from 2 to 1 and the wrecker
   preference rarely refills it). Real vehicle-swarm: 3 per list. The simulator under-fields
   the codex's most durable-share-efficient vehicle. This is durability the simulator UNDER-
   provisions versus the real vehicle-swarm.
3. **Bodies broadly matched.** Poxwalkers 26.75 simulator versus real 20–30; Plague Marines
   10 simulator versus real 0–10; Deathshroud 5.4 models simulator versus real 6–9;
   Foetid Bloat-drone 1.86 simulator versus real 3. Total models 50.6 simulator versus real
   47–55. The simulator sits inside the real band on every body count.
4. **Off-template contamination negligible.** The old audit's Chaos Predators / Land Raiders
   / Heldrakes / Defilers do NOT appear (see attribution) — the template-pool fill forecloses
   them.

Net: the simulator carries **5 to 7 percent LESS** durability-per-point than the real meta,
matches its durable-share, and under-provisions the one durable vehicle (Plagueburst Crawler)
the real swarm stacks. There is no direction in which the simulator's list is
over-durable-per-point.

---

## 4. Attribution (reproduced sc52a Death Guard wins)

`scripts/_list_audit_dg_attrib.py` replays the sc52a anchor Death Guard cells with the exact
evaluate-vs-meta reconstruction (`pair_seed = (ai*1000+bi)*100+s`, army A on `Random(s)`,
army B on `Random(s+10000)`, rotation map and mission keyed identically). Stratified subset:
first five seeds against each of the 21 opponents.

- **Winner reproduction: 105 of 105 = 100 percent.** These replays are the anchor's own games.
- **Off-template presence: 78 of 6282 Death Guard models = 1.2 percent.** Every off-template
  model is a cheap support character: Nurglings ×36 (13 points, Toughness 3), Noxious
  Blightbringer ×21 and Malignant Plaguecaster ×21 (50–60 points, Toughness 6, 4 wounds).
  **Zero durable phantoms** — no Chaos Predator, Land Raider, Defiler, Blightlord, Great
  Unclean One, or Rotigus was drafted into any of the 105 games. The template-pool fill plus
  the wrecker cap make the old durable-junk leak architecturally impossible.

Four reproduced Death Guard WINS, one per opponent class, with rosters and survivors:

| game | roster (durable pillars) | survivors | pillars started → survived | off-template |
|---|---|---|---|---|
| versus Adeptus Astartes, seed 0 (round 5) | Mortarion, Daemon Prince, 3 Bloat-drone, 3 Deathshroud, 2 Lord of Contagion | Mortarion, 3 Bloat-drone, 10 Poxwalkers, 3 Plague Marines | 10 → 4 | 1 Noxious Blightbringer |
| versus Necrons, seed 0 (round 5) | Mortarion, Daemon Prince, 3 Bloat-drone, 3 Deathshroud, 2 Lord of Contagion | Mortarion, Daemon Prince, 2 Bloat-drone, 3 Deathshroud, 2 Lord of Contagion, 24 Plague Marines, 19 Poxwalkers | 10 → 9 | 1 Noxious Blightbringer |
| versus Aeldari, seed 0 (round 5) | Mortarion, 2 Daemon Prince, Plagueburst Crawler, Bloat-drone, Deathshroud, Lord of Contagion | Mortarion, 2 Daemon Prince, Bloat-drone, 2 Deathshroud, Lord of Contagion, 20 Poxwalkers, 12 Plague Marines | 9 → 7 | 0 |
| versus Tyranids, seed 0 (round 5) | Mortarion, Daemon Prince, 3 Bloat-drone, 3 Deathshroud, 2 Lord of Contagion | Mortarion, Daemon Prince, 3 Bloat-drone, Deathshroud, 20 Plague Marines, 15 Poxwalkers | 10 → 6 | 1 Noxious Blightbringer |

Every durable pillar that survives to bank objectives is a REAL-LIST unit — Mortarion,
Daemon Prince of Nurgle, Foetid Bloat-drone, Deathshroud Terminators, Lord of Contagion,
Plagueburst Crawler. The only off-template survivor across the four games is a single
Noxious Blightbringer (a 50-point support character with no durability role). The simulator
is winning with the same units the real tournament list fields, at durable-shares matching
the real list. **A template or fill correction would not move the 68.6 percent** — there is
no over-durable unit to remove and no phantom carrying the wins.

This dovetails with `docs/_DURA_AUDIT_D_DEATHGUARD.md`: even in these wins Death Guard often
ends the game having lost most of its army (game 1: 18 of 66 models survive a win) while
banking primary victory points through durable-pillar objective uptime. The edge is
scoring-shaped, and the pillars carrying it are exactly the real-list pillars.

---

## 5. The crisp call

**The simulator's Death Guard list is NOT over-durable versus real — it is durability-per-
point faithful, and marginally UNDER real (5 to 7 percent lower wounds-per-point, matched
durable-share, one under-fielded durable vehicle).** List-fidelity is therefore NOT the
mechanism behind the plus-22.5 over-pole. The residual is the **pricing floor and the
scoring representation**:

- **Scoring representation (Stage-1 structural, already teed up):** the survivor-snapshot
  primary-objective uptime documented in `docs/DURABILITY_OVERREWARD_INVESTIGATION.md` and
  confirmed for Death Guard in `docs/_DURA_AUDIT_D_DEATHGUARD.md`. Faithful per-model contest
  sums plus a faithful Command-phase snapshot compose into an uptime premium for durable-
  pillar armies. No list change touches this.
- **Pricing floor (Stage-2):** the simulator already prices Death Guard's durable hulls
  ABOVE Games Workshop (the real Trimble swarm costs 2145 simulator points), so the faithful
  rules reward durability that the simulator's own points do not yet fully charge for. That
  is the points-equation's job, not the list's.

The only defensible list-realism tweak the census surfaces — dropping Mortarion's 100-percent
force-seed so some builds run the real Trimble no-Mortarion vehicle-swarm — would if anything
push the win rate UP (it raises wounds-per-point and durable-share toward the real swarm),
so it is not a lever for closing the over-pole and should be judged on fidelity grounds alone.
There is no list-fidelity correction that lowers the 68.6 percent, because the simulator is
already fielding the real army at the real durability-per-point.

## Sources

- `docs/_DURA_AUDIT_D_DEATHGUARD.md` — the win-shape proof (scoring-shaped, not attrition-
  shaped); this audit is its list-fidelity companion.
- `docs/ARCHETYPE_FIDELITY_AUDIT.md` — the 2026-07-01 archetype audit that first recorded
  "Death Guard real lists are at least as durable-share-heavy as the simulator's".
- `docs/WAVE250_LIST_REALISM.md` — sourced Virulent Vectorium structure (three Grimhammer
  lists, July/October/November 2025).
- `code/archetypes.py` `_effective_template` (`SWEG_DG_REALISM`) and `_random_fill`
  (`SWEG_FILL_TEMPLATE_POOL`) — the effective template and template-pool fill.
- Real-list structure (web, best-effort; hosts JavaScript-rendered / 403 to the fetcher):
  Warhammer Open Tacoma placings, https://spikeybits.com/top-40k-tournament-army-lists-from-warhammer-open-tacoma/
  (Steve Trimble, 1st, Mortarion's Hammer vehicle-swarm); Detachment Focus: Virulent
  Vectorium, https://www.tabletopbattles.com/detachment-focus-virulent-vectorium/ (Daemon
  Prince near-universal); Grimhammer competitive lists, https://grimhammertactics.com/top-10-competitive-warhammer-40k-lists-march-2026/ .
  Datasheet stats and points: BSData (`data/bsdata/cache/Chaos - Death Guard.cat.gz`) via the
  live `UNIT_CATALOG`, the project's canonical source (standing rule six).
