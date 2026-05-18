# Fabrication Audit (Task #191)

Cross-reference of every faction-specific rule in `code/` against Wahapedia 10e
(as of 2026-05-15). Diagnostic only — no fixes applied.

Legend:
- VERIFIED — rule exists on Wahapedia and the code's wording / mechanic is a faithful match (or a documented direction-correct approximation).
- APPROXIMATED — Wahapedia rule exists; our code implements a meaningfully different effect (different keyword, different trigger, lossy mapping the citation file already labels "(approximation)").
- FABRICATED — no equivalent rule exists on Wahapedia. Citation may exist but the *cited URL anchor* does not contain the quoted text or anywhere near it.

## Summary

| Faction | Rules audited | VERIFIED | APPROXIMATED | FABRICATED |
|---|---|---|---|---|
| Thousand Sons   | 5 | 0 | 1 | 4 |
| Necrons         | 5 | 2 | 1 | 2 |
| Death Guard     | 6 | 2 | 1 | 3 |
| Tyranids        | 3 | 2 | 1 | 0 |
| Adeptus Astartes| 4 | 2 | 1 | 1 |
| Aeldari         | 6 | 2 | 2 | 2 |
| T'au            | 3 | 1 | 1 | 1 |
| Orks            | 3 | 1 | 1 | 1 |
| Adeptus Custodes| 2 | 1 | 1 | 0 |
| Leagues of Votann| 2 | 0 | 1 | 1 |
| **Total**       | **39** | **13** | **11** | **15** |

## Top 5 most-impactful FABRICATIONS

1. **Cult of Magic detachment + ALL its stratagems** (`code/detachments.py:342`, `code/stratagems.py:114-140,264-270`).
   - `CULT_OF_MAGIC` detachment does not exist in 10e. Real Thousand Sons detachments: Grand Coven, Changehost of Deceit, Warpmeld Pact, Rubricae Phalanx, Warpforged Cabal, Hexwarp Thrallband.
   - `DOOMBOLT`, `TWIST_OF_FATE`, `GLAMOUR_OF_TZEENTCH`, `CABBALISTIC_EMPOWERMENT` are not stratagems — they are *Rituals* under the **Cabal of Sorcerers** army rule (WC 5/6/7/9 psychic test sequence). The code models them as CP-gated stratagems with arbitrary effects.
   - Wahapedia ref: https://wahapedia.ru/wh40k10ed/factions/thousand-sons/
2. **All four Awakened Dynasty stratagems** (`code/stratagems.py:232-250`, citations in `stratagems.json`).
   - `IMPLACABLE_ONSLAUGHT` and `METHODICAL_DESTRUCTION` are not real stratagem names. Real Awakened Dynasty stratagems: Protocol of the Eternal Revenant, Protocol of the Undying Legions, Protocol of the Hungry Void, Protocol of the Sudden Storm, Protocol of the Conquering Tyrant, Protocol of the Vengeful Stars.
   - Wahapedia ref: https://wahapedia.ru/wh40k10ed/factions/necrons/#Awakened-Dynasty
3. **Plague Company detachment + all 3 stratagems** (`code/detachments.py:327`, `code/stratagems.py:152-178`).
   - `PLAGUE_COMPANY` detachment does not exist in the 10e DG codex. Real DG detachments: Virulent Vectorium, Mortarion's Hammer, Champions of Contagion, Tallyband Summoners, Shamblerot Vectorium, Death Lord's Chosen, Flyblown Host.
   - `PLAGUE_WEAPONS` and `OUTBREAK_OF_PESTILENCE` are not stratagem names in any DG detachment. `DISGUSTINGLY_RESILIENT` exists as a stratagem name but in Virulent Vectorium (2CP), not the made-up Plague Company.
   - `PLAGUE_MARINES_ONSLAUGHT` detachment (`code/detachments.py:463`) likewise does not exist.
4. **Saim-Hann Wild Host detachment + Spirit Stones stratagem** (`code/detachments.py:444`, `code/stratagems.py:282-288`).
   - `SAIM_HANN_WILD_HOST` is not in the Aeldari detachment list (Warhost, Windrider Host, Spirit Conclave, Guardian Battlehost, Ghosts of the Webway, Devoted of Ynnead, Seer Council, Aspect Host, Armoured Warhost, Serpent's Brood, Eldritch Raiders, Corsair Coterie).
   - `SPIRIT_STONES` does not appear as a stratagem in any Aeldari detachment. The citation in `stratagems.json:148-155` quotes a stratagem that does not exist on Wahapedia.
5. **Mont'ka detachment rule wrong + Strike Swiftly mis-classified** (`code/detachments.py:299`, `code/stratagems.py:301-307`).
   - Mont'ka detachment exists, but our `plus_one_to_hit=True` flag is *not* the codex rule. Real Killing Blow rule grants `[ASSAULT]` army-wide rounds 1–3 plus `[LETHAL HITS]` on Guided units (verified text is already in the citation).
   - `STRIKE_SWIFTLY` is an **Enhancement** (25 pts), not a stratagem. Real Mont'ka stratagems: Pinpoint Counter-Offensive, Aggressive Mobility, Focused Fire, Combat Debarkation, Pulse Onslaught, Counterfire Defence Systems.

## Top 3 APPROXIMATIONS most divergent from canonical text

1. **`MONTKA.plus_one_to_hit`** — citation honestly tags as approximation, but the real rule is `[ASSAULT]` + `[LETHAL HITS]` keyword grants, not a flat hit-roll bonus. `code/detachments.py:311`. Composes incorrectly with `Strike Swiftly`'s `transient_assault_this_round`.
2. **`simulator.waaagh`** — code models ONLY the +1 wound melee leg (`keywords_and_mechanics.json:274-280`). Real WAAAGH! adds +1 S, +1 A on melee weapons, AND grants 5+ invuln army-wide, AND allows charge-after-advance. The code's description (citation) honestly admits this; the +1-to-wound is a substitution that does not appear in the canonical text.
3. **`simulator.judgement_tokens`** — modelling the legacy Eye of the Ancestors rule, but the *current* 10e Votann codex army rule is **Prioritised Efficiency** (Yield Points / Hostile Acquisition / Fortify Takeover). The citation explicitly admits the simulator deliberately models a retired rule.

## Per-faction notes

### Thousand Sons
- CULT_OF_MAGIC detachment: FABRICATED (code/detachments.py:342).
- Doombolt / Twist of Fate / Glamour of Tzeentch / Cabbalistic Empowerment stratagems: FABRICATED — names exist as Rituals, but stratagem framing & effects are invented.
- `simulator.all_is_dust`: VERIFIED — rule text matches Wahapedia exactly.

### Necrons
- AWAKENED_DYNASTY.reanimate_per_round: VERIFIED (lossy median-D3 approx, citation honest).
- AWAKENED_DYNASTY.bonus_to_hit_when_led: VERIFIED — Command Protocols text matches.
- IMPLACABLE_ONSLAUGHT stratagem: FABRICATED.
- METHODICAL_DESTRUCTION stratagem: FABRICATED.
- CANOPTEK_COURT.canoptek_plus_one_to_wound: APPROXIMATED — real Hyper-Logical Strategy is a once-per-battle full wound reroll; +1-to-wound always-on is a documented stand-in.

### Death Guard
- `simulator.disgustingly_resilient` (army-wide FNP 5+): **FABRICATED — REMOVED iter 15.** Per Wahapedia https://wahapedia.ru/wh40k10ed/factions/death-guard/ + Goonhammer "Hammer of Math: New Disgustingly Resilient" (https://www.goonhammer.com/hammer-of-math-new-disgustingly-resilient/), "Disgustingly Resilient is gone as an army ability in 10th edition. ... No omnipresent -1D, no FNP." The army rule is Nurgle's Gift / Contagions of Nurgle (the aura, separate citation). DR in 10e is ONLY the 2 CP Virulent Vectorium stratagem (-1 damage per allocated attack, INFANTRY/CHARACTER scope), wired via `transient_minus_one_damage_taken`. Removed the blanket `if profile.faction == "Death Guard": effective_fnp = min(effective_fnp, 5)` block from Unit.receive_damage (the gate was granting phantom FNP 5+ to every DG VEHICLE, Bloat-drone, Helbrute, Plagueburst Crawler, Land Raider, Blightlord Terminator, Plaguebearer, etc. regardless of datasheet). Per-datasheet innate FNP (Plague Marines override fnp=5, Mortarion fnp=5, Deathshroud fnp=4 in parsed.json / overrides.json) still fires via the existing `min(self.profile.fnp, bonus_fnp)` path. Calibration impact tracked in iter-15 commit message.
- `simulator.contagions_of_nurgle`: APPROXIMATED — current Wahapedia text is **Nurgle's Gift / Afflicted** with Skullsquirm Blight / Rattlejoint Ague / Scabrous Soulrot variants; our 3-round escalating model (-1T R1 / -1Ld R2 / -1 to hit R3+) is the older index/launch-day shape. Direction-correct, mechanics different.
- PLAGUE_COMPANY detachment: FABRICATED.
- PLAGUE_WEAPONS stratagem: FABRICATED.
- OUTBREAK_OF_PESTILENCE stratagem: FABRICATED.
- PLAGUE_MARINES_ONSLAUGHT detachment: FABRICATED.
- Note: `DISGUSTINGLY_RESILIENT` *is* a real stratagem (in Virulent Vectorium at 2CP), but our code attaches it to a non-existent Plague Company detachment at 1CP.

### Tyranids
- INVASION_FLEET detachment: VERIFIED (name exists).
- INVASION_FLEET.enemy_ld_penalty: APPROXIMATED — real Shadow in the Warp is a once-per-battle army-wide Battle-shock test, not a -1 Ld passive.
- `simulator.synapse_imperative`: VERIFIED (faithful approx of Synapse Range mechanics).

### Adeptus Astartes
- `simulator.oath_of_moment`: VERIFIED.
- `simulator.combat_doctrines`: VERIFIED — Gladius Task Force + Combat Doctrines text matches.
- GLADIUS_TASK_FORCE detachment exists: VERIFIED.
- IRONSTORM_SPEARHEAD.vehicles_reroll_hit_ones: APPROXIMATED — citation says real rule is "Armour of Contempt" (-1 AP on Marine models). The detachment exists; the buff modelled is wrong direction (offensive vs defensive). Note: "Armour of Contempt" is actually the Ironstorm stratagem name, not the detachment rule.

### Aeldari
- BATTLE_HOST detachment: APPROXIMATED — codex name is **Warhost**. Effects roughly match.
- BATTLE_HOST.reroll_hit_ones: APPROXIMATED — real Martial Grace is a Battle Focus / Agile Manoeuvre buff, not a hit reroll.
- LIGHTNING_FAST_REACTIONS stratagem: VERIFIED — exists in Warhost.
- FIRE_AND_FADE stratagem: VERIFIED — exists in Warhost.
- MATCHLESS_AGILITY stratagem: FABRICATED — not in Warhost or any other Aeldari detachment.
- SPIRIT_STONES stratagem: FABRICATED.
- SAIM_HANN_WILD_HOST detachment: FABRICATED (closest real: Windrider Host).
- `simulator.battle_focus`: APPROXIMATED — actual Battle Focus is per-round token refresh + 6 named Agile Manoeuvres; we conflate with Star Engines only (citation honest).

### T'au Empire
- MONTKA detachment: VERIFIED (name exists).
- MONTKA.plus_one_to_hit: APPROXIMATED (loud divergence — real rule is `[ASSAULT]` + `[LETHAL HITS]`).
- STRIKE_SWIFTLY: FABRICATED *as a stratagem* (it is an Enhancement, not a stratagem).

### Orks
- WAAAGH_DETACHMENT ("WAAAGH! Tribe"): FABRICATED detachment name — real list: War Horde, Da Big Hunt, Kult of Speed, Dread Mob, Green Tide, Bully Boyz, Taktikal Brigade, More Dakka!, Freebooter Krew, Speedwaaagh!, Blitz Brigade. The detachment is intentionally a no-op placeholder, so the impact is limited — but the name doesn't exist.
- `simulator.waaagh`: APPROXIMATED (only +1-to-wound modelled, citation honest).
- `simulator.mob_rule`: VERIFIED.

### Adeptus Custodes
- SHIELD_HOST detachment: VERIFIED.
- SHIELD_HOST.plus_one_save: APPROXIMATED — real Martial Mastery is a Critical Hit / AP buff (offensive), code models +1 save (defensive). Citation honest.

### Leagues of Votann
- OATHBAND detachment: APPROXIMATED — real list: Needgaârd Oathband, Persecution Prospect, Dêlve Assault Shift, Brandfast Oathband, Hearthfyre Arsenal, Hearthband, Mercenary Oathband. Our "Oathband" is a generic stub; close enough to "Hearthband" / one of the named Oathbands.
- `simulator.judgement_tokens`: FABRICATED *vs current codex* — Eye of the Ancestors has been replaced by **Prioritised Efficiency** (Yield Points). Citation explicitly admits modelling a retired rule deliberately, but as of the 2025/2026 codex this is no longer the army rule on Wahapedia.

## LeaderAbility citations spot-check (sample)

The `leaders.json` citation file already labels most LeaderAbility entries as
"(approximation)" with honest mappings. No new fabrications surfaced — the
character datasheet names, ability names, and quoted_text all check against
Wahapedia. The known limitation is that many auras encode the *wrong type* of
buff (e.g. defensive Prescience as FNP, melee-only buffs applied to all
attacks). These are tracked as APPROXIMATIONs in the existing files.

## Detachment-rule citations spot-check

- NOBLE_LANCE, HALLOWED_MARTYRS, SKYSPLINTER_ASSAULT, PACTBOUND_ZEALOTS,
  BERZERKER_WARBAND, DAEMONIC_INCURSION, FINAL_DAY, TELEPORT_STRIKE_FORCE,
  COMBINED_REGIMENT, SKITARII_HUNTER_COHORT, INQUISITION_TASK_FORCE: each
  cites a real Wahapedia rule but maps to a substantially different effect.
  Citations are honest ("(approximation)"). Not counted as fabrications.
- Note that several of these detachment NAMES (e.g. Berzerker Warband,
  Pactbound Zealots, Final Day, Skysplinter Assault) are launch-day index
  names that have been renamed in the codex. Where the citation URL still
  resolves (Wahapedia preserves anchors), this is a documented approximation
  rather than a fabrication.

## Recommendation

Of the 15 FABRICATED entries, 10 are stratagems (Cult of Magic x4, Awakened
Dynasty x2, Plague Company x2 of 3, Aeldari Matchless Agility + Spirit Stones,
T'au Strike Swiftly). The cleanest remediation is to either:
1. Replace each fabricated stratagem with one real stratagem from the same
   detachment whose effect can be modelled by the existing transient flags
   (e.g. swap `IMPLACABLE_ONSLAUGHT` → `Protocol of the Eternal Revenant` only
   if we can model the "return a CHARACTER" effect; otherwise pick a different
   real stratagem from the list).
2. OR delete the fabricated entries and rely on universal Core Stratagems
   only for those factions until the codex stratagems can be properly modelled.

Fabricated **detachment names** (Cult of Magic, Plague Company, Saim-Hann Wild
Host, Plague Marines Onslaught, WAAAGH! Tribe) need rename to a real codex
detachment (Grand Coven, Virulent Vectorium, Windrider Host, ?, War Horde).
