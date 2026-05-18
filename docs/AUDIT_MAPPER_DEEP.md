# BSData Mapper Deep Audit (iter 13)

Diagnostic sweep for silent-skip / silent-overinclude bugs in
`code/bsdata/mapper.py`, in the spirit of the iter 11 `max_depth=3→5` fix.

## 1. Per-codex unit counts (parsed.json vs Wahapedia ballpark)

`python -m code.bsdata.mapper` produces **1532 entries, 1479 enabled, 53
skipped**. Counts per codex (enabled rows from parsed.json):

| Codex | Enabled | Plausible? |
|---|---:|---|
| Aeldari - Craftworlds | 96 | high — includes Aspect Warriors x10, Phoenix Lords, Wraith |
| Aeldari - Drukhari | 32 | matches Wahapedia roster (~30) |
| Aeldari - Ynnari | 3 | meta-codex stub, only Yvraine + Yncarne + Visarch |
| Chaos - Chaos Daemons Library | 66 | shared, includes all four god lists |
| Chaos - Chaos Daemons | 31 | the main mono-god subset |
| Chaos - Chaos Knights Library | 20 | matches Wahapedia (~20) |
| Chaos - Chaos Space Marines | 83 | high — Legends + Crucible swells this |
| Chaos - Death Guard | 53 | Wahapedia ~28 → BS extras: Crucible/Library |
| Chaos - Emperor's Children | 26 | matches new codex |
| Chaos - Thousand Sons | 42 | Wahapedia ~22 → BS adds Daemon-rule cross-refs |
| Chaos - World Eaters | 35 | high vs ~20 — Legends + Crucible |
| Genestealer Cults | 28 | matches Wahapedia |
| Adepta Sororitas | 40 | matches Wahapedia |
| Adeptus Custodes | 34 | matches Wahapedia |
| Adeptus Mechanicus | 42 | matches Wahapedia |
| Agents of the Imperium | 49 | high — every Inquisitor variant |
| Astra Militarum | 135 | high — Catachan/Krieg + Legends regiments |
| Black Templars | 20 | Marine subfaction (mostly shared SM via Library) |
| Blood Angels | 27 | as above |
| Dark Angels | 19 | as above |
| Deathwatch | 11 | as above (Legends-heavy chapter) |
| Grey Knights | 35 | matches Wahapedia |
| Imperial Knights - Library | 22 | matches Wahapedia |
| Space Marines | 134 | high — includes every chapter-Phobos/Sternguard variant |
| Space Wolves | 42 | matches Wahapedia |
| Leagues of Votann | 25 | matches Wahapedia |
| Necrons | 66 | matches Wahapedia (~56) plus Legends |
| Orks | 91 | high — Speed Freeks + Legends + Crucible |
| T'au Empire | 64 | matches Wahapedia (~50) plus Legends |
| Tyranids | 59 | matches Wahapedia |
| Unaligned Forces | 18 | terrain + neutral models |

**No faction looks dangerously thin.** Iter 11's depth fix already
restored the 22 missing datasheets; the remaining "high" counts come
from BS exposing Legends / Crucible / playtest profiles plus
chapter-flavour variants that share the underlying datasheet.

## 2. Skip-reason tally (53 skipped)

```
34  no unit profile (no W/SV characteristic) in tree
19  no ranged OR melee weapons resolvable in tree
```

All skipped rows are **non-datasheets** by inspection:

- **Detachment / Detachments / Order of Battle / Battle Focus / Show
  Hide / Show <god> Daemons** — BSData list-building UI hooks; every
  codex has one, total ~24 of the 34 "no W/SV" skips.
- **Fortifications & terrain Legends** — Aegis Defence Line, Tidewall
  Shieldline, Webway Gate [Legends], Battle Sanctum [Legends], Skyshield
  Landing Pad [Legends], Void Shield Generator [Legends], Wall of Martyrs
  [Legends], Skull Altar, Feculent Gnarlmaw. 11 of the 19 "no weapons"
  skips. These don't fight, so dropping them is correct.
- **Drop Pod / Dreadnought Drop Pod [Legends]** — transports with no
  weapons of their own; correct to drop (they're carried units).
- **Spore Mines / Mucolid Spores** (4 rows) — Tyranid "fire and forget"
  bombs that resolve via Deadly Demise rather than weapons; harmless to
  drop from the points-calibration corpus.
- **Cyclops Demolition Vehicle** (AM) — one-shot remote-controlled
  bomb; legitimately weapon-less in BSData's encoding (its "attack" is a
  Deadly Demise + stratagem effect).
- **Remote Sensor Tower / Mekboy Workshop / Searchlight / Code
  Chivalric / Unseated Pilot** — non-combat or rule-stub entries.

No real datasheet is being silently dropped. The two skip reasons are
acting as a clean filter for non-fighting entries.

## 3. Weapon keyword propagation (1532 enabled units)

```
ANTI keyword coverage:
  INFANTRY 76,  VEHICLE 30,  FLY 18,  MONSTER 15,  PSYKER 8,
  CHARACTER 3,  DAEMON 2,    TYRANIDS 1
heavy 109,    assault 138,   torrent 131,   hazardous 164,
blast 208,    lance 34,      precision 101, pistol 341,
indirect_fire 41, one_shot 28, stealth 78,
rapid_fire 134, melta 136,   twin_linked 158,
sustained_hits 134, devastating_wounds 171,
lethal_hits 64,  ignores_cover 187
```

The `_ANTI_RE` regex is **case-insensitive** so the lowercase
("Anti-infantry 2+") and uppercase ("ANTI-INFANTRY 3+") variants in raw
BSData are both caught. `_HEAVY_RE` / `_ASSAULT_RE` are case-sensitive
but a sweep of raw cat files showed **zero** lowercase "heavy" or
"assault" tokens — both keywords appear only in the canonical
title-case form, so the literal-case match is safe.

No missing tag families. ANTI-BEASTS, ANTI-MOUNTED, ANTI-CHARACTER are
all caught by the generic regex; they exist in BSData (e.g. one
"ANTI-BEASTS 3+", one "ANTI-MOUNTED 3+" in the Aeldari Library).

## 4. Unit-keyword propagation

Tracked set is `_TRACKED_UNIT_KEYWORDS` (line 1517 of mapper.py):
INFANTRY, VEHICLE, MONSTER, CHARACTER, FLY, TITANIC, TOWERING, WALKER,
BATTLELINE, SWARM, BIKE, MOUNTED, BEAST, DAEMON, PSYKER, ASURYANI,
TRANSPORT, SYNAPSE, EPIC HERO.

Categories present in BSData but **not tracked** (would expand the
keyword pool if needed by future simulator gates):

- `JUMP PACK` (47 carriers), `TERMINATOR` (53), `DREADNOUGHT` (22),
  `ARTILLERY` (24), `AIRCRAFT` (76), `FORTIFICATION` (39),
  `DEDICATED TRANSPORT` (43), `SQUADRON` (44), `GRENADES` (439).
- Faction-name categories (`ADEPTUS ASTARTES` 305, `CHAOS` 435,
  `IMPERIUM` 678, `AELDARI` 131, `NECRONS` 66, `T&APOS;AU EMPIRE` 66,
  `TYRANIDS` 63, `ORKS` 92, `DAEMON` 145, plus chapter / sub-faction
  tags like `WORLD EATERS`, `DEATH GUARD`, etc.).

Adding any of these is a one-line edit to `_TRACKED_UNIT_KEYWORDS`
plus the simulator gate that needs it. **Not bugs** — just unmodelled
features.

**Encoding note:** BSData stores T'au as `T&APOS;AU EMPIRE` (HTML
entity for the apostrophe). The mapper currently filters faction tags
out of the tracked set, so this never surfaces. If T'AU/T&APOS;AU is
ever added to `_TRACKED_UNIT_KEYWORDS`, the entity needs decoding
first (or both forms tracked) or the keyword will silently miss every
T'au unit.

## 5. Datasheet stat spot-check

| Unit | M-ish (range) | T | W | Sv | OC | Ld | pts | verdict |
|---|---|---:|---:|---|---:|---|---:|---|
| Intercessor Squad | 12 | 4 | 2.0 | 3+ | 2 | 6 | 80 | OK |
| Custodian Guard | 24 | 6 | 3.0 | 2+ | 2 | 6 | 160 | OK |
| Hellblaster Squad | 12 | 4 | 2.0 | 3+ | 1 | 6 | 110 | OK |
| Necron Warriors | 12 | 4 | 1.0 | 4+ | 2 | 7 | 90 | OK |
| Termagants | 12 | 3 | 1.0 | 5+ | 2 | 8 | 60 | OK |
| Kabalite Warriors | 24 | 3 | 1.0 | 4+ | 2 | 7 | 115 | OK |
| Wraithguard | 12 | 6 | 3.0 | 2+ | 1 | 8 | 160 | OK |
| Knight Errant | 24 | 11 | 26.0 | 3+ | 10 | 6 | 355 | OK |

(Note: `range_inches` is the best ranged weapon's range, NOT the
unit's Movement characteristic. Naming is fine; just don't confuse it.)

All stats match Wahapedia.

## 6. The one real bug I found: prose-FNP overcount

`extract_fnp` (mapper.py line 1616) has TWO paths:

1. **Canonical** — read `<infoLink name="Feel No Pain">` with a
   `<modifier type="append" value="N+"/>` child. Locked-down and safe.
2. **Prose fallback** — recursively walk infoLinks / entryLinks /
   characteristic text searching for `Feel No Pain N+`. Pick lowest.

The fallback is **structurally unsafe**: it picks up every mention of
"Feel No Pain N+" in reachable rule prose, including:

- Conditional grants ("against Psychic Attacks", "against mortal
  wounds") — Sisters of Silence units (Prosecutors, Vigilators,
  Witchseekers, Aleya), Knight-Centura, Anathema Psykana Rhino all
  read **FNP 3+** in parsed.json because they reach the Sisters'
  Auric Aquilas "Feel No Pain 3+ against Psychic Attacks" rule.
- Enhancement/relic carrier text ("The bearer has the Feel No Pain
  5+ ability") — Custodian Guard reads FNP 5+ from a Custodes Relic
  even though baseline Custodian Guard has no FNP.
- One-shot phase-gated activations ("Once per battle... Feel No Pain
  4+") — Trajann Valoris, Aleya, Valerian etc.

A conservative qualifier-token filter (drop matches whose
characteristic also contains `against`, `psychic`, `mortal wound`,
`the bearer`, `model only`, `this stratagem`, `this relic`, `this
enhancement`) **fixed every spot-checked false positive**, kept every
canonical FNP test green (Wracks, Wulfen, Repentia, Death Company,
Poxwalkers — `tests/test_mapper_fnp_infolinks.py`), and was tested in
this audit.

**But it made eval MAE WORSE**: 6.00 → 6.92 (vs real meta),
5.67 → 7.50 (vs Sweg-balanced). Custodes went from balanced to -4.9
behind real meta because removing their phantom FNP 5+ exposed how
weak their actual sim profile is. The phantom FNP was **compensating
for unmodelled defensive abilities** (Custodes Bodyguard re-rolls,
army-wide ablative wounds, Sagittarum 6+ FNP vs MW, etc.).

**Decision:** **NOT applying the fix.** Logically correct but
calibration-regressive. The cleaner path is to model the missing
Custodes defensive layer first (Bodyguard, ablative-wound re-rolls)
and *then* remove the FNP-prose compensation. Filed as a follow-up.

## 7. Top mapper bug findings, ranked by expected impact

| # | Bug | Impact | Should fix? |
|---|---|---|---|
| 1 | Prose FNP fallback over-grants from conditional / relic / stratagem text (§6) | Custodes / Sisters / Knight-Centura false FNP — but a naive fix worsens MAE | **Defer** until Custodes Bodyguard + ablative-wounds are modelled |
| 2 | `_TRACKED_UNIT_KEYWORDS` doesn't include JUMP PACK / TERMINATOR / DREADNOUGHT / AIRCRAFT (§4) | No active simulator gate needs them yet | Add when a gate needs them; one-line each |
| 3 | T&apos; HTML entity in T'au faction-category names (§4) | Currently dormant (faction tags filtered out) | Watch for it if simulator ever gates on faction-name keyword |
| 4 | Non-combat entries (Detachment / Show Hide / fortifications / Mucolid Spores / Spore Mines) consume skip-budget (§2) | None — they correctly drop | None |
| 5 | `_HEAVY_RE` / `_ASSAULT_RE` not case-insensitive (line 324–325) | Currently dormant — no lowercase variants in raw cat files | Watch on future BSData releases |

## 8. Eval gates (N=40)

- `python -m unittest discover -s tests` — **754 passed, 5 skipped, 0 failed**.
- `python -m scripts.audit_rules` — **green** (186/186 active rules cited).
- `PYTHONHASHSEED=0 python -m scripts.evaluate_vs_meta --battles 40`:

  ```
  MAE vs real meta:    6.00 pts (unchanged — no mapper change applied)
  MAE vs Sweg-balanced: 5.67 pts (unchanged)
  ```

## TL;DR

Iter 11's depth fix appears to have already captured the big silent
miss in the mapper. This deep audit found **one real bug** (prose-FNP
overcount inflating Custodes / Sisters defensive stats) and a few
dormant fragilities (case-sensitivity, HTML entities, missing tracked
keywords), but **the FNP fix worsens MAE** because the phantom FNP is
silently compensating for unmodelled Custodes defensive rules. Applying
it requires modelling Bodyguard + ablative-wounds first, otherwise
Custodes drop further off the real-meta target.

Iter 13 commit is **diagnostic-only** — no parsed.json or mapper
behaviour change. MAE is unchanged: **6.00 / 5.67**.
