# DAEMONS-DIAG-10 — findings (Stage 1 calibration)

Outlier: Chaos Daemons gated **-12.52** (sim 35.1%, real 50.8%). Sim is TOO
WEAK. Diagnostic only — no fix this run.

Wave-43's "Greater Daemon seeding missing" hypothesis was wrong on its face
(`code/archetypes.py` lines 914-1011 do template-seed Bloodthirster / Lord of
Change / Great Unclean One / Keeper of Secrets, and `code/leaders.py` lines
618-640 do wire the Bloodmaster / Changecaster / Poxbringer / Contorted
Epitome locus auras with host_keys). However, the templates do not actually
land those Greater Daemons in the deployed army — the locus carriers are
wired but the seed loop drops them. Three candidate levers below, in
priority order.

## Lever 1 — Greater Daemons template-seeded but almost never deployed

**File / line.** `code/archetypes.py` lines 1270-1406 (`_instantiate_template`)
and `code/archetypes.py` lines 951-1011 (mono-god templates).

**Empirical observation.** Across N=80 `build_archetype_army("Chaos
Daemons", 1000)` builds at four uniform-rotation mono-god archetypes
(expected 25% each), the locus-carrying Greater Daemons appear at:

  * Bloodthirster — 1% (expected ~25%)
  * Lord of Change — 0% (expected ~25%)
  * Great Unclean One — 5% (expected ~25%)
  * Keeper of Secrets — 0% (expected ~25%)
  * Skarbrand — 0% (in template, not in any archetype)
  * Karanak — 28% (the cheap EPIC HERO, lands reliably)

**Mechanism.** `_instantiate_template` walks `(-count, -cost)` and packs each
template entry until `seed_budget = points_budget * 0.3 = 300pt` is full.
The Khorne Murderhost template puts Bloodletters (count=3) and
Bloodcrushers (count=2) first; their first squads alone consume ~220pt of
the 300pt seed. The Bloodthirster's count=1 entry then has 305pt to land
in <80pt — never fits.

The iter24-D2 EPIC HERO anchor guarantee at line 1352-1377 forces the
priciest EPIC HERO into the army (with 1.5x overflow). But none of the
four Greater Daemons that carry the locus auras (Bloodthirster, Lord of
Change, Great Unclean One, Keeper of Secrets) are EPIC HERO in BSData
v10.6.0 (`MONSTER + CHARACTER + FLY + DAEMON` only — verified via
`UNIT_CATALOG`). The cheapest-CHARACTER fallback (line 1395-1404)
satisfies its check via the cheap heralds (Bloodmaster 65pt, Karanak
75pt) so the Greater Daemons never get the overflow allowance.

Net effect: Bloodthirster's "Daemon Lord of Khorne" `plus_one_to_hit_melee_only`
aura, Lord of Change's `plus_one_strength_ranged` aura, Great Unclean
One's `plus_one_toughness` aura, and Keeper of Secrets' `plus_one_ap_melee`
aura — wired in `code/leaders.py` 665-726 — fire on at most 1/100 sim
games. Locus carriers are present (the cheap heralds), Greater Daemon
auras are not.

**Wahapedia.** https://wahapedia.ru/wh40k10ed/factions/chaos-daemons/ — the
four Greater Daemons are flagship-tier ~250-305pt MONSTER CHARACTERs that
typically anchor real mono-god lists; their omission removes ~25% of the
faction's offensive uplift per archetype.

**Verdict.** **Fix-first candidate.** Extend the iter24-D2 EPIC HERO
anchor block (`code/archetypes.py` line 1352) to also catch MONSTER +
CHARACTER template entries that aren't EPIC HERO — or hard-pin Greater
Daemons via a Daemons-specific anchor (same shape as the Death Guard
Mortarion seed in `code/army_builder.py` line 506). Magnitude estimate:
the four locus auras at ~25% archetype rotation each, currently firing 0-5%
of builds, is ~+15% per-attack uplift on ~3 squads (the matching battleline)
across the missing 20-25% of games — back-of-envelope ~+5-8 win-rate
points uplift if all four land at template intent.

## Lever 2 — Daemons detachment carries no army-rule offensive flag

**File / line.** `code/detachments.py` lines 1086-1238. The Daemonic
Incursion detachment (line 1086) was stripped of its `plus_one_to_hit=True`
proxy in SC5-11 (2026-05-21) because Warp Rifts is a deep-strike-distance
rule, not a +1-to-hit. The four god-aligned variants (Blood Legion / Legion
of Excess / Plague Legion / Scintillating Legion, lines 1137-1238) are
composition-only — each notes the codex rule cannot be reduced to a
schema field without fabrication. Each variant ships with the same lone
stratagem (`DAEMONIC_INCURSION_STRATAGEMS = (DENIZENS_OF_THE_WARP,)` at
`code/stratagems.py` line 1253).

**Comparable codex coverage.** Necrons Awakened Dynasty
(`code/stratagems.py` line 279) carries six Protocol stratagems plus
`bonus_to_hit_when_led=True` plus `necrons_melee_ap_plus_one_army_wide`.
Aeldari Warhost (line 194) carries six stratagems. Adeptus Custodes
Shield Host (line 931) carries multiple flag-bearing detachment fields
plus stratagems. World Eaters Berzerker Warband: 1 stratagem +
`simulator.blessings_of_khorne` (the 8D6 army rule at
`code/simulator.py` line 3792-3905 implementing three of the codex
Blessings). Daemons has **only** Denizens of the Warp + Shadow of Chaos
(`code/simulator.py` line 4629-4760 — verified working, -1 Battle-shock
+ D3 mortals on fail).

The four god-aligned legions each model a real published codex
detachment rule (Murdercall / Beguiling Aura / Melancholic Miasma /
Fates in Flux) — each could carry at least an approximation-side flag:

  * **Blood Legion / Murdercall** (Khorne): per-trigger reactive Surge
    move. Not expressible — composition-only is the right call.
  * **Legion of Excess / Beguiling Aura** (Slaanesh): fall-back-then-
    charge — sim doesn't model Fall Back state. Composition-only OK.
  * **Plague Legion / Melancholic Miasma** (Nurgle): extends Shadow of
    Chaos by 9" around each Nurgle unit + per-Command-phase forced
    Battle-shock on a selected enemy. The forced-test leg has no hook,
    but the **first leg** could fire as a wider Shadow of Chaos radius
    when this detachment is picked (already extends from board-centre
    18" — could become 21" or per-Nurgle-unit 9"-aura). Not fabrication
    since the codex literally says "is within your army's Shadow of
    Chaos" → expanding coverage is direction-correct.
  * **Scintillating Legion / Fates in Flux** (Tzeentch): 3 Flux tokens
    spent on rerolls. No token economy — composition-only OK, BUT could
    add 1 stratagem-equivalent (a one-shot reroll for Tzeentch units),
    same shape as Awakened Dynasty's `cp_refund_per_battle` pool.

**Wahapedia.** https://wahapedia.ru/wh40k10ed/factions/chaos-daemons/ —
section "Faction Rules / Detachments". Real codex: each god-aligned
detachment ships 6-8 stratagems, none of which are wired.

**Verdict.** **Fix-first candidate** for the stratagem leg
(`DAEMONIC_INCURSION_STRATAGEMS` is 1-deep where comparable factions ship
6-8) — even if each ports through an approximation flag, the AI gets more
CP-spend levers. Plague Legion's Shadow-of-Chaos extension is a smaller
follow-up. Magnitude estimate: +2-4 wr-points from stratagem parity with
peer factions; another +1-2 from a wider Shadow of Chaos when Plague
Legion is rolled.

## Lever 3 — Greater Daemon locus auras gate on catalogue keys but BSData has no god keywords

**File / line.** `code/leaders.py` lines 196-298 (the four `_<GOD>_DAEMON_HOSTS`
tuples). Each is a hard-coded list of `chaos_daemons_library_*`
catalogue keys. The codex aura wording (line 198) is "While a friendly
KHORNE Legiones Daemonica unit is within 6\"". The simulator's gate
substitutes "is in this hard-coded host_keys list" for the keyword check.

**Empirical observation.** None of the 97 `faction=="Chaos Daemons"`
profiles in `UNIT_CATALOG` carries any of `KHORNE` / `TZEENTCH` /
`NURGLE` / `SLAANESH` / `LEGIONES DAEMONICA` keywords. Their `unit_keywords`
are stripped to `('INFANTRY', 'BATTLELINE', 'DAEMON')` and similar (verified
via direct UNIT_CATALOG inspection). The hard-coded substitution works for
the catalogue keys that exist today but:

  1. New Daemons units added in future BSData refreshes will silently
     miss the locus aura until manually added to the host tuple.
  2. The "Chaos Daemons" faction in BSData also bundles HERETIC ASTARTES
     allied units (Legionaries, Dark Commune, Havocs, Warp Talons, etc.
     — verified — 32 of the 97 profiles don't carry LEGIONES DAEMONICA
     in the actual codex). `_random_fill` picks these as same-faction
     daemonic-roster filler, diluting the mono-god army shape (e.g.
     seed=1 Khorne Murderhost build drafted Pink Horrors + Screamers
     + Fiends + Tzeentch Soul Grinder — Slaanesh+Tzeentch units in a
     Khorne template).
  3. The pollution by HERETIC ASTARTES allies in random_fill means even
     when a Bloodthirster does seed (1/100 builds), only a fraction of
     its in-aura squads will actually be Khorne-keyworded battleline
     because the army is dominated by allied CSM chaff.

**Wahapedia.** https://wahapedia.ru/wh40k10ed/factions/chaos-daemons/ —
every datasheet carries one of KHORNE / TZEENTCH / NURGLE / SLAANESH
plus LEGIONES DAEMONICA as faction keywords. The BSData mapper at
`code/bsdata/mapper.py` is dropping these from `unit_keywords`.

**Verdict.** **Needs more investigation.** Two separate sub-issues here:
  * (3a) BSData mapper not extracting god keywords — would need a mapper
    audit. Direction: trace why `LEGIONES DAEMONICA` doesn't survive
    `code/bsdata/mapper.py`. Smaller impact than Lever 1: even with
    god keywords, the auras still fire (the hard-coded tuples cover the
    real catalogue keys). The main payoff is correctness on
    `_random_fill` archetype purity, not direct WR uplift.
  * (3b) `_random_fill` should filter to god-tagged Daemons within a
    mono-god archetype rather than to `faction == "Chaos Daemons"`.
    Currently a Khorne build can pull in Tzeentch / Slaanesh battleline
    that the Bloodthirster aura can't buff anyway. Probably +1-2 wr-points
    if combined with Lever 1.

## Ranking

| # | Lever | Magnitude estimate | Confidence |
|---|-------|---------------------|------------|
| 1 | Greater Daemon seeding gap (`archetypes.py`) | ~+5-8 wr | high — empirical 0-1% vs expected 25% |
| 2 | Stratagem / detachment-flag parity | ~+3-6 wr | medium — peer-faction comparison only |
| 3 | God-keyword gate / random_fill purity | ~+1-2 wr | low — secondary to Lever 1 |

Lever 1 is the strongest fix-first candidate: the entire god-aura
investment in `code/leaders.py` (DAEMONS-DIAG-3, LEADERABILITY-SCHEMA)
is sitting dormant because the carriers don't actually deploy. Add the
MONSTER+CHARACTER-anchor branch parallel to the EPIC HERO branch at
`code/archetypes.py` line 1352 — small surgical change.
