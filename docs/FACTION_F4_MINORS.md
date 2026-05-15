# Faction F4 — Minor outliers diagnostic (Necrons, Death Guard, Orks, Custodes, T'au)

Status: diagnostic only. No sim/AI code changes in this pass.

Eval-vs-meta (archetype=True) puts these five factions inside ±10 pts of real
WR — secondary outliers, brief diagnosis only. N=20 seeded battles per matchup
(focus vs each of the 9 others, 1000 pts, archetype=True both sides, seeds
9001–9020). Source: `scripts/f4_minors_diag.py`.

| Faction          | Sim WR (this diag) | Real WR | Eval gap |
|------------------|-------------------:|--------:|---------:|
| Necrons          | 66.7 %             |  ~52 %  |   +8.7   |
| Death Guard      | 61.1 %             |  ~47 %  |   +8.9   |
| Orks             | 43.3 %             |  ~49 %  |   -5.3   |
| Adeptus Custodes | 45.0 %             |  ~50 %  |   -3.9   |
| T'au Empire      | 46.7 %             |  ~52 %  |   -4.9   |

Sim-WR numbers above are mean-of-9 matchup WRs from this N=20 diag and differ
slightly from the larger eval mean, which is expected. Worst-matchup signal is
what matters for the diagnosis.

## Necrons (+8.7)

Worst 2: vs Tyranids 20.0 %, vs Death Guard 50.0 % (the 50 %/50 % vs Astartes
and Death Guard are still below mean 66.7 %). Otherwise the matrix is 75–95 %
across seven matchups — a *moderate* over-performer.

**Cause:** Reanimation Protocols on big Lychguard/Immortal blocks holds up
well against most factions (Lychguard survive 50–67 % even into Tyranids /
Marines). The only matchups that crack it are Tyranids (mass low-AP wounds
outscale RP rolls per round) and Death Guard (S5–7 plague weapons + DR mean
they trade favourably even into Sv2+ bodies). Diagnostic shows Cryptek and
Doomstalker **never seeded** at 1000 pts — Crypteks are the RP-buff source.
So Necrons under-perform vs anti-horde lists and *over*-perform vs everyone
else because the rest of the field can't dent T4–T5 Sv3+ infantry blocks fast
enough to keep up with primary scoring.

**Quick fix:** Cost-bump Lychguard/Immortals by ~5 % (currently their
points-per-wound is the cheapest Sv3+ 2W body in the sim catalogue).

## Death Guard (+8.9)

Worst 2: vs Tyranids 25.0 %, vs Necrons 30.0 %. Best are Custodes 80 %,
Thousand Sons 85 %. Diagnostic: Plague Weapons stratagem fires 2.5×/battle,
Outbreak of Pestilence 2.3×/battle — the lethal-1+anti-infantry combo is
firing every round.

**Cause:** Plague Marines start 5.3/battle and survive 48–64 % into the worst
matchups. Poxwalker screen evaporates (0.9–5 % survival into Tyranids/Necrons)
but that's their actual job — they soak overwatch / charge while the Plague
Marines and Plagueburst Crawler do the killing. Diagnostic flags **three
never-seeded units**: Biologus Putrifier, DG Terminators, Myphitic Blight-
hauler. Death Guard is over-performing because Plague Weapons gives them a
better wound-roll re-distribution than the cost model accounts for, especially
against Marines and Custodes who lack volume-anti-armour.

**Quick fix:** Audit Plague Weapons stratagem effect — if currently re-rolling
1s to wound army-wide-on-plague, restrict to one PLAGUE MARINE unit per use
(actual 10e rule) and confirm `data/rule_citations.json` entry matches.

## Orks (-5.3)

Worst 2: vs Tyranids 5.0 %, vs Astartes 20.0 %. Best Thousand Sons 80 %.
Diagnostic: Heroic Intervention fires 3.65–7.0×/battle (Orks getting reactively
charged a lot). Boyz start 10.9/battle but survive only 1.8–2.8 % vs Tyranids
and Astartes — total wipeout.

**Cause:** 'Ere We Go (extra-attack on charge) and Waaagh! (the army's whole
identity) don't appear in any stratagem-fire counter — likely under-modelled.
Boyz are arriving into combat with vanilla A2 S4 profiles instead of their
WAAAGH-buffed A3 S5, so the matchup vs S6+ Tyranid Warriors / Marine bolters
is a brick wall. Deff Dread, Nobz, Gretchin, Killa Kans **never seeded** at
1000 pts.

**Quick fix:** Implement the Waaagh! army rule (Round 2 or 3 declare: +1 to
charge, advance-and-charge, melee +1 to wound) with proper rule citation —
this is the single biggest missing buff for the faction.

## Adeptus Custodes (-3.9)

Worst 2: vs Tyranids 10.0 %, vs Astartes 35.0 % (tied with Necrons / DG / T'au
all at 35 %). Diagnostic: army size is *tiny* — only Custodian Guard (start
0.8/battle) and Shield-Captain (1.1/battle) ever seed. **Seven of nine
tracked profiles never seeded**: Sagittarum, Allarus, Wardens, Vexilus, Jetbike,
Prosecutor, Witchseeker.

**Cause:** Custodian Guard cost 220 in `parsed.json` and the random army
builder + archetype seeding can only afford ~1 unit at 1000 pts after the
character is paid for. So the army is fighting most battles with 5–6 models
total, gets out-scored on every objective, and loses on primary regardless of
its quality stats. The Tyranid swarm matchup (10 %) is the extreme version of
this.

**Quick fix:** Lower Custodian Guard's per-unit cost in `data/overrides.json`
to match 10e GW costing (e.g. 130 for a 4-model squad) — currently the unit
is mispriced 1.5×+, which is why no list-builder selects more than one.

## T'au Empire (-4.9)

Worst 2: vs Tyranids 0.0 % (!), vs Necrons 15.0 %. Best Custodes 75 %,
Thousand Sons 75 %. Diagnostic: Strike Team starts 19.4/battle (full Fire
Warrior conscript wave) but survives just 0.8 % vs Tyranids and 11 % vs
Necrons. **Riptide, Crisis Battlesuit, Commander, Broadside never seeded** —
all four iconic T'au battlesuits are squeezed out by the cheap-first walker.

**Cause:** T'au are fighting at 1000 pts with only Fire Warriors + Pathfinders
+ one Devilfish + one Hammerhead — no battlesuits at all. Their entire
shooting army identity (Crisis suits with markerlight support, JSJ, Mont'ka
focus-fire) is gating out of the budget. Against Tyranids the 19 Fire Warriors
get tied up in melee turn 1 and never shoot meaningfully again. For the
Strike Swiftly stratagem fires (0.8–1.0×/battle), it's not enough to compensate.

**Quick fix:** Cap Strike Team random-fill to ≤2 units per army-build pass
in `army_builder.py` selection logic — this frees ~200 pts for a Crisis or
Broadside team and pushes a Battlesuit T'au identity instead of conscript-spam.

## Worst-matchup summary

| Faction          | Worst | 2nd worst |
|------------------|------|-----------|
| Necrons          | vs Tyranids (20 %) | vs Death Guard (50 %) |
| Death Guard      | vs Tyranids (25 %) | vs Necrons (30 %) |
| Orks             | vs Tyranids (5 %)  | vs Astartes (20 %) |
| Adeptus Custodes | vs Tyranids (10 %) | vs Astartes (35 %) |
| T'au Empire      | vs Tyranids (0 %)  | vs Necrons (15 %) |

Five of five worst matchups are vs Tyranids — consistent with F1's headline
finding that Tyranid swarm is broadly over-tuned. Three of five second-worst
involve Astartes or Necrons (the other heavy-elite armies), suggesting that
fixing the F1 Tyranid issue alongside Custodes / T'au unit-seeding will
recover most of these residuals without needing per-faction stratagem code
changes.
