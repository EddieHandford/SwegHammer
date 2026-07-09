# List-composition audit — the over-pole factions: over-built list, or faithful substrate wall? (2026-07-04)

Read-only audit. Base branch `claude/sim-calibration-19`, top commit `b31ff8a`
(Emperor's Children Coterie of the Conceited). Standing anchor
`data/_anchor_sc55a_n80_log.json`. Scratch script:
`scripts/_compaudit_over_census.py`. Windows discipline: `PYTHONIOENCODING=utf-8`,
`PYTHONHASHSEED=0`.

## The question (applied to the over-poles)

The Magnus finding proved list-composition is a live Stage-1 axis and that it cuts
both ways: fixing the Thousand Sons list also deflated the Death Guard over-pole by
−1.02 (fixing an under-built *opponent* chips an over-pole from the other side). For
each over-pole faction the two-fold question is: **(a)** is the over-pole faction's
OWN list OVER-built — fielding a detachment / centerpiece / units STRONGER than the
real May-2026 competitive list (a fixable over-pole, the phantom-force-seed class)?
or **(b)** is its list FAITHFUL, meaning its over-pole is the durability / mechanic
substrate that shrinks only as its under-built opponents get fixed?

Death Guard (+18) is the reference for the FAITHFUL answer — its own list was audited
faithful (`docs/_LIST_AUDIT_DEATHGUARD.md`) and is **not** re-audited here.

## Headline verdict

**Of the five over-poles, only ONE (Adeptus Astartes) is genuinely list-over-built,
and it is over-built on FIREPOWER, not the phantom-force-seed class. The other four
are list-FAITHFUL substrate.** The Canis-Rex-class phantom the 2026-07-01 archetype
audit flagged has already been removed from the two Knight factions by default gates —
the current builds field real chassis. Aeldari, the standout, fields a list that
matches its sourced tournament lists unit-for-unit; its +9.2 is a mechanic (the
economy over-paying a fragile elite army's aspect-warrior output/uptime), not a list
artifact. The one clean detachment-picker quirk (Adeptus Custodes fields the stronger
Shield Host on a 50/50 coin-flip against the faithful Auric Champions) is a weak lever
because Shield Host is itself a real competitive Custodes detachment.

The pattern from the fill-mechanism audit holds: **the over-poles are per-faction list
divergences on an economy that over-pays low-model survivor uptime, not a durability
provisioning artifact.** For four of the five, the list is not the lever.

---

## Ranked divergence table (ranked by expected impact of a LIST/DETACHMENT change)

| Rank | Faction | Pole (brief sc55a) | Sim archetype (what it actually fields) | Real May-2026 list (sourced) | Verdict + specific piece | Direction | Expected impact | The exact change a build agent would make |
|---|---|---:|---|---|---|---|---|---|
| 1 | **Adeptus Astartes** | +4.3 (51.3 v 47.0) | Gladius template but the template-pool fill STACKS premium firepower: **15.8 Hellblasters (~3 squads) + 12.1 Aggressors + 8.5 Eradicators** in 100% of builds; only **1 Intercessor squad (7.6 models, 76% presence)** of OC battleline. Detachment: Ironstorm Spearhead 60% / Gladius 40% | Gladius Task Force character goodstuff — Guilliman/Calgar + 14 Victrix Honour Guard + multiple Intercessor/Incursor OC squads; 1-2 premium-shooting units, not three triplicate squads | **OVER-BUILT (firepower).** Template is 3/7 premium-shooting elites + only 1 battleline, so the uniform template-pool fill over-produces plasma/melta/Gravis far beyond any real list. NOT phantom-force-seed; NOT detachment (Ironstorm is a no-op — see note) | DOWN | **Moderate–high** (Astartes plays every opponent in the matrix; a real list lever) | Broaden the `Adeptus Astartes` template battleline: bump `space_marines_intercessor_squad` to count=2 and add 1-2 more OC/battleline entries (Assault Intercessors / Infiltrators / Scouts). This re-shapes the fill toward OC bodies and caps the premium-shooting stack |
| 2 | **Adeptus Custodes** | +6.0 (55.5 v 49.5) | "Auric Champions" template but the picker returns **Shield Host 56% / Auric Champions 44%** — a pure coin-flip. Shield Host applies army-wide melee AP+1 (Rendax, odd rounds); Auric Champions is character-only Assemblage of Might. List: Wardens, Vertus Praetors, Allarus, Blade Champion, Trajann, Prosecutors — character/melee, faithful | Shield Host melee (Blade-Champion builds) IS competitively real; Auric Champions is rated weak; newest meta picks are Solar Spearhead / Lions of the Emperor (both unmodelled) | **MOSTLY FAITHFUL, minor detachment quirk.** The picker has no list-identity tiebreak (both score infantry +10, no keyword affinity), so Shield Host — the stronger army-wide melee buff — lands on 56% by chance | Down (weak) | **Low–moderate** (Shield Host is a real Custodes detachment, so the lever is defensible-only) | Optional: pin `Adeptus Custodes` to `auric_champions` (drop `shield_host` from `FACTION_DETACHMENTS` or add an Auric affinity) so the template's named detachment is fielded 100%. Deflates the pole, but weak-confidence since Shield Host is real |
| 3 | **Chaos Knights** | +10.1 (54.8 v 44.7) | Iconoclast Fiefdom 100% (real default). Anchors on **Knight Tyrant (558 pts, seeded 100%)** + War Dogs + Questoris spread (Abominant 56%, Despoiler 44%). `SWEG_CK_REALISM` (adds Chaos Cerastus pair + 2nd Despoiler) is **default-OFF** | Big Sky Open: Chaos Cerastus Atrapos + 2× Knight Despoiler + Rampager + 3× War Dog Karnivore. CaptainCon 2026: double Chaos Cerastus Lancer | **FAITHFUL substrate.** Shape (big Knights + War Dogs, Iconoclast) matches. Real lists anchor on Despoiler/Cerastus, sim on Knight Tyrant — a divergence, BUT the audit found Despoiler's sim output is HIGHER than the Tyrant's, so the faithful fix is **flat-or-up** | Substrate (list fix not downward) | **~Zero downward** (list lever pushes wrong way; over-pole is Knight-durability economy) | None downward. If fidelity-first, adopt `SWEG_CK_REALISM` default-on (Cerastus + 2 Despoiler) accepting flat/up. The pole shrinks only as anti-tank opponents get fixed |
| 4 | **Imperial Knights** | +11.9 (59.7 v 47.7) | Valourstrike Lance 52% / Noble Lance 48%. **Canis Rex ABSENT (0%)** — `SWEG_IK_REALISM` default-on drops it and seeds Knight Defender (515) + Armigers + Questoris spread + Cerastus Atrapos 24% / Lancer 12% | CaptainCon 2026 1st (Jonas Beardsley): Cerastus Knight Lancer + Knight Defender Warlord + Armiger Helverin, Questoris Companions detachment | **FAITHFUL substrate.** The phantom (Canis Rex double-model bug) the archetype audit flagged is ALREADY fixed by default. Current chassis mix matches the CaptainCon winner. Over-pole is the kill economy over-valuing T11-12 / 26-28-wound Knight survivability | Substrate | **~Zero from list** (phantom already gone; list is faithful) | None. Over-pole is primary/kill-economy survivor-uptime (fill-audit's Knight row: brick-share faithful). Shrinks as under-built anti-tank opponents get fixed. Minor: Questoris Companions detachment is unmodelled (sim uses Valourstrike, also real) |
| 5 | **Aeldari** ⭐ | +9.2 (50.8 v 41.5) | Warhost 100%. **Matches sourced lists unit-for-unit:** Fuegan + Jain Zar + Lhykhis (all seeded 100%), Fire Dragons 13.8, Warp Spiders 13.0, Dark Reapers, Howling Banshees, Swooping Hawks, Wave Serpent, Corsair Voidreavers, Rangers, Autarch. Zero durable bricks; wpp 0.054 (lowest in game) | Nova Open 2025 1st (Folger Pyles): Eldrad + Fuegan + Jain Zar + Maugan Ra + Lhykhis + Fire Dragons + Warp Spiders×3 + Corsair Voidreavers×3 + Rangers. Salt City GT IV 7-0 (Brad Chester): Fuegan + Jain Zar + Lhykhis + Fire Dragons×2 + Warp Spiders×2 | **FAITHFUL — the over-pole is a MECHANIC, not the list.** The standout scrutiny confirms: no stronger-than-real unit, no over-tuned detachment. Fire Dragons at 13.8 (~2.5 squads) is high-end but within real range (real runs 2 squads). Zero bricks over-poling = economy over-pays aspect output/uptime | Substrate (mechanic) | **Zero from list** (list is faithful; lever is the elite-output economy) | None to the list. This is the primary/kill economy over-paying a fragile low-model army's per-model shooting/uptime — the surface the fill-audit named. NOT list-fixable downward without breaking fidelity |

Notes:
- **Astartes detachment leans the WRONG way for the over-pole.** Ironstorm Spearhead
  (60% of builds) is a **no-op** in the sim — its `vehicles_reroll_hit_ones` proxy was
  removed as a fabrication, so it carries no offensive flag and no stratagems. Gladius
  Task Force (40%) carries Combat Doctrines (+1 wound rotating) plus six stratagems.
  So the sim UNDER-buffs Astartes on the detachment axis yet still over-poles — the
  over-pole is the **firepower list-shape**, and pinning to the faithful Gladius would
  raise the WR, not lower it. The list (firepower stack) is the only downward lever.
- **Pole reconstruction caveat.** A raw per-faction win-rate tally from the sc55a log
  gives IK +9.4, CK +10.3, Aeldari +13.9, Custodes +2.3, Astartes +7.7 (real win rates
  match the brief exactly; the sim-WR differences are the field-weighting — the brief's
  poles are opponent-game-count-weighted, the raw tally is cell-uniform). The table
  quotes the brief's authoritative field-weighted poles. The composition verdicts are
  independent of the aggregation.

---

## Per-faction detail

### 1. Adeptus Astartes (+4.3) — the one genuine list over-build

The `Gladius Strike Force` template is `{Intercessor 1, Hellblaster 1, Eradicator 1,
Aggressor 1, Captain-in-Terminator-Armour 1, Apothecary 1, Repulsor 1}`. Three of the
seven entries are premium-shooting elites (Hellblaster plasma, Eradicator melta,
Aggressor Gravis) and only ONE is OC battleline (Intercessors). The seed
(`SEED_FRACTION_LEADER_STACK["Adeptus Astartes"] = 0.31`) seats one squad each of the
elites, the two characters and the Repulsor — but NOT the Intercessors. The
template-pool fill (`SWEG_FILL_TEMPLATE_POOL`, default-on) then draws uniformly among
the seven template units. The BATTLELINE cap throttles Intercessors to one extra fill
squad, but the three elite shooters are ELITE/HEAVY, capped only by the per-name spend
cap, so they stack:

| unit | mean models | seed | fill | in % |
|---|---:|---:|---:|---:|
| Hellblaster Squad | 15.8 | 5.0 | 10.8 | 100 |
| Aggressor Squad | 12.1 | 3.0 | 9.1 | 100 |
| Eradicator Squad | 8.5 | 3.0 | 5.5 | 100 |
| Intercessor Squad | 7.6 | 0.0 | 7.6 | 76 |
| Repulsor | 2.5 | 1.0 | 1.5 | 100 |

15.8 Hellblasters is ~3 squads of plasma; 8.5 Eradicators ~2 squads of melta. Real
competitive Gladius lists (Manel Tulla 2nd, Peyton Link 2nd — Goonhammer Competitive
Innovations) are character goodstuff: Guilliman/Calgar + ~14 Victrix Honour Guard +
several Intercessor/Incursor OC squads, with 1-2 premium-shooting units, not three
triplicate squads. **The sim fields more premium firepower than any real Gladius
list** — a firepower over-build produced by an elite-heavy template + flat fill. Fix:
broaden the template's battleline (Intercessors count=2 plus Infiltrators / Scouts /
Assault Intercessors) so the fill produces OC bodies rather than a third Hellblaster
squad.

### 2. Adeptus Custodes (+6.0) — faithful list, coin-flip detachment

The "Auric Champions" template is character/melee (Wardens, Vertus Praetors, Allarus,
Blade Champion, Shield-Captain, Trajann, Custodian Guard, Caladius, Prosecutors) and is
faithful in shape. The divergence is the picker: `FACTION_DETACHMENTS["Adeptus
Custodes"] = ("shield_host", "auric_champions")`, both `preferred_composition="infantry"`,
and `_keyword_affinity_score` has no branch for either — so both score exactly +10 and
`pick_detachment_for_army` is a 50/50 weighted coin-flip. The census returns **Shield
Host 56% / Auric Champions 44%**. Shield Host applies army-wide melee AP+1 (Rendax, odd
rounds) — the stronger, broader buff; Auric Champions applies character-only +1-to-wound
against one designated enemy unit (Assemblage of Might). Because Shield Host is itself a
real competitive Custodes detachment (Goonhammer/Tabletop Battles: viable, "melee armies
running multiple Blade Champions" — and the sim's list HAS a Blade Champion), the 56%
Shield Host picks are defensible, not a clear fabrication. The modest over-pole is
largely elite-durability substrate. Weak downward lever: pin to `auric_champions`.

### 3. Chaos Knights (+10.1) — faithful substrate; list fix is flat/up

Iconoclast Fiefdom (Dread Tyrants aura) 100% — the real competitive default. The sim
anchors on Knight Tyrant (558 sim pts, seeded 100%) plus a full War Dog escort and a
Questoris spread. Real 2026 lists (Big Sky Open: Chaos Cerastus Atrapos + 2× Despoiler +
Rampager + 3× War Dog Karnivore; CaptainCon: double Chaos Cerastus Lancer) anchor on
Cerastus + Despoilers. The `SWEG_CK_REALISM` gate that would add the Chaos Cerastus pair
and a 2nd Despoiler is **default-OFF**. So there is a real chassis divergence — but the
archetype-fidelity audit measured the Despoiler's sim output as HIGHER than the Tyrant's,
so applying the faithful fix moves the pole **flat-or-up**. Not a downward lever. The
+10.1 is the same Knight-durability economy as Imperial Knights.

### 4. Imperial Knights (+11.9) — phantom already removed; faithful substrate

The Canis-Rex phantom (force-seeded into 100% of builds as a double-26-wound TITANIC via
a BSData model-fold bug, per the archetype audit) is **already gone**: `SWEG_IK_REALISM`
(default-on) drops `imperial_knights_library_canis_rex` from the effective template and
seeds the Knight Defender instead. The census confirms **Canis Rex at 0%**. Current
builds field Knight Defender (anchor) + Armigers (Warglaive/Helverin/Moirax) + a Questoris
spread + Cerastus Atrapos (24%) / Lancer (12%) — matching the CaptainCon 2026 1st-place
list (Cerastus Knight Lancer + Knight Defender Warlord + Armiger Helverin). Detachment
Valourstrike Lance (Bold Gallantry + Bondsman) 52% — real. The over-pole is the kill
economy over-valuing Knight survivability (fill-audit: IK brick-share is faithful to
reality). No list lever downward; the phantom that WAS the lever is fixed.

### 5. Aeldari (+9.2) — the standout: faithful list, mechanic over-pole

Scrutinized per the brief. The Warhost list matches its sourced tournament lists
unit-for-unit: three Phoenix Lords (Fuegan + Jain Zar + Lhykhis, all seeded 100%) — the
Nova Open 2025 winner ran FIVE Phoenix Lords/characters (Eldrad + Fuegan + Jain Zar +
Maugan Ra + Lhykhis), so three is if anything conservative — plus Fire Dragons, Warp
Spiders, Dark Reapers, Howling Banshees, Swooping Hawks, Wave Serpent, Corsair
Voidreavers, Rangers. No stronger-than-real unit; no over-tuned detachment (Warhost is
the sole registered detachment). Fire Dragons at 13.8 models (~2.5 squads) is the only
marginally-high count, and real Warhost lists run 2 Fire Dragon squads, so it is inside
the band. The list carries **zero durable bricks** and the lowest wounds-per-point in the
game (0.054), yet over-poles +9.2 — which the fill-mechanism audit already proved cannot
be a durability-provisioning artifact. The +9.2 is the primary/kill economy over-paying a
fragile low-model elite army's per-model aspect-warrior shooting and survivor uptime.
**Aeldari's over-pole is a mechanic, not the list** — it is not list-fixable downward
without breaking fidelity.

---

## Handoff

The list zone yields ONE actionable downward lever among the five over-poles:
**Adeptus Astartes** (broaden the template battleline to break the flat-fill firepower
stack). A second, weak lever exists for **Adeptus Custodes** (pin the detachment to the
faithful Auric Champions, deflating the 56% Shield-Host coin-flip — weak because Shield
Host is competitively real). The other three (Imperial Knights, Chaos Knights, Aeldari)
are **list-faithful**: their over-poles belong to the primary/kill-economy survivor-uptime
surface, not to list fidelity — Imperial Knights' phantom is already removed, Chaos
Knights' faithful list-fix pushes the pole flat/up, and Aeldari fields exactly the sourced
tournament list. Per the Magnus/Death-Guard precedent, these three shrink as their
under-built *opponents* are fixed, not by touching their own lists.

## Sources

- `docs/_LIST_AUDIT_DEATHGUARD.md` — the reference faithful-over-pole audit (not re-run).
- `docs/_LIST_AUDIT_FILL_MECHANISM.md` — durable-share does not track the pole; IK/CK
  brick-share faithful; Aeldari zero-brick over-pole is not a durability artifact.
- `docs/ARCHETYPE_FIDELITY_AUDIT.md` — the Canis-Rex phantom flag (now fixed), the
  Despoiler > Tyrant output note, the detachment-decoupling pattern.
- `code/archetypes.py` `_effective_template` (`SWEG_IK_REALISM` drops Canis Rex default-on;
  `SWEG_CK_REALISM` default-off), `_random_fill` (`SWEG_FILL_TEMPLATE_POOL`).
- `code/detachments.py` — `SHIELD_HOST` (melee_ap_plus_one) vs `AURIC_CHAMPIONS`
  (assemblage_of_might); `IRONSTORM_SPEARHEAD` (no-op, proxy removed) vs
  `GLADIUS_TASK_FORCE` (Combat Doctrines); `pick_detachment_for_army` /
  `_keyword_affinity_score` (no Custodes tiebreak → coin-flip).
- Real-list structure (web, best-effort; several decklist hosts JavaScript-rendered):
  Imperial Knights CaptainCon 2026 1st, https://spikeybits.com/top-40k-unbeatable-army-lists-captaincon-2026/ ;
  Chaos Knights Big Sky Open, https://spikeybits.com/top-40k-tournament-army-lists-from-the-big-sky-open/ ;
  Aeldari Nova Open 2025 1st, https://spikeybits.com/top-40k-unbeatable-army-lists-nova-open-gt/ ;
  Aeldari Salt City GT IV 7-0, https://grimhammertactics.com/top-10-competitive-warhammer-40k-lists-august-2025/ ;
  Custodes detachment meta, https://www.tabletopbattles.com/detachment-focus-shield-host/ and
  https://www.tabletopbattles.com/detachment-focus-auric-champions/ ;
  Space Marines Gladius goodstuff, Goonhammer Competitive Innovations (Manel Tulla /
  Peyton Link 2nd), https://www.goonhammer.com/40k-competitive-innovations-in-10th-plus-ultra-pt-3 .
- Datasheet stats and points: BSData via the live `UNIT_CATALOG` (standing rule six).

## Reproduction

`scripts/_compaudit_over_census.py` — samples 25 archetype builds per over-pole faction
at 2000 points via the real `build_archetype_army` (all env gates at sc55a production
defaults), splits seed versus fill on a `_random_fill` wrapper, and reports the
detachment distribution and per-unit presence. Run with
`PYTHONIOENCODING=utf-8 PYTHONHASHSEED=0 python -m scripts._compaudit_over_census`.
Writes `scripts/_compaudit_over_census_out.json`. No tracked source files are modified.
