# Cross-faction modelling parity audit

**Worktree base:** `b4b2bd1` (`claude/auto-loop-carryover`).
**Gate:** `python -m unittest discover -s tests` → 710 passed, 4 skipped.
**Scope:** every faction with at least one entry in `code.units.UNIT_CATALOG`.

Legend: ✅ FULL · ⚠️ PARTIAL · ⛔ STUB · ❌ MISSING.

## Scorecard

| Faction | Army rule | Detachment rule | Strats wired | Enhancements | Leader abil. | Faction kw | Units |
|---|---|---|---|---|---|---|---|
| Adeptus Astartes (Gladius) | ✅ `simulator.combat_doctrines` (rotating Dev/Tac/Asslt) | ✅ Combat Doctrines is detachment-baked (no separate flag) | ⛔ 0/6 | ⚠️ 1 (Champion of Humanity, gladius only) | 3 non-default (Guilliman, Captain, Chaplain) | ❌ none | 134 |
| Adeptus Astartes (Ironstorm) | ✅ shares Doctrines | ⛔ flat `vehicles_reroll_hit_ones` | ⛔ 0/6 | ❌ 0 | (shares) | ❌ | (incl. above) |
| Necrons (Awakened Dynasty) | ✅ `reanimate_per_round` + Command Protocols `bonus_to_hit_when_led` | ✅ FULL (cited verbatim) | ✅ 6/6 (2 are no-op approximations: Eternal Revenant, Vengeful Stars → ⚠️ effective 4/6) | ⚠️ 1 (Hyperphasic Fulcrum) | 2 (Trazyn, Overlord etc.; Chrono/Plasma/Techno = no-op) | ❌ none | 64 |
| Necrons (Canoptek Court) | ✅ shares Reanimation | ⛔ flat `canoptek_plus_one_to_wound` | ⛔ 0/6 | ❌ 0 | (shares) | ❌ | (incl.) |
| Tyranids (Invasion Fleet) | ✅ Synapse + Shadow in the Warp (army-wide Ld) | ⚠️ `enemy_ld_penalty=1` (range-gated → army-wide approximation) | ⛔ 0/6 | ❌ 0 | 1 (Hive Tyrant) | ✅ SYNAPSE wired (19 units) | 59 |
| Aeldari (Warhost) | ✅ Battle Focus + Strands of Fate, `martial_grace` token bump | ⚠️ token+1 wired; +1″ move / +1 D6 Agile = APPROX | ✅ 6/6 (all listed APPROXIMATIONs) | ❌ 0 | 3 (Farseer, Autarch, Avatar) | ❌ no `BATTLE_FOCUS` keyword | 96 |
| Orks (War Horde) | ✅ `_try_power_of_the_waaagh` (WAAAGH!) | ✅ Get Stuck In = `melee_sustained_hits_army_wide` (verbatim) | ✅ 6/6 (flagged APPROX where transient_* can't capture) | ❌ 0 | 1 (Warboss) | ❌ no MOB keyword gate | 87 |
| T'au Empire (Mont'ka) | ✅ Markerlights + Guided + `_run_markerlight_phase` | ✅ `army_wide_assault_rounds_1_3` + `lethal_hits_on_guided` (cited) | ✅ 6/6 | ⚠️ 1 (Puretide Engram, montka only) | 1 (Commander, Ethereal/Fireblade defaults) | ✅ MARKERLIGHT (3 units) | 64 |
| Thousand Sons (Grand Coven) | ✅ Cabal of Sorcerers rituals + PSYKER gating | ⚠️ Kindred Sorcery → flat `psychic_mortal_wounds_per_round=2` (proxy) | ✅ 6/6 | ❌ 0 | 1 (Sorcerer) | ✅ PSYKER (17 Tson) | 42 |
| Death Guard (Vir. Vectorium) | ⚠️ Contagion ranges referenced but mostly text/notes | ⚠️ `worldblight_sticky_dg_objectives` (sticky half); contagion-on-objective = APPROX | ✅ 6/6 | ❌ 0 | 1 (Typhus, LoC default-ish) | ⚠️ CONTAGION not modelled as keyword | 49 |
| Adeptus Custodes (Shield Host) | ❌ no separate army rule gate | ✅ Martial Ka'tah = both bullets always-on (`melee_crit_on_5_plus_hits` + `melee_ap_plus_one`); flagged APPROX (dual instead of pick-one) | ✅ 6/6 | ❌ 0 | 2 (Trajann, Shield-Captain) | ❌ MARTIAL KA-TAH keyword unwired | 34 |
| Leagues of Votann (Oathband) | ✅ `simulator.judgement_tokens` (Eye of the Ancestors, 1+/3+ re-roll thresholds) | ⛔ no detachment-rule flag (raw judgement is army-rule; Voidsmen Oaths removed to avoid double-stack) | ✅ 6/6 | ❌ 0 | 1 (Kâhl) | ❌ no Oath/Grudge keyword gate | 25 |
| Astra Militarum (Combined Regiment) | ❌ no Fire Orders / Voice of Command modelling | ⛔ flat `plus_one_to_hit` | ⛔ 0/6 | ❌ 0 | 0 non-default | ❌ no OFFICER / ORDER gates | 132 |
| World Eaters (Berzerker Warband) | ✅ `_maybe_award_blood_tithe` (Blood Tithe accumulation) | ⛔ flat `plus_one_to_hit` (no roster spend) | ⛔ 0/6 | ❌ 0 | 0 non-default | ⚠️ keyword present but no spend menu | 35 |
| Genestealer Cults (Final Day) | ⚠️ `is_gsc` ambush gate exists | ⛔ flat `reroll_hit_ones`; no Ambush/Onslaught/Annihilation rotation | ⛔ 0/6 | ❌ 0 | 1 (Primus) | ❌ no Cult Ambush deepstrike menu | 28 |
| Drukhari (Skysplinter Assault) | ✅ Pain Tokens (`pain_tokens > 0`-gated FNP/dmg buffs) | ⛔ flat `reroll_wound_ones` (real = +1 to wound on charge) | ⛔ 0/6 | ❌ 0 | 2 (Archon, Succubus) | ⚠️ Pain Tokens wired; Combat Drugs missing | 32 |
| Chaos Daemons (Daemonic Incursion) | ❌ no Shadow of Chaos / god aura | ⛔ flat `plus_one_to_hit` | ⛔ 0/6 | ❌ 0 | 2 (Daemon characters generic) | ⚠️ DAEMON kw present, no zone effect | 97 |
| Imperial Knights (Noble Lance) | ❌ Code Chivalric / oaths missing | ⛔ flat `plus_one_to_wound` (charge/lance conditional gone) | ⛔ 0/6 | ❌ 0 | 0 non-default | ❌ no LANCE rule | 22 |
| Chaos Knights | ❌ no detachment registered (no Pact of Damnation) | ❌ no entry | ❌ 0/6 | ❌ 0 | 0 | ❌ | 20 |
| Adepta Sororitas (Hallowed Martyrs) | ❌ no Acts of Faith / Miracle Dice | ⛔ flat `plus_one_to_wound` (destroyed-Sororitas trigger ignored) | ⛔ 0/6 | ❌ 0 | 1 (Canoness) | ❌ no MIRACLE_DICE | 40 |
| Adeptus Mechanicus (Skitarii Hunter) | ⚠️ Doctrina Imperatives string only, no rotation | ⛔ flat `reroll_hit_ones` | ⛔ 0/6 | ❌ 0 | 2 (Belisarius Cawl, Dominus) | ❌ Doctrina rotation missing | 42 |
| Chaos Space Marines (Pactbound Zealots) | ❌ no Dark Pacts test/cost | ⛔ flat `reroll_wound_ones` | ⛔ 0/6 | ❌ 0 | 2 (Sorcerer, Dark Apostle, Chaos Lord) | ❌ no DARK_PACT mechanic | 83 |
| Grey Knights (Teleport Strike Force) | ❌ no Brotherhood Psychics / Teleport rule | ⛔ flat `reroll_wound_ones` | ⛔ 0/6 | ❌ 0 | 2 (Brother-Captain, Grand Master) | ✅ PSYKER kw populated (23 GK) — but no GK psychic phase | 35 |
| Agents of the Imperium (Inquisition TF) | ❌ no Imperial Authority | ⛔ flat `reroll_hit_ones` | ⛔ 0/6 | ❌ 0 | 0 | ❌ | 45 |
| Black Templars | ❌ no Vows | ❌ no detachment | ❌ 0/6 | ❌ 0 | 0 | ❌ | 20 |
| Blood Angels | ❌ Red Thirst missing | ❌ no detachment | ❌ 0/6 | ❌ 0 | 0 | ❌ | 26 |
| Dark Angels | ❌ Grim Resolve missing | ❌ no detachment | ❌ 0/6 | ❌ 0 | 0 | ❌ | 19 |
| Space Wolves | ❌ no army rule | ❌ no detachment | ❌ 0/6 | ❌ 0 | 0 | ❌ | 39 |
| Deathwatch | ❌ Mission Tactics missing | ❌ no detachment | ❌ 0/6 | ❌ 0 | 0 | ❌ | 9 |
| Emperor's Children (Coterie of the Conceited) | ❌ Slaanesh/Noise rules missing | ⚠️ `coterie_pact_points` = Slaanesh's Due Pact-point tracker (four cumulative tiers, verbatim-cited); pledge idealised as competent play + D3 mortal-wound downside omitted (APPROX); gated `SWEG_EC_DETACHMENT` default-OFF | ⛔ 0/6 | ❌ 0 | 0 | ❌ | 26 |
| Imperial Fists / Iron Hands / Salamanders / Raven Guard / White Scars / Ultramarines | ❌ (fall back to Gladius via Adeptus Astartes — chapter trait missing) | ❌ no chapter detachment | ❌ | ❌ | varies | ❌ | 3/2/2/2/2/16 |
| Ynnari | ❌ | ❌ | ❌ | ❌ | 0 | ❌ | 3 |
| Chaos Titans | ❌ | ❌ | ❌ | ❌ | 0 | ❌ | 4 |
| Unaligned | n/a | n/a | n/a | n/a | 0 | n/a | 18 |

### Summary counts (army-rule / detachment-rule / strats / enhancements)

- **Army rule:** FULL=8 (Marines, Necrons, Tyranids, Aeldari, Orks, T'au, Tson, Votann) · PARTIAL=2 (DG, Mechanicus) · STUB=0 · MISSING=18 (Custodes army-tier, AM, Sororitas, GSC, CSM, GK, Daemons, IK, CK, EC, all minor chapters, Ynnari, Chaos Titans).
- **Detachment rule:** FULL=5 (Awakened Dynasty, Mont'ka, War Horde, Shield Host, Gladius via Doctrines) · PARTIAL=3 (Warhost, Vectorium, Grand Coven) · STUB=12 · MISSING=4 (Chaos Knights, Templars, BA, DA, SW, DW, EC, Ynnari and other unregistered codices).
- **Stratagems:** 6/6 wired for 8 detachments (Awakened Dynasty, Shield Host, Warhost, Mont'ka, Oathband, Virulent Vectorium, Grand Coven, War Horde). 0/6 for 14 detachments. Effective firing depth lower — many entries are no-op APPROXIMATIONs.
- **Enhancements:** only 3 registered total (Gladius, Awakened Dynasty, Mont'ka).
- **Leaders with non-default abilities:** 27 / 34 (`code.leaders._REGISTRY`).
- **Detachments registered:** 23 (covering 21 distinct faction roots, none for Chaos Knights / BA / DA / SW / Templars / EC / Ynnari / minor chapters).

### Faction-specific keywords actually read by the simulator

- ✅ wired and gated: `SYNAPSE` (Tyranids, 19 units), `MARKERLIGHT` (T'au, 3 units), `PSYKER` (Tson rituals; GK populated but inert), `CHARACTER` / `EPIC HERO` / `BATTLELINE` / `VEHICLE` (core/cross-faction).
- ⛔ keyword on profile but unused: `DAEMON` (Daemons/CSM/Tson — no Shadow of Chaos zone), `MOUNTED` (no mounted-only rule), `CANOPTEK` (canoptek_court flat flag instead).
- ❌ absent entirely: `MARTIAL KA-TAH` (Custodes — no per-round picker), `CONTAGION` (DG), `OFFICER` / `ORDER` (AM), `MIRACLE_DICE` (Sororitas), `OATH OF MOMENT` (Marines), `DARK PACT` (CSM), `CULT AMBUSH` (GSC), `LANCE` (IK), `COMBAT DRUGS` (Drukhari).

### Citation completeness

`data/rule_citations.d/`: present for admech, aeldari, death_guard, drukhari, genestealer_cults, marines, necrons, tyranids, thousand_sons, world_eaters, detachments, leaders, stratagems, enhancements, plus core. **Missing citation files:** Orks (despite War Horde wired), T'au, Custodes (Shield Host wired), Sororitas, Astra Militarum, CSM, Grey Knights, Daemons, Imperial Knights, Chaos Knights, Votann (despite Oathband wired). Most of these are covered piecemeal in `detachments.json` / `stratagems.json` but no faction-named file exists.

## Factions ranked by overall completeness

1. **Necrons (Awakened Dynasty)** — army + detachment + 6/6 strats + 1 enhancement. Highest.
2. **T'au Empire (Mont'ka)** — army + detachment cited verbatim + 6/6 + 1 enhancement.
3. **Orks (War Horde)** — army + detachment cited + 6/6.
4. **Aeldari (Warhost)** — army (Battle Focus + Strands) + 6/6, detachment partial.
5. **Adeptus Custodes (Shield Host)** — detachment FULL + 6/6, but no separate army rule.
6. **Thousand Sons (Grand Coven)** — army (Cabal) + 6/6, detachment proxy.
7. **Leagues of Votann (Oathband)** — Eye of the Ancestors army-rule + 6/6, no detachment effect.
8. **Death Guard (Virulent Vectorium)** — partial contagion + 6/6.
9. **Adeptus Astartes (Gladius/Ironstorm)** — army FULL, 0/6 strats, 1 enhancement.
10. **Tyranids (Invasion Fleet)** — Synapse FULL, detachment partial, 0/6 strats.
11. **Adeptus Mechanicus** — stub detachment + Doctrina note only, 0/6 strats, but 2 leaders.
12. **Drukhari** — Pain Tokens wired (army-rule level) but stub detachment + 0/6.
13. **World Eaters** — Blood Tithe wired but stub detachment + 0/6.
14. **Genestealer Cults** — partial GSC ambush gate, stub detachment, 0/6.
15. **CSM, Sororitas, AM, GK, Daemons, IK, Inquisition** — stub detachments only, 0/6.
16. **Chaos Knights, Templars, BA, DA, SW, Deathwatch, Emperor's Children, Ynnari** — fully unmodelled beyond unit stats.

## Top 10 highest-leverage parity fixes

1. **Marines Gladius — wire 6 detachment stratagems** (Armour of Contempt, Storm of Fire, Honour the Chapter, Squad Tactics, Adaptive Strategy, Only In Death Does Duty End). Marines are 134 units and the most-used codex in simulations; 0/6 makes every Marines matchup understate offence by ~2-3 CP/round. **Effort: 1-1.5 days** (mirror Awakened Dynasty's structure; cite Wahapedia Gladius page).
2. **Astra Militarum — Officer / Order system + 6 stratagems** (FRFSRF, Take Aim, Move! Move! Move!, Fix Bayonets, Insane Bravery, Inspired Command). 132 units catalogued; currently 0/6 strats and a flat `plus_one_to_hit` stub. **Effort: 2-3 days** — needs an Order picker akin to Battle Focus token plumbing.
3. **CSM Pactbound Zealots — Dark Pacts + 6 strats** (Pacts is the entire codex teeth; current `reroll_wound_ones` flat is wrong). Add Battleshock-cost test for [LETHAL HITS]/[SUSTAINED HITS] pick. 83 units. **Effort: 1.5-2 days**.
4. **Sororitas Hallowed Martyrs — Miracle Dice + Acts of Faith + 6 strats**. Currently no army rule. 40 units. **Effort: 2 days** (new dice pool, simulate per-turn earn + spend).
5. **Grey Knights — Brotherhood Psychic phase + 6 strats**. PSYKER keyword is populated (23 GK) but inert. **Effort: 1-1.5 days** (extend Tson rituals pattern, restrict to GK faction).
6. **Imperial Knights Noble Lance — Code Chivalric oaths + LANCE keyword + 6 strats**. Currently flat `+1 wound`. **Effort: 1 day** (oath = round-1 self-target buff; LANCE = melee charged-turn +1 wound gate already partially present elsewhere).
7. **Chaos Daemons Daemonic Incursion — Shadow of Chaos zone + god-aura + 6 strats**. Daemons are 97 units (3rd-largest codex) with zero gameplay teeth. **Effort: 2 days** (zone proximity check, Battleshock immunity, four god-keyword buffs).
8. **World Eaters Blood Tithe spend menu**. The accumulation half exists (`_maybe_award_blood_tithe`); add the 1-/2-/3-/4-/6-tithe spends as transient buffs gated on WE faction. **Effort: 1 day**.
9. **Custodes Martial Ka'tah — pick-one-per-round picker**. Currently both bullets always-on (overshoots). Add a battle-round choice between Crit-on-5 and AP+1. **Effort: 0.5 day**.
10. **Awakened Dynasty Protocol of the Eternal Revenant + Vengeful Stars** — both currently no-op APPROXIMATIONs. Add a "revive 1 destroyed CHARACTER per game" hook and a "+1 to wound vs MONSTER/VEHICLE for ranged" transient. **Effort: 0.5-1 day**.

Honourable mention (lower priority but cheap): **register a Chaos Knights detachment** (`pact_of_damnation`) so the 20 CK units aren't blanked, **enhancements registry expansion** (only 3 entries — every faction should have at least one), and **Genestealer Cults rotating stages** (`final_day` stub → Ambush/Onslaught/Annihilation toggle).
