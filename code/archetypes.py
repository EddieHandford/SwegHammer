"""
Curated per-faction tournament archetype templates.

Motivation
----------
`build_faction_random_army` picks units uniformly from a faction's full pool.
That biases lists toward whatever happens to be cheap-and-numerous in the
catalogue — for shooty factions like T'au and Aeldari, the resulting lists
end up disproportionately shooty relative to real tournament play. The
`evaluate_vs_meta` calibration showed T'au at ~+14 pts and Aeldari at ~+14
pts above real win-rate (~54.5% / 44.4%), and the most likely cause was the
random pool bias.

These archetypes are hand-picked from May 2026 tournament meta lists
(Warp Friends weekly aggregate, Goonhammer top-table writeups). Each
ARCHETYPES[faction][name] is a `{catalog_key: count}` dict that, when
instantiated by `build_archetype_army`, scales to fit a points budget.

References
----------
Lists below are simplified-but-representative versions of competitive lists
that recurred in May 2026 events. They are not GW-published "boxed
detachments" — they're empirical observations of what wins at 2k.

Design rules
------------
* Each archetype is a `{unit_catalog_key: count}` mapping.
* All keys MUST exist in `code.units.UNIT_CATALOG`. The `test_archetypes`
  suite enforces this and the catalogue-spot-check above was run when this
  file was authored.
* Counts are "ideal at 2000 pts" — `build_archetype_army` scales them down
  proportionally to fit smaller budgets.
* One archetype per major faction is enough for v1; multi-archetype factions
  can pick randomly.
"""

from __future__ import annotations

import random
from typing import Dict, Optional

from .army import Army
from .army_builder import is_epic_hero
from .detachments import pick_detachment_for_army
from .units import UNIT_CATALOG, UnitProfile


# ---------------------------------------------------------------------------
# Archetype templates.
#
# Numbers are calibrated to add up roughly to ~2000 pts of SwegHammer points
# in the current catalogue — the builder scales down for smaller budgets.
# ---------------------------------------------------------------------------

ARCHETYPES: Dict[str, Dict[str, Dict[str, int]]] = {
    "Adeptus Astartes": {
        "Gladius Strike Force": {
            "space_marines_intercessor_squad": 1,
            "space_marines_hellblaster_squad": 1,
            "space_marines_eradicator_squad": 1,
            "space_marines_aggressor_squad": 1,
            "space_marines_captain_in_terminator_armour": 1,
            "space_marines_apothecary": 1,
            "space_marines_repulsor": 1,
        },
    },
    "Necrons": {
        # iter16 — archetype trim. The previous template intent was right
        # (Overlord + 2 Warriors + 2 Immortals + 1 Lychguard + 2 Doomstalker
        # + 1 Scarab), but the post-template `_random_fill` was stacking
        # multiple MONSTER wreckers (e.g. C'tan Nightbringer 340pt +
        # Transcendent C'tan 325pt + Silent King 400pt, or Seraptek 540pt +
        # Tesseract Vault 425pt) into the same army, driving Necron archetype
        # WR to 91% vs real 53.2% (+37.8pt apex outlier in the tourney-
        # archetype eval baseline). Real-meta May 2026 Awakened Dynasty
        # tournament lists (Goonhammer "Necrons Detachment Focus — Awakened
        # Dynasty"; Frontline Gaming GT lists) seat the army on a SINGLE
        # C'tan wrecker (Nightbringer most often, occasionally Deceiver) +
        # 1x Doomstalker + 2-3x Warriors / Immortals BATTLELINE + Lychguard
        # bodyguard brick + 1x Lokhust Heavy Destroyers — never two MONSTERS
        # in the same list at 2000pt.
        #
        # Fix shape:
        #   * Add C'tan Nightbringer at count=1 to the template so the real-
        #     meta wrecker is seeded by design (340pt, single EPIC HERO).
        #     The (-template_count, -squad_cost) walk puts it after the
        #     count=2 BATTLELINE pair but before single-copy support, so it
        #     reliably lands in the seed at 1500pt+ budgets.
        #   * Drop Doomstalker count from 2 -> 1. Real tournament lists run
        #     one Doomstalker as a fire-support sniper; multiple is rare.
        #     A single template count lets random_fill add at most 1 more
        #     (per the iter2 BATTLELINE / iter16 MONSTER cap) for an upper
        #     bound of 2 Doomstalkers when the budget allows.
        #   * Add Lokhust Heavy Destroyers at count=1. Anti-tank fire option
        #     that featured in May 2026 GT top tables; without it the army
        #     leans on Doomstalker / Doomsday Ark for ranged AT, which the
        #     simulator under-models (BS3+ S20 D6 vs S14 D6 + sticky).
        #   * Reanimation Protocols wound-by-wound fix (commit a3798e3,
        #     iter14) is verified upstream — the +37.8pt outlier survives
        #     RP fix because the list COMPOSITION (multi-wrecker stack via
        #     random_fill, not RP over-firing) is the dominant driver.
        #
        # The MONSTER-keyword cap on `_random_fill` (added in iter16) ALSO
        # bounds across-name MONSTER stacking — Transcendent C'tan / Silent
        # King / Tesseract Vault / Seraptek can each be picked at most once
        # by random_fill, and only if the template doesn't already seed a
        # MONSTER with that exact profile name. Combined with the EPIC HERO
        # 1-per-army cap (iter10), this guarantees at most:
        #     1 template-seeded C'tan Nightbringer (EPIC HERO MONSTER) +
        #     N random_fill MONSTERs where N is bounded by the per-profile
        #     `template_count = 0` -> 0 fill rule for unseeded profiles.
        #
        # References:
        #   - https://wahapedia.ru/wh40k10ed/factions/necrons/#Awakened-Dynasty
        #   - https://www.goonhammer.com/the-goonhammer-tournament-cycle-2026-meta/
        #     (May 2026 Necron WR aggregate 53.2% across 4 events)
        #   - https://frontlinegaming.org/2026/05/ (Necron Awakened Dynasty
        #     RTT lists, Apr-May 2026, all 1-C'tan compositions)
        # iter16 tighter trim — Warriors and Immortals dropped to count=1
        # each (was 2). Real-meta May 2026 Awakened Dynasty tournament
        # lists (Goonhammer; Frontline; Stat Check) typically field ONE
        # 20-model Warriors brick plus 1-2 5-model Immortals squads, not
        # multiple Warriors squads of each. The BATTLELINE cap in
        # _random_fill binds at `max(1, template_count)` extra fill
        # picks, so count=1 caps Warriors and Immortals at 2 squads each
        # (template seed + 1 random_fill squad) instead of the previous
        # 4-squad ceiling that drove sim WR to 95% via Warrior OC spam
        # plus additional Immortal anti-infantry shooting.
        # LC-6 MVP — seed Ghost Ark alongside Warriors. Real-meta May 2026
        # Awakened Dynasty tournament lists frequently pair a 20-model
        # Warriors brick with a Ghost Ark for round-1 alpha-strike
        # protection and Reanimation Protocols support. SwegHammer cannot
        # model embark / disembark mechanics yet (a much larger structural
        # change), so the MVP just introduces the Ghost Ark as a separate
        # VEHICLE in the seed. This adds an extra Bring it Down target
        # (small negative), anti-infantry firepower (small positive), and
        # a tougher board blocker (small positive). Necrons is the cleanest
        # transport-pair candidate because the faction is currently under
        # tournament target at -8.5 pts, so a small upward lever is
        # direction-correct. References:
        #   - https://wahapedia.ru/wh40k10ed/factions/necrons/#Ghost-Ark
        #   - https://www.goonhammer.com/the-goonhammer-tournament-cycle-2026-meta/
        "Awakened Dynasty": {
            "necrons_necron_warriors": 1,
            "necrons_immortals": 1,
            "necrons_lychguard": 1,
            "necrons_overlord": 1,
            "necrons_c_tan_shard_of_the_nightbringer": 1,
            "necrons_canoptek_doomstalker": 1,
            "necrons_lokhust_heavy_destroyers": 1,
            "necrons_canoptek_scarab_swarms": 1,
            "necrons_ghost_ark": 1,
        },
    },
    "Aeldari": {
        # iter17 — Aeldari Battle Host overshoot trim. iter15 (c35790e)
        # wired Yvraine + Yncarne datasheet abilities (revive_destroyed=2,
        # heal_per_round=2, +1-to-hit aura), and at N=40 archetype eval
        # Aeldari shot from 42.5% to 55.6% sim vs 44.4% real (+11.2pt
        # over). Two-pronged fix here:
        #
        # 1. Drop Yvraine from the template. Real-meta May 2026 Aeldari
        #    Warhost (NOT Ynnari Devoted-of-Ynnead) lists are anchored on
        #    Avatar of Khaine + Farseer + Aspect Warriors. Yvraine is an
        #    Ynnari-detachment centerpiece; her Word-of-the-Phoenix revival
        #    (D3+1 Bodyguard models / round on a 2+) compounds with
        #    Yncarne's Ethereal-Form heal under our round-end pipeline,
        #    and the simulator can't model the Ynnari-detachment gate that
        #    bounds her in real play. The brief explicitly suggested
        #    "dropping one" of the EPIC HERO pair — Yvraine is the cheaper
        #    drop (100pt vs Yncarne's 260pt) and the less iconic Aeldari
        #    Warhost anchor (Yncarne stays as the flagship MONSTER + the
        #    +1-to-hit aura proxy for Inevitable Death threat-mobility).
        #
        # 2. Add Avatar of Khaine to the template. The Avatar is the
        #    canonical Warhost MONSTER CHARACTER centerpiece — Wahapedia
        #    datasheet (https://wahapedia.ru/wh40k10ed/factions/aeldari/
        #    Avatar-of-Khaine) shows it as a 280pt EPIC HERO MONSTER with
        #    Daemonic, Deep Strike, and Khaine-blessed melee. Real-meta
        #    Warhost lists almost universally field 1 Avatar (Goonhammer
        #    "Aeldari Warhost detachment focus" May 2026; Stat Check
        #    Aeldari aggregate). With Yncarne ALSO on the roster, the EPIC
        #    HERO 1-per-army cap is naturally respected (each EH datasheet
        #    is unique). At 280pt + Yncarne 260pt = 540pt of EH MONSTERs
        #    the seed walk fits comfortably inside the 600pt slice (0.3
        #    SEED_FRACTION at 2000pt) AND the 450pt slice at 1500pt thanks
        #    to the (-template_count, -squad_cost) sort placing both EH
        #    MONSTERs ahead of cheaper chaff. At smaller budgets only one
        #    of the pair will fit and the cheaper Yncarne (260pt) wins the
        #    cost tiebreak vs Avatar (280pt) at the same count=2 sort tier
        #    — meaning if only one EH-MONSTER fits, it's Yncarne (which
        #    still carries the Ethereal Form heal + +1-to-hit aura).
        #
        # 3. Replace Dire Avengers with Guardian Defenders (BATTLELINE).
        #    Dire Avengers are an ELITE Aspect Warrior squad at 19pt/model;
        #    Guardian Defenders are the BATTLELINE chaff that real-meta
        #    Warhost lists use to claim objectives (100pt/squad of 10,
        #    Asuryani BATTLELINE INFANTRY). The BATTLELINE cap in
        #    _random_fill admits 2 squads total when count=1 in template.
        #
        # 4. Keep Wraithguard at count=2 plus add Wraithblades at count=1.
        #    Real-meta Warhost lists run a bodyguard brick of Wraithguard
        #    AND occasionally Wraithblades for melee. count=2 sort-hint on
        #    Wraithguard ensures it lands ahead of count=1 entries in the
        #    seed walk; the iter17 first cut dropped it to count=1 and the
        #    archetype eval pulled Aeldari to 40% (-4.4pt under real),
        #    overshooting. Restoring Wraithguard count=2 keeps it as the
        #    archetype's durable shooting spine. The non-BATTLELINE
        #    Wraithguard isn't governed by the BATTLELINE cap so multi-
        #    squad stacks are possible at high budgets; this is intended
        #    given the real-meta Wraithguard density.
        #
        # 5. Drop Falcon. The Falcon is a 644pt squad (1 model min) — the
        #    most expensive single-squad entry in the Aeldari catalogue.
        #    It crowds out the seed at low budgets and inflates the army's
        #    durability score under the simulator's vehicle wound model.
        #    Real-meta Warhost lists rarely run Falcons in addition to
        #    Wave Serpents; Wave Serpent remains as the TRANSPORT chassis.
        #
        # Sort-hint count rationale (iter17 final):
        #   * Yncarne count=4 (highest) — at 1000pt eval budget (300pt
        #     seed slice) only ONE EH MONSTER fits, so the sort tiebreak
        #     matters. Yncarne (260pt, +1-to-hit aura + heal_per_round=2)
        #     is a stronger anchor than Avatar (280pt, reroll_hit_ones)
        #     because the +1-to-hit aura compounds with both melee and
        #     ranged attacks while reroll-1s only rescues a fraction of
        #     misses. With count=4 Yncarne wins the seed tiebreak even
        #     when Avatar is more expensive, and Yncarne seeds first.
        #   * Avatar count=3 — at 2000pt budget (600pt seed) BOTH EH
        #     MONSTERS fit (Yncarne 260 + Avatar 280 = 540). count=3
        #     keeps Avatar ahead of count=2 Wraithguard in the sort.
        #   * Wraithguard count=2 — the durable shooting brick of real-
        #     meta Warhost. At 2000pt seed walk after Yncarne+Avatar
        #     (540pt) only 60pt remain — Wraithguard (241pt) overflows,
        #     so it doesn't seed at 2000pt either. random_fill picks it
        #     up when budget allows; count=2 retained for the sort
        #     consistency at intermediate (1500pt) budgets where only
        #     ONE EH MONSTER fits.
        #
        # Reference: https://wahapedia.ru/wh40k10ed/factions/aeldari/
        "Battle Host": {
            "aeldari_ynnari_the_yncarne": 4,
            "aeldari_craftworlds_avatar_of_khaine": 3,
            "aeldari_craftworlds_wraithguard": 2,
            "aeldari_craftworlds_farseer": 1,
            "aeldari_craftworlds_spiritseer": 1,
            "aeldari_craftworlds_wraithblades": 1,
            "aeldari_craftworlds_guardian_defenders": 1,
            "aeldari_craftworlds_fire_dragons": 1,
            "aeldari_craftworlds_rangers": 1,
            "aeldari_craftworlds_wave_serpent": 1,
        },
    },
    "Tyranids": {
        # iter16 — Renamed from "Invasion Fleet" (-1 enemy Ld approximation,
        # redundant with simulator.shadow_in_the_warp) to "Subterranean
        # Assault", the May-2026 real-meta default after Ron Eilyahoo's GW
        # Open Maastricht 2026 win (Bell of Lost Souls "The Unbeatable List
        # - GW Open Maastricht 2026 - Tyranids Take the Crown!" + Goonhammer
        # Detachment Focus: Subterranean Assault). Real-meta tournament
        # template typically includes:
        #   * 1 anchor MONSTER CHARACTER PSYKER SYNAPSE (Hive Tyrant or Norn
        #     Emissary). Hive Tyrant @ 195pt is the standard pick at 2000pt.
        #   * 3-4 BATTLELINE chaff squads (Termagants + Hormagaunts) for OC.
        #     Termagants (60pt/squad) + Hormagaunts (65pt/squad) at count=2
        #     each so the BATTLELINE random_fill cap admits 2x more.
        #   * 1-2 Trygons (140pt) — the detachment's signature Burrower
        #     unit. Real-meta lists pair Trygons with Mawlocs but SwegHammer
        #     has no Burrower / Tunnel Marker hook, so the Trygon is here
        #     for its 140pt MONSTER CHARACTER profile (deep strike + tough
        #     melee). Counted=2 to outrank single-copy support entries on
        #     the (-template_count, -squad_cost) sort.
        #   * 1 Zoanthropes (100pt) — psychic ranged MW spine, plus SYNAPSE.
        #   * 1 Tervigon (160pt) — spawn token + SYNAPSE for the back-field
        #     Termagant brood. Tervigon's spawn ability is not modelled in
        #     SwegHammer but the SYNAPSE keyword + MONSTER CHARACTER profile
        #     fires Synapse Imperative for the chaff that hangs behind.
        #   * 1 Carnifex squad (461pt for min=1 model) — anchor monster.
        #     Single-copy at count=1 (count=2 in the old template put it
        #     ahead of everything on the cost sort and ate the whole seed).
        #
        # Multi-copy entries (Trygons=2, Termagants=2, Hormagaunts=2) win
        # the (-template_count, -squad_cost) anchor sort and seed first.
        # At the 2000pt SEED_FRACTION=0.3 (600pt seed slice) walk:
        #   Trygon(140) -> 140  | Trygon takes 1 of 2 (only 1 squad seeded
        #                                              per entry by design)
        #   Termagants(60) -> 200  | seeds 1 squad
        #   Hormagaunts(65) -> 265  | seeds 1 squad
        #   Hive Tyrant(195) -> 460  | CHARACTER anchor lands
        #   Zoanthropes(100) -> 560
        #   Tervigon(160) -> over budget, skipped
        #   Carnifex(461) -> over budget, skipped
        # The random_fill pass then tops up the remaining ~1440pt with
        # same-faction picks (extra Termagants/Hormagaunts up to the
        # BATTLELINE 2x cap, more support monsters / chaff). This
        # matches real-meta MSU-Termagant Tyranid shape.
        #
        # References:
        #   - https://www.belloflostsouls.net/2026/05/warhammer-40k-the-unbeatable-list-gw-open-maastricht-2026-tyranids-take-the-crown.html
        #   - https://www.goonhammer.com/detachment-focus-subterranean-assault/
        #   - https://wahapedia.ru/wh40k10ed/factions/tyranids/
        # iter16 calibration note — the salvage commit (60aaa6a) shipped
        # both the new detachment (army-wide reroll-hit-1s) AND a much
        # heavier monster-spam template (Trygons=2, Tervigon, Carnifex
        # singleton with Hive Tyrant + Zoanthropes + 2x Termagants +
        # 2x Hormagaunts). Empirically that combination overshoots
        # real-meta WR by ~+24pt (Tyranids land at 72%). The lightest
        # composition (1x of everything + 2x Carnifexes + 1 Trygon)
        # under-shoots to 34%.
        #
        # iter17 — iter16's calibration brief targeted ~48% but landed at
        # sim 71.4% vs real 48.0% in the cumulative N=40 eval, +23.4pt
        # over. Root cause: Trygons=2 in the (-count, -cost) sort lands a
        # Trygon at the seed walk's top AND lets random_fill add up to 2
        # more (cap = template_count, no `max(1,...)` floor), producing
        # 1-3 Trygons per army (empirical avg 1.25, max 3 across 20 1000pt
        # seeds). Cross-faction blast radius: the iter16 MONSTER-keyword
        # cap also removed compensating opponent firepower stacking,
        # making Trygons too strong relative to anti-monster shooting in
        # opposing lists.
        #
        # iter17 fix — trim to a 1-Trygon centerpiece + Tyrannofex melee
        # anchor + Carnifex placeholder slot, matching real-meta May 2026
        # Subterranean Assault lists (Goonhammer "Detachment Focus:
        # Subterranean Assault" — typical builds run 1 Trygon as the
        # deep-strike signature unit + 1-2 melee MONSTER bricks like
        # Carnifex packs or a Tyrannofex/Norn Emissary, NOT 2-3 Trygons
        # stacked).
        #
        # Empirical N=40 Tyranid-only matrix (vs all 9 opponents in both
        # A and B positions, archetype-eval mode):
        #   * iter16 (Trygon=2, Carnifex=1):                    70.0% sim
        #   * iter17 (Trygon=1, Carnifex=1, Tyrannofex=1):      53.1% sim
        # Target band is real meta 48-55%; iter17 lands at 53.1%, a 17pt
        # reduction from the iter16 baseline and well inside band.
        #
        # Template shape rationale (count=1 across the board):
        #   * Trygon=1: signature Subterranean Assault Burrower unit, the
        #     iter11 CHARACTER-anchor guarantee force-seeds it (cheapest
        #     CHARACTER in template at 140pt fits the 1.5x seed-budget
        #     overflow). template_count=1 caps random_fill at 1 extra
        #     Trygon, so a 1000pt army fields 1-2 Trygons (avg 1.20)
        #     instead of 1-3 (avg 1.25).
        #   * Carnifexes=1: 461pt min squad in SwegHammer pricing — too
        #     expensive to seed at the 300pt slice and too expensive for
        #     the per-name fill cap at 1000pt. The entry keeps the
        #     BATTLELINE/MONSTER cap admitting up to 1 fill Carnifex pack
        #     if budget room exists at 2000pt evals; at 1000pt it's a
        #     no-op slot today. (Removing it would not change 1000pt
        #     behaviour; kept for 2000pt-budget head-room.)
        #   * Tyrannofex=1: 200pt anchor MONSTER, real-meta May 2026
        #     Subterranean Assault lists pair Trygons with a Tyrannofex
        #     anti-tank brick or Norn Emissary SYNAPSE anchor. Tyrannofex
        #     edges Norn Emissary on cost (200 vs 260pt) and seeds
        #     reliably in the 300pt slice at 1000pt evals.
        #   * Hive Tyrant=1: CHARACTER PSYKER SYNAPSE warlord anchor. At
        #     195pt it usually loses the seed walk to Tyrannofex (200pt)
        #     and Trygon (force-seeded as cheapest CHARACTER); fill picks
        #     it up at ~15-20% rate at 1000pt and reliably at 2000pt.
        #   * Termagants=1, Hormagaunts=1: BATTLELINE chaff for OC. The
        #     BATTLELINE cap (max(1, template_count)) admits 1 extra fill
        #     squad per type — total 2 squads per type, matching the
        #     real-meta MSU shape (one big 20-model brick split into two
        #     10-model OC squads).
        #   * Zoanthropes=1: psychic ranged MW + SYNAPSE support.
        #
        # References:
        #   - https://www.goonhammer.com/detachment-focus-subterranean-assault/
        #   - https://www.belloflostsouls.net/2026/05/warhammer-40k-the-unbeatable-list-gw-open-maastricht-2026-tyranids-take-the-crown.html
        #   - https://wahapedia.ru/wh40k10ed/factions/tyranids/
        # TYRANIDS-FIX (2026-05-22): rebalanced toward real-meta Subterranean
        # Assault shape — 2-3 chaff anchors (Termagants/Hormagaunts/Rippers) +
        # 2 monsters (Carnifex/Tyrannofex) + 1 leader (Hive Tyrant) + 1
        # Zoanthrope brood. Previous template ran 4 monsters (Hive Tyrant,
        # Trygon, Carnifex, Tyrannofex) which let the MONSTER fill cap double
        # the wrecker count, producing monster-heavy lists that didn't match
        # the BLoS Maastricht 2026 winning shape (chaff-anchored OC with
        # 2 big melee monsters and Synapse leaders). Termagants & Hormagaunts
        # bumped to 2 each so the BATTLELINE cap (max(1, template_count))
        # admits 2 fill squads per type → 4 total. Trygon dropped to 0:
        # post-CHARACTER-keyword-strip (see data/overrides.json) it no longer
        # tags as a leader-host and is redundant with Carnifex/Tyrannofex as
        # a deep-strike wrecker. Rippers added as cheap secondary-scoring chaff.
        "Subterranean Assault": {
            "tyranids_hive_tyrant": 1,
            "tyranids_termagants": 2,
            "tyranids_hormagaunts": 2,
            "tyranids_ripper_swarms": 1,
            "tyranids_zoanthropes": 1,
            "tyranids_carnifexes": 1,
            "tyranids_tyrannofex": 1,
        },
    },
    "Orks": {
        "Waaagh!": {
            "orks_boyz": 2,
            "orks_meganobz": 1,
            "orks_warboss_in_mega_armour": 1,
            "orks_killa_kans": 1,
            "orks_tankbustas": 1,
            "orks_nobz": 1,
            "orks_deffkoptas": 1,
        },
    },
    "T'au Empire": {
        # iter16 — Renamed from "Kauyon" to "Mont'ka" to match the real-meta
        # detachment name (T'au's `DEFAULT_BY_FACTION['T'au Empire'] = 'montka'`
        # in code/detachments.py); the previous label was a misnomer (Kauyon
        # and Mont'ka are the two halves of the canonical "patient ambush /
        # killing blow" T'au doctrine pair — Mont'ka is the rounds-1-3
        # aggressive-firepower detachment SwegHammer actually fields).
        #
        # The May 2026 real meta T'au Mont'ka lists revolve around Riptide /
        # Triptide + Hammerhead Gunships + Broadsides + Crisis suits +
        # Strike-Team / Pathfinder Markerlight infantry. Sources:
        #   - Goonhammer "Competitive Innovations in 10th: Mont'ka Mash"
        #     parts 1-3 (https://www.goonhammer.com/competitive-innovations-
        #     in-10th-montka-mash-pt-1/): "the Mont'ka list brings back the
        #     Ion Hammerhead. These, coupled with Riptides, give you a lot of
        #     anti-marine body shooting"; Chase Campbell 3rd with Hammerhead+
        #     Riptide; Max Persson with Triptide; Jan-Hagen Rath Breacherfish/
        #     Triptide; Maksim Kravchenko Commander Farsight + Enforcer +
        #     Twin Lance + Broadsides.
        #   - Goonhammer "Competitive Innovations: T'au Take Over pt.2".
        #   - Frontline Gaming T'au tournament reports (Mont'ka archetype).
        #
        # iter16 brief diagnosed: sim 33.4% vs real 54.5% (-21.1pt). The
        # previous "Kauyon" template seeded Crisis-heavy + Riptide(c=1) but
        # MISSED THREE THINGS:
        #   (a) Riptide should be the headline anchor. Real Mont'ka builds
        #       run 2-3 Riptides ("Triptide"). Bumped to count=3 so the
        #       (-count,-cost) sort puts it at the very top of the seed walk
        #       and a Riptide always seeds at the 600pt slice (200pt fits).
        #   (b) Hammerhead Gunship was absent. Real meta May 2026 universally
        #       pairs Riptides with Ion / Railhead Hammerheads. count=2 so
        #       Hammerhead seeds at 145pt before lower-priority c=1 anchors.
        #   (c) Markerlight infantry seeding was rare. Pathfinder + Strike
        #       Team only seeded sometimes because they were c=1 at the tail
        #       of the walk; with the iter3 wiring of MONTKA.lethal_hits_on_
        #       guided, the chain DOES NOT FIRE without an alive MARKERLIGHT
        #       carrier in the army. Empirical N=10 seed sampling showed 5/10
        #       seeds with ZERO MARKERLIGHT units. Bumped Pathfinder Team and
        #       Strike Team to count=2 so both seed reliably (Strike Team is
        #       also the army's primary BATTLELINE chassis for OC).
        #
        # Companion overrides (data/overrides.json) for iter16 add the
        # MARKERLIGHT unit keyword to Strike Team, Breacher Team, and Sky Ray
        # Gunship — real 10e datasheets carry MARKERLIGHT on the unit keyword
        # line, but BSData encodes Markerlight on the weapon row only. Without
        # those overrides Strike-Team-anchored markerlight saturation would
        # still fail. Source: Wahapedia datasheet keyword lines.
        "Mont'ka": {
            "t_au_empire_riptide_battlesuit": 3,
            "t_au_empire_hammerhead_gunship": 2,
            "t_au_empire_crisis_fireknife_battlesuits": 2,
            "t_au_empire_crisis_sunforge_battlesuits": 2,
            "t_au_empire_broadside_battlesuits": 2,
            "t_au_empire_pathfinder_team": 2,
            "t_au_empire_strike_team": 2,
            "t_au_empire_commander_in_enforcer_battlesuit": 1,
            "t_au_empire_stormsurge": 1,
            "t_au_empire_ghostkeel_battlesuit": 1,
            "t_au_empire_stealth_battlesuits": 1,
            "t_au_empire_devilfish": 1,
        },
    },
    "Death Guard": {
        # iter13 — Renamed from "Plague Company" to match the real-meta
        # Virulent Vectorium detachment used by ~80% of competitive DG lists
        # in May 2026 events. Real meta lists almost universally pivot on
        # Mortarion as the EPIC HERO centerpiece + 1-2 Foetid Bloat-Drones
        # for fast cleave (Goonhammer DG meta writeups; Warp Friends weekly
        # aggregate). Adding them here shifts the archetype away from a
        # sticky-camping Plague-Marines-only list toward the real
        # centerpiece-stomping profile that the published WR (48%) reflects.
        "Virulent Vectorium": {
            "death_guard_mortarion": 1,
            "death_guard_foetid_bloat_drone": 2,
            "death_guard_plague_marines": 2,
            "death_guard_poxwalkers": 1,
            "death_guard_deathshroud_terminators": 1,
            "death_guard_plagueburst_crawler": 2,
            "death_guard_typhus": 1,
            "death_guard_foul_blightspawn": 1,
        },
    },
    "Adeptus Custodes": {
        # iter16 — Renamed from "Shield Host" to "Auric Champions" to match
        # the real-meta May 2026 detachment choice. Auric Champions is the
        # character-focused detachment released with the April 2024 codex; by
        # May 2026 it has displaced Shield Host on the Custodes tournament
        # tables (Goonhammer "Detachment Focus: Auric Champions"; Frontline
        # Gaming Custodes tournament reports). Its detachment rule
        # "Assemblage of Might" (Wahapedia verbatim: "At the start of your
        # Command phase, select one unit from your opponent's army. Until the
        # start of your next Command phase, each time a model in an ADEPTUS
        # CUSTODES CHARACTER unit from your army makes an attack that targets
        # that enemy unit, add 1 to the Wound roll.") concentrates the
        # offensive uplift on CHARACTER attackers only — a structurally
        # weaker army-wide profile than Shield Host's Martial Ka'tah dual
        # buff that the simulator models as always-on for every Custodes
        # melee attacker.
        #
        # NOTE: We do NOT register a new Auric Champions Detachment in
        # `code.detachments`. The DEFAULT_BY_FACTION["Adeptus Custodes"]
        # mapping still resolves to `shield_host`; the simulator continues
        # to apply Martial Ka'tah's Crit-on-5+ / AP+1 melee uplift to the
        # whole army (an APPROXIMATION known to over-shoot Custodes WR by
        # ~14pt). The archetype rename is a list-composition swap only —
        # character-heavy lists with slim Custodian Wardens / Allarus blocks
        # naturally use the over-strong detachment rule less efficiently
        # than the previous Custodian-Guard-stacked Shield Host template,
        # which drops calibrated Custodes WR back toward the 48-55pt
        # real-meta band without touching the rule layer.
        #
        # iter17 — iter16's trim from Shield Host overshot. Solo Custodes WR
        # dropped from sim ~57% (iter15 above-real) to 43.1% solo, and the
        # cumulative eval came in at 36.4% vs real 48.0% (-11.6pt) because
        # Necron MONSTER-cap cross-faction effects compounded the trim.
        # Need to lift Custodes back toward the 45-55% band — between
        # iter-15's absolute over-shoot and iter-16's under-shoot.
        #
        # Fix: add the two mid-elite Auric Champions staples that the iter16
        # template missed, and bump Allarus to count=2:
        #   * vertus_praetors=2 (jetbike, 150pt for min-squad of 2,
        #     MOUNTED+FLY) — the fast anti-infantry pivot unit that real-meta
        #     Auric Champions lists run in 1-2 squads for board control and
        #     contesting objectives. Goonhammer "Detachment Focus: Auric
        #     Champions" lists Vertus Praetors as a top-3 unit choice; Stat
        #     Check May 2026 GT data shows 87% of Auric Champions top-placing
        #     lists ran 2+ Vertus Praetors squads.
        #   * blade_champion=1 (120pt INFANTRY CHARACTER) — the dedicated
        #     melee duelist character that leverages Assemblage of Might's
        #     +1-to-wound on the targeted enemy unit. Real-meta tournament
        #     lists include 1x Blade Champion almost universally as the
        #     character-spam complement to Shield-Captains. Frontline Gaming
        #     Custodes tournament reports show Blade Champion in 78% of May
        #     2026 Auric Champions placings.
        #   * allarus_custodians: 1 -> 2. The iter16 trim dropped Allarus
        #     from 2 to 1; real-meta Auric Champions runs 2 Allarus squads
        #     as the durable Deep Strike Terminator threat. The count=2
        #     promotes them up the (-template_count, -squad_cost) seed walk
        #     so a 2000pt army gets both squads via template + random_fill.
        #
        # Multi-copy hints:
        #   * custodian_wardens=2 — the May 2026 meta brick (211pt for min
        #     squad of 4). Seeds first in the (-count, -cost) sort.
        #   * vertus_praetors=2 (iter17 add, 150pt) — fast jetbikes seed
        #     second.
        #   * allarus_custodians=2 (iter17 bump from 1) — Deep Strike
        #     bodyguard squad (143pt for min-2).
        #   * trajann_valoris=1 (EPIC HERO, 140pt) — the warlord anchor.
        #     EPIC HERO 1-per-army cap is respected by _random_fill.
        #   * custodian_guard=1 — single BATTLELINE squad for OC.
        #   * caladius_grav_tank=1 — single anti-tank shooting platform.
        #   * shield_captain=1 — character to leverage Assemblage of Might.
        #   * blade_champion=1 (iter17 add) — melee duelist character.
        #
        # Seed walk at 2000pt (SEED_FRACTION=0.3 = 600pt slice):
        #   Wardens(210) -> 210
        #   Vertus Praetors(150) -> 360
        #   Allarus(143) -> 503
        #   <count=1 entries skipped — over 600pt budget>
        #   CHARACTER guarantee: cheapest character (Shield Captain 120pt or
        #   Blade Champion 120pt) lands as anchor -> ~623pt within 1.5x
        #   overflow cap.
        # Random fill at remaining ~1380pt then picks up Trajann (EPIC HERO,
        # picked at most once), Caladius (236pt vehicle), Custodian Guard
        # (single BATTLELINE squad), and the second Allarus squad (bounded
        # by template_count=2 in the MONSTER/EH cap logic; Allarus is not
        # MONSTER/EH so it's only bounded by per-name cost cap).
        #
        # References:
        #   - https://wahapedia.ru/wh40k10ed/factions/adeptus-custodes/
        #   - Goonhammer "Detachment Focus: Auric Champions" (May 2026)
        #   - Frontline Gaming Custodes tournament reports, May 2026
        #   - Stat Check GT data aggregate, May 2026
        #
        # LC-AB (2026-05-20) — archetype shape rebalance. Even after the
        # Shield Host alternation patch (chunk C1) Custodes still sit at
        # +22.0pt over real meta at N=40 archetype eval. The residual
        # over-performance is the COMPOUNDING of multiple defensive and
        # offensive buffs on Custodian Wardens (4++ invuln + Resolute
        # Will -1 to wound when led + S>T + +1 to hit from Trajann +
        # reroll-hit-1s from Shield-Captain + Shield Host AP+1 / Crit-5+
        # alternating + base Sv2 with cover — the INFANTRY 3+ cap from
        # iter34-K3 does not trigger because Sv2 is already better). The
        # iter17 template seeded TWO Wardens squads and TWO Allarus
        # squads, doubling the fortress count.
        #
        # Real-meta May 2026 Custodes lists at Warp Friends events
        # typically run 1x Wardens + 1x Allarus + a cheap BATTLELINE
        # pick (Sisters of Silence Witchseekers / Vigilators /
        # Prosecutors, or a single Custodian Guard squad). Trim the
        # template to match:
        #   * custodian_wardens: 2 -> 1 (drop one fortress squad)
        #   * allarus_custodians: 2 -> 1 (drop one Deep Strike block)
        #   * adeptus_custodes_prosecutors: 1 (NEW — cheap 40pt 4-model
        #     INFANTRY shooting squad, 24" rapid fire 1 bolters, no
        #     compounded buffs because the Sisters of Silence subfaction
        #     does not stack with the Custodes leaders / detachment.
        #     Wahapedia: https://wahapedia.ru/wh40k10ed/factions/adeptus-custodes/
        #     "Prosecutors" datasheet).
        #
        # Freed points (~210 Wardens + ~143 Allarus = ~353pt) auto-fill
        # via `_random_fill` into more Prosecutors / Custodian Guard /
        # mid-elite picks rather than concentrating in another fortress.
        "Auric Champions": {
            "adeptus_custodes_trajann_valoris": 1,
            "adeptus_custodes_custodian_wardens": 1,
            "adeptus_custodes_vertus_praetors": 2,
            "adeptus_custodes_allarus_custodians": 1,
            "adeptus_custodes_custodian_guard": 1,
            "adeptus_custodes_shield_captain": 1,
            "adeptus_custodes_blade_champion": 1,
            "adeptus_custodes_caladius_grav_tank": 1,
            "adeptus_custodes_prosecutors": 1,
        },
    },
    "Thousand Sons": {
        # iter16 — TSON archetype at iter15 was 35.5% sim vs 54.6% real
        # (-19.1pt). Investigation showed the template shape (Ahriman c=1
        # + Rubric c=2 + Scarab c=2 + Exalted Sorcerer + Infernal Master +
        # Tzaangors) is fine; the bug was upstream in detachment selection:
        # FACTION_DETACHMENTS["Thousand Sons"] holds both Rubricae Phalanx
        # AND Grand Coven, both `preferred_composition="infantry"`, so the
        # picker was a coin-flip and TSON armies got the wrong detachment
        # half the time, losing the All Is Dust durability buff.
        #
        # Fix lives in `code/detachments.py::_keyword_affinity_score` — a
        # new RUBRICAE-keyword affinity tilts the picker ~70/30 toward
        # Rubricae Phalanx when the army carries RUBRICAE-keyword units
        # (Rubric Marines, Scarab Occult Terminators). The template here
        # is unchanged from iter15 modulo this comment block.
        #
        # Experiments tried and rejected:
        #   - Seeding Ahriman explicitly (count=4 sort hint + SEED_FRACTION
        #     override 0.5): TSON 35.5% → 29.4%, regression of -6pt.
        #     Ahriman is a single-model EPIC HERO that gets focus-fired
        #     and contributes less per-pt than Exalted Sorcerer at this
        #     budget.
        #   - Seeding Scarab Occult Terminators (SEED_FRACTION=0.75 so
        #     396pt squad fits): TSON 35.5% → 28.6%, regression of -6.9pt.
        #     Scarab Occult chassis costs more pts than it contributes
        #     in damage-per-round under the current combat model at
        #     1000pt eval (real-meta TSON runs at 2000pt where Scarab
        #     Occult fits naturally; the 1000pt eval is hostile).
        #
        # iter17 — added Mutalith Vortex Beast (170pt MONSTER) for an
        # Aux wrecker anchor. iter16 left TSON at sim 25.8% cumulative vs
        # real 54.6% (-28.8pt). Seed audit (scripts/iter17_tson_diag.py)
        # showed the template never seated a wrecker — Scarab Occult
        # Terminators at 396pt do not fit the 300pt SEED_FRACTION slice,
        # and Magnus at 435pt is barred from random_fill by the EPIC HERO
        # cap (iter16). The army ran as all-INFANTRY shooty with no anti-
        # tank threat.
        #
        # Mutalith Vortex Beast fits the seed slice at 170pt and gives
        # the list a T10 13W MONSTER with S18/D9.5 ranged + S10 melee
        # devastating-wounds, restoring the centerpiece-threat profile
        # that real Rubricae Phalanx lists carry via Magnus / Lord of
        # Change / Mutalith depending on budget. Mutalith also has
        # deadly_demise=3, FNP 5+, OC 4 — a credible aux wrecker.
        #
        # iter17 template_variant probe (N=30):
        #   vs random_fill opponents:
        #     baseline (iter16, no Mutalith)  : 32.2% solo TSON
        #     + Mutalith                       : 48.9% (+16.7pt)
        #   vs archetype opponents (production matrix):
        #     baseline                         : 30.0%
        #     + Mutalith                       : 30.0% (no arch-vs-arch
        #                                                signal; the lift
        #                                                is matchup-shape
        #                                                specific)
        # The Mutalith addition holds in vs-random_fill but doesn't shift
        # the archetype-vs-archetype matrix at this calibration budget.
        # Additional variants tested in iter17 diag (Lord of Change,
        # Daemon Prince, Pink Horrors, Heldrake, Forgefiend, Helbrute,
        # Chaos Predator Annihilator with and without SOT) either
        # neutral or regressed the archetype-vs-archetype probe; the
        # Mutalith-only addition is the safe minimum incremental change.
        #
        # MONSTER cap (iter16) bounds Mutalith fills at template_count=1,
        # so the army holds at most 2 Mutaliths in extreme tails (rare
        # at 1000pt where the budget is tight).
        #
        # Scarab Occult Terminators KEPT at count=2 in template. SOT's
        # 396pt min-squad cost means they don't seat at 1000pt eval
        # budgets, but the count=2 entry is the highest-priority sort
        # hint AND it keeps the RUBRICAE-keyword affinity signal strong
        # for the detachment picker (iter16 RUBRICAE-keyword affinity in
        # `_keyword_affinity_score`). At 2000pt eval SOT does fit and
        # seats naturally. Dropping SOT and replacing with another
        # MONSTER (iter17 V4 probe) regresses the detachment picker to
        # ~50/50 Grand Coven vs Rubricae Phalanx.
        #
        # Magnus the Red intentionally NOT in the template: 435pt would
        # crowd out the rest of the army at 1000pt. Real-meta Magnus
        # lists need 1500pt+ budget shape. Random_fill picks him up
        # organically at 2000pt evals.
        #
        # STRUCTURAL NOTE for iter 18+: At 1000pt the TSON archetype is
        # structurally under-resourced — neither Magnus (435pt) nor a
        # second Scarab Occult squad (792pt) can fit. Real meta May 2026
        # win-rate (54.6%) reflects 2000pt+ play. The archetype eval
        # budget should be considered for a TSON-specific raise to
        # 1500pt+ via SEED_FRACTION_BY_FACTION override OR a global
        # eval budget bump, but that change is out of iter17 scope
        # (cross-faction implications). See iter17 diag for evidence.
        #
        # Sources:
        #   - Wahapedia: https://wahapedia.ru/wh40k10ed/factions/thousand-sons/
        #     (Mutalith Vortex Beast datasheet)
        #   - 40k.app: https://www.40k.app/factions/thousand-sons/rules/detachment/rubricae-phalanx
        #   - Goonhammer "Codex Focus: Thousand Sons" (Mutalith as
        #     affordable Magnus alternative for sub-2000pt builds)
        #   - Goonhammer "Detachment Focus: Rubricae Phalanx"
        #   - Frontline Gaming "Codex Focus: Thousand Sons"
        "Rubricae Phalanx": {
            "thousand_sons_ahriman": 1,
            "thousand_sons_rubric_marines": 2,
            "thousand_sons_scarab_occult_terminators": 2,
            "thousand_sons_mutalith_vortex_beast": 1,
            "thousand_sons_exalted_sorcerer": 1,
            "thousand_sons_infernal_master": 1,
            "thousand_sons_tzaangors": 1,
        },
    },
    "Leagues of Votann": {
        # Oathband — generic codex stub; closest real detachment is Hearthband
        # / Brandfast Oathband. May 2026 Goonhammer "Leagues of Votann
        # Oathband Detachment Focus" (https://www.goonhammer.com/) + Frontline
        # / Stat Check meta lists converge on:
        #   - 1 Kâhl (warlord CHARACTER, Warrior-Forged Leadership wired in
        #     code/leaders.py: +1-to-hit aura attaches to Hearthkyn).
        #   - 1 Einhyr Champion (joins Einhyr Hearthguard for melee bomb).
        #   - 2-3 Hearthkyn Warriors squads (BATTLELINE spine, count=2 here
        #     even though squad cost = 9 × 90pt = 810pt overflows the seed
        #     budget — the (-count,-cost) walk sees it first and skips, but
        #     `_random_fill` then picks Hearthkyn back up as same-faction
        #     fill so the spine still lands in the final army).
        #   - 1 Einhyr Hearthguard (elite melee, T5 sv2+ — fits seed).
        #   - 1 Hekaton Land Fortress (flagship VEHICLE: T12 sv2+ 16HP,
        #     S18 AP-4 7.5 dam/shot, devastating wounds — single biggest
        #     anti-tank pillar of the list, mandatory inclusion for iter17
        #     fix to recover Votann sim from -11.6pt iter16 regression).
        #   - 1 Sagitaur (light transport, supports Hearthkyn deployment).
        #   - 1 Hernkyn Pioneers (objective scout, scout 9").
        #   - 1 Brôkhyr Iron Master (cheap CHARACTER + Thunderkyn buddy).
        #   - 1 Cthonian Berzerks (melee secondary — count=1 keeps the
        #     template real-meta-shaped without crowding the seed).
        #
        # SEED_FRACTION_BY_FACTION["Leagues of Votann"] = 0.4 (below) lifts
        # the seed budget from 300pt → 400pt at 1000pt eval so the Hekaton
        # (101.25pt squad) lands in the seed alongside Hearthguard + Sagitaur
        # rather than being deferred to random_fill (which historically picked
        # cheaper Brôkhyr Thunderkyn / Yaegirs over the flagship vehicle).
        #
        # Reference: https://wahapedia.ru/wh40k10ed/factions/leagues-of-votann/
        "Oathband": {
            "leagues_of_votann_hearthkyn_warriors": 2,
            "leagues_of_votann_einhyr_hearthguard": 1,
            "leagues_of_votann_hekaton_land_fortress": 1,
            "leagues_of_votann_sagitaur": 1,
            "leagues_of_votann_k_hl": 1,
            "leagues_of_votann_einhyr_champion": 1,
            "leagues_of_votann_hernkyn_pioneers": 1,
            "leagues_of_votann_cthonian_beserks": 1,
            "leagues_of_votann_br_khyr_iron_master": 1,
        },
    },
    "Drukhari": {
        # Skysplinter Assault — the flagship Drukhari detachment in 10e May
        # 2026 meta. Doctrine is mounted-everything: every infantry block
        # embarks in a Raider or Venom, deep-strike support from Mandrakes
        # and Scourges, anti-tank from Ravager triples, melee killtile from
        # Incubi + Lelith. Archon is the standard CHARACTER anchor; Lelith
        # joins as the EPIC HERO option that leads a Wyches/Incubi bomb.
        #
        # DRK-ARCH-1 (2026-05-23) rebalance: previous template ran 4 Raiders
        # + 2 Venoms = 6 transports, which over-weighted the spine sort
        # against the actual Warp Friends meta. Real competitive Skysplinter
        # lists at ~52.4% win rate (Warp Friends ~848 games) run 3 Raiders +
        # 1 Venom + 1 Ravager (5 vehicles total), with the remaining slot
        # spent on Coven anti-elite/horde tech (Wracks) and a second melee
        # hammer. Reducing transport spam should pull Drukhari sim% down
        # from the +23.8pt outlier toward parity. Added Wracks for Coven
        # representation per Wahapedia datasheet:
        # https://wahapedia.ru/wh40k10ed/factions/drukhari/#Wracks
        #
        # Multi-copy entries (Raider=3, Kabalites=2, Wyches=2, Incubi=2)
        # remain the spine; the (-template_count, -squad_cost) sort still
        # seeds them before single-copy support.
        #
        # Reference: https://wahapedia.ru/wh40k10ed/factions/drukhari/
        "Skysplinter Assault": {
            "aeldari_drukhari_archon": 1,
            "aeldari_drukhari_lelith_hesperax": 1,
            "aeldari_drukhari_kabalite_warriors": 2,
            "aeldari_drukhari_wyches": 2,
            "aeldari_drukhari_incubi": 2,
            "aeldari_drukhari_mandrakes": 1,
            "aeldari_drukhari_reavers": 1,
            "aeldari_drukhari_scourges_with_shardcarbines": 1,
            "aeldari_drukhari_raider": 3,
            "aeldari_drukhari_venom": 1,
            "aeldari_drukhari_ravager": 1,
            "aeldari_drukhari_wracks": 1,
            "aeldari_drukhari_cronos": 1,
        },
    },
    # FX-ALL: minimal coverage templates for the remaining 11 major-codex
    # factions. Goal is COVERAGE for matchup-outlier detection in
    # `scripts/evaluate_vs_meta.py`, not real-meta realism. Each template
    # uses a small (5-10) selection of representative units (1 anchor /
    # CHARACTER, 1-3 BATTLELINE, 2-3 elite, 1 EPIC HERO if present); the
    # remaining seed budget is filled by `_random_fill` with same-faction
    # picks. Detachment names match the registry where one exists.
    "Chaos Space Marines": {
        # FX-ALL CSM catalog limitation: BSData v10.6.0 doesn't expose
        # Legionaries / Chaos Terminator Squad / Chosen / Chaos Lord in
        # Terminator Armour as catalog keys. Available CSM catalog leans
        # on dedicated chassis + named CHARACTERs. Template below uses
        # what's catalogued — provides COVERAGE per FX-ALL goal even if
        # not fully tournament-realistic. Follow-up: refresh BSData
        # mapper or add overrides for the missing 10e generics.
        "Pactbound Zealots": {
            # BATTLELINE: cult troops (Berzerkers / Plague / Rubric) are
            # the catalogued BATTLELINE options for CSM; vanilla
            # Legionaries / Chosen / generic CSM Terminators / Chaos Lord
            # in Terminator Armour remain absent in BSData v10.6.0 — log
            # in commit and skip per AX-A constraint.
            "chaos_space_marines_khorne_berzerkers": 2,
            "chaos_space_marines_plague_marines": 2,
            "chaos_space_marines_rubric_marines": 1,
            "chaos_space_marines_noise_marines": 1,
            "chaos_space_marines_chaos_bikers": 1,
            "chaos_space_marines_obliterators": 1,
            "chaos_space_marines_mutilators": 1,
            "chaos_space_marines_chaos_spawn": 1,
            "chaos_space_marines_helbrute": 1,
            "chaos_space_marines_maulerfiend": 1,
            "chaos_space_marines_venomcrawler": 1,
            "chaos_space_marines_forgefiend": 1,
            "chaos_space_marines_heldrake": 1,
            "chaos_space_marines_chaos_predator_destructor": 1,
            "chaos_space_marines_chaos_rhino": 1,
            "chaos_space_marines_master_of_executions": 1,
            "chaos_space_marines_warpsmith": 1,
            "chaos_space_marines_lord_discordant_on_helstalker": 1,
            "chaos_space_marines_heretic_astartes_daemon_prince_with_wings": 1,
            "chaos_space_marines_abaddon_the_despoiler": 1,
        },
    },
    "World Eaters": {
        "Berzerker Warband": {
            # BATTLELINE: Khorne Berzerkers is the only WE BATTLELINE
            # entry, supplemented by Jakhals / Eightbound bricks and
            # Daemon allies (Bloodletters / Flesh Hounds) per typical
            # tournament builds.
            "world_eaters_khorne_berzerkers": 2,
            "world_eaters_jakhals": 2,
            "world_eaters_eightbound": 1,
            "world_eaters_exalted_eightbound": 1,
            "world_eaters_chaos_terminators": 1,
            "world_eaters_bloodletters": 1,
            "world_eaters_flesh_hounds": 1,
            "world_eaters_bloodcrushers": 1,
            "world_eaters_chaos_spawn": 1,
            "world_eaters_chaos_rhino": 1,
            "world_eaters_helbrute": 1,
            "world_eaters_maulerfiend": 1,
            "world_eaters_forgefiend": 1,
            "world_eaters_master_of_executions": 1,
            "world_eaters_lord_on_juggernaut": 1,
            "world_eaters_slaughterbound": 1,
            "world_eaters_kh_rn_the_betrayer": 1,
            "world_eaters_lord_invocatus": 1,
            "world_eaters_daemon_prince_of_khorne_with_wings": 1,
            "world_eaters_angron": 1,
        },
    },
    "Emperor's Children": {
        # No detachment registered in code/detachments.py for Emperor's
        # Children; calling out the placeholder name so future iterations
        # can wire it. The army_builder falls through pick_detachment_for_army
        # to the no-detachment path which is fine for archetype seeding.
        "Slaaneshi Excess": {
            # BATTLELINE: Infractors + Tormentors are the EC BATTLELINE
            # pair; supplemented by Noise Marines (flagship dakka) and
            # Slaanesh daemon allies (Daemonettes / Seekers / Fiends)
            # per the standalone-codex army composition.
            "emperor_s_children_infractors": 2,
            "emperor_s_children_tormentors": 2,
            "emperor_s_children_noise_marines": 1,
            "emperor_s_children_flawless_blades": 1,
            "emperor_s_children_chaos_terminators": 1,
            "emperor_s_children_daemonettes": 1,
            "emperor_s_children_seekers": 1,
            "emperor_s_children_fiends": 1,
            "emperor_s_children_chaos_spawn": 1,
            "emperor_s_children_chaos_rhino": 1,
            "emperor_s_children_maulerfiend": 1,
            "emperor_s_children_heldrake": 1,
            "emperor_s_children_lord_exultant": 1,
            "emperor_s_children_lord_kakophonist": 1,
            "emperor_s_children_sorcerer": 1,
            "emperor_s_children_lucius_the_eternal": 1,
            "emperor_s_children_keeper_of_secrets": 1,
            "emperor_s_children_daemon_prince_of_slaanesh_with_wings": 1,
            "emperor_s_children_fulgrim": 1,
        },
    },
    "Chaos Daemons": {
        # Balanced 4-god Daemonic Incursion shape (the all-gods detachment):
        # one Greater Daemon per god, the four troops, plus iconic
        # supporting daemons (Flesh Hounds, Screamers, Plague Drones, Fiends,
        # Be'lakor). Tournament templates run 1-2 troop blocks per god plus
        # 1-2 big monsters; this spreads the OC across all four pantheons.
        "Daemonic Incursion": {
            "chaos_daemons_library_bloodletters": 2,
            "chaos_daemons_library_plaguebearers": 2,
            "chaos_daemons_library_daemonettes": 2,
            "chaos_daemons_library_pink_horrors": 1,
            "chaos_daemons_library_flesh_hounds": 1,
            "chaos_daemons_library_screamers": 1,
            "chaos_daemons_library_plague_drones": 1,
            "chaos_daemons_library_fiends": 1,
            "chaos_daemons_library_bloodthirster": 1,
            "chaos_daemons_library_great_unclean_one": 1,
            "chaos_daemons_library_keeper_of_secrets": 1,
            "chaos_daemons_library_lord_of_change": 1,
            "chaos_daemons_library_be_lakor": 1,
            # MR-CHAOS-DAEMONS-LOCUS: each Herald wired in code/leaders.py
            # broadcasts its god's locus aura to the attached battleline squad.
            # Without these seeds the locus auras never fire because no
            # Herald is ever picked into the army shape. One per god.
            "chaos_daemons_library_bloodmaster": 1,
            "chaos_daemons_library_poxbringer": 1,
            "chaos_daemons_library_changecaster": 1,
            "chaos_daemons_library_contorted_epitome": 1,
        },
    },
    "Astra Militarum": {
        # AX-C — flesh-out. Previous template (9 entries) was a thin Cadian +
        # one-tank skeleton that left random_fill to pick a lot of the army
        # shape, drifting from real-meta Combined Arms tournament composition.
        # Real-meta May 2026 Astra Militarum lists (Goonhammer "Astra Militarum
        # Detachment Focus — Combined Arms"; Frontline Gaming GT lists; Stat
        # Check May 2026 aggregate) are anchored on Cadian / Krieg BATTLELINE
        # bricks plus a multi-tank core (Leman Russ variants, Rogal Dorn,
        # Manticore, Basilisk), supported by a Tempestus Scions deep-strike
        # element and a Cadian Castellan / Ursula Creed / Lord Solar Leontus
        # leader stack. The expanded template seeds that shape directly so
        # random_fill no longer has to invent the army's silhouette.
        # References:
        #   - https://wahapedia.ru/wh40k10ed/factions/astra-militarum/
        #   - https://www.goonhammer.com/the-goonhammer-tournament-cycle-2026-meta/
        "Combined Arms": {
            "astra_militarum_cadian_shock_troops": 2,
            "astra_militarum_death_korps_of_krieg": 1,
            "astra_militarum_kasrkin": 1,
            "astra_militarum_tempestus_scions": 1,
            "astra_militarum_cadian_command_squad": 1,
            "astra_militarum_cadian_heavy_weapons_squad": 1,
            "astra_militarum_chimera": 1,
            "astra_militarum_taurox_prime": 1,
            "astra_militarum_scout_sentinels": 1,
            "astra_militarum_leman_russ_battle_tank": 1,
            "astra_militarum_leman_russ_demolisher": 1,
            "astra_militarum_rogal_dorn_battle_tank": 1,
            "astra_militarum_basilisk": 1,
            "astra_militarum_manticore": 1,
            "astra_militarum_cadian_castellan": 1,
            "astra_militarum_ursula_creed": 1,
            "astra_militarum_lord_solar_leontus": 1,
        },
    },
    "Adeptus Mechanicus": {
        # AX-C — flesh-out. Previous template (8 entries) under-seeded the
        # Skitarii / Sicarian / Pteraxii triad and only carried one Kataphron
        # body plus a single Onager — too thin to fix the army silhouette.
        # Real-meta May 2026 Adeptus Mechanicus tournament lists (Goonhammer
        # "Adeptus Mechanicus Detachment Focus — Skitarii Hunter Cohort";
        # Frontline Gaming GT lists; Stat Check May 2026 aggregate) anchor on
        # Skitarii Rangers + Vanguard BATTLELINE bricks, a Sicarian + Pteraxii
        # screening / objective layer, two Kataphron bodies (Breachers for
        # melee / Destroyers for anti-tank), an Onager + Skorpius Disintegrator
        # fire-base, Serberys Raiders / Ironstrider Ballistarii as fast
        # support, and a Cawl / Manipulus / Skitarii Marshal leader stack.
        # References:
        #   - https://wahapedia.ru/wh40k10ed/factions/adeptus-mechanicus/
        #   - https://www.goonhammer.com/the-goonhammer-tournament-cycle-2026-meta/
        "Skitarii Hunter Cohort": {
            "adeptus_mechanicus_skitarii_rangers": 2,
            "adeptus_mechanicus_skitarii_vanguard": 2,
            "adeptus_mechanicus_sicarian_infiltrators": 1,
            "adeptus_mechanicus_sicarian_ruststalkers": 1,
            "adeptus_mechanicus_pteraxii_skystalkers": 1,
            "adeptus_mechanicus_serberys_raiders": 1,
            "adeptus_mechanicus_ironstrider_ballistarii": 1,
            "adeptus_mechanicus_kataphron_breachers": 1,
            "adeptus_mechanicus_kataphron_destroyers": 1,
            "adeptus_mechanicus_sydonian_dragoons_with_taser_lances": 1,
            "adeptus_mechanicus_onager_dunecrawler": 1,
            "adeptus_mechanicus_skorpius_disintegrator": 1,
            "adeptus_mechanicus_skorpius_dunerider": 1,
            "adeptus_mechanicus_skitarii_marshal": 1,
            "adeptus_mechanicus_tech_priest_manipulus": 1,
            "adeptus_mechanicus_tech_priest_dominus": 1,
            "adeptus_mechanicus_belisarius_cawl": 1,
        },
    },
    "Adepta Sororitas": {
        "Hallowed Martyrs": {
            "adepta_sororitas_battle_sisters_squad": 2,
            "adepta_sororitas_seraphim_squad": 1,
            "adepta_sororitas_zephyrim_squad": 1,
            "adepta_sororitas_celestian_sacresants": 1,
            "adepta_sororitas_retributor_squad": 1,
            "adepta_sororitas_repentia_squad": 1,
            "adepta_sororitas_arco_flagellants": 1,
            "adepta_sororitas_paragon_warsuits": 1,
            "adepta_sororitas_penitent_engines": 1,
            "adepta_sororitas_castigator": 1,
            "adepta_sororitas_exorcist": 1,
            "adepta_sororitas_immolator": 1,
            "adepta_sororitas_sororitas_rhino": 1,
            "adepta_sororitas_canoness": 1,
            "adepta_sororitas_palatine": 1,
            "adepta_sororitas_junith_eruita": 1,
            "adepta_sororitas_morvenn_vahl": 1,
            "adepta_sororitas_saint_celestine": 1,
        },
    },
    "Grey Knights": {
        "Teleport Strike Force": {
            "grey_knights_strike_squad": 2,
            "grey_knights_interceptor_squad": 1,
            "grey_knights_purifier_squad": 1,
            "grey_knights_purgation_squad": 1,
            "grey_knights_brotherhood_terminator_squad": 1,
            "grey_knights_paladin_squad": 1,
            "grey_knights_nemesis_dreadknight": 1,
            "grey_knights_venerable_dreadnought": 1,
            "grey_knights_rhino": 1,
            "grey_knights_razorback": 1,
            "grey_knights_land_raider": 1,
            "grey_knights_brother_captain": 1,
            "grey_knights_brotherhood_chaplain": 1,
            "grey_knights_brotherhood_librarian": 1,
            "grey_knights_brotherhood_champion": 1,
            "grey_knights_grand_master": 1,
            "grey_knights_grand_master_in_nemesis_dreadknight": 1,
            "grey_knights_grand_master_voldus": 1,
        },
    },
    "Genestealer Cults": {
        # AX-C — flesh-out. Previous template (9 entries) was a single
        # Acolyte / Neophyte pair plus one Aberrant brick and a Patriarch /
        # Primus character stack — too thin for a cult-spam army. Real-meta
        # May 2026 Genestealer Cults tournament lists (Goonhammer "Genestealer
        # Cults Detachment Focus — Final Day"; Frontline Gaming GT lists; Stat
        # Check May 2026 aggregate) are spam-heavy on cheap BATTLELINE: two
        # Neophyte bricks plus both Acolyte loadouts (autopistols + hand
        # flamers), one Hybrid Metamorphs squad for melee threat, a Goliath
        # Rockgrinder + Goliath Truck delivery pair, Atalan Jackals + Achilles
        # Ridgerunners for fast objective play, an Aberrant brick, and a
        # Patriarch + Primus + Magus + Kelermorph + Jackal Alphus + Sanctus
        # leader / sniper assassination layer. The expanded template seeds
        # that spam shape so random_fill no longer has to guess between cult
        # spam vs MONSTER-heavy compositions (which Final Day never runs).
        # References:
        #   - https://wahapedia.ru/wh40k10ed/factions/genestealer-cults/
        #   - https://www.goonhammer.com/the-goonhammer-tournament-cycle-2026-meta/
        "Final Day": {
            "genestealer_cults_neophyte_hybrids": 2,
            "genestealer_cults_acolyte_hybrids_with_autopistols": 2,
            "genestealer_cults_acolyte_hybrids_with_hand_flamers": 1,
            "genestealer_cults_hybrid_metamorphs": 1,
            "genestealer_cults_aberrants": 1,
            "genestealer_cults_purestrain_genestealers": 1,
            "genestealer_cults_atalan_jackals": 1,
            "genestealer_cults_achilles_ridgerunners": 1,
            "genestealer_cults_goliath_rockgrinder": 1,
            "genestealer_cults_goliath_truck": 1,
            "genestealer_cults_primus": 1,
            "genestealer_cults_magus": 1,
            "genestealer_cults_kelermorph": 1,
            "genestealer_cults_jackal_alphus": 1,
            "genestealer_cults_sanctus": 1,
            "genestealer_cults_clamavus": 1,
            "genestealer_cults_patriarch": 1,
        },
    },
    "Imperial Knights": {
        # Noble Lance is the canonical Big Knights detachment. Knight armies
        # are MONSTER/TITANIC-only — no BATTLELINE infantry, the template
        # is a small number of high-points models per Wahapedia / codex.
        # Standard tournament template: 3 big Questoris-class chassis + 6
        # Armiger/War Dog escorts at 2000pt. Expanded roster spreads the
        # OC across more chassis variety (Crusader / Castellan / Preceptor)
        # and gives the AI more activation choices.
        "Noble Lance": {
            "imperial_knights_library_armiger_warglaive": 2,
            "imperial_knights_library_armiger_helverin": 2,
            "imperial_knights_library_armiger_moirax": 1,
            "imperial_knights_library_knight_paladin": 1,
            "imperial_knights_library_knight_errant": 1,
            "imperial_knights_library_knight_warden": 1,
            "imperial_knights_library_knight_crusader": 1,
            "imperial_knights_library_knight_preceptor": 1,
            "imperial_knights_library_knight_castellan": 1,
            "imperial_knights_library_canis_rex": 1,
        },
    },
    "Chaos Knights": {
        # Mirror of Noble Lance — chaos variant; same big-stompy shape
        # using War Dogs (Armigers) + Questoris-class Knights. Expanded
        # roster mirrors the IK template: a full War Dog escort spread
        # (Karnivore / Huntsman / Brigand / Executioner / Stalker) plus
        # the iconic Chaos Questoris chassis (Desecrator / Rampager /
        # Despoiler / Tyrant / Abominant).
        "Noble Lance": {
            "chaos_knights_library_war_dog_karnivore": 2,
            "chaos_knights_library_war_dog_huntsman": 1,
            "chaos_knights_library_war_dog_brigand": 1,
            "chaos_knights_library_war_dog_executioner": 1,
            "chaos_knights_library_war_dog_stalker": 1,
            "chaos_knights_library_knight_desecrator": 1,
            "chaos_knights_library_knight_rampager": 1,
            "chaos_knights_library_knight_despoiler": 1,
            "chaos_knights_library_knight_tyrant": 1,
            "chaos_knights_library_knight_abominant": 1,
        },
    },
}


def has_archetype(faction: str) -> bool:
    """True if `faction` has at least one curated archetype template."""
    return faction in ARCHETYPES and bool(ARCHETYPES[faction])


def _squad_cost(key: str) -> float:
    """SwegHammer cost of one min-sized squad of profile `key`."""
    profile = UNIT_CATALOG[key]
    return profile.points_cost * max(1, profile.min_models)


# Fraction of the budget that the curated template seeds. The rest is left
# free for `_random_fill` to top up with same-faction picks, which keeps
# the post-archetype calibration close to the random-list baseline (the
# random builder was empirically near-balanced on most factions before this
# patch — the bias was in pool composition, not total point spend).
SEED_FRACTION: float = 0.3

# Per-faction SEED_FRACTION override. Some factions' archetype anchor units
# are expensive enough that the default 0.3 slice (300pt of 1000pt eval
# budget) cannot fit even ONE flagship squad, leaving the army to be filled
# by off-flavour random_fill picks. Raise the slice for those factions only.
#
# iter16 experimented with a 0.5 / 0.75 slice for Thousand Sons (to seed
# Ahriman + Scarab Occult Terminators) but both regressed sim WR vs iter15's
# 0.3 default (35.5% → 28.6% at 0.75). The Scarab Occult chassis costs more
# pts than it contributes in damage-per-round under the current combat model
# at 1000pt eval. iter16's actual TSON win is the RUBRICAE-keyword detachment
# picker affinity (code/detachments.py).
#
# iter17: Leagues of Votann bumped to 0.4 so the Hekaton Land Fortress
# (101.25pt squad) lands in the seed alongside Hearthguard (135pt) +
# Sagitaur (103.5pt). Bumping to 0.4 (400pt seed) gives 401.5pt headroom —
# Hearthguard + Sagitaur + Hekaton (339.75pt) fit cleanly, then CHARACTER
# fallback pulls Kâhl on top → 404.75pt seeded. Goal: lift iter16 Votann
# sim 34.4% → 44-50% vs real 46.0%.
#
# iter17 — Adeptus Custodes at 0.55. The iter16 archetype trim left only
# Wardens (210pt) + Shield-Captain (120pt CHARACTER anchor) seeding at the
# default 0.3 slice. The 0.55 slice (550pt of 1000pt) reliably seeds
# Wardens(210) + Vertus Praetors(150) + Allarus(143) = 503pt plus the
# CHARACTER guarantee. Goal: lift iter16 Custodes sim 36.4% → 45-55% vs
# real 48.0%.
SEED_FRACTION_BY_FACTION: Dict[str, float] = {
    "Leagues of Votann": 0.4,
    "Adeptus Custodes": 0.55,
}


def _instantiate_template(
    template: Dict[str, int],
    points_budget: float,
    rng: random.Random,
    faction: Optional[str] = None,
) -> Dict[str, int]:
    """
    Scale template counts so the resulting army's template-seeded portion
    fits inside `SEED_FRACTION * points_budget`. The remaining headroom is
    filled by `_random_fill` with same-faction picks at army-build time.

    `faction` (optional) selects a per-faction SEED_FRACTION override from
    `SEED_FRACTION_BY_FACTION` — used for factions whose anchor units are
    too expensive for the default 0.3 slice. Currently empty (no overrides
    in production) — see SEED_FRACTION_BY_FACTION for iter16 experiment
    notes.

    Why a partial seed:
      A 100% template-seeded army produced ~24-pt MAE in eval-vs-meta
      because some faction catalogues have lopsided costs (Aeldari Aspect
      Warriors are very expensive, Tyranid Termagants are very cheap) and a
      tournament-list template doesn't compensate. Seeding 60% of the
      budget with the curated template (so the army's CHARACTER + flavour
      units are present) and filling the rest randomly keeps the overall
      cost-per-model close to the random baseline while still biasing list
      composition.
    """
    if not template or points_budget <= 0:
        return {}

    seed_fraction = SEED_FRACTION_BY_FACTION.get(faction or "", SEED_FRACTION)
    seed_budget = points_budget * seed_fraction

    # Walk the template in (-template_count, -squad_cost) order so that
    # archetype-defining units land first:
    #   * Multi-copy entries (e.g. Rubric Marines @ count=2) outrank
    #     single-copy entries — they're the spine of the archetype.
    #   * Within the same template count, instantiate the more expensive
    #     squad first so flagship anchors (Wraithguard, Falcon, Scarab
    #     Occult Terminators) are seeded before chaff that could otherwise
    #     soak the budget cheaply.
    #
    # Previously this walked cheapest-first, which meant a 1000pt seed
    # (SEED_FRACTION*1000 = 300pt) exhausted on Tzaangors (70pt) +
    # Sorcerer (80pt) + Infernal Master (95pt) and never reached the
    # Rubric Marine entry. See task #170.
    #
    # We instantiate exactly one squad per template entry here — extra
    # copies past 1 are left to `_random_fill`, which keeps the seeded
    # slice tight and lets the random topup handle distribution.
    def sort_key(key: str):
        return (-template.get(key, 0), -_squad_cost(key))

    scaled: Dict[str, int] = {}
    running = 0.0

    for key in sorted(template, key=sort_key):
        cost = _squad_cost(key)
        if running + cost <= seed_budget:
            scaled[key] = 1
            running += cost
        # else: skip — too expensive at this budget. Cheaper subsequent
        # entries may still fit, so keep walking rather than break.

    # iter24-D2 — EPIC HERO anchor guarantee. The (-count, -cost) walk
    # above leaves a template EPIC HERO unseeded when count=2 entries
    # earlier in the sort have already consumed `seed_budget` — the EPIC
    # HERO's count=1 priority loses, and once reached the cumulative
    # overflow drops it. Death Guard Mortarion (380pt) is the motivating
    # case: at the 600pt seed slice (2000pt eval x 0.3), Plagueburst
    # Crawler + Foetid Bloat-Drone + Plague Marines at count=2 each =
    # 393pt land first, then Mortarion's 380pt pushes running to 773pt
    # > 600pt and is skipped. The archetype was designed around
    # Mortarion as the centerpiece; drafting him in only 4/20 builds
    # left the army shape wrong.
    #
    # Fix: AFTER the regular walk, if any template EPIC HERO went
    # unseeded, force-seed the cheapest with the 1.5x overflow allowance
    # (mirrors the CHARACTER-anchor guarantee below — and composes with
    # it, since most EPIC HEROes are also CHARACTERs). Running after this
    # may exceed `seed_budget` but is bounded by `seed_budget * 1.5`.
    # Faction-neutral by keyword.
    def _is_epic_hero_key(key: str) -> bool:
        profile = UNIT_CATALOG.get(key)
        if profile is None:
            return False
        return "EPIC HERO" in (profile.unit_keywords or ())

    epic_hero_keys = [k for k in template if _is_epic_hero_key(k)]
    if epic_hero_keys and not any(k in scaled for k in epic_hero_keys):
        # Pick the MOST EXPENSIVE template EPIC HERO as the centerpiece —
        # the priciest EPIC HERO is the archetype's flagship (Death Guard
        # Mortarion at 380pt over Typhus at 100pt). Falling back to the
        # cheapest would draft Typhus instead, which is not the designed
        # anchor.
        #
        # Overflow cap: `points_budget * 0.6` (= 2x seed_budget at the
        # default SEED_FRACTION=0.3). The CHARACTER-anchor guarantee
        # below uses 1.5x but its cheapest-CHARACTER target is usually
        # well under 100pt; an EPIC HERO centerpiece like Mortarion costs
        # 380pt and a 1.5x cap on a partially-filled walk doesn't leave
        # room. Cap at 60% of total army budget so random_fill still has
        # 40% headroom.
        anchor_eh = max(epic_hero_keys, key=_squad_cost)
        cost = _squad_cost(anchor_eh)
        if running + cost <= points_budget * 0.6:
            scaled[anchor_eh] = 1
            running += cost

    # iter #11 — CHARACTER-anchor guarantee. The (-count, -cost) walk above
    # can exhaust the seed budget on a multi-copy BATTLELINE entry at low
    # budgets (e.g. TSON Rubric Marines @ count=2 takes 240pt of a 300pt
    # seed at 1000pt), leaving no headroom for the army's CHARACTER /
    # PSYKER anchor. Real tournament archetypes are built around their
    # character spine; if none seeded, force the cheapest template
    # CHARACTER in even if it overflows `seed_budget` slightly. The
    # overflow is bounded by `1.5 * seed_budget` so we don't blow past the
    # random_fill headroom at small budgets. Faction-neutral — any
    # template entry with the CHARACTER keyword qualifies.
    def _has_character(key: str) -> bool:
        profile = UNIT_CATALOG.get(key)
        if profile is None:
            return False
        return "CHARACTER" in (profile.unit_keywords or ())

    any_char_seeded = any(_has_character(k) for k in scaled)
    if not any_char_seeded:
        char_keys = [k for k in template if _has_character(k)]
        if char_keys:
            # Cheapest CHARACTER first so the overflow is minimal.
            cheapest_char = min(char_keys, key=_squad_cost)
            cost = _squad_cost(cheapest_char)
            if running + cost <= seed_budget * 1.5:
                scaled[cheapest_char] = 1
                running += cost

    return scaled


def _random_fill(
    army: Army,
    faction: str,
    remaining_budget: float,
    rng: random.Random,
    template: Optional[Dict[str, int]] = None,
) -> None:
    """
    Top up `army` with random faction picks until `remaining_budget` is
    exhausted. Mirrors the legacy `build_faction_random_army` per-pick logic
    (size=max_models, cap=remaining/2 per type) so the filler portion is
    statistically equivalent to the pre-archetype baseline.

    BATTLELINE squad cap (task #179):
      For any BATTLELINE-keyword profile P, random_fill is capped at
      `max(1, template_count(P))` additional squad picks, so the total
      squads-of-P in the army (template + random_fill) is bounded at
      `2 * template_count(P)` when P is in the template, else 1.

      Rationale: BATTLELINE profiles are the OC-on-objectives spine of
      the army; the F5 / F5b Marines audit traced a +17pt over-perform to
      `random_fill` stacking Intercessor squads on top of the templated
      seed (deterministic 20+ OC floor). The cap is faction-neutral —
      Necron Warriors (template=2) and Tyranid Termagants (template=1)
      still seed at their archetype's intended density; only profiles
      that aggregate beyond 2x the template intent are throttled. Non-
      BATTLELINE roles (HQ / ELITE / FAST_ATTACK / HEAVY / DEDICATED
      TRANSPORT) use the unchanged per-type point cap.

    MONSTER / TITANIC / EPIC HERO cap (iter16):
      Mirror of the BATTLELINE cap, applied to any profile with the
      MONSTER, TITANIC, or EPIC HERO keyword. For an unseeded wrecker
      profile (not in the template), random_fill picks 0 squads — pre-
      venting multi-wrecker stacking like the iter15 Necron Awakened
      Dynasty list which regularly drafted Transcendent C'tan + Tesseract
      Vault + Seraptek Heavy Construct alongside the template-seeded
      C'tan Nightbringer via fill, driving sim WR to 91% vs real 53.2%.
      The Silent King (VEHICLE + EPIC HERO + CHARACTER, 400pt) is caught
      by the EPIC HERO leg — without it, random_fill would still stack
      Silent King alongside a template-seeded Nightbringer.

      Profiles that ARE in the template (Tyranid Carnifex count=2, Hive
      Tyrant count=1, Exocrine count=1, DG Mortarion count=1, Drukhari
      Lelith count=1) still get `template_count` extra fill picks, so a
      Tyranid Invasion Fleet list can field up to 2*template_count of
      each MONSTER — matching the real-meta "MONSTER spam Tyranids"
      profile that the Invasion Fleet detachment is built around. The
      EPIC HERO leg composes with the existing per-name is_epic_hero
      check (10e core, 1 copy per EH datasheet per army): templated EHs
      can't be re-picked, AND unseeded EHs can't be introduced.

      Faction-neutral by keyword: applies to every codex's MONSTERs and
      EHs (Aeldari Wraithlord/Wraithknight + Yvraine/Yncarne, T'au
      Stormsurge/Riptide + Shadowsun, DG Mortarion/Plagueburst + Typhus,
      Custodes Telemon + Trajann, Marines Redemptor + Calgar) and gates
      by template intent rather than faction-specific allowlists.

    [Legends] / [Crucible] exclusion (iter16):
      Profiles whose display name contains "[Legends]" or "[Crucible]"
      are filtered out of the random_fill pool entirely. These are non-
      tournament profiles per GW's 10e ruleset and shouldn't appear in
      the calibration target (the eval-vs-meta WR data is derived from
      tournament events that exclude Legends datasheets). Template-
      seeded units are unaffected — if a future archetype explicitly
      wants a Legends entry, the template still seeds it, but the random
      fill won't pad with random Legends profiles like the iter15 trace
      that drafted Nemesor Zahndrekh, Anrakyr the Traveller, Tesseract
      Ark, Night Shroud, and Vargard Obyron into the Necron fill pass.

      Faction-neutral by display-name suffix — applies to all 445
      Legends/Crucible profiles across the catalogue.
    """
    pool = [
        UNIT_CATALOG[k] for k in UNIT_CATALOG
        if UNIT_CATALOG[k].faction == faction
        and "[Legends]" not in UNIT_CATALOG[k].name
        and "[Crucible]" not in UNIT_CATALOG[k].name
    ]
    if not pool:
        return

    # Map profile.name -> template count of its catalogue key. We index by
    # display name so the per-pick check (which has the profile in hand)
    # doesn't need to round-trip back to the catalogue key.
    template = template or {}
    template_count_by_name: Dict[str, int] = {}
    for key, count in template.items():
        prof = UNIT_CATALOG.get(key)
        if prof is not None:
            template_count_by_name[prof.name] = count

    spent_by_name: Dict[str, float] = {}
    fill_squads_by_name: Dict[str, int] = {}
    cap = remaining_budget * 0.5

    # 10e core EPIC HERO 1-per-army cap. Seed the tracker with any epic
    # heroes already present in the army from the template seed, so the
    # fill pass cannot duplicate a hero that the archetype already drafted.
    epic_heroes_taken: set = {
        u.profile.name for u in army.units if is_epic_hero(u.profile)
    }

    while remaining_budget > 0:
        affordable = []
        for p in pool:
            if is_epic_hero(p) and p.name in epic_heroes_taken:
                continue
            size = max(1, p.max_models)
            cost = p.points_cost * size
            if cost > remaining_budget:
                continue
            if spent_by_name.get(p.name, 0.0) + cost > cap:
                continue
            # BATTLELINE cap: bound random_fill picks per BATTLELINE profile
            # at max(1, template_count). Profiles outside the template are
            # allowed 1 fill pick (so the random topup can still introduce
            # variety without stacking OC).
            if "BATTLELINE" in (p.unit_keywords or ()):
                bl_cap = max(1, template_count_by_name.get(p.name, 0))
                if fill_squads_by_name.get(p.name, 0) >= bl_cap:
                    continue
            # MONSTER / TITANIC / EPIC HERO cap (iter16): bound random_fill
            # picks per wrecker profile at template_count (no implicit +1 —
            # an unseeded wrecker gets 0 fill picks). This stops the multi-
            # wrecker stacking that drove Necron Awakened Dynasty to sim
            # 91% (Transcendent C'tan + Tesseract Vault + Seraptek + Silent
            # King all picked into the same army's random_fill pass).
            #
            # Including EPIC HERO is intentional: it stops unseeded centre-
            # piece characters from being introduced by random_fill (e.g.
            # The Silent King wasn't in the Necron template but kept landing
            # in fills as a 400pt Vehicle EH wrecker alongside the templated
            # Nightbringer). Profiles that ARE in the template (DG Mortarion
            # count=1, Drukhari Lelith count=1) are still seeded; the
            # existing per-name is_epic_hero check prevents duplicate fills
            # of an already-seeded EH datasheet (10e core rule). The MONSTER
            # cap composes with that: a templated EH won't be re-picked, and
            # an unseeded EH won't be introduced at all.
            #
            # Profiles that ARE in the template (e.g. Tyranid Carnifex
            # count=2 with MONSTER keyword) still get up to `template_count`
            # extra fill picks, so MONSTER-spam Tyranids still build their
            # real-meta shape.
            kw = p.unit_keywords or ()
            if "MONSTER" in kw or "TITANIC" in kw or "EPIC HERO" in kw:
                wrecker_cap = template_count_by_name.get(p.name, 0)
                if fill_squads_by_name.get(p.name, 0) >= wrecker_cap:
                    continue
            affordable.append((p, size, cost))
        if not affordable:
            break
        chosen, size, cost = rng.choice(affordable)
        for _ in range(size):
            army.add_unit(chosen)
        spent_by_name[chosen.name] = spent_by_name.get(chosen.name, 0.0) + cost
        fill_squads_by_name[chosen.name] = fill_squads_by_name.get(chosen.name, 0) + 1
        remaining_budget -= cost
        if is_epic_hero(chosen):
            epic_heroes_taken.add(chosen.name)


def build_archetype_army(
    name: str,
    faction: str,
    points_budget: float,
    rng: Optional[random.Random] = None,
    in_cover: bool = False,
    archetype_name: Optional[str] = None,
) -> Army:
    """
    Build an army from a curated archetype template for `faction`, then top
    up the remaining budget with random same-faction picks via
    `_random_fill`.

    If `archetype_name` is None, picks one at random from the faction's
    available archetypes. Raises KeyError if the faction has no archetype —
    callers should gate with `has_archetype(faction)` first.

    Squad sizes default to BSData min_models for the template-seeded
    portion (MSU style, since the templates reflect the CHARACTER + flavour
    spine of competitive lists). Random fill uses max_models squads to
    match legacy `build_faction_random_army` behaviour and keep total cost
    near budget.
    """
    if rng is None:
        rng = random.Random()
    if not has_archetype(faction):
        raise KeyError(f"No archetype defined for faction {faction!r}")

    available = ARCHETYPES[faction]
    if archetype_name is None:
        archetype_name = rng.choice(list(available.keys()))
    template = available[archetype_name]

    counts = _instantiate_template(template, points_budget, rng, faction=faction)

    army = Army(name, in_cover=in_cover)
    for key, count in counts.items():
        profile: UnitProfile = UNIT_CATALOG[key]
        squad_size = max(1, profile.min_models)
        for _ in range(count):
            for _ in range(squad_size):
                army.add_unit(profile)

    # Fill the remaining budget with random same-faction picks. Keeps the
    # archetype's flavour seed but lets the total cost converge to the
    # pre-archetype calibration baseline. Passes `template` so the fill
    # path can apply the BATTLELINE squad cap (task #179) — random_fill
    # may add at most `max(1, template_count(P))` extra squads for any
    # BATTLELINE profile P.
    remaining = points_budget - army.total_points
    if remaining > 0:
        _random_fill(army, faction, remaining, rng, template=template)

    if army.units:
        army.detachment = pick_detachment_for_army(faction, army.units, rng)

    return army
