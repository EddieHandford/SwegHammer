# Leader / Attached-unit protection + secondary per-unit counting (2026-07-12)

Origin: the Astra Militarum under-pole hand-pilot (see `PILOT_FINDINGS.md`
2026-07-12) traced AM's worst matchups to an **Assassination bleed** — AM loses
the *secondary* race, not primary or durability, because its ~10 fragile
CHARACTERs feed the opponent ~20 Assassination VP/game. Three additive causes:

1. **Per-model Assassination counting** (bug): a 5-model Cadian Command Squad
   scored Assassination 5×. Confirmed 1.83× AM over-count. **FIXED.**
2. **Character exposure** (missing 10e Leader rule): the sim never modelled
   Leader/Attached-unit protection, so characters were free snipe/charge
   targets. **BUILT.** (The old `simulator.look_out_sir` gate was a fabricated
   proxy — "Look Out, Sir" is not a real 10e rule; the 12" clause is Lone
   Operative's. Verified absent from the Wahapedia core rules.)
3. **Fixed-Assassination auto-pick** (`pick_secondaries` gives every ≥2-CHARACTER
   opponent Fixed Assassination). Rules-legal but aggressive — **registered as a
   follow-up**, not changed.

## What is built (this session) — all gated, byte-identical off, tests +0 failures

| Gate | Effect | Files |
|---|---|---|
| `SWEG_LEADER_ATTACH` | An attached CHARACTER cannot be selected as a ranged OR melee target while its bound host squad has a living non-CHARACTER (bodyguard) model; `[PRECISION]` bypasses; position/range-independent (an Attached unit can't separate). Replaces Look Out Sir. Multi-leader hosts allowed. | `code/attachment.py` (new), `code/army.py` (`can_target_for_ranged`), `code/simulator.py` (`_do_fight`, bind call), `code/strategy.py` (`pick_charge_target`), `code/units.py` (`__slots__`), `code/leaders.py` (`attach_keys` field) |
| `SWEG_SECONDARY_PER_UNIT` | Assassination counts one score per destroyed CHARACTER **unit** (squad_id group), not per model — mirroring the existing No Prisoners / Cull per-squad handling. (Bring It Down is also per-unit in CA-2025 — same fix pending, near-zero impact: only multi-model vehicle squadrons differ.) | `code/secondaries.py` (`RoundSnapshot`, `score_round_delta`) |

Faithful model (one-Unit-per-model representation): the sim has no intra-unit
wound-allocation step, so "un-targetable Leader while bodyguard squad alive" is
the exact equivalent of the real "allocate attacks to Bodyguard models" rule —
the enemy's fire lands on the (separate) bodyguard squad; when it dies the
Leader is exposed. Citation: `simulator.leader_attachment` (Precision-verbatim
backed) in `data/rule_citations.d/core_targeting.json`.

Verification: byte-identical with both gates off (every reference seed exact);
full test suite adds **0** failures (proven by stash-compare; the 51 suite
failures are pre-existing, in unrelated subsystems); combined quick A/B (N=20)
moves AM's worst matchups ~5% → ~15% (the per-unit counting fix is the larger
of the two levers). N=40 screen result: see `PILOT_FINDINGS.md` / `DECISION_LEDGER.md`.

## Architectural requirements for the full gap-fill (NEXT PHASE — not yet done)

The all-faction gap-fill data (below) is validated but **cannot be applied
correctly until two structural issues are fixed**:

1. **`attach_keys` split — DONE.** `host_keys` carried double duty (aura gate +
   attach target). Some leaders attach to a unit but broadcast an army-wide aura
   (Hive Tyrant → Tyrant Guard; Abaddon → Terminators/Chosen; Syll'esske, a
   MONSTER that attaches → Daemonettes). `LeaderAbility.attach_keys` now decouples
   the attach target from the aura gate; `bind_leaders` prefers it, falling back
   to `host_keys`. Populate `attach_keys` for these cases.
2. **`lookup_ability` substring-name matching — NOT DONE (blocker).** It matches
   by substring on profile name only, so it cannot disambiguate cross-faction
   identical names. This must take a faction / UNIT_CATALOG-key argument.
   - **Cross-faction identical names** (unfixable by ordering): `Sorcerer` ×3
     (CSM / Thousand Sons / Emperor's Children, different hosts); `Sorcerer in
     Terminator Armour` ×2 (CSM gets TSON's Scarab Occult key today = never
     fires); `Master of Executions` ×2 (CSM vs World Eaters); `Ministorum Priest`
     ×2 (AM vs Sororitas).
   - **Within-faction substring collisions** (fixable by pinning longer names
     first): Space Marines `Captain` / `Chaplain` / `Librarian` / `Apothecary`
     variants ALL currently inherit the generic `_MARINE_HOSTS`
     (assault_intercessor + tactical) — **wrong for nearly every one** (Gravis →
     Aggressors/Eradicators/Heavy Intercessors; Phobos → Phobos squads;
     Terminator → Terminator squads; etc.). Same for `Chaos Lord` variants,
     `Shield-Captain` in Allarus/on Jetbike, `Exalted Sorcerer on Disc`.

## Pre-existing REGISTRY BUGS found (fix during gap-fill)

- **Typhus** host_keys = `plague_marines` (WRONG) → real: Blightlord/Deathshroud
  Terminators + Poxwalkers. Typhus's FNP never reaches its real led unit.
- **Chronomancer/Technomancer** use `_NECRON_HOSTS` (incl. Lychguard) — over-broad;
  Technomancer also missing Canoptek Wraiths.
- **Ynnari Archon/Succubus** route to *Drukhari* keys (substring collision) — a
  Ynnari Archon can't attach to Drukhari Kabalites.
- **Hive Tyrant / Swarmlord / Neurotyrant** DO attach to Tyrant Guard — current
  code comment wrongly denies it; Swarmlord & The Visarch entirely absent from
  the registry (violates the §13 fail-loud convention applied to Magnus/etc.).
- **Chief Librarian Mephiston** is Lone Operative but matches the generic
  `Librarian` substring → inherits `fnp=5` + `_MARINE_HOSTS` = live fabrication.
- **Grand Master in Nemesis Dreadknight** (VEHICLE, non-attaching) matches
  `Grand Master` → would wrongly inherit infantry hosts.
- **Roboute Guilliman / Belisarius Cawl**: registry carries host_keys but BSData
  shows no "attached to" text for either (both MONSTER Epic Heroes) — verify /
  likely should be non-attaching.
- **Votann Kâhl** baseline (gate off) host_keys missing Einhyr Hearthguard.

## Multi-leader & special cases (the mechanic already allows N leaders per squad)

- **Necron**: Crypteks (all 5) + Orikan co-attach *even if* an Overlord / Royal
  Warden (a "Noble") is already attached — a Warriors/Immortals unit legitimately
  carries TWO Leaders. **Cryptothralls is NOT an attach target** — it's a unit
  that *joins* a Cryptek-led unit via its own "Cryptek Retinue" ability; do NOT
  add `necrons_cryptothralls` to any host_keys.
- **Sororitas**: Dogmata/Dialogus/Hospitaller/Imagifier co-attach onto a Battle
  Sisters Squad alongside a Canoness/Palatine. Also add `celestian_insidiants` as
  a host wherever `dominion_squad` appears (reciprocal rule BSData omits).
- **Space Marines**: most support characters (Apothecary/Chaplain/Librarian/
  Ancient/Lieutenant) stack with a Captain/Chapter Master/Lieutenant.
- **Cybernetica Datasmith**: MANDATORY attach to Kastelan Robots (undeployable
  otherwise) and **loses the INFANTRY keyword while attached** — a concrete
  attach-changes-keywords case for the logical-unit view.
- **AM Death Rider Commissar [Legends]**, **SM Cato Sicarius + Marneus Calgar**:
  further stacking clauses.

## Unmappable hosts (no UNIT_CATALOG key — flag, do not invent)

`Mek Gunz` (Ork Big Mek/Mek), `XV9 Hazard Battlesuits` (T'au Shas'o R'alai
Legends), `Infantry Squad` (AM Quartermaster Cadre Legends), `Hellflayers`
(Daemons Tormentbringer), `Kravek Morne` character itself (CSM, absent from
UNIT_CATALOG). Breaka Boyz missing from the cached BSData `Orks.cat.gz` (stale
cache; Wahapedia lists it on Warboss/Big Mek/Painboy/Ghazghkull) — consider
`python -m code.bsdata.fetch` refresh.

## Coverage summary (from the four read-only gap-fill agents, all BSData v10.6.0)

| Group | Real gaps (attach, not registered) | Correctly non-attaching |
|---|---|---|
| Imperial (AM, Astartes+successors, Custodes, Sisters, GK, AdMech, Knights) | AM: Commissar/Primaris Psyker/Ministorum Priest/command squads (+Legends); Custodes: Aleya/Knight-Centura/Valerian/Allarus+Jetbike Shield-Captains; Sisters: Canoness/Palatine/Dogmata line (+insidiants); GK: Brotherhood Champion/Techmarine/Crowe; AdMech: Skitarii Marshal/Datasmith/Enginseer/Technoarcheologist; SM: ~all wargear variants + named heroes (huge — substring-collision) | **Imperial Knights: ALL** (Lone Op + Titanic); Mephiston/Sanguinor/Shrike (Lone Op); Guilliman/Calgar-in-armour edge |
| Chaos (CSM, DG, WE, EC, TSON, ChaosKnights, Daemons) | CSM: Fabius/Haarken/Huron/MoE/Firebrand/Reave-captain + Chaos Lord variants; DG: Lord of Virulence/Plaguecaster/support characters (shared profile); WE: Kharn/Invocatus/Lord-on-Jugg/MoE/Slaughterbound; EC: Lucius/Lord Exultant/Kakophonist/Sorcerer; TSON: Sorcerer/Tzaangor Shaman/Exalted-on-Disc; Daemons: Skullmaster/Karanak/Fateskimmer/Epidemius/Syll'esske/etc. | **Chaos Knights: ALL**; all Primarchs/Greater Daemons/Daemon Princes |
| Xenos-1 (Necrons, Orks, T'au, Votann) | Necrons: Psychomancer/Geomancer/Royal Warden/Orikan/Imotekh/Skorpekh+Lokhust Lords; Orks: ~all bosses (Ghazghkull/Beastboss/Snikrot/Zodgrod/Weirdboy/Meks); T'au: Farsight/Commanders/Darkstrider/Kroot Shapers; Votann: Ûthar/Champion/Grimnyr/Iron-master/Memnyr/Berehk | C'tan/Silent King/Shadowsun (Lone Op)/Wazdakka (Lone Op) |
| Xenos-2 (Aeldari, Drukhari, Tyranids, GSC) | Aeldari: Phoenix Lords/Eldrad/Warlock/Troupe Master/Visarch (+Yvraine/Autarch/Farseer incomplete); Drukhari: Drazhar/Haemonculus/Lelith/Lady Malys; Tyranids: Swarmlord/Hive Tyrant/Neurotyrant/Broodlord/Old One Eye/Primes; GSC: Abominant/Magus/Clamavus/Iconward/Biophagus/etc. | Kelermorph/Sanctus/Death Jester/Solitaire/Deathleaper (Lone Op); Avatar/Yncarne/synapse monsters; Lictor/Neurolictor (NOT characters) |

Full per-leader host_keys + citations are in the four agent transcripts and the
Imperial agent's machine-readable scratch dump
(`…/scratchpad/leaders_extracted_imperium2.json`, 181 entries). Apply
programmatically after the `lookup_ability` disambiguation lands.

## UPDATE 2026-07-12 (later) — gap-fill DATA-APPLIED, cap added

- **`data/leader_attach_targets.json` written and wired** — 372 attaching leaders,
  1021 leader→host pairs, every key validated against UNIT_CATALOG (extracted
  from BSData v10.6.0). `code/attachment.py::bind_leaders` consults this
  catalog-key map FIRST (unique keys → no substring collisions), then the
  registry as fallback. This **obsoletes the `lookup_ability` refactor for
  ATTACHMENT** (the map bypasses the collisions); the refactor is still needed
  only for the separate AURA-buff bugs (Typhus FNP etc.), which this file does
  NOT touch (calibration-neutral for auras). The known bugs (Typhus, Ynnari,
  Hive Tyrant/Swarmlord, Neurotyrant's wider hosts, Syll'esske, Datasmith) are
  all encoded CORRECTLY in the JSON.
- **`_MAX_LEADERS_PER_SQUAD = 2`** — a bodyguard unit takes at most 2 leaders
  (10e: one, occasionally two — Cryptek + a Noble). Excess leaders stay
  unattached/exposed. This is faithful and REVEALS AM's real problem: the
  archetype fields ~10 characters with ~2 host squads, so 8 stay exposed —
  a list-realism artifact (likely the 5-model Cadian Command Squad being tagged
  CHARACTER at all). The per-unit COUNTING fix is the robust lever; attachment
  is capped by list realism.
- **N=40 AM screen (cap + full map): mean 27→29.8 (+2.8pp)**, redistributed vs
  the pre-gap-fill screen (Sororitas +10, Chaos Knights +10, DG +7.5; World
  Eaters −15 — attribute: WE is character-light, AM loses old inflated
  Assassination profit). Byte-identical off holds; tests +0.

## UPDATE 2026-07-12 (later 2) — the LIST-HOSTING fix unlocks attachment

The faithful cap revealed AM's real problem: the archetype **under-fields host
squads** (leaders = ~100% guaranteed spine; their bodyguard infantry = 20-40%
lottery tail; char:host-squad ratio 2.16-2.34:1), so most leaders are orphaned
and attachment can't protect them. **`SWEG_LEADER_HOSTED`** (`code/archetypes.py`
`_ensure_leader_hosts`, gated, byte-identical off): after the template lottery
realizes an army, guarantee each attaching Leader has ceil(leaders/2) host squads
(the 2-per-squad cap) — "no list takes a Leader it cannot put in a squad." Missing
hosts are added to the seed counts; `_random_fill` absorbs the cost so points stay
~2000 (verified 1988). Ratio 2.34→1.79 (within cap → all leaders can attach).

**Full-stack AM screen (N=20, OFF vs attach+count vs FULL=+hosting):** mean
20.8 → 22.5 → **30.0 (+9.2 over OFF, ~5x the attach+count-only +1.7)**. The
Assassination craters break open (Astartes 5→30, Chaos Knights 10→35, Imperial
Knights 0→25) and the World Eaters regression RECOVERS (35→45). New mirror to
watch: Adepta Sororitas −20 (character-heavy opponent — its leaders now protected
too, so AM loses old Assassination profit). This confirms the full chain:
under-hosting suppresses attachment; pairing leaders with squads is the key lever.

## UPDATE 2026-07-13 — GLOBAL paired screen (N=8, CRN vs sc63a anchor)

The eval harness is NOT broken (an earlier "~5%-everyone" read was scoped-run
pollution — `--factions X` leaves the other 21 factions playing only 1 opponent,
field-weighted to ~0, garbaging the aggregate MAE; the per-game engine
`_run_battle_job` is correct). Full N=8 eval (`--workers 14`, ~9 min foreground —
the sim runs ~0.5-3s/game here, so full N>=20 exceeds the foreground cap and
background runs get killed; N=8 is the feasible directional read), paired via
`scripts/paired_delta.py` against the sc63a anchor:

| config | global gated-MAE delta | AM (paired) | notes |
|---|---|---|---|
| attach + count (no hosting) | **+0.10 (neutral)** | 22.4→29.1 (+6.6) | + Imperial Knights onto real; ADOPTABLE pending N=40 confirm |
| + hosting (full stack) | **+0.73 (worse)** | 22.4→30.6 (+8.2) | blanket ceil(leaders/2) over-buffs body-heavy factions (Votann/CSM/DG over-pole) |

**UPDATE (N=16, firmer — supersedes the N=8 "neutral" read):** attach+count paired
vs anchor = gated MAE OFF 3.33 -> ON 3.91, **delta +0.58 (WORSE)** — the N=8 movers
were NOT all noise; they persist/grow. Decisive over-poles: Votann +12.0, Chaos
Space Marines +14.6, Custodes +7.3, Necrons +7.5; decisive improvements: Imperial
Knights -4.4 (toward real), Grey Knights -15.7. AM only +2.6 (field-weighting +
side-rolloff dilute the concentrated crater gains). The full stack (+hosting) is
+0.73. HONEST REFRAME: both configs WORSEN the global gated-MAE because the sim's
per-faction calibration was tuned WITHOUT these rules — adding faithful mechanics
re-shuffles the residuals (fixes AM/IK, pushes character-heavy factions over as
their leaders now survive). Per the project's FIDELITY-FIRST doctrine ("never gate
a faithful mechanic off to protect the metric; a headline rise is expected +
authorized; re-fitting to force win rates is forbidden"): `SWEG_LEADER_ATTACH` +
`SWEG_SECONDARY_PER_UNIT` are CORRECT 10e rules -> adopt fidelity-first + RE-CALIBRATE
the over-poled factions to the new baseline (NOT reject). `SWEG_LEADER_HOSTED` is a
list HEURISTIC (not a rule) -> needs per-faction realism rework before adoption.
Screen logs: `data/_atkcnt_on_n16_log.json`, `data/_leaderfix_on_n8_log.json`.

**Original (N=8) verdict, kept for context:** the `SWEG_LEADER_ATTACH` +
`SWEG_SECONDARY_PER_UNIT` pair read ~global-neutral (+0.10) at N=8 AND fixes
AM + Imperial Knights. `SWEG_LEADER_HOSTED` is the right IDEA (real lists pair leaders
with squads) but the wrong MECHANISM globally — the blanket host-add over-corrects;
the faithful version is per-faction realistic archetype host counts
(`archetypes.py` template realism), not `ceil(leaders/2)`. Caveats: N=8 is noisy
(only ~5 factions clear the 95% CI; AM reads "flat"); Chaos Space Marines +18 /
Grey Knights −14 in attach+count are unexplained movers to check at N=40.
Screen logs: `data/_leaderfix_on_n8_log.json`, `data/_atkcnt_on_n8_log.json`
(join vs `data/_anchor_sc63a_n80_log.json`).

## UPDATE 2026-07-13 (later) — SWEG_LEADER_HOSTED REWORKED (per-faction, template-capped)

The blanket `ceil(leaders/2)` add over-buffed body-heavy factions (+0.73 full stack)
and echoed the rejected `SWEG_TEMPLATE_REALIZE` starvation failure. Reworked
`_ensure_leader_hosts` to **cap host-restoration at each faction's own archetype
template host count** — restore what the lottery DROPPED (the real orphaning bug),
never add past the template's designed composition. A Leader whose hosts the
template omitted still gets one host (min 1), capped at ceil(leaders/2). Per-faction
by construction (uses each template), byte-identical off.

Reworked full-stack N=8 paired vs anchor: **gated MAE +0.56** (vs blanket +0.73,
vs attach+count-only +0.58) with **AM +9.3 (decisive)** — the cap recovered the
over-buff (Votann +10.5→+8.9 etc.) WHILE preserving/improving AM's fix. Net: the
reworked hosting now adds real AM value (+9.3 vs attach+count-alone's +2.6) at ~zero
extra global cost. Remaining +0.56 is the FAITHFUL attach+count re-shuffle
(fidelity-first adopt + re-calibrate, not reject). N=8 noisy; AM decisive.
Screen log: `data/_hostfix_on_n8_log.json`.

## Remaining phases

0. **The three gates are complementary** — `SWEG_LEADER_HOSTED` (list) +
   `SWEG_LEADER_ATTACH` (protection) + `SWEG_SECONDARY_PER_UNIT` (counting).
   `SWEG_LEADER_HOSTED` applies to ALL factions (no-op where leaders already have
   hosts / don't attach), so its calibration effect is global.
1. **THE ADOPTION GATE (owner call):** full N=80 anchor gated-MAE with the gates
   on (`SWEG_LEADER_HOSTED=1 SWEG_LEADER_ATTACH=1 SWEG_SECONDARY_PER_UNIT=1`) vs the sc63a anchor —
   this global fidelity change is decided on the gated metric across all 22
   factions, NOT the AM-scoped +2.8. Attribute the World Eaters −15.
2. On adoption: flip defaults on, DELETE the Look Out Sir branch + its deprecated
   citation.
3. Fold Bring It Down into `SWEG_SECONDARY_PER_UNIT` (per-unit, total-wounds
   brackets) — near-zero impact, cohesion only.
4. Separate lane (AURA bugs, NOT attachment): fix the registry host_keys bugs
   (Typhus→Plague Marines wrong, Ynnari→Drukhari, Chronomancer/Technomancer
   over-broad) that mis-route leader AURAS — each shifts a faction's calibration,
   so screen individually.
5. Optional: the Cadian Command Squad CHARACTER-keyword faithfulness check
   (list-realism; feeds both the character count and the Assassination pool).

---

## Multi-model leader squad de-duplication (`SWEG_LEADER_SQUAD_DEDUPE`, built 2026-07-13, default-OFF)

The follow-up item #5 above turned out to be a **catalogue keyword-promotion bug**
with a clean fix. The 2026-07-13 AM re-anchor pilot (see `PILOT_FINDINGS.md`
Matchup 2) localised AM's persistent Assassination bleed to it.

**The bug.** BSData applies the `CHARACTER` keyword to a unit at unit-level, but a
class of multi-model **Leader** units are squads in which only ONE embedded model
(the commander) is a CHARACTER — the rest are ordinary bodyguards. The mapper has
no per-model keyword data (`model_loadouts` carries names only), so all N models
inherit `CHARACTER`. Because every one then satisfies `_is_attachable_character`,
`bind_leaders` treated each of the N models as a **separate leader** competing for
the host's `_MAX_LEADERS_PER_SQUAD` (=2) slots — so one Cadian Command Squad
consumed both slots on a Cadian Shock Troops squad and **crowded the army's real
single-model characters (Cadian Castellans) out of a host**, leaving them unbound =
unprotected = Assassination-exposed. Per-unit Assassination already groups by
`squad_id`, so this was **not** a raw over-count — the harm was the crowding-out.

**Full scope (Wahapedia-verified, 2 agents, 2026-07-13).** 14 units, all the
identical "one embedded CHARACTER officer in an otherwise non-character squad, each
a Leader" pattern:

| Unit | Faction | models / chars | in archetype template |
|---|---|---|---|
| Cadian Command Squad | Astra Militarum | 5 / 1 | yes |
| Dark Apostle | Chaos Space Marines | 3 / 1 | yes |
| Brôkhyr Iron-master | Leagues of Votann | 5 / 1 | yes |
| Krieg Command Squad | Astra Militarum | 6 / 1 | random-fill |
| Catachan Command Squad | Astra Militarum | 5 / 1 | random-fill |
| Militarum Tempestus Command Squad | Astra Militarum | 5 / 1 | random-fill |
| Dark Commune | Chaos Space Marines | 5 / 1 | random-fill |
| Traitor Enforcer | Chaos Space Marines | 2 / 1 | random-fill |
| Ravenwing Command Squad | Dark Angels | 3 / 1 | random-fill |
| Grimnyr | Leagues of Votann | 3 / 1 | random-fill |
| Hyperadapted Raveners | Tyranids | 5 / 1 | random-fill |
| Rogue Trader Entourage | Imperial Agents | 4 / 1 | random-fill |
| Quartermaster Cadre Squad *(Legends)* | Astra Militarum | 5 / 1 | catalogue only |
| Hell's Last *(Legends)* | Astra Militarum | 5 / 1 | catalogue only |

Confirmed **NOT** bugs (left as-is): every EPIC HERO retinue (Calgar, Ghazghkull,
Grimaldus, Silent King …) — genuine character units; Great Unclean One and Ogryn
Bodyguard (single-model, legitimately CHARACTER); Rein and Raus (two Epic Heroes).

**The fix (chosen: dedupe, not keyword-strip).** These are all *genuine 10e
Leaders* with a real embedded character, so stripping `CHARACTER` in overrides
would break their leader function and remove them as legitimate Assassination
targets — a fidelity loss. Instead `bind_leaders`, when the gate is ON, groups
attachable-character model-Units by `squad_id` and binds each **group** as one
leader (one host slot, all its models pointed at the same host). This keeps every
unit faithful (still a 1× Assassination target, still a real leader), fixes the
crowding-out for all 14 units at once (and any future BSData unit of this shape),
and needs no per-unit data edits or re-citations. Implemented in `code/attachment.py`
(`_squad_dedupe_enabled`, `_resolve_attach`, restructured `bind_leaders`). Covered
by the existing `simulator.leader_attachment` citation (a refinement of the same
rule, not a new one — `audit_rules` clean).

**Verification.** Byte-identical off — function-level proof over 3876 unit-bindings
(22 factions × 3 seeds) vs a verbatim copy of the old loop, zero mismatches; plus a
sc64a game-replay control. Gate-on frees a crowded-out Castellan (seed-5 probe:
Command Squad 5-models-scattered → one host; one Castellan None → bound). Tests:
`tests/test_targeting_restrictions.py::LeaderSquadDedupeTests` (off hogs both slots /
Castellan exposed; on binds squad as one / Castellan protected). Full suite 51/2 =
baseline (0 new). `run.py --cli` clean.

**ADOPTED 2026-07-13 (default-ON; anchor sc65a).** Paired CRN screen, N=40 vs
sc64a (18,480 matched games): gated MAE **2.41 → 2.22 A-frame / 2.83 → 2.73
symmetrized** — a fidelity fix that *improves* both frames, not one adopted despite
a cost. AM (deepest under-pole) **28.7 → 30.6% symmetrized (+1.9pp)**, its
symmetrized gated error 13.44 → 11.49. The pre-screen worry that it would push the
over-poles (CSM Dark Apostle, Votann Iron-master) further over was **wrong**: the
dominant effect is AM — the most character-crowded army — finally protecting its
Castellans, so across AM's matchups the over-poled factions that fed on it drift
*toward* their real rates (Votann −1.5, CSM −1.0, Aeldari −1.0, all toward target).
No single faction is decisive at N=40 (paired CIs span 0) but the gate fires (AM 97
/ Votann 152 / CSM 80 flips) and every direction is consistent, so the global
improvement is real but diffuse; an N=80 confirm would sharpen the per-faction
picture. `SWEG_LEADER_SQUAD_DEDUPE=0` reverts byte-identically to sc64a. The exact
ON log was promoted as `data/_anchor_sc65a_n40_log.json` (protocol rule 4).

Related follow-up still open: Lord Solar Leontus (MOUNTED EPIC HERO) is mis-bound as
an infantry leader — a separate attach-eligibility fix — and one Cadian Castellan +
the Ogryn Bodyguard remain unbound in AM's list because only 2 host squads × 2 slots
exist (a host-count / `_MAX_LEADERS_PER_SQUAD` question, not this bug).
