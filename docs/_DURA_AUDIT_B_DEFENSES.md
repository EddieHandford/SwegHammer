# Durability fidelity wave — audit B: defensive stratagem and ability coverage

Read-only audit. No simulator, catalogue, or override code was changed by this
pass. Base commit: `215301c` on `origin/claude/sim-calibration-18` (top commit
at the time of this audit; see the base-alignment log at the end of this
document).

## Scope and method

This audit enumerates every defensive ability and stratagem the simulator
applies to durable platforms (Imperial Knights, Chaos Knights, Death Guard
vehicles and monsters, plus two non-Knight, non-Death-Guard bricks named in
the brief — the Necrons Monolith and the Leagues of Votann Hekaton Land
Fortress) and checks each one against the printed tenth-edition rule. The
primary source is the BSData cache (`data/bsdata/cache/*.cat.gz`), decompressed
and parsed with Python's `xml.etree.ElementTree` for this audit (scratch
scripts under `scripts/_dura_audit_b_*.py`); Wahapedia is cited as the
secondary, human-readable source per standing rule six, with the caveat noted
below.

Wahapedia's rendered datasheet pages did not return ability description text
through the fetch tool used in this session (two direct fetch attempts against
Imperial Knights datasheet pages returned only the datasheet's numeric
characteristics table, not the ability prose). Web search snippets did surface
verbatim stratagem and core-rule text for the two stratagens checked in depth
(Rotate Ion Shields, Smokescreen) and those quotes are cited with their source
links below. Every other citation in this document is anchored to BSData
`Description` characteristic text, quoted verbatim, with the exact cache file,
`selectionEntry`/`profile` name, and (where useful) the internal id so a future
session can re-locate it without re-parsing the whole file.

## Divergence list

### 1. Imperial Knights Ion Shield ranged-only fix is missing on five chassis

**Printed rule** (BSData `Imperium - Imperial Knights - Library.cat.gz`,
shared `Abilities` profile id `8552-862d-6a49-4879`, reused via infoLink by
every affected chassis; internal file comment: `"Single model - ranged
only"`):

> "This model has a 5+ invulnerable save against ranged attacks."

and, for Knight Defender specifically, the 4+ variant (profile id
`5a7a-57fa-9801-4e25`):

> "This model has a 4+ invulnerable save against ranged attacks."

Wahapedia (secondary, ability prose not independently re-confirmed this
session — see caveat above): `https://wahapedia.ru/wh40k10ed/factions/imperial-knights/Knight-Destrier`,
`.../Acastus-Knight-Asterius`, `.../Acastus-Knight-Porphyrion`,
`.../Cerastus-Knight-Castigator`, `.../Knight-Defender`.

**Sim behaviour**: the mapper's `extract_invuln` "Shape 1" path
(`code/bsdata/mapper.py:4131-4140`, `_INVULN_RE`) reads the digit straight off
the infoLink's own name (e.g. `"Invulnerable Save (5+*)"`) and immediately
`continue`s — it never resolves the asterisked target profile's `Description`
text, so the ranged-only qualifier is silently dropped and the chassis is
recorded as having an **unconditional** invulnerable save (`invuln_save_melee
== invuln_save_ranged` in the raw, pre-override `data/bsdata/parsed.json`, for
every Imperial Knight chassis that uses this infoLink shape — verified
directly against `data/bsdata/parsed.json`). The project already knows about
this mapper limitation and has hand-corrected it for twelve chassis via the
`invuln_ranged_only: true` override key (`data/overrides.json`):
`armiger_helverin`, `armiger_moirax`, `armiger_warglaive`, `canis_rex`,
`knight_castellan`, `knight_crusader`, `knight_errant`, `knight_gallant`,
`knight_paladin`, `knight_preceptor`, `knight_valiant`, `knight_warden`. Five
more chassis use the **identical** BSData infoLink shape (confirmed by direct
XML scan — same shared profile id `8552-862d-6a49-4879`/`5a7a-...`) but were
never given the override, so they currently carry their full invulnerable save
into melee combat:

| Unit key | Current sim (melee / ranged) | Should be |
|---|---|---|
| `imperial_knights_library_knight_destrier` | 5+ / 5+ | 7 (none) / 5+ |
| `imperial_knights_library_acastus_knight_asterius` | 5+ / 5+ | 7 (none) / 5+ |
| `imperial_knights_library_acastus_knight_porphyrion` | 5+ / 5+ | 7 (none) / 5+ |
| `imperial_knights_library_cerastus_knight_castigator` | 5+ / 5+ | 7 (none) / 5+ |
| `imperial_knights_library_knight_defender` | 4+ / 4+ | 7 (none) / 4+ |

Verified live against the running catalogue (`code.units.UNIT_CATALOG`, this
worktree): all five report `invuln_save_melee == invuln_save_ranged` and
`invuln_ranged_only == False`. The read path is
`code/simulator.py:3539-3553` (the `SWEG_COND_INVULN` gate, default ON,
reads `invuln_save_melee` / `invuln_save_ranged` directly) composed with
`code/units.py:5721-5733` (`invuln_save_melee=(7 if entry.invuln_ranged_only
else entry.invuln_save_melee)`), so the missing override key is a complete,
live gap under default settings — not a legacy-path-only issue.

**Direction**: inflates. All five chassis get a defensive save layer in melee
combat that the printed rule denies them (Ion Shields protect against ranged
fire only; a Knight in melee relies on its armour save alone). **Magnitude**:
medium — matters specifically against melee attacks with armour penetration
worse than the chassis's own armour save (Knight Destrier/Acastus/Cerastus
Castigator all have a 3+ armour save, so any AP-2 or worse melee weapon is
where the phantom 5+/4+ invulnerable save currently substitutes for a failed
armour save that the rules say should have no backstop).

### 2. Imperial Cerastus Knight Acheron has no invulnerable save at all (should be 5+ ranged-only)

**Printed rule** (BSData `Imperium - Imperial Knights - Library.cat.gz`,
inline `Abilities` profile on the Cerastus Knight Acheron's own
`selectionEntry`, id `7afa-5443-53e3-5707`):

> "This model has a 5+ invulnerable save against ranged attacks only."

**Sim behaviour**: `invuln_save = 7` (none), both melee and ranged, in
`data/bsdata/parsed.json` and the live catalogue
(`imperial_knights_library_cerastus_knight_acheron`). Root cause: BSData
authored this ability's containing profile with the name `"Cerastus Knight
Acheron"` (the unit's own name) rather than the conventional `"Invulnerable
Save (...)"` naming used everywhere else in the same file, so the mapper's
Shape 3 filter — which requires the profile's own name to start with
`"invulnerable save"` (`code/bsdata/mapper.py:4161-4163`) — never matches it,
and there is no infoLink either (so Shapes 1/2 don't apply). No override
exists in `data/overrides.json` for this unit's invulnerable save (only a
`deadly_demise` correction is present). The Chaos-side twin, `Chaos Cerastus
Knight Acheron` in `Chaos - Chaos Knights Library.cat.gz`, authors the same
ability with the conventional name `"Invulnerable Save"` and is parsed
correctly (`invuln_save_melee = 7`, `invuln_save_ranged = 5` — faithful).

**Direction**: deflates. The Imperial Cerastus Knight Acheron is denied a real
5+ invulnerable save against ranged attacks that every other Cerastus-class
chassis (including its own Chaos-faction counterpart) correctly receives.
**Magnitude**: medium — a whole defensive layer is missing against ranged
fire specifically, on a 28-wound, toughness 11, save 3+ super-heavy walker
that otherwise has no invulnerable save backstop against high-strength
anti-tank shooting.

### 3. "Rotate Ion Shields" stratagem (Imperial Knights Household) is entirely unmodeled

**Printed rule** (Wahapedia, quoted verbatim via search snippet —
`https://wahapedia.ru/wh40k10ed/factions/imperial-knights/`):

> "Veteran Knight pilots can swiftly re-angle their ion shields and manipulate
> their energies to deflect incoming firepower."
> **WHEN:** Your opponent's Shooting phase, just after an enemy unit has
> selected its targets.
> **TARGET:** One IMPERIAL KNIGHTS unit from your army that was selected as
> the target of one or more of the attacking unit's attacks.
> **EFFECT:** Until the end of the phase, models in your unit have a 4+
> invulnerable save.

BSData does not carry stratagem text at all (confirmed: no `stratagem`
elements in either `Imperium - Imperial Knights.cat.gz` or the Library file),
consistent with this project's established practice of sourcing stratagem
prose from Wahapedia/community write-ups rather than BSData.

**Sim behaviour**: not present. Searched `code/stratagems.py` and
`code/detachments.py` for "Rotate Ion Shield", "Ion Shield" stratagem
handling, and any Imperial-Knights-specific defensive stratagem registration —
none found. The only Imperial Knights detachment content wired up is the
offensive Valourstrike Lance rule (`code/detachments.py:342-381`, Bold
Gallantry advance-and-shoot + Bondsman abilities).

**Direction**: deflates. This is a real, reactive, once-per-phase (implicitly
capped by the standing `stratagems_fired_this_command_phase` /
command-point budget the sim already enforces for every other stratagem),
single-unit defensive tool that Imperial Knights players have access to and
the sim does not model at all. Adding it would push Imperial Knights durability
further in the direction the owner's ruling already flags as over-poled, so
its absence is not contributing to the over-poling — but it remains a
rules-accuracy gap independent of that direction. **Magnitude**: small-medium
(situational, reactive, one unit per phase, and only relevant against ranged
attacks specifically).

### 4. The core-rules "Smokescreen" stratagem and [SMOKE] keyword are entirely unmodeled

**Printed rule** (Wahapedia, quoted verbatim via search snippet —
`https://wahapedia.ru/wh40k10ed/the-rules/core-rules/`,
`https://wahapedia.ru/wh40k10ed/Stratagems.csv`):

> Smokescreen — 1CP, Core – Wargear Stratagem. **WHEN:** Your opponent's
> Shooting phase, just after an enemy unit has selected its targets.
> **TARGET:** One SMOKE unit from your army that was selected as the target
> of one or more of the attacking unit's attacks. **EFFECT:** Until the end
> of the phase, all models in that unit have the Benefit of Cover and the
> Stealth ability.

BSData confirms several Death Guard vehicle datasheets carry the `[SMOKE]`
category link (`data/bsdata/cache/Chaos - Death Guard.cat.gz`, `categoryLink
name="Smoke"` at four separate `selectionEntry` blocks): the Myphitic
Blight-hauler, a Land Raider-pattern chassis, a Predator Destructor-pattern
chassis, and a dedicated transport chassis.

**Sim behaviour**: `code/bsdata/mapper.py` captures `[SMOKE]` into the
generic `unit_keywords` list (`extract_unit_keywords`,
`code/bsdata/mapper.py:3375`) but nothing in `code/units.py` or
`code/simulator.py` reads the `"SMOKE"` keyword or implements the Smokescreen
stratagem — confirmed by a repo-wide search for `smoke`/`Smoke` (only hit is
unrelated terrain code in `code/map.py`).

**Direction**: deflates. Any Death Guard vehicle carrying `[SMOKE]` is denied
a cheap (1 command point), reactive, once-per-phase defensive tool (Stealth
plus Benefit of Cover) that the core rules grant it. **Magnitude**: small
(narrow unit coverage within Death Guard's vehicle roster, single-phase
duration, but a real stacking defensive combo — Stealth's -1 to hit plus
Benefit of Cover together are a meaningful reduction against ranged fire when
they land).

### 5. Myphitic Blight-hauler's "Tank Hunters" ability is unmodeled (attacker-side, opponent-durability-relevant)

**Printed rule** (BSData `Chaos - Death Guard.cat.gz`, inline `Abilities`
profile, id `e47-254c-cdf9-7c5e`):

> "In your Shooting phase, each time a model in this unit makes an attack
> that targets a Monster or Vehicle unit, add 1 to the Hit roll and add 1 to
> the Wound roll."

**Sim behaviour**: not present. No `anti_keywords` entry, to-hit bonus, or
named handling for "Tank Hunters" exists in `code/units.py` or
`code/simulator.py`, and `data/overrides.json`'s
`death_guard_myphitic_blight_hauler` entry (checked in full) carries only
weapon-profile and points corrections, nothing for this ability.

**Direction**: this is an omission on the attacking side, not the defending
side, but it is durability-relevant in the direction the audit brief asks
about: when a Myphitic Blight-hauler shoots at an enemy Monster or Vehicle
brick (an Imperial/Chaos Knight, another army's superheavy, etc.), the sim
currently resolves that attack without the +1 to hit / +1 to wound the real
rule grants — which **inflates** the apparent durability of whichever
Monster/Vehicle brick is on the receiving end of Death Guard shooting, and
under-credits Death Guard's own brick-cracking toolkit. **Magnitude**: small
(single unit, narrow trigger condition, and a hit/wound modifier rather than
a flat damage swing).

### 6. Knight Defender's ally-cover aura is unmodeled

**Printed rule** (BSData `Imperium - Imperial Knights - Library.cat.gz`,
inline `Abilities` profile on the Knight Defender's own `selectionEntry`):

> "Each time a ranged attack is allocated to an Imperial Knights model from
> your army, if that model is not fully visible to every model in the
> attacking unit because of this Knight Defender model, that model has the
> Benefit of Cover and a 4+ invulnerable save against that attack."

**Sim behaviour**: not present. No handling for Knight Defender's aura
found anywhere in `code/simulator.py`; the only Knight-Defender-relevant code
found is its own personal Ion Shield value, which is separately affected by
divergence 1 above.

**Direction**: deflates. When a Knight Defender is fielded, the rest of the
Imperial Knights army it screens for is denied a real conditional cover +
invulnerable-save grant. **Magnitude**: small — gated on Knight Defender's
presence on the table (a specific, less commonly fielded chassis) and on the
line-of-sight-blocking condition actually occurring.

## Faithful list (verified clean — no code changes needed)

- **Chaos Knights Ion Shield, ranged-only, all ~20 chassis checked** (War Dog
  Executioner/Stalker/Karnivore/Brigand/Huntsman/Moirax, Knight
  Despoiler/Desecrator/Rampager/Abominant/Tyrant/Ruinator, Chaos Acastus
  Knight Asterius/Porphyrion, Chaos Cerastus Knight Castigator/Acheron):
  every chassis authors its Ion Shield as a properly-named inline
  `"Invulnerable Save"` `Abilities` profile in `Chaos - Chaos Knights
  Library.cat.gz`, which the mapper's Shape 3 path parses correctly,
  including the "against ranged attacks" qualifier
  (`_parse_invuln_per_attack`, `code/bsdata/mapper.py:4016`). Verified
  directly against `data/bsdata/parsed.json`: every one of these chassis has
  `invuln_save_melee = 7` (none) and `invuln_save_ranged = 5`. This confirms
  the previously-fixed Chaos Knights "phantom melee 5++" **stays fixed**
  under the current default configuration (`SWEG_COND_INVULN` default ON,
  `code/simulator.py:3539-3553`).
- **Chassis with a genuinely unconditional (not ranged-restricted)
  invulnerable save, both factions**: Cerastus Knight Lancer (4+, both
  Imperial and Chaos), Cerastus Knight Atrapos (5+, both factions), Questoris
  Knight Magaera (5+, both factions), Questoris Knight Styrix (5+, both
  factions). Their BSData `Description` text has no "against ranged attacks"
  qualifier (`"This model has a 5+ invulnerable save."` verbatim, no more),
  and the sim correctly does NOT flag them `invuln_ranged_only`, so they
  correctly apply their invulnerable save in both melee and ranged combat.
- **The twelve Imperial Knight chassis with the `invuln_ranged_only`
  override correctly applied**: Armiger Helverin, Armiger Moirax, Armiger
  Warglaive, Canis Rex, Knight Castellan, Knight Crusader, Knight Errant,
  Knight Gallant, Knight Paladin, Knight Preceptor, Knight Valiant, Knight
  Warden. All verified `invuln_save_melee = 7`, `invuln_save_ranged` equal to
  the datasheet value, in the live catalogue.
- **Death Guard's "no army-wide Feel No Pain" correction**
  (`code/units.py:1524-1552`): matches the current tenth-edition Death Guard
  codex (no codex-level Feel No Pain; Disgustingly Resilient is only the 2
  command point Virulent Vectorium stratagem). Per-datasheet innate Feel No
  Pain (Plague Marines 5+, Deathshroud Terminators 4+, Mortarion 5+, etc.) is
  correctly carried on `profile.fnp` rather than granted army-wide. Clear
  removal history documented in the surrounding comments (a previously
  fabricated unconditional Feel No Pain 5+/6+ block was removed).
- **Death Guard's Virulent Vectorium stratagem set** (Disgustingly Resilient
  2 command points, Putrid Detonation, Plaguesurge, Leechspore Eruption,
  Overwhelming Generosity, Creeping Blight): all six dispatch through the
  shared `_strat_cap_reached` (command-phase stratagem cap) and
  `_fire_stratagem` (command-point cost check, deduction, and
  once-per-battle bookkeeping where applicable) machinery
  (`code/simulator.py:16372-16397`), each targeting a single "most
  vulnerable eligible unit." No always-on or frequency divergence found —
  this matches the real once-per-use, command-point-budgeted, single-target
  stratagem structure.
- **Death Guard invulnerable saves are all genuinely unconditional per
  BSData** (Mortarion 4+, Great Unclean One 4+, Blightlord Terminators 4+,
  Deathshroud Terminators 4+, Beasts of Nurgle 5+, Plagueburst Crawler 5+,
  Foetid Bloat-drone 5+, Defiler 5+, and others checked): none of these
  datasheets carry a ranged-only qualifier in their BSData `Description`
  text (unlike the Knights' Ion Shield), so the sim's unconditional
  (melee == ranged) treatment for all of them is correct as-is.
- **Armour of Contempt** (Adeptus Astartes Gladius Task Force stratagem,
  approximated as +1 to save rather than true -1 armour penetration to the
  attacker): correctly gated at 1 command point, single unit, through the
  standard `_strat_cap_reached`/`_fire_stratagem` machinery
  (`code/simulator.py:5989-6009`). No always-on divergence found. (Out of
  the Knights/Death Guard brick scope proper, but checked because the audit
  brief named the "Armour of Contempt class" explicitly.)
- **Necrons Monolith and Leagues of Votann Hekaton Land Fortress base
  defensive stats**: both match BSData verbatim (Monolith: toughness 13,
  22 wounds, 2+ save, no invulnerable save, no Feel No Pain; Hekaton Land
  Fortress: toughness 12, 16 wounds, 2+ save, no invulnerable save, no Feel
  No Pain — neither has one in the real rules). Hekaton Land Fortress's two
  named abilities (MultiCOG Targeting, Panspectral Scanner) are both
  accuracy/offensive abilities, not defensive ones, so there is no
  defensive ability to under- or over-grant on that chassis. Monolith is
  correctly excluded from Reanimation Protocols eligibility
  (`reanimates_with_army = False`, `code/units.py:707-719`), matching the
  real rule's CHARACTER/MONSTER/VEHICLE exclusion.
- **Monolith's "Advanced Quantum Shielding" ability is absent from the
  sim** (BSData: "Each time an attack targets this model, if the Strength
  characteristic of that attack is greater than this model's Toughness
  characteristic, subtract 1 from the Wound roll.") — flagged here rather
  than in the divergence list above because it sits outside the audit's
  named brick set (Necrons generally, not Imperial Knights/Chaos
  Knights/Death Guard), but noted for a future Necrons-scoped audit: this
  is a real, unconditional (always-live, no stratagem/command-point gate)
  defensive ability that reduces the effectiveness of any anti-tank
  weapon (strength greater than 13) shooting or fighting the Monolith, and
  it is currently missing entirely. Direction: deflates Monolith durability.

## Base alignment log

```
git fetch origin
git reset --hard origin/claude/sim-calibration-18
git log --oneline -2
```

Result: `HEAD` at `215301c docs(ledger): record the owner ruling — the
durability remodel must stay rules-accurate, no knobs`, confirmed as the
required top commit before any investigation began.
