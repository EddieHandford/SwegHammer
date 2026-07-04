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

import os
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
            "necrons_lokhust_destroyers": 1,
            "necrons_canoptek_scarab_swarms": 1,
            "necrons_ghost_ark": 1,
        },
    },
    "Aeldari": {
        # wave-240 list-realism reshape (docs/AELDARI_LIST_REALISM_SPEC.md).
        # The previous iter17 template was built around Yncarne + Avatar of
        # Khaine + Wraithguard — a Wraith-heavy list that does not match
        # confirmed May 2026 tournament play. The reshape replaces it with
        # the Phoenix Lord + Aspect Warrior spine that actually won
        # competitive events.
        #
        # Two strongest sources (six total in the spec):
        #   - Grimhammer Tactics: Top 10 Competitive Lists August 2025
        #     https://grimhammertactics.com/top-10-competitive-warhammer-40k-lists-august-2025/
        #     (Brad Chester, Salt City Grand Tournament IV, 7-0 first place;
        #     Fuegan + Jain Zar + Lhykhis + Warp Spiders x2 + Fire Dragons x2
        #     + Dark Reapers x2 + Howling Banshees x2 + Wave Serpent + Rangers
        #     + Swooping Hawks x2 + Corsair Voidreavers x2)
        #   - Spikeybits: Top Unbeatable Army Lists — Nova Open 2025
        #     https://spikeybits.com/top-40k-unbeatable-army-lists-nova-open-gt/
        #     (Folger Pyles, 1st place, Warhost; Fuegan + Jain Zar + Lhykhis +
        #     Maugan Ra + Eldrad + Warp Spiders x3 + Fire Dragons + Dark Reapers
        #     + Howling Banshees + Swooping Hawks x3 + Wave Serpent + Corsair
        #     Voidreavers x3 + Rangers + Falcon)
        #
        # The Yncarne has zero appearances in any confirmed Warhost or Aspect
        # Host tournament list; it belongs to the Devoted of Ynnead detachment.
        # The Avatar of Khaine likewise has zero appearances across all six
        # confirmed lists, including Warhost lists where it theoretically belongs.
        # Both are removed from the template (see spec section 2 and 4 for the
        # full evidence record).
        #
        # Sort-hint count rationale:
        #   * Phoenix Lords count=3 — at the 1000pt eval budget (300pt seed
        #     slice) a single Phoenix Lord (120-135pt) fits in the seed walk
        #     ahead of any count=2 entry. At 2000pt (600pt seed) all three
        #     fit alongside one Wave Serpent (125pt) before the slice fills.
        #   * Warp Spiders count=3 — 6/6 confirmed lists run 2-3 squads;
        #     the highest Aspect presence across all evidence. count=3 seeds
        #     Warp Spiders ahead of count=2 Aspect Warriors in the sort.
        #   * Fire Dragons / Dark Reapers / Howling Banshees / Swooping Hawks /
        #     Wave Serpent count=2 — 4-6/6 list appearances each; count=2
        #     seeds all five ahead of count=1 filler entries.
        #   * Autarch / Corsair Voidreavers / Rangers count=1-2 — support
        #     characters and cheap battleline filler; lower sort priority
        #     so they fill remaining budget after Aspect Warriors seed.
        #
        # Reference: https://wahapedia.ru/wh40k10ed/factions/aeldari/
        "Warhost": {
            # Phoenix Lords — the competitive backbone. Fuegan + Jain Zar +
            # Lhykhis appear in 4-5 of 6 confirmed tournament lists.
            # count=3 ensures one seeds at every budget tier.
            "aeldari_craftworlds_fuegan": 3,           # leads Fire Dragons; anti-tank anchor
            "aeldari_craftworlds_jain_zar": 3,         # leads Howling Banshees; melee pressure
            "aeldari_craftworlds_lhykhis": 3,          # leads Warp Spiders; mobility

            # Support character — Autarch is the generic officer filler in 3/6 lists.
            "aeldari_craftworlds_autarch": 2,

            # Aspect Warriors — universal in all 6 confirmed lists.
            "aeldari_craftworlds_warp_spiders": 3,      # 2-3 squads in every list; high mobility
            "aeldari_craftworlds_fire_dragons": 2,      # 2 squads in every list; anti-tank
            "aeldari_craftworlds_dark_reapers": 2,      # 1-2 squads; long-range firepower
            "aeldari_craftworlds_howling_banshees": 2,  # 1-2 squads; melee pressure
            "aeldari_craftworlds_swooping_hawks": 2,    # 2-3 squads; fast objective control

            # Dedicated transport — universal in all 6 lists.
            "aeldari_craftworlds_wave_serpent": 2,      # primary transport for Fire Dragons

            # Battleline filler — Corsair Voidreavers appear as cheap
            # battleline in 4/6 lists.
            "aeldari_craftworlds_corsair_voidreavers": 1,

            # Objective holders — Rangers appear in 5/6 lists.
            "aeldari_craftworlds_rangers": 1,
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
            "tyranids_exocrine": 1,
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
        # wave 239 — FX-ALL stub (21 unit types, all count=1 except Legionaries)
        # retired and replaced with the real May 2026 competitive Pactbound
        # Zealots backbone. The stub's 0.3-seed walk placed ~2 units then
        # random-filled from 18 leftovers, building a different incoherent army
        # every game — the signature of an army-construction problem, not a
        # missing mechanic (wave 238 re-diagnosis, FACTION_RESIDUAL_ANALYSIS.md).
        # The Chaos Daemons conversion from the same stub class to tight mono-god
        # templates moved that faction from -9.7 to -0.4; the same approach is
        # applied here.
        #
        # SOURCES (cross-checked against two independent sources per standing
        # rule — verified 2026-06-11):
        #
        # Source 1 — Spikey Bits, "Undefeated Warhammer Open UK Games Expo Army
        #   Lists: Chaos Space Marines Take 1st + 2nd"
        #   https://spikeybits.com/undefeated-warhammer-open-uk-games-expo-army-lists/
        #   Mani Cheema 1st place (8-0): Abaddon + Huron Blackheart + Vashtorr
        #   the Arkifane + 2x Cultist Mob (Nurgle) + 1x Legionaries (Slaanesh)
        #   + Chaos Rhino + Chaos Bikers + 1x Chosen + 3x Defilers (Nurgle) +
        #   Masters of the Maelstrom + Red Corsairs Raiders.
        #   Innes Wilson 2nd place: same Defiler triple core, Abaddon + Vashtorr,
        #   Traitor Enforcers instead of Legionaries (not in catalogue — omitted).
        #
        # Source 2 — Grimhammer Tactics, "40K Faction Focus: Competitive Chaos
        #   Space Marine Lists in 2025"
        #   https://grimhammertactics.com/40k-faction-focus-competitive-chaos-space-marine-lists-in-2025/
        #   Confirms: Vashtorr (daemon-engine strength aura), Forgefiend (Nurgle
        #   marked with ectoplasma cannons, "powerhouse damage dealers"), Chaos
        #   Predator Destructor, Possessed, Lord Discordant on Helstalker. Defiler
        #   is described as the new Pactbound engine since the datasheet refresh.
        #
        # REAL-META SHAPE: Abaddon + Vashtorr + Huron triple-character anchor,
        # three Defilers as the damage spine (Mark of Nurgle, ectoplasma /
        # lascannon config), two Cultist Mob screens for marker presence,
        # one Legionaries squad for the BATTLELINE Dark Pacts conduit, Chosen
        # for close-range firepower, Chaos Bikers for fast objective pressure,
        # Chaos Rhino transport, and a Forgefiend for sustained ranged firepower.
        # 10 unit types (down from 21), concentrated count-anchors on Defiler=3
        # and Cultist Mob=2 to drive seeding coherence.
        #
        # SEED WALK at 1000pt (SEED_FRACTION=0.3 = 300pt slice):
        # Sort order (-template_count, -squad_cost):
        #   Defiler=3   (250pt) -> 250pt — 1 Defiler seeds
        #   Cultist Mob=2 (50pt) -> 300pt — Cultist Mob seeds
        #   All count=1 entries overflow the 300pt budget after Defiler
        # CHARACTER guarantee: cheapest CHARACTER in template is Dark Apostle
        # (65pt) — lands within the 1.5x seed-budget overflow (450pt cap).
        # Random fill at remaining ~700pt then adds Abaddon (270pt, EPIC HERO
        # cap: 1 per army), Vashtorr (175pt, EPIC HERO MONSTER cap: 1 per
        # army), Huron (120pt, EPIC HERO cap), Legionaries (BATTLELINE fill),
        # Chosen, Chaos Bikers, Forgefiend, and a second Defiler (fill cap =
        # template_count=3 so up to 3 Defilers total at 2000pt budgets — the
        # real triple-Defiler shape emerges naturally at full-sized eval).
        "Pactbound Zealots": {
            # Daemon-engine spine — Defiler is the real-meta damage chassis;
            # count=3 ensures it wins the (-count, -cost) seed sort and one
            # Defiler always seeds at 1000pt. Random fill adds up to 2 more
            # (fill cap = template_count) so the triple-Defiler shape emerges
            # at 2000pt budgets.
            "chaos_space_marines_defiler": 3,
            # BATTLELINE screens — two Cultist Mob squads for marker presence
            # and objective control; count=2 places them second in the seed sort
            # after the Defiler. Legionaries=1 retains the Dark Pacts BATTLELINE
            # conduit (single squad — the real-meta carries 1 not 3).
            "chaos_space_marines_cultist_mob": 2,
            "chaos_space_marines_legionaries": 1,
            # EPIC HERO characters — Abaddon warlord (hit-roll re-roll aura
            # within 6" + 4++ Chosen), Vashtorr (daemon-vehicle strength aura,
            # MONSTER), Huron Blackheart (all-comers character support). All
            # three confirmed in the Mani Cheema 8-0 1st-place list. EPIC HERO
            # 1-per-army cap in _random_fill is respected for each.
            "chaos_space_marines_abaddon_the_despoiler": 1,
            "chaos_space_marines_vashtorr_the_arkifane": 1,
            "chaos_space_marines_huron_blackheart": 1,
            # Support CHARACTER — Dark Apostle seeds via the CHARACTER guarantee
            # even when over the seed-budget slice (cheapest CHARACTER at 65pt).
            # Provides Dark Pacts re-roll support.
            "chaos_space_marines_dark_apostle": 1,
            # Elite and fast attack — Chosen (close-range firepower, Abaddon
            # pairing), Chaos Bikers (fast objective pressure per Cheema's list).
            "chaos_space_marines_chosen": 1,
            "chaos_space_marines_chaos_bikers": 1,
            # Transport and shooty vehicle — Chaos Rhino in Cheema's 1st-place
            # list; Forgefiend (source 2: Nurgle-marked ectoplasma cannons,
            # "powerhouse damage dealer", the known under-valued durable shooty
            # vehicle class per FACTION_RESIDUAL_ANALYSIS.md list-realism note).
            "chaos_space_marines_chaos_rhino": 1,
            "chaos_space_marines_forgefiend": 1,
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
        # EC-COTERIE-V1: Coterie of the Conceited (Slaanesh's Due) is now the
        # registered Emperor's Children detachment, gated SWEG_EC_DETACHMENT
        # (default OFF). With the gate on, the army_builder's
        # pick_detachment_for_army resolves it deterministically (sole entry);
        # with the gate off, Emperor's Children still falls through to the
        # no-detachment path (byte-identical to before). The "Slaaneshi Excess"
        # key below is a SwegHammer archetype-seed label (the list shape), NOT a
        # detachment name — the real detachment is Coterie of the Conceited.
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
        # DAEMONS-MONOGOD (iter post-VOTANN-DIAG): replaced the previous all-
        # gods "Daemonic Incursion" template with four mono-god sub-archetypes.
        #
        # Why mono-god rotation. Real 10e Chaos Daemons competitive lists are
        # typically MONO-GOD — a Khorne-only, Tzeentch-only, Nurgle-only, or
        # Slaanesh-only army with one Greater Daemon of that god plus that
        # god's battleline, characters, and supporting daemons. Mixed-god
        # builds exist but are uncommon at the tournament level. The previous
        # all-gods template seeded one Greater Daemon of every god (4 x ~280pt
        # = 1120pt of Greater Daemons before any battleline / heralds got
        # picked) and a thinly spread troop layer that no single Locus aura
        # could focus on. An earlier attempt to surface the Locus auras by
        # packing all four Greater Daemons into every build (DAEMONS-ARCHETYPE)
        # regressed by +8pt because that crowded the rest of the army out.
        #
        # Approach. Four separate sub-templates — _DAEMONS_KHORNE,
        # _DAEMONS_TZEENTCH, _DAEMONS_NURGLE, _DAEMONS_SLAANESH — each with
        # exactly one Greater Daemon of its god, 1-2 god-aligned Heralds (so
        # the matching Locus aura fires), 2-3 battleline of that god, and
        # 1-2 elites / fast / vehicle slots from the same god's roster.
        # `build_archetype_army` already uniform-randomly picks one entry per
        # faction at build time (line ~1507 `rng.choice(list(available))`), so
        # over many sim runs the four sub-archetypes rotate 25% / 25% / 25%
        # / 25%. Real-meta proportions skew toward Khorne and Slaanesh, but
        # the simulator's job is to exercise each god's rules — uniform
        # rotation is sufficient for that without modifying the builder.
        #
        # Citations (real-meta rosters per god):
        #   https://wahapedia.ru/wh40k10ed/factions/chaos-daemons/
        #   Each unit key below is verified against data/bsdata/parsed.json
        #   under the "chaos_daemons_library_*" prefix.
        #
        # MR-CHAOS-DAEMONS-LOCUS: each Herald wired in code/leaders.py
        # broadcasts its god's locus aura to the attached battleline squad.
        # With a mono-god army the matching Locus fires every build instead
        # of one-in-four.
        "Khorne Murderhost": {
            # Bloodthirster anchor + Bloodletters battleline + Bloodcrushers/
            # Flesh Hounds melee fast + Skull Cannon ranged + Daemon Prince of
            # Chaos / Karanak character flex. Khorne is the most-played mono-
            # god list (real-meta Goonhammer/Frontline May 2026 GT lists).
            "chaos_daemons_library_bloodthirster": 1,
            "chaos_daemons_library_bloodmaster": 1,
            "chaos_daemons_library_skullmaster": 1,
            "chaos_daemons_library_bloodletters": 3,
            "chaos_daemons_library_bloodcrushers": 2,
            "chaos_daemons_library_flesh_hounds": 1,
            "chaos_daemons_library_skull_cannon": 1,
            "chaos_daemons_library_karanak": 1,
            "chaos_daemons_library_daemon_prince_of_chaos": 1,
        },
        "Tzeentch Manifestation": {
            # Lord of Change anchor + Pink Horrors battleline + Flamers /
            # Screamers fast attack + Burning Chariot vehicle + The Changeling
            # / Fluxmaster character flex. Tzeentch is the ranged-shooting /
            # psychic-pivot mono-god build.
            "chaos_daemons_library_lord_of_change": 1,
            "chaos_daemons_library_changecaster": 1,
            "chaos_daemons_library_fluxmaster": 1,
            "chaos_daemons_library_pink_horrors": 3,
            "chaos_daemons_library_flamers": 2,
            "chaos_daemons_library_screamers": 1,
            "chaos_daemons_library_burning_chariot": 1,
            "chaos_daemons_library_the_changeling": 1,
            "chaos_daemons_library_daemon_prince_of_chaos": 1,
        },
        "Nurgle Pestilence": {
            # Great Unclean One anchor + Plaguebearers battleline + Plague
            # Drones / Beasts of Nurgle / Nurglings supporting elites +
            # Nurgle Soul Grinder fire support + Poxbringer / Sloppity
            # Bilepiper heralds. Nurgle is the resilience / objective-holding
            # mono-god build.
            "chaos_daemons_library_great_unclean_one": 1,
            "chaos_daemons_library_poxbringer": 1,
            "chaos_daemons_library_sloppity_bilepiper": 1,
            "chaos_daemons_library_plaguebearers": 3,
            "chaos_daemons_library_plague_drones": 2,
            "chaos_daemons_library_beasts_of_nurgle": 1,
            "chaos_daemons_library_nurglings": 1,
            "chaos_daemons_library_nurgle_soul_grinder": 1,
            "chaos_daemons_library_daemon_prince_of_chaos": 1,
        },
        "Slaanesh Excess": {
            # Keeper of Secrets anchor + Daemonettes battleline + Seekers /
            # Fiends fast melee + Slaanesh Soul Grinder fire support + The
            # Masque of Slaanesh / Contorted Epitome heralds. Slaanesh is
            # the speed / fights-first mono-god build.
            "chaos_daemons_library_keeper_of_secrets": 1,
            "chaos_daemons_library_contorted_epitome": 1,
            "chaos_daemons_library_tormentbringer": 1,
            "chaos_daemons_library_daemonettes": 3,
            "chaos_daemons_library_seekers": 2,
            "chaos_daemons_library_fiends": 1,
            "chaos_daemons_library_slaanesh_soul_grinder": 1,
            "chaos_daemons_library_the_masque_of_slaanesh": 1,
            "chaos_daemons_library_daemon_prince_of_chaos": 1,
        },
        # SWEG_DAEMONS_BELAKOR (2026-07-02, default OFF) — Be'lakor-anchored
        # multi-god "Scintillating Legion" fifth sub-archetype. The four
        # mono-god templates above rotate uniformly (25% each) and cover the
        # "one Greater Daemon of one god" shape, but the real 2026
        # competitive Chaos Daemons meta is instead Be'lakor-anchored and
        # deliberately multi-god:
        #
        # Source 1 — Spikey Bits, "Top 40k Tournament Army Lists: Leeds
        #   Super Major" (https://spikeybits.com/top-40k-tournament-army-
        #   lists-leeds-super-major/). Second place ran Be'lakor + Great
        #   Unclean One + Kairos Fateweaver + Lord of Change + Skarbrand —
        #   described as "five Greater Daemons" — under Daemonic Incursion
        #   with a thin troop screen.
        #
        # Source 2 — Bell of Lost Souls, "Goatboys' Grimdark Army List:
        #   Chaos Daemons Scintillating Legion, Kicking It Bird Style"
        #   (https://www.belloflostsouls.net/2026/01/goatboys-grimdark-
        #   armylist-chaos-daemons-scintillating-legion-kicking-it-bird-
        #   style.html), cross-checked against Grimhammer Tactics, "Top 10
        #   Competitive Warhammer 40k Lists — March 2026"
        #   (https://grimhammertactics.com/top-10-competitive-warhammer-
        #   40k-lists-march-2026/). Wheat City Grand Tournament first place
        #   "Quad Birds" ran Be'lakor + Kairos Fateweaver + 2x Lord of
        #   Change under the Scintillating Legion detachment.
        #
        # REAL-META SHAPE: this template takes the intersection sourced
        # from both lists — Be'lakor (EPIC HERO anchor, both sources),
        # Kairos Fateweaver (both sources), one Lord of Change (both
        # sources; the "Quad Birds" list runs two but a single-copy seed
        # keeps this template's core cost inside the archetype seed
        # budget — the second Lord of Change is available to `_random_fill`
        # via the MONSTER wrecker cap), and one Great Unclean One (source
        # 1's "five Greater Daemons" reading, providing the Nurgle
        # resilience leg the two all-Tzeentch lists omit). Skarbrand is not
        # in the catalogue (verified against `data/bsdata/parsed.json` —
        # no `chaos_daemons_library_skarbrand` key — so it is dropped
        # rather than invented per CLAUDE.md rule 9). Pink Horrors (count=2)
        # and Plaguebearers (count=1) supply the BATTLELINE troop screen
        # both sources describe; The Changeling adds a cheap EPIC HERO
        # scoring/infiltration piece (verified
        # `chaos_daemons_library_the_changeling` resolves in the
        # catalogue).
        #
        # Gating: this entry is ALWAYS present in the ARCHETYPES dict (a
        # module-level dict literal cannot conditionally omit a key at
        # import time without an import-order-dependent env read — see the
        # CRITICAL GATING CONSTRAINT note on `build_archetype_army` below).
        # Visibility is instead gated at the point `build_archetype_army`
        # reads `ARCHETYPES[faction]` into `available` and rolls
        # `rng.choice(list(available.keys()))`: when SWEG_DAEMONS_BELAKOR
        # is not "1", "Scintillating Legion" is filtered out of `available`
        # BEFORE the `rng.choice` call, so the choice list has the same 4
        # entries, in the same order, as the pre-existing code — byte-
        # identical off. See DAEMONS-FIX-1 below (in `_instantiate_template`)
        # for the paired force-seed pre-pass that fields this template's
        # four-Greater-Daemon core, and `_keyword_affinity_score` in
        # `code/detachments.py` for the paired detachment-picker affinity.
        "Scintillating Legion": {
            "chaos_daemons_library_be_lakor": 1,
            "chaos_daemons_library_kairos_fateweaver": 1,
            "chaos_daemons_library_lord_of_change": 1,
            "chaos_daemons_library_great_unclean_one": 1,
            "chaos_daemons_library_pink_horrors": 2,
            "chaos_daemons_library_plaguebearers": 1,
            "chaos_daemons_library_the_changeling": 1,
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
            "astra_militarum_attilan_rough_riders": 1,
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
            "adeptus_mechanicus_serberys_sulphurhounds": 1,
            "adeptus_mechanicus_kataphron_breachers": 1,
            "adeptus_mechanicus_kataphron_destroyers": 1,
            "adeptus_mechanicus_pteraxii_sterylizors": 1,
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
            "adepta_sororitas_celestian_insidiants": 1,
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


def _is_antitank_profile(profile: UnitProfile) -> bool:
    """Heuristic anti-armour classifier (wave 190 over-pole probe only — NOT a
    rules flag): a unit counts as anti-tank if its main weapon is high-strength
    (S>=10), high-damage (>=3 per shot), high-AP (<=-3), or carries an
    anti-VEHICLE/MONSTER/TITANIC keyword. Used to isolate the "opponent
    anti-tank STRENGTH" sub-lever from the budget-crowding confound of maxing
    every seed squad. Mirrors the audit script in data/wf_wave190_squadsize_audit.txt."""
    strength = getattr(profile, "strength", 0) or 0
    dmg = getattr(profile, "per_shot_damage", 0) or getattr(profile, "damage", 0) or 0
    ap = getattr(profile, "ap", 0) or 0
    ak = getattr(profile, "anti_keywords", None) or {}
    anti = any(k in ("VEHICLE", "MONSTER", "TITANIC")
               for k in (ak.keys() if hasattr(ak, "keys") else ak))
    return strength >= 10 or dmg >= 3 or ap <= -3 or anti


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
    # AdMech-DIAG (wave 173): the cited Skitarii Hunter Cohort seed encodes the
    # real May-2026 list's DURABLE CORE (Belisarius Cawl, an Onager Dunecrawler,
    # a Skorpius Disintegrator, two Kataphron bodies). At the default 0.3 slice
    # (600pt at 2000pt) that expensive core does not fit, so the seed walk drops
    # the Onager (realizes ~0.4/btl vs the seeded 1) and the 70% random_fill
    # piles on cheap fragile Skitarii — the REALIZED list is more fragile than
    # the cited real list, the under-side mirror of an unfaithful realization.
    # The AdMech diagnostic localized AdMech's under-shoot to ATTRITION (38%
    # survival vs 60%); the over-fragile realization is part of that. 0.65 (1300pt
    # seed) reliably realizes the durable core (Onager 1.1, Skorpius 1.4,
    # Kataphrons, Cawl) and trims the fragile fill (68→57 units/btl) so the
    # realized list matches the cited Goonhammer/Frontline/Stat-Check May-2026
    # Skitarii Hunter Cohort. FAITHFUL list-realism (matching reality), not
    # win-rate tuning — landed even though it is expected to raise AdMech's
    # under-shooting win rate toward 50% (fidelity-first; the "faithful but
    # raises the metric -> skip" reflex is forbidden).
    "Adeptus Mechanicus": 0.65,
    # SYSTEMATIC LIST-REALISM PASS (wave 174, user-requested audit). The default
    # 0.3 seed slice drops the FIXED durable/support core of several factions'
    # cited real lists (the units the real list ALWAYS runs), filling instead
    # with cheap fragile units → an unfaithful realization. `diag_list_realism.py`
    # found the drops; each fraction below is the lowest that realizes the cited
    # dropped core (verified realized-MATCHES-real, NOT chosen to move win rate).
    # EVEN-HANDED: applied to ALL distorted fixed-core factions regardless of
    # over/under/in-band, accepting whatever metric direction. MENU seeds
    # (IK/CK/Daemons/Emperor's Children/Aeldari/World Eaters — a menu of big
    # variants @1 from which the builder picks a faithful subset) are LEFT alone.
    "Astra Militarum": 0.55,     # realizes Scout Sentinels + Leman Russ + Manticore (tank/support core)
    "Chaos Space Marines": 0.65,  # realizes Forgefiend + Lord Discordant + Daemon Prince (heavy support + characters)
    "Adepta Sororitas": 0.55,    # realizes Castigator + Saint Celestine
    "Grey Knights": 0.45,        # realizes Nemesis Dreadknight
    "T'au Empire": 0.55,         # realizes Ghostkeel + keeps Riptide (Stormsurge/Ghostkeel are menu alternatives)
    # KNIGHTS-DIAG-3 (wave 33): Default 0.3 = 300pt seed budget at 1000pt
    # eval. Every Questoris-class Chaos Knight costs 355–410pt — more
    # than the entire seed budget — so the template seed always picks
    # War Dogs (140–150pt) and the random-fill 50% cap excludes
    # Rampager (365pt) entirely and Abominant (355pt) in 67% of builds.
    # Raising to 0.45 = 450pt seeds one Questoris knight per build,
    # which is required for KNIGHTS-MULTIPROFILE-2 extra_melee_profiles
    # work to reach the faction-level metric. Imperial Knights mirrors
    # the same chassis cost shape so the bump applies symmetrically.
    "Chaos Knights": 0.45,
    "Imperial Knights": 0.45,
}

# Wave 244 (gated SWEG_SEED_LEADERS) — fraction re-derivation under the
# leader-stack tiebreak. The per-faction fractions above were each derived
# as "the lowest that realizes the cited dropped core" (wave-174 method)
# under the old (-count, -cost) walk. With the leader-stack tiebreak on,
# characters seed ahead of equally-counted heavy support, so the same
# fraction can no longer guarantee the gate-on seeded set is a superset of
# the gate-off seeded set.
#
# Superset criterion (wave 244 amendment): gate-on seeded set must be a
# strict superset of gate-off seeded set — no entry that the gate-off walk
# realizes may be absent from the gate-on walk. Any missing entry is a
# list-realism regression (the gate-on build loses a documented template
# entry that the baseline build fielded). The original four entries were
# derived against a 150-point screening threshold and missed cheaper
# de-realizations (for example, Adeptus Astartes Apothecary at 50 points
# displaces the Eradicator Squad at 90 points in the count=1 tier).
#
# Each value below is the minimal fraction at which the gate-on
# deterministic seed walk realizes a superset of the gate-off seeded set
# (scanned in 0.01 steps at the 2000-point eval budget). Derivation is
# realized-MATCHES-real, NOT chosen to move win rate. Menu factions
# (Imperial Knights, Chaos Knights, Chaos Daemons, Emperor's Children,
# World Eaters, Aeldari) are left alone per the wave-174 rule. Consulted
# only when the gate is on; fold into SEED_FRACTION_BY_FACTION at
# default-flip.
#
# Fractions where the dict folds into SEED_FRACTION_BY_FACTION (gate-off
# baseline) are also the fallback for gate-on when no entry is listed
# here — any faction not listed below had no de-realization at 2000 points
# and needs no extra headroom.
#
# Per-faction table (gate-off effective fraction -> gate-on minimal):
#   Adeptus Astartes:  0.30 -> 0.31  restores Eradicator Squad (90pt)
#   Necrons:           0.30 -> 0.34  restores Ghost Ark (115pt)
#   T'au Empire:       0.55 -> 0.59  restores Devilfish (85pt)
#   Death Guard:       0.30 -> 0.37  restores Deathshroud Terminators (160pt)
#   Adeptus Custodes:  0.55 -> 0.58  restores Custodian Guard (160pt) +
#                                    Prosecutors (40pt)
#   Leagues of Votann: 0.40 -> 0.48  restores Hernkyn Pioneers (80pt) +
#                                    Sagitaur (90pt)
#   Drukhari:          0.30 -> 0.33  restores Ravager (110pt)
#   Chaos Space Marines: 0.65 -> 0.66  restores Legionaries (90pt)
#   Astra Militarum:   0.67 -> 0.72  restores Taurox Prime (90pt)
#                                    (old 0.67 missed this sub-150pt drop)
#   Adeptus Mechanicus: 0.65 -> 0.73  restores Pteraxii Sterylizors (80pt) +
#                                    Sicarian Infiltrators (75pt)
#   Adepta Sororitas:  0.61 -> 0.65  restores Seraphim Squad (80pt)
#                                    (old 0.61 missed this sub-150pt drop)
#   Grey Knights:      0.72 -> 0.78  restores Interceptor Squad (125pt)
#                                    (old 0.72 missed this sub-150pt drop)
#   Thousand Sons:     0.37 unchanged  already a superset at 0.37
#   Genestealer Cults: 0.30 -> 0.49  restores Aberrants (135pt) +
#                                    Achilles Ridgerunners (95pt) +
#                                    Atalan Jackals (85pt) +
#                                    Goliath Rockgrinder (120pt)
SEED_FRACTION_LEADER_STACK: Dict[str, float] = {
    # Adeptus Astartes: 0.30 -> 0.31; restores Eradicator Squad (90pt)
    # displaced by the Apothecary CHARACTER tiebreak (50pt).
    "Adeptus Astartes": 0.31,
    # Necrons: 0.30 -> 0.34; restores Ghost Ark (115pt) displaced by
    # the Overlord CHARACTER tiebreak (85pt).
    "Necrons": 0.34,
    # T'au Empire: 0.55 -> 0.59; restores Devilfish (85pt) displaced by
    # the Commander in Enforcer Battlesuit CHARACTER tiebreak (95pt).
    "T'au Empire": 0.59,
    # Death Guard: 0.30 -> 0.37; restores Deathshroud Terminators (160pt)
    # displaced by Foul Blightspawn (75pt) + Typhus (100pt) CHARACTER tiebreaks.
    "Death Guard": 0.37,
    # Adeptus Custodes: 0.55 -> 0.58; restores Custodian Guard (160pt) +
    # Prosecutors (40pt) displaced by Blade Champion (120pt) + Allarus
    # Custodians (110pt) tiebreaks.
    "Adeptus Custodes": 0.58,
    # Leagues of Votann: 0.40 -> 0.48; restores Hernkyn Pioneers (80pt) +
    # Sagitaur (90pt) displaced by Einhyr Champion (70pt) + Brokhyr Iron
    # Master (75pt) CHARACTER tiebreaks.
    "Leagues of Votann": 0.48,
    # Drukhari: 0.30 -> 0.33; restores Ravager (110pt) displaced by
    # Archon CHARACTER tiebreak (80pt).
    "Drukhari": 0.33,
    # Chaos Space Marines: 0.65 -> 0.66; restores Legionaries (90pt)
    # displaced by Dark Apostle CHARACTER tiebreak (65pt).
    "Chaos Space Marines": 0.66,
    # Astra Militarum: 0.67 -> 0.72; restores Taurox Prime (90pt)
    # displaced by Cadian Command Squad (65pt) + Ursula Creed (85pt) +
    # Lord Solar Leontus (130pt) CHARACTER tiebreaks. Old value 0.67
    # restored the 150pt+ heavy core but missed this sub-150pt entry.
    "Astra Militarum": 0.72,
    # Adeptus Mechanicus: 0.65 -> 0.73; restores Pteraxii Sterylizors
    # (80pt) + Sicarian Infiltrators (75pt) displaced by Skitarii Marshal
    # (35pt) + Tech-Priest Manipulus (60pt) + Tech-Priest Dominus (65pt)
    # CHARACTER tiebreaks.
    "Adeptus Mechanicus": 0.73,
    # Adepta Sororitas: 0.61 -> 0.65; restores Seraphim Squad (80pt)
    # displaced by Canoness (60pt) + Palatine (50pt) + Junith Eruita (80pt)
    # CHARACTER tiebreaks. Old value 0.61 restored the Castigator but
    # missed this sub-150pt entry.
    "Adepta Sororitas": 0.65,
    # Grey Knights: 0.72 -> 0.78; restores Interceptor Squad (125pt)
    # displaced by five CHARACTER tiebreaks (Brother Captain 90pt,
    # Brotherhood Chaplain 65pt, Brotherhood Librarian 80pt, Brotherhood
    # Champion 70pt, Grand Master 95pt) + Venerable Dreadnought (140pt).
    # Old value 0.72 restored the Nemesis Dreadknight + Land Raider but
    # missed this sub-150pt entry.
    "Grey Knights": 0.78,
    # Thousand Sons: 0.37 unchanged; gate-on seeded set is already a
    # superset of gate-off seeded set at 0.37 (Mutalith Vortex Beast +
    # Rubric Marines + Scarab Occult Terminators all realized).
    "Thousand Sons": 0.37,
    # Genestealer Cults: 0.30 -> 0.49; restores Aberrants (135pt) +
    # Achilles Ridgerunners (95pt) + Atalan Jackals (85pt) + Goliath
    # Rockgrinder (120pt) displaced by six CHARACTER tiebreaks (Patriarch
    # 75pt, Primus 70pt, Clamavus 50pt, Jackal Alphus 55pt, Kelermorph
    # 60pt, Sanctus 50pt).
    "Genestealer Cults": 0.49,
}

# Menu factions: the template is deliberately an oversized menu of big
# single-count options (partial realization is the design), so the
# CHARACTER-priority tiebreak has no leader-stack rationale there and the
# wave-174 rule forbids seed-fraction tuning for them. Measured wave 244:
# the un-scoped tiebreak DE-realized faithful menu entries (Aeldari Fire
# Dragons, Emperor's Children Daemonettes, Chaos Daemons Flesh Hounds /
# Beasts of Nurgle / Slaanesh Soul Grinder) with no permitted fraction fix,
# while Imperial Knights / World Eaters builds were byte-identical either
# way (seed budget exhausts before the tiebreak reaches a live choice).
# Scoping the gate to non-menu factions keeps every menu build identical
# to the gate-off walk.
MENU_FACTIONS = frozenset({
    "Imperial Knights",
    "Chaos Knights",
    "Chaos Daemons",
    "Emperor's Children",
    "World Eaters",
    "Aeldari",
})


def _effective_template(
    faction: Optional[str], template: Dict[str, int]
) -> Dict[str, int]:
    """Apply every env-gated list-realism correction and return the
    EFFECTIVE template.

    Fidelity-first phase B (2026-07-02, owner-authorized; per-faction
    sourcing in docs/ARCHETYPE_FIDELITY_AUDIT.md and the wave-250/251
    citations below): called ONCE by `build_archetype_army` so the same
    effective template reaches BOTH the seed walk AND `_random_fill` —
    the old in-function gates leaked (the fill received the raw template,
    so dropped units re-entered via the fill's template-count lookup;
    with template-first fill adopted, that leak would have been fatal).
    Every gate is idempotent (pure filters and explicit count
    assignments), so double application through direct
    `_instantiate_template` callers is harmless. All gates default OFF;
    each is faithful list-realism matching sourced tournament lists, NOT
    win-rate tuning — the metric direction is accepted whatever it is.
    """
    fac = faction or ""

    # SWEG_WE_REALISM (wave 250, EXTENDED 2026-07-02) — World Eaters.
    # Sourced (wave-250 Grimhammer/Best Coast Pairings lists + the
    # 2026-07-01 audit re-verification, e.g. Bell of Lost Souls April
    # 2026 "Defiled World Eaters"): real Berzerker Warband lists are
    # Khârn-anchored with NO Angron, and field none of Bloodletters /
    # Bloodcrushers / Chaos Terminators / Helbrute; the freshest sourced
    # list runs 2x Defiler. Drop the phantoms (Khârn, already templated,
    # becomes the epic-hero anchor) and add the Defiler pillar.
    if os.environ.get("SWEG_WE_REALISM", "1") != "0" and fac == "World Eaters":
        _we_drop = {
            "world_eaters_angron",
            "world_eaters_bloodletters",
            "world_eaters_bloodcrushers",
            "world_eaters_chaos_terminators",
            "world_eaters_helbrute",
        }
        template = {k: v for k, v in template.items() if k not in _we_drop}
        template["world_eaters_defiler"] = 2

    # SWEG_AM_REALISM (wave 251, moved here 2026-07-02 unchanged) —
    # Astra Militarum infantry-heavy Combined Arms spine. Sourced:
    #   https://bladesandbolts.com/2025/10/06/astra-militarum-warhammer-40k-lvo/
    #   https://grimhammertactics.com/top-10-competitive-warhammer-40k-lists-november-2025/
    #   https://spikeybits.com/top-40k-tournament-army-lists-rise-of-the-empire-gt/
    if os.environ.get("SWEG_AM_REALISM") == "1" and fac == "Astra Militarum":
        template = {
            "astra_militarum_cadian_shock_troops": 3,
            "astra_militarum_death_korps_of_krieg": 2,
            "astra_militarum_kasrkin": 3,
            "astra_militarum_tempestus_scions": 1,
            "astra_militarum_cadian_command_squad": 1,
            "astra_militarum_cadian_heavy_weapons_squad": 1,
            "astra_militarum_leman_russ_battle_tank": 1,
            "astra_militarum_leman_russ_demolisher": 1,
            "astra_militarum_rogal_dorn_battle_tank": 1,
            "astra_militarum_chimera": 1,
            "astra_militarum_cadian_castellan": 1,
            "astra_militarum_ursula_creed": 1,
            "astra_militarum_lord_solar_leontus": 1,
        }

    # SWEG_DG_REALISM (2026-07-02) — Death Guard. Sourced (audit agent:
    # Warhammer Open Tacoma 1st, Lorecast Major 1st, tabletopbattles
    # detachment focus; zero sourced lists field Typhus or the Foul
    # Blightspawn; the Daemon Prince of Nurgle "shows up in most, if not
    # all, competitive lists"; "at least two units of Deathshroud";
    # ~48-58 real models vs the sim's ~34): drop the two phantom
    # characters, add the Daemon Prince + a second Lord of Contagion,
    # double Deathshroud and Poxwalkers bodies, and thin the Plagueburst
    # Crawler seed to one (the post-Q1-2026-dataslate meta moved off
    # multi-Crawler builds — the weakest-sourced item here, flagged for
    # re-verification in the audit).
    if os.environ.get("SWEG_DG_REALISM", "1") != "0" and fac == "Death Guard":
        _dg_drop = {"death_guard_typhus", "death_guard_foul_blightspawn"}
        template = {k: v for k, v in template.items() if k not in _dg_drop}
        template["death_guard_daemon_prince_of_nurgle"] = 1
        template["death_guard_lord_of_contagion"] = 2
        template["death_guard_deathshroud_terminators"] = 2
        template["death_guard_poxwalkers"] = 2
        template["death_guard_plagueburst_crawler"] = 1
        # MYPHITIC-REENABLE (2026-07-02) — the Myphitic Blight-hauler was
        # disabled by the 38-unit no-canonical-points sweep (BSData encodes
        # no cost for its datasheet) despite being a real near-universal
        # tournament pick: docs/ARCHETYPE_FIDELITY_AUDIT.md's decision menu
        # calls for "re-enable the Myphitic Blight-hauler at its cited 100
        # points", and the sourced "Virulent Vectorium" Death Guard lists in
        # docs/WAVE250_LIST_REALISM.md field 2 per list. Re-enabled in
        # data/overrides.json with the canonical Wahapedia cost (100 points,
        # cited there); added here at a conservative floor of 1 rather than
        # the sourced list's 2, since the audit's claim is "near-universal
        # presence", not a fixed count. Guarded per CLAUDE.md rule 13 (fail
        # loud on missing data, no silent defaults): if the override entry
        # ever stops resolving in UNIT_CATALOG, this raises instead of
        # silently dropping the unit from an already-default-on template.
        if "death_guard_myphitic_blight_hauler" not in UNIT_CATALOG:
            raise KeyError(
                "archetypes._effective_template: SWEG_DG_REALISM expects "
                "'death_guard_myphitic_blight_hauler' to resolve in "
                "UNIT_CATALOG (re-enabled in data/overrides.json) but it is "
                "missing — check the override entry for a typo'd key or a "
                "regression that dropped it from the catalogue."
            )
        template["death_guard_myphitic_blight_hauler"] = 1

    # SWEG_EC_REALISM (2026-07-02) — Emperor's Children. Sourced (audit
    # agent: Kyle Sams 2nd Battle For The Capital, Bell of Lost Souls
    # "Triple Defiler" April 2026, Stoke Gifford Supermajor): Fulgrim /
    # Keeper of Secrets / Daemonettes / Seekers / Fiends / Chaos
    # Terminators / Heldrake appear in ZERO sourced lists (Fulgrim alone
    # was 17% of every sim army's points); real lists run 3x Lord
    # Exultant, 2x Noise Marines, and Defilers as the monster pillar.
    if os.environ.get("SWEG_EC_REALISM", "1") != "0" and fac == "Emperor's Children":
        _ec_drop = {
            "emperor_s_children_fulgrim",
            "emperor_s_children_keeper_of_secrets",
            "emperor_s_children_daemonettes",
            "emperor_s_children_seekers",
            "emperor_s_children_fiends",
            "emperor_s_children_chaos_terminators",
            "emperor_s_children_heldrake",
        }
        template = {k: v for k, v in template.items() if k not in _ec_drop}
        template["emperor_s_children_lord_exultant"] = 3
        template["emperor_s_children_noise_marines"] = 2
        template["emperor_s_children_defiler"] = 2

    # SWEG_IK_REALISM (2026-07-02) — Imperial Knights. Sourced (audit
    # agent: CaptainCon 2026 1st place ran Cerastus Atrapos + Cerastus
    # Lancer + Knight Defender + Armigers; ZERO sourced lists ran Canis
    # Rex, which the greedy walk force-seeded into 100% of builds): drop
    # Canis Rex and add the real big-Knight core to the menu. With Canis
    # dropped the deterministic anchor becomes the Knight Defender (415),
    # matching the sourced core.
    if os.environ.get("SWEG_IK_REALISM", "1") != "0" and fac == "Imperial Knights":
        template = {
            k: v for k, v in template.items()
            if k != "imperial_knights_library_canis_rex"
        }
        template["imperial_knights_library_cerastus_knight_lancer"] = 1
        template["imperial_knights_library_cerastus_knight_atrapos"] = 1
        template["imperial_knights_library_knight_defender"] = 1

    # SWEG_CK_REALISM (2026-07-02) — Chaos Knights. Sourced (audit agent:
    # CaptainCon 2026 2nd ran 2x Chaos Cerastus Lancer + Despoilers; Big
    # Sky Open 1st ran Chaos Cerastus Atrapos + 2x Despoiler; the meta
    # commentary pick is "three Knight Despoilers"): add the Chaos
    # Cerastus pair and raise the Despoiler count to two. The Knight
    # Tyrant (410) remains the deterministic anchor, matching the
    # Tyrant-anchored Iconoclast 3-0 sourced list.
    if os.environ.get("SWEG_CK_REALISM") == "1" and fac == "Chaos Knights":
        template = dict(template)
        template["chaos_knights_library_chaos_cerastus_knight_lancer"] = 1
        template["chaos_knights_library_chaos_cerastus_knight_atrapos"] = 1
        template["chaos_knights_library_knight_despoiler"] = 2

    # SWEG_TSONS_MAGNUS (2026-07-04) — Thousand Sons Magnus the Red
    # centerpiece. Default OFF (screening gate; adopt default-on only after
    # the orchestrator's N=80 screen). List-realism correction, NOT win-rate
    # tuning — the metric direction is accepted whatever it is.
    #
    # WHY: the Thousand Sons template (Rubricae Phalanx) intentionally
    # excluded Magnus on STALE 1000-point-budget logic ("435pt would crowd
    # out the army at 1000pt"; "random_fill picks him up at 2000pt"). But the
    # production eval budget is 2000pt, and Magnus is BARRED from random_fill
    # by the MONSTER / EPIC HERO cap (a template_count of 0 caps his fills at
    # 0), so he was fielded in 0% of builds — the sim fought the Death Guard
    # brick (Toughness-12, 2+/4++) without its single hardest anti-brick tool
    # (Gaze of Magnus: 3D3 shots, Strength-11, AP-2, Damage-3, Devastating
    # Wounds, Psychic; + Blade of Magnus melee, Strength-16 AP-3).
    #
    # SOURCED — real May/2026 competitive 2000-point Thousand Sons run Magnus
    # as a common centerpiece (a genuine ~50/50 split with Ahriman-led Rubric
    # spam, NOT universal — documented honestly), including within the
    # Rubricae Phalanx detachment this template names:
    #   - Broadsword Wargaming (March 2026): UNDEFEATED Rubricae Phalanx =
    #     Rubric Marines + Scarab Occult Terminators + Predators + Magnus the
    #     Red (Magnus enables 2 Rituals/turn). Cited in Grimhammer Tactics
    #     "Top 10 Competitive Warhammer 40K Lists March 2026".
    #   - Las Vegas Open 2026, Nick Hodson 5-1: Magnus + Mutalith Vortex Beast
    #     + Ahriman + Rubric spam + Cultists + Tzaangor Enlightened
    #     (warphammer40k.com "For the Changer of Ways" LVO report) — the sim's
    #     template shape plus Magnus.
    #   - Grand Coven Magnus builds placed 3rd/6th/8th at Feb-Apr 2026 events
    #     (Goonhammer Competitive Innovations).
    # MECHANISM: seed Magnus into the template (count=1). He is the most
    # expensive template EPIC HERO (435pt vs Ahriman 100pt), so the existing
    # iter24-D2 EPIC HERO anchor guarantee in `_instantiate_template`
    # force-seeds him as the centerpiece at ~100% of 2000-point builds
    # (Thousand Sons is not a MENU faction, so the wave-244 leader-stack
    # anchor trigger fires whenever the flagship epic hero is unseeded) —
    # the same mechanism that seeds Death Guard Mortarion and World Eaters
    # Khârn. This over-represents relative to the real ~50% split (the sim
    # carries ONE representative build, per the project's one-representative-
    # build convention, so the Magnus-centerpiece variant is modelled), which
    # gives a clean anti-brick signal and matches the sourced undefeated
    # Rubricae Phalanx + Magnus list. Random_fill's EPIC HERO cap is
    # unchanged. The RUBRICAE-keyword affinity that tilts the detachment
    # picker toward Rubricae Phalanx is PRESERVED — Scarab Occult Terminators
    # and Rubric Marines are still seeded (Magnus is added, nothing dropped),
    # so the picker stays Rubricae Phalanx (verified in the N=20 probe).
    # Guarded per CLAUDE.md rule 13 (fail loud on missing data): if the
    # override/catalogue key ever stops resolving, raise instead of silently
    # dropping the centerpiece from a would-be-default-on template.
    # ADOPTED default-on 2026-07-04 (`=0` kill-switch). N=80 Thousand-Sons-scoped
    # screen vs sc54a: Thousand Sons 46.3 -> 53.0 (+6.70, landing on real 53.9),
    # gated 3.60 -> 3.51, and Death Guard deflates -1.02 toward real (the crater
    # was a LIST gap, not a durability floor — Magnus is the missing anti-brick
    # tool; the Death-Guard-vs-Thousand-Sons cell collapses 90 -> 52.5). Sourced:
    # real 2026 competitive Thousand Sons run Magnus as a common centerpiece.
    if os.environ.get("SWEG_TSONS_MAGNUS", "1") != "0" and fac == "Thousand Sons":
        if "thousand_sons_magnus_the_red" not in UNIT_CATALOG:
            raise KeyError(
                "archetypes._effective_template: SWEG_TSONS_MAGNUS expects "
                "'thousand_sons_magnus_the_red' to resolve in UNIT_CATALOG "
                "but it is missing — check for a regression that dropped the "
                "datasheet from the catalogue or a typo'd key."
            )
        template = dict(template)
        template["thousand_sons_magnus_the_red"] = 1

    # SWEG_ORKS_GHAZGHKULL (2026-07-04) — Orks Ghazghkull Thraka centerpiece.
    # Default OFF (screening gate; adopt default-on only after the
    # orchestrator's N=80 screen). List-realism correction, NOT win-rate
    # tuning — the metric direction is accepted whatever it is.
    #
    # WHY: the Orks template (Waaagh!) fields Boyz x2, Meganobz, Warboss in
    # Mega Armour, Killa Kans, Tankbustas, Nobz, Deffkoptas — a headless
    # chaff mob with zero epic heroes. Ghazghkull Thraka is in the catalogue
    # but absent from the template, so he is BARRED from random_fill by the
    # MONSTER / EPIC HERO cap (a template_count of 0 caps his fills at 0) —
    # the exact bar that hid Magnus from Thousand Sons. He was fielded in 0%
    # of builds (`docs/_COMPAUDIT_UNDERPOLES.md`, 20/20 census), so the sim
    # fights without its only durable anchor and without its only army-wide
    # offence multiplier.
    #
    # SOURCED — real May/2026 competitive Orks run Ghazghkull as the War
    # Horde centerpiece (the detachment SwegHammer already fields for Orks):
    #   - Tabletop Battles "Detachment Focus: War Horde" (updated
    #     2025-12-30): "you need Ghazghkull, who during a Waaagh! gives his
    #     unit Crits on a 5+ and through Makari gives Ork units within 12"
    #     LETHAL HITS"; War Horde is "the only [detachment] where Ghazghkull
    #     is a must-take" and "currently the preferred way to run the
    #     faction competitively." https://www.tabletopbattles.com/
    #     detachment-focus-war-horde/
    #   - Tabletop Battles "10th Edition Competitive Faction Focus: Orks".
    #     https://www.tabletopbattles.com/10th-edition-competitive-faction-
    #     focus-orks/
    #   - Bolter and Chainsword "2,000 Point Tournament War Horde List" — a
    #     Ghazghkull-anchored 2000-point tournament build.
    #     https://bolterandchainsword.com/topic/382953-2000-point-
    #     tournament-war-horde-list/
    #   - Corroborated 2026-07-04: Ghazghkull typically rides a Battlewagon
    #     ('Ard Case) or joins 20 Boyz / Breaka Boyz / Nobz; the War Horde's
    #     always-on abilities (Prophet of Da Great Waaagh! crits-on-5+ in
    #     melee while the Waaagh! is active; Makari's Waaagh! Banner grants
    #     Lethal Hits to friendly ORKS within 12" of Makari) became much more
    #     viable in late 2025 when Battlewagon and Ghazghkull changes landed,
    #     and the detachment "remains competitive in 2026, particularly when
    #     built around Ghazghkull as a centerpiece."
    # MECHANISM: seed Ghazghkull into the template (count=1). He is the sole
    # template EPIC HERO once added, so the existing EPIC HERO anchor
    # guarantee in `_instantiate_template` force-seeds him as the centerpiece
    # (validated 20/20 in the under-pole audit's read-only probe) — the same
    # mechanism that seeds Death Guard Mortarion, World Eaters Khârn, and
    # (once adopted) Thousand Sons Magnus. Random_fill's EPIC HERO cap is
    # unchanged. The War Horde detachment picker is untouched — nothing is
    # dropped from the existing template, only added.
    # Guarded per CLAUDE.md rule 13 (fail loud on missing data): if the
    # catalogue key ever stops resolving, raise instead of silently dropping
    # the centerpiece from a would-be-default-on template.
    if os.environ.get("SWEG_ORKS_GHAZGHKULL", "0") == "1" and fac == "Orks":
        if "orks_ghazghkull_thraka" not in UNIT_CATALOG:
            raise KeyError(
                "archetypes._effective_template: SWEG_ORKS_GHAZGHKULL expects "
                "'orks_ghazghkull_thraka' to resolve in UNIT_CATALOG but it "
                "is missing — check for a regression that dropped the "
                "datasheet from the catalogue or a typo'd key."
            )
        template = dict(template)
        template["orks_ghazghkull_thraka"] = 1

    return template


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

    # List-realism gates now live in `_effective_template` (2026-07-02,
    # fidelity-first phase B) so the SAME effective template reaches BOTH
    # this seed walk and `_random_fill` — the old in-function gates leaked:
    # the fill received the RAW template, so a unit the gate dropped
    # (Angron) re-entered ~27% of builds via the fill's template-count
    # lookup. Applied here for direct callers; idempotent, so the second
    # application via build_archetype_army is harmless.
    template = _effective_template(faction, template)


    # Wave 244 leader-stack gate — read once, consulted by the sort-key
    # tiebreak, the EPIC HERO anchor trigger, and the fraction override
    # below (all three move together as one gated lever). Scoped to
    # non-menu factions (see MENU_FACTIONS): menu builds stay identical to
    # the gate-off walk because the tiebreak de-realized faithful menu
    # entries with no permitted fraction fix. Default ON since the
    # wave-244 adoption; SWEG_SEED_LEADERS=0 is the kill-switch (the
    # fraction dict stays separate from SEED_FRACTION_BY_FACTION for
    # exactly this reason — fold only when the gate is removed).
    _leader_stack_priority = (
        os.environ.get("SWEG_SEED_LEADERS", "1") == "1"
        and (faction or "") not in MENU_FACTIONS
    )

    seed_fraction = SEED_FRACTION_BY_FACTION.get(faction or "", SEED_FRACTION)
    if _leader_stack_priority:
        seed_fraction = SEED_FRACTION_LEADER_STACK.get(
            faction or "", seed_fraction
        )
    seed_budget = points_budget * seed_fraction

    # DAEMONS-FIX-1 — Chaos Daemons mono-god Greater Daemon anchor.
    # The four Chaos Daemons mono-god sub-archetypes (Khorne Murderhost,
    # Tzeentch Manifestation, Nurgle Pestilence, Slaanesh Excess) each
    # name a single Greater Daemon as their centerpiece:
    #   chaos_daemons_library_bloodthirster        (Khorne)
    #   chaos_daemons_library_lord_of_change       (Tzeentch)
    #   chaos_daemons_library_great_unclean_one    (Nurgle)
    #   chaos_daemons_library_keeper_of_secrets    (Slaanesh)
    # These four cost ~305pt each, do not carry the EPIC HERO keyword in
    # BSData v10.6.0, and lose the (-count, -cost) walk below to the
    # multi-copy Bloodletters / Pink Horrors / Plaguebearers / Daemonettes
    # battleline entries (count=3) that exhaust seed_budget first. The
    # DAEMONS-DIAG-10 audit (docs/DAEMONS_DIAG_10_findings.md) measured 80
    # builds: Bloodthirster 1%, Lord of Change 0%, Keeper of Secrets 0%,
    # Great Unclean One 5% — the mono-god army's anchor was almost never
    # actually seeded.
    #
    # Real 10e Chaos Daemons mono-god lists are built around their Greater
    # Daemon (Wahapedia codex restriction: 1 per army for each named
    # Greater Daemon datasheet). Force-include it BEFORE the walking pass,
    # reserving its cost from `running` so the rest of the seed walk
    # accounts for it. Overflow is allowed (mirrors the EPIC HERO anchor's
    # 1.5x rule below) — the Greater Daemon is the archetype's flagship
    # and seeding it is more important than staying under seed_budget.
    _MONO_GOD_GREATER_DAEMONS = (
        "chaos_daemons_library_bloodthirster",
        "chaos_daemons_library_lord_of_change",
        "chaos_daemons_library_great_unclean_one",
        "chaos_daemons_library_keeper_of_secrets",
    )

    scaled: Dict[str, int] = {}
    running = 0.0

    mono_god_anchor = next(
        (k for k in _MONO_GOD_GREATER_DAEMONS if k in template),
        None,
    )
    if mono_god_anchor is not None and mono_god_anchor in UNIT_CATALOG:
        scaled[mono_god_anchor] = 1
        running += _squad_cost(mono_god_anchor)

    # SWEG_DAEMONS_BELAKOR (2026-07-02) — Scintillating Legion multi-
    # Greater-Daemon core force-seed. The DAEMONS-FIX-1 pre-pass just above
    # force-seeds exactly ONE Greater Daemon per template, because each of
    # the four mono-god templates names exactly one — it grabs Lord of
    # Change here (the only Scintillating Legion entry that also appears
    # in `_MONO_GOD_GREATER_DAEMONS`) and stops. The Scintillating Legion
    # sub-archetype is deliberately built around FOUR flagship characters
    # (Be'lakor, Kairos Fateweaver, Lord of Change, Great Unclean One) —
    # that is the point of the archetype (see the template's sourcing
    # comment above), so a single-anchor pre-pass under-fields it: the
    # EPIC HERO anchor guarantee further down only rescues the single most
    # expensive unseeded EPIC HERO (Be'lakor), and Kairos Fateweaver /
    # Great Unclean One are left to compete for space in the regular
    # (-count, -cost) walk below, where their high per-model cost usually
    # loses to the count=2 Pink Horrors entry and they are frequently
    # dropped. Force-seed the full flagship quartet before the regular
    # walk, but ONLY when the template is unmistakably Scintillating
    # Legion — identified by carrying BOTH Be'lakor and Kairos Fateweaver,
    # a combination no other template uses — and only when the gate is
    # explicitly on, so the four existing mono-god templates and the
    # gate-off path are untouched (byte-identical off). `running` is
    # allowed to exceed `seed_budget` here, mirroring the overflow
    # allowance on the mono-god anchor above and the EPIC HERO anchor
    # below — the flagship core is more important than staying under the
    # nominal seed slice.
    if (
        os.environ.get("SWEG_DAEMONS_BELAKOR", "1") != "0"
        and "chaos_daemons_library_be_lakor" in template
        and "chaos_daemons_library_kairos_fateweaver" in template
    ):
        for _sl_key in (
            "chaos_daemons_library_be_lakor",
            "chaos_daemons_library_kairos_fateweaver",
            "chaos_daemons_library_lord_of_change",
            "chaos_daemons_library_great_unclean_one",
        ):
            if (
                _sl_key in template
                and _sl_key in UNIT_CATALOG
                and _sl_key not in scaled
            ):
                scaled[_sl_key] = 1
                running += _squad_cost(_sl_key)

    # Wave 250 (gated SWEG_WE_REALISM) — World Eaters Khârn anchor. The template
    # filter above drops Angron when the gate is on; here we force-seed Khârn the
    # Betrayer (mirroring the mono-god Greater Daemon anchor pre-pass) so the
    # build is Khârn-anchored like the three sourced real lists (Khârn appears in
    # all three; see the SWEG_WE_REALISM comment at the top of this function for
    # the citations). World Eaters is a MENU faction, so the EPIC HERO anchor
    # below only fires when no epic hero is seeded — without this pre-pass,
    # dropping Angron would let an arbitrary character anchor instead of Khârn.
    if (
        os.environ.get("SWEG_WE_REALISM", "1") != "0"
        and (faction or "") == "World Eaters"
        and "world_eaters_kh_rn_the_betrayer" in template
        and "world_eaters_kh_rn_the_betrayer" in UNIT_CATALOG
    ):
        scaled["world_eaters_kh_rn_the_betrayer"] = 1
        running += _squad_cost("world_eaters_kh_rn_the_betrayer")

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
    #
    # Wave 244 — leader-stack priority (gated SWEG_SEED_LEADERS, default
    # ON since the wave-244 adoption; =0 is the kill-switch). Within the
    # SAME template count,
    # CHARACTER entries seed before non-CHARACTER entries. Motivating
    # failure (wave-243 orders diagnostic): the Astra Militarum Combined
    # Arms template documents a three-officer leader stack (Cadian
    # Castellan / Ursula Creed / Lord Solar Leontus — the cited real
    # May-2026 composition), but the (-count, -cost) walk spends the
    # 1100-point seed slice on the tank spine (running 1095), skips
    # Leontus (130) and Creed (85), and the CHARACTER anchor below
    # rescues only the cheapest officer (Castellan, 55) — the built army
    # issues ~2 Orders a round against a template intent of ~8. Real
    # tournament lists fix their character stack FIRST and scale the
    # rest; encoding that as a TIEBREAK (not a pre-pass) keeps multi-copy
    # spine entries (Rubric Marines at count=2) seeding ahead of
    # characters, preserving small-budget anchor behaviour. List-realism
    # fidelity (wave-174/175 precedent), not win-rate tuning.
    def _is_character_key(key: str) -> bool:
        profile = UNIT_CATALOG.get(key)
        if profile is None:
            return False
        return "CHARACTER" in (profile.unit_keywords or ())

    def sort_key(key: str):
        if _leader_stack_priority:
            return (
                -template.get(key, 0),
                0 if _is_character_key(key) else 1,
                -_squad_cost(key),
            )
        return (-template.get(key, 0), -_squad_cost(key))

    for key in sorted(template, key=sort_key):
        if key in scaled:
            # Already seeded by the mono-god anchor pre-pass.
            continue
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

    # Wave 244 (gated SWEG_SEED_LEADERS): the leader-stack tiebreak above
    # exposes a hole in this anchor's trigger. With characters seeding
    # first within the same template count, a CHEAP epic-hero character
    # (Death Guard Typhus, 100pt) now lands in the regular walk, the
    # "no epic hero seeded" condition is satisfied, and the FLAGSHIP
    # (Mortarion, 380pt) is silently dropped — exactly the failure this
    # anchor's comment warns about. Under the gate, fire the anchor
    # whenever the flagship (most expensive template EPIC HERO) itself is
    # unseeded, not merely when zero epic heroes are seeded. Un-gated
    # behaviour is unchanged (the A/B OFF arm must stay byte-identical).
    epic_hero_keys = [k for k in template if _is_epic_hero_key(k)]
    if _leader_stack_priority:
        _eh_anchor_needed = bool(epic_hero_keys) and (
            max(epic_hero_keys, key=_squad_cost) not in scaled
        )
    else:
        _eh_anchor_needed = bool(epic_hero_keys) and not any(
            k in scaled for k in epic_hero_keys
        )
    if _eh_anchor_needed:
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
    # template entry with the CHARACTER keyword qualifies (predicate
    # `_is_character_key` shared with the wave-244 leader-stack tiebreak).
    any_char_seeded = any(_is_character_key(k) for k in scaled)
    if not any_char_seeded:
        char_keys = [k for k in template if _is_character_key(k)]
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

    # SWEG_FILL_TEMPLATE_POOL (fidelity-first phase B mechanism lever,
    # default-off while screening) — template-first random fill. The
    # 2026-07-01 archetype-fidelity audit (docs/ARCHETYPE_FIDELITY_AUDIT.md)
    # measured that ~55-70% of every build's points come from this fill
    # drawing UNIFORMLY across the whole faction catalogue, which is how
    # units appearing in essentially no sourced tournament list (Chaos
    # Predators, Land Raiders, Heldrakes) reach production armies, and how
    # every "mono-god" Chaos Daemons army ends up ~35% off-god. When the
    # gate is ON the fill draws from the CURATED TEMPLATE pool first (the
    # units real lists actually field, at the template's intended shape)
    # and falls back to the whole-catalogue pool only when no template unit
    # is affordable — so the archetype governs the whole army, not just the
    # seed slice. All caps (BATTLELINE, wrecker, EPIC HERO, per-name spend)
    # apply unchanged on both paths. OFF path byte-identical (the template
    # preference is never consulted). Cited `simulator.fill_template_pool`.
    # ADOPTED default-on 2026-07-02: full-frame N=40 vs sc36a read an
    # aggregate WASH (5.01 -> 4.96) over a huge faithful redistribution —
    # good templates snapped toward real (Chaos Daemons -13.5 onto its
    # target as the off-god contamination cured), bad templates were
    # AMPLIFIED (Death Guard +14.2 = the phantom-heavy template expressed
    # fully). Template quality now governs the army; the phase-B template
    # corrections land on this frame. `=0` kill-switch.
    _fill_template_pool = (
        os.environ.get("SWEG_FILL_TEMPLATE_POOL", "1") != "0"
        and bool(template_count_by_name)
    )

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
        # Template-first pick (see the SWEG_FILL_TEMPLATE_POOL comment
        # above): when any affordable candidate is a curated-template unit,
        # restrict the draw to those; the whole-catalogue candidates serve
        # only as the fallback once the template pool is exhausted or
        # unaffordable. Exactly one rng.choice per pick on both paths.
        if _fill_template_pool:
            _tpl_affordable = [
                a for a in affordable
                if a[0].name in template_count_by_name
            ]
            if _tpl_affordable:
                affordable = _tpl_affordable
        chosen, size, cost = rng.choice(affordable)
        # RANDOM-FILL RE-BASE (gated SWEG_FILL_SQUADS). The template seed path
        # already fields proper squads via add_squad; this aligns the random
        # topup, which historically added `size` independent 1-model Units (the
        # one-Unit-per-model representation amplification: codex "once per unit
        # per phase" economies, squad-activation, coherency, leader-attach,
        # OC-blobs and Blast all mis-fire on size separate units). add_squad
        # builds the SAME `size` model-Units but sharing one squad_id, so the
        # army's total Units / models / points are identical — only the squad
        # GROUPING changes (representation-only). Default 0 reverts to the
        # byte-identical per-model loop. See [[project-one-unit-per-model-amplification]].
        if os.environ.get("SWEG_FILL_SQUADS", "1") != "0":
            army.add_squad(chosen, size)
        else:
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
    # CRITICAL GATING CONSTRAINT (SWEG_DAEMONS_BELAKOR, 2026-07-02): the
    # "Scintillating Legion" entry in ARCHETYPES["Chaos Daemons"] is always
    # present in the module-level dict (a dict literal can't conditionally
    # omit a key at import time without an import-order-dependent env
    # read, which is fragile — see the entry's own comment). Filter it out
    # of `available` HERE, at build time, whenever the gate is not
    # explicitly on, so `rng.choice(list(available.keys()))` below sees the
    # exact same 4-entry list, in the same order, that it saw before this
    # sub-archetype was added — the OFF path is byte-identical to the
    # pre-change code. When the gate IS on, "Scintillating Legion" is one
    # of 5 uniformly-chosen entries, same as any other faction archetype.
    if (
        faction == "Chaos Daemons"
        and "Scintillating Legion" in available
        and os.environ.get("SWEG_DAEMONS_BELAKOR", "1") == "0"
    ):
        available = {
            k: v for k, v in available.items() if k != "Scintillating Legion"
        }
    if archetype_name is None:
        archetype_name = rng.choice(list(available.keys()))
    # Apply the env-gated list-realism corrections ONCE so the seed walk
    # and `_random_fill` see the SAME effective template (the fix for the
    # wave-250 gate leak; `_instantiate_template` re-applies internally
    # for direct callers — idempotent, harmless).
    template = _effective_template(faction, available[archetype_name])

    counts = _instantiate_template(template, points_budget, rng, faction=faction)

    army = Army(name, in_cover=in_cover)
    # OVER-POLE / list-realism PROBE (wave 190, gated SWEG_SEEDMAX, default-OFF
    # => byte-identical). The curated SEED fields each anchor squad at
    # min_models (MSU), while `_random_fill` already fields its picks at
    # max_models. That systematically UNDER-fields the competitive anti-tank /
    # objective anchors the templates were written around — Lokhust Heavy
    # Destroyers seed at 1-of-3, Eradicators at 3-of-6, and the 10-model
    # BATTLELINE bricks (Warriors / Boyz / Termagants) that real lists run at
    # 20 seed at 10. For the over-pole this is asymmetric: an Imperial Knight
    # is a single-model unit with NO squad-size shortfall to correct, while its
    # multi-model anti-tank opponents are fielded at a fraction of their real
    # strength, so the opponents' anti-Knight firepower is structurally too
    # weak (the watchdog's "anti-tank STRENGTH" half of the compound over-pole).
    # When the gate is set, seed squads field at max_models to match the
    # random-fill convention; total army points stay near budget because
    # `_random_fill` self-corrects on the smaller `remaining`. This is an
    # upper-bound DIRECTIONAL probe (the faithful per-unit competitive sizes lie
    # between min and max for some units), not a default flip.
    #   SWEG_SEEDMAX=1   -> max ALL seed squads (confounded: bloats chaff and
    #                       starves firepower via budget crowding; wave 190 saw
    #                       a hard regression that AMPLIFIED the residual).
    #   SWEG_SEEDMAX=at  -> max only the anti-tank-CLASS seed squads, leaving
    #                       chaff at min_models. De-confounds the "opponent
    #                       anti-tank STRENGTH" sub-lever from the chaff-crowding
    #                       artifact: does stronger opponent anti-tank alone drop
    #                       the Knight over-pole?
    _seed_max_mode = (os.environ.get("SWEG_SEEDMAX") or "").lower()
    for key, count in counts.items():
        profile: UnitProfile = UNIT_CATALOG[key]
        squad_size = max(1, profile.min_models)
        if _seed_max_mode == "1" or (
            _seed_max_mode == "at" and _is_antitank_profile(profile)
        ):
            squad_size = max(squad_size, profile.max_models or squad_size)
        # SQUAD-ACTIVATION (Lever 1, P1): each instantiated squad gets its own
        # squad_id so P3 activates it once. Same Units / order as the previous
        # per-model add_unit loop — behaviour-neutral until P3 reads squad_id.
        for _ in range(count):
            army.add_squad(profile, squad_size)

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
