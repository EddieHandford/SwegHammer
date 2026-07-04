# List-composition audit — the under-pole factions (2026-07-04)

Read-only audit. No simulator or list code was changed. Product: a ranked
divergence report telling the orchestrator which under-built lists to fix next,
in priority order, following the proven Magnus / Emperor's Children pattern
(a real, competitively dominant piece the simulator was not fielding).

- **Base:** branch `worktree-agent-a4e20fd9946d99439`, tip `bdf86fc`
  (`feat(archetypes): adopt Magnus in the Thousand Sons list`), a descendant of
  the `claude/sim-calibration-19` line. Standing anchor
  `data/_anchor_sc55a_n80_log.json` copied in.
- **Scope:** the four live under-pole targets on the sc55a error surface —
  Astra Militarum −16.4 (28.9 vs 45.3), Orks −13.4 (31.9 vs 45.3), Chaos Daemons
  −8.2 (44.4 vs 52.6), Genestealer Cults −4.5 (42.1 vs 46.7). Emperor's Children
  and Thousand Sons are already handled and are referenced only as the template
  of what a fix looks like.
- **Method:** 20 archetype builds per faction at 2000 points
  (`build_faction_random_army("A", <faction>, 2000, rng=random.Random(s),
  use_archetype=True)`, seeds 0–19) via `scripts/_compaudit_under_census.py`;
  each proposed top lever validated by a read-only build probe
  (`scripts/_compaudit_under_probe.py`). No evaluation sweep.

## The mechanism that blocks these lists

Three build-pipeline facts (from `code/archetypes.py`) explain every divergence
below:

1. **The epic-hero random-fill bar.** In `_random_fill`, an EPIC HERO not named
   in the template gets `wrecker_cap = template_count = 0` fill picks — it is
   *architecturally impossible* to field. A faction's signature epic-hero
   centerpiece therefore appears in **zero** builds unless it is written into the
   template. This is the exact bar that hid Magnus from Thousand Sons.
2. **The EPIC HERO anchor guarantee** force-seeds the most-expensive template
   EPIC HERO in every build. So adding a centerpiece to the template does not
   merely make it *possible* — it makes it *certain* (validated 20/20 for Orks
   below).
3. **Detachment gates default off.** `SWEG_AM_GRIZZLED` (Astra Militarum's real
   2026 top detachment) defaults **off**, so the army fields the weaker Combined
   Arms rule. (`SWEG_DAEMONS_BELAKOR` — the Chaos Daemons Scintillating Legion
   fix — already defaults **on**, and is fielding as intended; see below.)

## Ranked divergence table (by expected metric impact)

| Rank | Faction | Pole | Simulator fields now | Real 2026 competitive shape | The missing piece | Expected impact | Exact change a build agent makes |
|---|---|---|---|---|---|---|---|
| 1 | **Orks** | −13.4 | War Horde (correct); **zero epic heroes**; headless chaff, "centerpiece" = Killa Kans | War Horde with **Ghazghkull Thraka + Makari** as the mandatory warlord brick | Ghazghkull entirely absent — blocked by the epic-hero bar (not in template) | **High** — anti-brick durability *and* army-wide offence (Makari Lethal Hits within 12" on the Waaagh!, crits-on-5s), hits the loss shape from both sides; cleanest Magnus analog | Add `"orks_ghazghkull_thraka": 1` to `ARCHETYPES["Orks"]["Waaagh!"]`. Sole epic hero → force-seeded 20/20 (validated). |
| 2 | **Astra Militarum** | −16.4 | **Combined Arms** detachment 100%; tank toolbox + Cadian chaff | **Grizzled Company** (the top-performing 2026 detachment); Vanquisher / Rogal Dorn tanks + Kasrkin / Scions + Bullgryn or Rough Riders + Field Ordnance | Wrong detachment — Grizzled Company is built but gated off | **High-medium** — biggest raw gap; Grizzled Company nearly doubles the Orders economy (+1 order per officer) + reroll Hit 1s on ordered units, a broad offensive uplift. Caveat: an acknowledged structural durability component the detachment only partly addresses; and a fidelity dispute on the wound-reroll clause | Set default `SWEG_AM_GRIZZLED=1` (flips `DEFAULT_BY_FACTION` / `FACTION_DETACHMENTS` to `grizzled_company`). Flips detachment 20/20 (validated). Optionally shift the tank spine toward Leman Russ Vanquisher + Field Ordnance Battery. |
| 3 | **Chaos Daemons** | −8.2 | Scintillating Legion **already fielded** (~4/20); 5-way uniform archetype rotation | Scintillating Legion **dominates** the real meta (Be'lakor + Kairos + double/triple Lord of Change "Quad Birds") | Not a missing piece — an under-**weighting** (real meta is majority Belakor, sim rotates it at 1-in-5). Detachment rules are mechanically inert in the sim | **Low-medium** — softer lever; the list is largely faithful and the pole is substantially **structural** (all Daemon detachment rules are unmodelable). Skewing rotation toward Scintillating Legion's 4-flagship durable shape is direction-correct but low-confidence | Optionally weight the archetype `rng.choice` toward "Scintillating Legion", and swap its Great Unclean One for a second `chaos_daemons_library_lord_of_change` to match real Quad Birds. No detachment lever exists. |
| — | **Genestealer Cults** | −4.5 | Final Day (inert); Patriarch-anchored Aberrant/Acolyte/Neophyte spam + full character suite | Final Day spam, Patriarch-anchored — **matches the sim** | **Nothing** — list is faithful; Final Day's real rule ("Psionic Parasitism") buffs a *Tyranids* unit via a cross-faction Synapse trade, so it is **correctly inert** for a pure-Genestealer army | **None (faithful)** — the −4.5 is structural: the sim under-models the Cult Ambush deep-strike / blip / Crossfire identity | **No list fix.** |

## Per-faction detail

### 1. Orks −13.4 (sim 31.9 vs real 45.3) — missing Ghazghkull Thraka

**Sim census (20 builds).** Detachment War Horde 20/20 (correct). **Zero epic
heroes fielded in any build.** Body count averages 92 models; the "centerpiece"
(most-expensive squad) is Killa Kans (13/20) or Nobz (7/20) — i.e. no real
anchor. Template `"Waaagh!"` = Boyz ×2, Meganobz, Warboss in Mega Armour, Killa
Kans, Tankbustas, Nobz, Deffkoptas. It contains no Ghazghkull, no Beast Snagga
package, no transports.

**Real 2026 list.** War Horde is "the only [detachment] where Ghazghkull is a
must-take" and "currently the preferred way to run the faction competitively";
"you need Ghazghkull, who during a Waaagh! gives his unit Crits on a 5+ and
through Makari gives Ork units within 12" LETHAL HITS." Ghaz rides a Battlewagon
('Ard Case) or joins 20 Boyz / Nobz / Breaka Boyz; supporting Beast Snagga Boyz
+ Beastbosses in Trukks. A Pendleton OR Grand Tournament winner fielded
Ghazghkull as warlord with Beastboss, Snikrot, Painboy, Zodgrod, Beast Snagga
Boyz + Boyz battleline.
Sources: Tabletop Battles "Detachment Focus: War Horde" (updated 2025-12-30),
https://www.tabletopbattles.com/detachment-focus-war-horde/ ; Tabletop Battles
"10th Edition Competitive Faction Focus: Orks",
https://www.tabletopbattles.com/10th-edition-competitive-faction-focus-orks/ ;
Bolter and Chainsword "2,000 Point Tournament War Horde List",
https://bolterandchainsword.com/topic/382953-2000-point-tournament-war-horde-list/ .

**The divergence.** The detachment is right; the list is missing its single most
important unit. `orks_ghazghkull_thraka` (EPIC HERO, 117.5 simulator points) is
in the catalogue but absent from the template, so the epic-hero bar fields him in
0/20 builds. This is the Magnus case exactly: a must-take centerpiece, blocked by
the epic-hero random-fill bar and a template that never named it.

**Cross-check against the loss shape.** Orks at −13.4 lose the attrition / contest
war — a chaff mob with no durable anchor and no army-wide damage multiplier.
Ghazghkull addresses **both**: a T9 2+/4++ high-wound brick (durability) plus
Makari's within-12" Lethal Hits and Waaagh! crits-on-5s (army-wide offence). The
missing piece maps precisely onto the deficit.

**Expected impact: High.** Highest-confidence lever of the four. Probe: adding
`"orks_ghazghkull_thraka": 1` fields him 20/20 (sole epic hero → EPIC HERO anchor
guarantee force-seeds him).

### 2. Astra Militarum −16.4 (sim 28.9 vs real 45.3) — wrong detachment

**Sim census (20 builds).** Detachment **Combined Arms 20/20**. Centerpiece Rogal
Dorn 20/20; Leman Russ Battle Tank + Demolisher + Basilisk + Manticore all 20/20;
epic heroes Ursula Creed + Lord Solar Leontus 20/20. Body count ~49. A faithful
tank-plus-elite silhouette — but under the weaker detachment.

**Real 2026 list.** **Grizzled Company** "has come out as the top performing
Detachment in major events since its release during Grotmas" and continued to
take top placings through the Q1 2026 dataslate. Rule: each officer issues +1
order, and ordered units re-roll Hit rolls of 1 (press sources add a re-roll
Wound 1s vs objective-marker clause — see fidelity note). Winning builds: Roger
Boira (Open Talavera 2026) Bullgryn + Commissar, Leman Russ Vanquishers, Kasrkin,
Rogal Dorns; Dan Sammons triple Vanquishers + Rogal Dorns + Gaunt's Ghosts +
indirect Field Ordnance Batteries + Death Riders + Attilan Rough Riders.
Sources: Grimhammer Tactics "Competitive Monday Meta Review: Grizzled Company
Marches On",
https://grimhammertactics.com/warhammer-40k-competitive-monday-meta-review-grizzled-company-marches-on/ ;
Tabletop Battles "Detachment Focus: Grizzled Company",
https://www.tabletopbattles.com/detachment-focus-grizzled-company ; Wargamer
"Warhammer 40k drops a surprise new Astra Militarum detachment, and it's super
strong", https://www.wargamer.com/warhammer-40k/grizzled-company .

**The divergence.** The 2026-07-01 fidelity audit already flagged "real top
detachment Grizzled Company unimplemented." It has since been **built** —
`GRIZZLED_COMPANY` in `code/detachments.py`, order economy wired in
`code/orders.py`, gated `SWEG_AM_GRIZZLED` — but the gate **defaults off**, so the
army still fields Combined Arms. This is the Emperor's-Children-detachment case: a
real dominant detachment present in the tree but not switched on.

**Cross-check / caveats.** Direction-correct for the largest under-pole (a broad
Orders + reroll uplift). Two caveats keep it below Orks in confidence: (a) the
fidelity audit found a *list-composition* rework (`SWEG_AM_REALISM`) screened
**worse** and called the pole partly "structural durability-in-contest" — the
detachment is a cleaner sub-lever than the list swap, but may not fully close −16;
(b) a citation dispute: SwegHammer models only +1 order + reroll Hit 1s, omitting
the wound-reroll-vs-objective clause that several press sources report (the team
cross-checked Wahapedia raw HTML and treats the third clause as unconfirmed).

**Expected impact: High-medium.** Probe: `SWEG_AM_GRIZZLED=1` flips the detachment
to Grizzled Company 20/20 (validated). Optional secondary: shift the tank spine
toward Leman Russ Vanquisher + Field Ordnance Battery to match the sourced lists.

### 3. Chaos Daemons −8.2 (sim 44.4 vs real 52.6) — already fixed on list; pole is structural

**Sim census (20 builds).** The Belakor **Scintillating Legion is already being
fielded** — `SWEG_DAEMONS_BELAKOR` defaults **on** ("1"), the sub-archetype is one
of five in the uniform rotation, and Be'lakor + Kairos Fateweaver appear in 4/20
builds each with the full four-flagship core force-seeded. Detachment rotation:
Legion of Excess 6, Daemonic Incursion 4, Blood Legion 4, Scintillating Legion 4,
Plague Legion 2. Composition otherwise mono-god (Greater Daemon + god battleline)
and looks faithful.

**Real 2026 meta.** Scintillating Legion **dominates**: Wheat City GT win
(Be'lakor + Kairos + double Lord of Change), Manchester CT win, RJ Flores 3rd at
Milwaukee (Quad Birds), 8 Grand Tournament wins in January 2026. Real shape is
Be'lakor + Kairos + **two or three** Lords of Change ("Quad Birds") + minimal
scoring units.
Sources: Bell of Lost Souls "Goatboy's Grimdark Armylist: Chaos Daemons —
Scintillating Legion",
https://www.belloflostsouls.net/2026/01/goatboys-grimdark-armylist-chaos-daemons-scintillating-legion-kicking-it-bird-style.html ;
Grimhammer Tactics "Top 10 Competitive Warhammer 40K Lists March 2026",
https://grimhammertactics.com/top-10-competitive-warhammer-40k-lists-march-2026/ .

**The divergence (soft).** Two residual gaps, both lower-value than Orks/Astra
Militarum: (a) the archetype rotation is **uniform** (Scintillating Legion at
1-in-5) while the real meta is majority-Belakor — the simulator under-weights its
strongest real list; (b) the Scintillating Legion template substitutes a Great
Unclean One for the second Lord of Change, diverging from the pure-Tzeentch Quad
Birds. **The pole is substantially structural:** every Chaos Daemons detachment
rule (Murdercall Surge, Beguiling Aura fall-back-and-charge, Melancholic Miasma
battle-shock, Fates in Flux tokens) is a no-flag inert shell because none is
expressible in the current schema — so the faction fights with essentially no
detachment rule while opponents get theirs, and its Shadow-of-Chaos / deep-strike
board-control identity is under-modeled.

**Expected impact: Low-medium.** If a lever is wanted: bias the archetype choice
toward Scintillating Legion and swap its Great Unclean One for a second Lord of
Change. But the list is already largely correct; the residual −8.2 is a rules-zone
(structural) problem, not a list gap.

### 4. Genestealer Cults −4.5 (sim 42.1 vs real 46.7) — FAITHFUL, no list fix

**Sim census (20 builds).** Detachment Final Day 20/20. Patriarch anchored 20/20;
Aberrants (centerpiece 9/20), Achilles Ridgerunners, Goliath Rockgrinder, Acolyte
(autopistol + hand-flamer) and Neophyte spam, full character suite (Primus, Magus,
Kelermorph, Jackal Alphus, Sanctus, Clamavus). Body count ~80 — a faithful cult
spam shape. No epic hero exists at Magnus tier for this faction; the Patriarch is
the anchor and it is fielded.

**Real list + detachment fidelity.** Final Day spam, Aberrant / Purestrain blobs
with demolition charges, Patriarch-anchored — matches the sim. The Final Day
detachment rule is **"Psionic Parasitism"** (verified verbatim against 40k.app):
"…for each TYRANIDS SYNAPSE unit … that GENESTEALER CULTS unit suffers D3+1 mortal
wounds and one model in the selected TYRANIDS unit regains … lost wounds and …
add 1 to the Hit roll" — the +1 to hit lands on a **Tyranids** unit, via a
cross-faction Synapse trade. A pure-Genestealer army has no Tyranids Synapse
units, so the rule correctly does nothing — SwegHammer's inert Final Day is
**faithful**. (A web-search summary claiming "all Genestealer units +1 to hit"
is wrong; the primary source does not support it.)
Sources: 40k.app Final Day detachment,
https://www.40k.app/factions/genestealer-cults/detachments/final-day ;
Goonhammer "Competitive Innovations in 10th: Cult Classics pt.2",
https://www.goonhammer.com/competitive-innovations-in-10th-cult-classics-pt-2/ .

**Verdict: no list fix.** The list and the (inert) detachment are both faithful.
The −4.5 is structural — the simulator under-models the Cult Ambush deep-strike
returns, blip movement, and Crossfire that are the whole Genestealer identity.
This is the confirmed "genuinely faithful, pole is structural" case among the four.

## Dispatch order for the orchestrator

1. **Orks** — add Ghazghkull Thraka to the Waaagh! template (one line; validated
   20/20). Highest confidence, addresses the loss shape from both durability and
   damage.
2. **Astra Militarum** — flip `SWEG_AM_GRIZZLED` to default-on (validated 20/20).
   Largest gap; screen for the residual structural component and resolve the
   wound-reroll citation before adopting.
3. **Chaos Daemons** — optional list-mix weighting toward Scintillating Legion +
   second Lord of Change; low-confidence, the pole is mostly structural.
4. **Genestealer Cults** — no list fix; faithful, structural pole.

Scratch scripts: `scripts/_compaudit_under_census.py`,
`scripts/_compaudit_under_probe.py`.
