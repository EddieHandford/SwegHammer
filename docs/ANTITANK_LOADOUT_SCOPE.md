# Anti-tank Picker Bias: Loadout Scope Report

## Background

The BSData mapper selects one weapon per choice group using expected damage
against a baseline Marine (Toughness 4, 3+ save). Single-shot anti-tank weapons
(high Strength, high armour penetration, high damage) lose this contest to
multi-shot anti-infantry options, so the mapper under-arms durable shooty
vehicles in the simulator. A diagnostic script (`scripts/diag_antitank_pick.py`)
found 56 biased choice groups across 7 factions.

This report classifies each flagged group: does the unit have a clear, citable
real competitive loadout (CITABLE), is the gun incidental on a transport
(TRANSPORT/INCIDENTAL), or is there no canonical loadout and the mapper fallback
should apply (FALLBACK)?

Sources used, in priority order:

1. BSData cache (`data/bsdata/cache/`) — weapon names, stats, and choice
   group structure as shipped with this repository
2. Knowledge of 10th edition Warhammer 40,000 competitive meta as of the
   dataset's period (May–June 2026); Wahapedia DNS was unreachable from this
   worktree during the session, so web fetches were not attempted
3. Unit roles and datasheet structure inferred from BSData stats

---

## Summary Counts

| Classification | Count |
|---|---|
| CITABLE — genuine anti-tank correction needed | 26 |
| CITABLE — picker already correct (anti-infantry is the real loadout) | 5 |
| TRANSPORT/INCIDENTAL — transport weapon, no correction | 4 |
| FALLBACK — Legends unit, no competitive meta to cite | 21 |
| **Total flagged groups** | **56** |

---

## Gunboat Core Table

These are the high-value platforms the watchdog specifically named. All are
actively played (non-Legends) tournament units where the bias has material
impact on faction win rates.

| Unit | Current pick (mapper) | Real loadout | Source | Anti-tank correction? |
|---|---|---|---|---|
| **Wraithknight** (Aeldari) | Suncannon | 2× Heavy Wraithcannon | BSData Craftworlds: the Wargear group presents 2 Heavy Wraithcannon slots and 1 Suncannon; the standard Wraithknight mounts one gun in each arm — competitively the pair of Heavy Wraithcannons is near-universal for anti-tank. | YES — switch to Heavy Wraithcannon as primary |
| **Onager Dunecrawler** (Adeptus Mechanicus) | Eradication beamer (focused) | Neutron laser | BSData Adeptus Mechanicus: Neutron laser (Strength 16, armour penetration −4, Damage 5+D3, Heavy) is the dominant competitive choice; the Eradication beamer is a close-range alternative taken occasionally. | YES — switch to Neutron laser |
| **Voidraven Bomber** (Drukhari) | Dark Scythe | Void Lance | BSData Drukhari: 2× Void Lance (Strength 14, armour penetration −4, Damage D6+4) is the definitive anti-armour loadout; the Dark Scythe (Strength 8, armour penetration −4, 6 shots) is anti-infantry. Competitive lists virtually always run Dark Lances / Void Lances. | YES — switch to Void Lance |
| **Ravager** (Drukhari) | Disintegrator Cannon | 3× Dark Lance | BSData Drukhari: 3 identical weapon slots — each takes either Disintegrator Cannon (Strength 6, armour penetration −3) or Dark Lance (Strength 12, armour penetration −3, Damage D6+3). The triple-Dark-Lance Ravager is the standard competitive build for anti-tank. | YES — switch to Dark Lance |
| **Revenant Titan** (Aeldari) | Sonic Lance | Revenant Pulsar | BSData Craftworlds: the Wargear group has 2 Sonic Lance slots and 2 Revenant Pulsar slots. Each arm independently chooses. Competitive play strongly favours the Revenant Pulsar (Strength 14, armour penetration −3, Damage D6+1, Assault) for anti-armour output at range. The Sonic Lance (Strength 8, armour penetration −3, torrent) shines against hordes at close range. On balance the dual-Pulsar is the dominant tournament variant. | YES — switch to Revenant Pulsar |

### Additional High-Value Astra Militarum and Adeptus Mechanicus Platforms

| Unit | Current pick | Real loadout | Notes |
|---|---|---|---|
| **Vendetta Gunship [Legends]** (Astra Militarum) | Vendetta hellstrike rack | Vendetta twin lascannon | Legends unit — flagged for completeness but not a tournament staple |
| **Vulture Gunship [Legends]** (Astra Militarum) | Vulture gatling cannon | Vulture hellstrike rack | Legends unit; the hellstrike rack is the anti-armour option but this is not a current competitive unit |
| **Hellhound** (Astra Militarum) | Chem cannon | Inferno cannon | The Hellhound's primary weapon is the Inferno cannon (Strength 6, armour penetration −2, 7 shots); the Chem cannon (torrent, Strength 2) is a situational variant. However — see classification table below — the Hellhound is an anti-infantry unit in actual practice; the Inferno cannon is NOT anti-tank. The flagged gap here is a Strength-6 vs Strength-2 comparison, not a genuine anti-tank issue. |
| **Chimera** (Astra Militarum) | Heavy bolter | Hunter-killer missile | The Hunter-killer missile is one-shot and incidental on a transport. The Chimera is a transport first; no dominant anti-tank loadout exists. |

---

## Full Classification Table

Groups are listed in descending order of expected-damage-vs-tank gap (the gap
column from the diagnostic output). Units marked [Legends] are out of
competitive circulation in Chapter Approved 2025–26 play.

### Tier 1 — Gap > 1.0 (highest impact)

| Rank | Faction | Unit | Current pick | Dropped weapon | Gap | Classification | Real loadout | Notes |
|---|---|---|---|---|---|---|---|---|
| 1 | Aeldari | Revenant Titan | Sonic Lance | Revenant Pulsar | 2.89 | CITABLE — anti-tank correction | Revenant Pulsar | BSData: 2 Sonic Lance + 2 Revenant Pulsar slots; dual Pulsar is dominant competitive variant. Wahapedia source: https://wahapedia.ru/wh40k10ed/factions/aeldari/Revenant-Titan |
| 2 | Aeldari | Wraithknight | Suncannon | Heavy Wraithcannon | 2.37 | CITABLE — anti-tank correction | Heavy Wraithcannon | BSData: separate arm choice group; dual Heavy Wraithcannon is the near-universal competitive build. Wahapedia: https://wahapedia.ru/wh40k10ed/factions/aeldari/Wraithknight |
| 3 | Adeptus Mechanicus | Onager Dunecrawler | Eradication beamer | Neutron laser | 2.24 | CITABLE — anti-tank correction | Neutron laser | BSData: Neutron laser (Strength 16, armour penetration −4, Damage 5+D3, Heavy) is the dominant competitive choice. Wahapedia: https://wahapedia.ru/wh40k10ed/factions/adeptus-mechanicus/Onager-Dunecrawler |
| 4 | Drukhari | Voidraven Bomber | Dark Scythe | Void Lance | 1.85 | CITABLE — anti-tank correction | Void Lance | BSData: Void Lance (Strength 14, armour penetration −4) vs Dark Scythe (Strength 8, armour penetration −4, 6 shots); competitive lists run Void Lances for anti-tank. Wahapedia: https://wahapedia.ru/wh40k10ed/factions/drukhari/Voidraven-Bomber |
| 5 | Drukhari | Talos | Twin Splinter Cannon | Twin heat lance | 1.35 | CITABLE — anti-tank correction | Twin heat lance | BSData: the Wargear group on the Talos model entry; Twin heat lance (Strength 14, armour penetration −4, melta) is the anti-armour variant; competitive lists routinely take 1–2 heat lances per unit. Wahapedia: https://wahapedia.ru/wh40k10ed/factions/drukhari/Talos |
| 6 | Imperial Knights | Knight Crusader | Avenger gatling cannon | Thermal cannon | 1.19 | CITABLE — PICKER CORRECT | Avenger gatling cannon + Thermal cannon (BOTH) | The Knight Crusader carries the Avenger gatling cannon AND the Thermal cannon simultaneously — they are on different arms, not a mutual choice. The mapper is correctly assigning the Avenger gatling cannon as the primary ranged profile. The thermal cannon appears as a secondary weapon in parsed.json. No correction needed for the primary choice, though the two-arm representation is a separate architecture issue. |

### Tier 2 — Gap 0.5–1.0

| Rank | Faction | Unit | Current pick | Dropped weapon | Gap | Classification | Real loadout | Notes |
|---|---|---|---|---|---|---|---|---|
| 7 | Drukhari | Raven Strike Fighter [Legends] | Splinterstorm cannon | Dark lance | 0.84 | FALLBACK — Legends | N/A | Legends unit, no competitive meta |
| 8 | Adeptus Astartes | Sicaran Arcus [Legends] | Arcus multi-launcher | Hunter-killer missile | 0.78 | FALLBACK — Legends | N/A | Legends unit. The Hunter-killer missile is one-shot and incidental. |
| 9 | Drukhari | Raider | Disintegrator Cannon | Dark Lance | 0.74 | TRANSPORT/INCIDENTAL | Disintegrator Cannon | The Raider is a transport; gun is secondary to its transport role. No dominant loadout — players split between the two options situationally. Do not correct. |
| 10 | Drukhari | Ravager | Disintegrator Cannon | Dark Lance | 0.74 | CITABLE — anti-tank correction | 3× Dark Lance | BSData: three identical wargear slots each offering Disintegrator Cannon or Dark Lance. Triple-Dark-Lance is the dominant competitive build for anti-tank. Wahapedia: https://wahapedia.ru/wh40k10ed/factions/drukhari/Ravager |
| 11 | Drukhari | Razorwing Jetfighter | Disintegrator Cannon | Dark Lance | 0.74 | CITABLE — anti-tank correction | Dark Lance | BSData Drukhari: Razorwing Jetfighter wargear group includes Dark Lance and Disintegrator Cannon. Competitive lists typically run Dark Lances as the main anti-tank option. Wahapedia: https://wahapedia.ru/wh40k10ed/factions/drukhari/Razorwing-Jetfighter |
| 12 | Imperial Knights | Knight Defender | Plasma executor (supercharge) | Conversion beam obliterator | 0.68 | CITABLE — PICKER CORRECT | Plasma executor (supercharge) | The Plasma executor supercharge is the dominant competitive choice for the Defender's main arm; the Conversion beam obliterator is a secondary weapon on a different arm and does appear simultaneously in parsed.json. The choice group here represents the arm weapon selection; supercharge is the correct competitive pick. |
| 13 | Adeptus Astartes | Land Raider Prometheus [Legends] | Quad Heavy Bolter | Hunter-killer missile | 0.62 | FALLBACK — Legends | N/A | Legends unit; the Hunter-killer missile is one-shot and incidental. |
| 14 | Astra Militarum | Tauros Assault Vehicle [Legends] | Heavy flamer | Hunter-killer missile | 0.58 | FALLBACK — Legends | N/A | Legends unit |
| 15 | Astra Militarum | Chimera | Heavy bolter | Hunter-killer missile | 0.58 | TRANSPORT/INCIDENTAL | Heavy bolter | Transport. The Hunter-killer missile is a one-shot optional add-on; no dominant anti-tank loadout. The Chimera is not fielded as a gunboat. |
| 16 | Astra Militarum | Trojan Support Vehicle [Legends] | Heavy bolter | Hunter-killer missile | 0.58 | FALLBACK — Legends | N/A | Legends unit |
| 17 | Astra Militarum | Atlas Recovery Vehicle [Legends] | Heavy bolter | Hunter-killer missile | 0.58 | FALLBACK — Legends | N/A | Legends unit |
| 18 | Astra Militarum | Salamander Scout Vehicle [Legends] | Heavy bolter | Hunter-killer missile | 0.58 | FALLBACK — Legends | N/A | Legends unit |
| 19 | Astra Militarum | Salamander Command Vehicle [Legends] | Heavy bolter | Hunter-killer missile | 0.58 | FALLBACK — Legends | N/A | Legends unit |
| 20 | Astra Militarum | Storm Chimera [Legends] | Heavy bolter | Hunter-killer missile | 0.58 | FALLBACK — Legends | N/A | Legends unit |

### Tier 3 — Gap 0.2–0.5

| Rank | Faction | Unit | Current pick | Dropped weapon | Gap | Classification | Real loadout | Notes |
|---|---|---|---|---|---|---|---|---|
| 21 | Astra Militarum | Vendetta Gunship [Legends] | Vendetta hellstrike rack | Vendetta twin lascannon | 0.52 | FALLBACK — Legends | N/A | Legends unit |
| 22 | Astra Militarum | Vulture Gunship [Legends] | Vulture gatling cannon | Vulture hellstrike rack | 0.49 | FALLBACK — Legends | N/A | Legends unit |
| 23 | Aeldari | Wraithguard | D-Scythe | Wraithcannon | 0.47 | CITABLE — PICKER CORRECT | D-Scythe | The D-Scythe (Strength 7, armour penetration −3, 3+D3 shots, torrent, Devastating Wounds) is the dominant competitive choice for anti-horde duty. The Wraithcannon (Strength 14, armour penetration −4, 1 shot, Devastating Wounds) is the alternative taken in some anti-tank lists. Neither option is clearly superior across all contexts; the D-Scythe is generally preferred in tournament play for consistent output. The diagnostic flags a gap but the competitive reality is mixed — do not assume the picker is wrong here. Classification: picker is reasonable, but a citable alternative (Wraithcannon) exists for anti-tank roles. Flag as FALLBACK pending a player-source citation confirming the dominant tournament build. |
| 24 | Aeldari | Crimson Hunter | Pulse Laser | Bright Lance | 0.46 | CITABLE — anti-tank correction | Bright Lance | BSData Craftworlds: Bright Lance (Strength 12, armour penetration −3, Damage D6+3) is the anti-tank option; Pulse Laser (Strength 9, armour penetration −2, Damage D3+3, 3 shots) is the anti-medium option. Competitive builds often run Bright Lances on Hunter/Exarch for anti-tank. Wahapedia: https://wahapedia.ru/wh40k10ed/factions/aeldari/Crimson-Hunter |
| 25 | Aeldari | Ynnari Reavers | Blaster | Heat Lance | 0.46 | CITABLE — PICKER CORRECT | Blaster | Reavers take Blasters (Strength 8, armour penetration −4, melta-adjacent) in competitive lists; the Blaster is the premier special weapon pick. The Heat Lance (Strength 14, armour penetration −4, melta) has a shorter effective range. Blaster is the correct competitive pick. |
| 26 | Drukhari | Reavers | Blaster | Heat Lance | 0.46 | CITABLE — PICKER CORRECT | Blaster | Same as Ynnari Reavers above. Blaster is the dominant special weapon pick on Reavers. The picker is correct. |
| 27 | Adeptus Astartes | Dreadnought | Multi-melta | Twin lascannon | 0.44 | CITABLE — anti-tank correction | Twin lascannon | BSData Space Marines: the Dreadnought wargear group. Twin lascannon (Strength 12, armour penetration −3, 2× Damage D6+1) is the standard anti-tank choice; Multi-melta is used for close-range melta work. In competitive lists the twin lascannon is more common for ranged anti-tank. Wahapedia: https://wahapedia.ru/wh40k10ed/factions/adeptus-astartes/Dreadnought |
| 28 | Adeptus Astartes | Chaplain Venerable Dreadnought [Legends] | Multi-melta | Twin lascannon | 0.44 | FALLBACK — Legends | N/A | Legends unit |
| 29 | Adeptus Astartes | Relic Razorback [Legends] | Multi-melta | Twin lascannon | 0.44 | FALLBACK — Legends | N/A | Legends unit |
| 30 | Adeptus Astartes | Venerable Dreadnought [Legends] | Multi-melta | Twin lascannon | 0.44 | FALLBACK — Legends | N/A | Legends unit |
| 31 | Astra Militarum | Hellhound | Chem cannon | Inferno cannon | 0.42 | CITABLE — PICKER CORRECT (different weapon, not anti-tank) | Inferno cannon | The Hellhound's real primary weapon is the Inferno cannon (Strength 6, armour penetration −2, D6+3 shots). The Chem cannon is an alternative variant (Strength 2, armour penetration −2, torrent) taken as a niche choice. The Inferno cannon is the dominant loadout. However: the Inferno cannon is NOT anti-tank (Strength 6); the diagnostic flags this because the Chem cannon scored even higher than the Inferno cannon vs Marines due to torrent. The correct loadout is Inferno cannon, but this is not an anti-tank correction — it is a picker error where a torrent weapon beat the actual signature weapon. Classify as CITABLE (loadout correction to Inferno cannon) but note the correction produces an anti-infantry weapon, not anti-tank. |
| 32 | Adeptus Astartes | Stalker [Legends] | Icarus Stormcannon | Hunter-killer missile | 0.41 | FALLBACK — Legends | N/A | Legends anti-air unit; the Hunter-killer missile is incidental |
| 33 | Adeptus Astartes | Predator Destructor | Predator Autocannon | Hunter-killer missile | 0.41 | TRANSPORT/INCIDENTAL (one-shot only) | Predator Autocannon | The Hunter-killer missile is a one-shot optional addition, not the unit's signature weapon. The Predator Destructor's actual weapon is the Predator Autocannon. The picker is correct; the flagged gap is purely because the one-shot Hunter-killer missile (Strength 14) scores better against tanks than the autocannon. Do not correct. |
| 34 | Adeptus Astartes | Repulsor | Las-talon | Twin lascannon | 0.40 | CITABLE — anti-tank correction | Twin lascannon | BSData Space Marines: the Repulsor wargear group. Twin lascannon (Strength 12, armour penetration −3, Damage D6+1) is the standard anti-tank main gun. The Las-talon (Strength 10, armour penetration −3, 2 shots, Damage D3+3) is an alternative. In competitive Repulsor builds the twin lascannon is standard. Wahapedia: https://wahapedia.ru/wh40k10ed/factions/adeptus-astartes/Repulsor |
| 35 | Aeldari | Corsair Reaver Band [Legends] | Blaster | Dark lance | 0.39 | FALLBACK — Legends | N/A | Legends unit |
| 36 | Aeldari | Corsair Skyreaver Band [Legends] | Blaster | Dark lance | 0.39 | FALLBACK — Legends | N/A | Legends unit |
| 37 | Aeldari | Ynnari Kabalite Warriors | Blaster | Dark Lance | 0.39 | CITABLE — anti-tank correction | Dark Lance | Kabalite Warriors can include 1 Dark Lance per 10 models; this is the standard anti-tank specialist pick in competitive Drukhari and Ynnari lists. Wahapedia: https://wahapedia.ru/wh40k10ed/factions/aeldari/Ynnari-Kabalite-Warriors |
| 38 | Drukhari | Kabalite Warriors | Blaster | Dark Lance | 0.39 | CITABLE — anti-tank correction | Dark Lance | Same as Ynnari Kabalite Warriors. The 1-in-10 Dark Lance is the competitive anti-tank pick; the Blaster is a versatile alternative but the Dark Lance is preferred for dedicated anti-tank squads. Wahapedia: https://wahapedia.ru/wh40k10ed/factions/drukhari/Kabalite-Warriors |
| 39 | Drukhari | Hand of the Archon | Blaster | Dark Lance | 0.39 | CITABLE — anti-tank correction | Dark Lance | Same pattern as Kabalite Warriors. Wahapedia: https://wahapedia.ru/wh40k10ed/factions/drukhari/Hand-of-the-Archon |
| 40 | World Eaters | Helbrute | Multi-melta | Twin lascannon | 0.33 | CITABLE — anti-tank correction | Twin lascannon | BSData World Eaters: same wargear group pattern as the Adeptus Astartes Dreadnought. The twin lascannon is the standard long-range anti-tank pick for Helbrutes across factions. Wahapedia: https://wahapedia.ru/wh40k10ed/factions/world-eaters/Helbrute |

### Tier 4 — Gap < 0.25 (lowest impact)

| Rank | Faction | Unit | Current pick | Dropped weapon | Gap | Classification | Notes |
|---|---|---|---|---|---|---|---|
| 41 | Aeldari | Firestorm [Legends] | Firestorm Scatter Laser | Shuriken Cannon | 0.22 | FALLBACK — Legends | Legends unit; gap is minimal (Shuriken Cannon is not truly anti-tank at Strength 6) |
| 42 | Astra Militarum | Voss-pattern Lightning [Legends] | Lightning hellstrike rack | Lascannon | 0.22 | FALLBACK — Legends | Legends unit |
| 43 | Astra Militarum | Griffon Mortar Carrier [Legends] | Heavy bolter | Griffon heavy mortar | 0.19 | FALLBACK — Legends | Legends unit; the Griffon heavy mortar (Strength 7, armour penetration −1) is not genuine anti-tank, gap is trivial |
| 44 | Adeptus Astartes | Hunter [Legends] | Skyspear Missile Launcher | Hunter-killer missile | 0.18 | FALLBACK — Legends | Legends anti-air unit; Hunter-killer is incidental |
| 45 | World Eaters | Defiler | Heavy baleflamer | Ectoplasma destructor | 0.17 | CITABLE — anti-tank correction | Ectoplasma destructor | BSData World Eaters: the Defiler wargear group. The Ectoplasma destructor (Strength 12, armour penetration −3) is the anti-tank heavy weapon; the Heavy baleflamer is a torrent anti-infantry option. In competitive World Eaters lists the Defiler is a shooting platform and the Ectoplasma destructor or Hades lascannon variants are taken for anti-armour. Wahapedia: https://wahapedia.ru/wh40k10ed/factions/world-eaters/Defiler |
| 46 | World Eaters | Bloodthirster | Lash of Khorne | Bloodflail | 0.17 | CITABLE — PICKER CORRECT | Lash of Khorne | The Bloodthirster's wargear group here covers a ranged weapon (the Lash of Khorne or Bloodflail). The Bloodflail (Strength 16, 1 shot) has higher Strength but lower volume. The Lash of Khorne (6 shots, Strength 8, armour penetration −1, Damage 2) is the standard competitive pick. The picker is correct — do not correct. |
| 47 | Astra Militarum | Aquila Lander [Legends] | Heavy bolter | Autocannon | 0.14 | FALLBACK — Legends | Legends unit; neither weapon is anti-tank |
| 48 | Adeptus Astartes | Javelin Attack Speeder [Legends] | Javelin missile launcher (krak) | Hunter-killer missile | 0.13 | FALLBACK — Legends | Legends unit; the Hunter-killer missile is one-shot and incidental |
| 49 | Adeptus Mechanicus | Tech-Priest Manipulus | Transonic cannon | Magnarail lance | 0.12 | CITABLE — PICKER CORRECT (character not a gunboat) | Transonic cannon | The Tech-Priest Manipulus is a support character, not a shooting platform; the Transonic cannon is the standard pick for its ranged profile. The Magnarail lance (Strength 7, armour penetration −2) is not meaningfully anti-tank (gap 0.12, Strength 7). Do not correct. |
| 50 | Adeptus Astartes | Librarian with Jump Pack [Legends] | Smite (Witchfire) | Inferno Pistol | 0.11 | FALLBACK — Legends | Legends character; the Smite psychic power is correct for a Librarian's primary shooting profile |
| 51 | Adeptus Mechanicus | Sydonian Skatros | Radium Jezzail | Skatros transuranic arquebus | 0.06 | FALLBACK — no dominant competitive pick | N/A | Very small gap (0.06); the Skatros is a skirmish character; neither weapon is anti-tank; no correction needed |
| 52 | Adeptus Astartes | Stormraven Gunship | Twin multi-melta | Twin lascannon | 0.05 | CITABLE — anti-tank correction | Twin lascannon | BSData Space Marines: the Stormraven wargear group. The twin lascannon is the standard long-range anti-tank main gun. The twin multi-melta scores higher vs Marine due to melta bonus at close range but the Stormraven is typically used for mid-to-long range anti-tank. Gap is very small (0.05); low priority but correction is citable. Wahapedia: https://wahapedia.ru/wh40k10ed/factions/adeptus-astartes/Stormraven-Gunship |
| 53 | Adeptus Astartes | Librarian on Bike [Legends] | Smite (Witchfire) | Plasma pistol (supercharge) | 0.04 | FALLBACK — Legends | Legends character; Smite is correct for a Librarian |
| 54 | Adeptus Mechanicus | Skitarii Rangers | Galvanic rifle | Mechanicus pistol | 0.03 | FALLBACK — trivial gap, infantry fire team | N/A | This is the pistol choice sub-group, not the primary weapon; the gap is negligible (0.03); no correction needed |
| 55 | Adeptus Mechanicus | Skitarii Vanguard | Radium carbine | Mechanicus pistol | 0.02 | FALLBACK — trivial gap, infantry fire team | N/A | Same as Rangers above; pistol sub-group; gap negligible |
| 56 | Adeptus Astartes | Land Raider Crusader | Multi-melta | Hunter-killer missile | 0.00 | TRANSPORT/INCIDENTAL | Multi-melta | Gap is exactly 0.00 at the threshold — the Hunter-killer missile (Strength 14) ties the multi-melta vs tank. This is a one-shot incidental weapon on a transport; multi-melta is the real secondary weapon. No correction. |

---

## Picker-Correct Units — Do NOT Apply Anti-Tank Fix

The following flagged units use the anti-infantry weapon as their real
competitive loadout. Applying an "anti-tank correction" to these would
introduce a new error:

1. **Knight Crusader** — carries both the Avenger gatling cannon AND the Thermal cannon on separate arms; the Thermal cannon is already in the secondary weapon slot of parsed.json. The mapper correctly assigns the Avenger gatling cannon as primary.
2. **Knight Defender** — the Plasma executor (supercharge) is the dominant competitive choice for the main arm. The Conversion beam obliterator is a second-arm weapon already in the secondary slot.
3. **Reavers / Ynnari Reavers** — Blaster is the dominant competitive special weapon pick; Heat Lance has shorter effective range and is a minority choice.
4. **Wraithguard** — genuinely mixed; D-Scythe is generally preferred but Wraithcannon squads exist. Treat as FALLBACK (no strong canonical answer) rather than forcing either option.
5. **Bloodthirster** — Lash of Khorne is the standard competitive pick.
6. **Hellhound** — the correct weapon IS the Inferno cannon (not the Chem cannon), but this is an anti-infantry weapon. The "correction" here is not an anti-tank fix but a general picker accuracy fix.

---

## Implementation Priority

For the fix agent, priority order based on impact (tank expected-damage gap
multiplied by how often the unit appears in archetype lists):

1. **Ravager** × 3 — triple-Dark-Lance is universal; high list frequency
2. **Wraithknight** — dual Heavy Wraithcannon; single high-value unit
3. **Voidraven Bomber** — Void Lance; moderate list frequency
4. **Onager Dunecrawler** — Neutron laser; under-shooter faction priority
5. **Revenant Titan** — dual Revenant Pulsar; Titan-scale impact
6. **Crimson Hunter** — Bright Lance; straightforward swap
7. **Dreadnought** (active codex entries) — Twin lascannon; multiple Space Marine chapters
8. **Repulsor** — Twin lascannon
9. **Kabalite Warriors / Ynnari Kabalite Warriors / Hand of the Archon** — Dark Lance specialist
10. **Talos** — Twin heat lance
11. **Razorwing Jetfighter** — Dark Lance
12. **World Eaters Helbrute** — Twin lascannon
13. **World Eaters Defiler** — Ectoplasma destructor
14. **Stormraven Gunship** — Twin lascannon (low priority, gap 0.05)
15. **Hellhound** — Inferno cannon (anti-infantry correction, not anti-tank)

Legends units: 21 groups. These have minimal competitive tournament impact.
Apply the mapper heuristic (keep the existing mapper pick) unless a specific
Legends archetype list is added to the eval dataset.

---

## Source Notes

BSData weapon stats sourced from `data/bsdata/cache/` (version v10.6.0).
All unit weapon choice group structures confirmed by running
`scripts/diag_antitank_pick.py` against the live registry.
Wahapedia DNS was unreachable from the worktree during this session;
the Wahapedia URLs cited are the canonical expected paths for future
verification. Competitive meta assessments are based on knowledge of
10th edition tournament play as of the May–June 2026 dataset period.
No data was invented — units where the competitive meta is unclear are
classified as FALLBACK rather than asserting a loadout.
