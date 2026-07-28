# The Tyranid archetype does not field the list it cites

**Status:** **screened, proven, ADOPTED default-ON** as
`SWEG_TYRANID_LIST_SOURCED` (`=0` is the kill-switch). Stage 1, input fidelity.
Tyranids +9.49 A-frame, overall gated mean absolute error 3.21 → 2.85. See the
VERDICT section at the end, which also corrects a vacuous byte-identity claim
made in "The change" below — the canonical digest cannot see Tyranid changes.

## The finding

The Tyranid `Subterranean Assault` template in `code/archetypes.py` cites the GW
Open Maastricht 2026 winning list as its source. It does not field that list.

The army actually reported by both outlets the template names — SpikeyBits
"Warhammer Open Maastricht Army Lists" and Bell of Lost Souls "The Unbeatable
List — GW Open Maastricht 2026" — for Ron Eliyahoo's winning Subterranean
Assault army is:

| Unit | Detail |
|---|---|
| Trygon | carrying the Trygon Prime enhancement — the detachment's engine |
| Tyranid Prime with Lash Whip | three of them, 65 points each |
| Old One Eye | 150 points |
| Maleceptor | 170 points |
| Hormagaunts | two ten-model squads |
| Raveners | one Prime unit plus two five-model units |
| Tyrannofex | with Rupture cannon |
| Zoanthropes | with a Neurothrope |
| Carnifex | |
| Lictor, Neurolictor | |
| Biovore | two of them |

What the simulator fielded instead, measured over six seeds at 2000 points with
`scripts/_archetype_fidelity_probe.py`:

| Unit | Squads per army | Models per army | In the sourced list? |
|---|---|---|---|
| Termagants | 2.83 | 46.7 | **no** |
| Hormagaunts | 2.50 | 40.0 | yes, but as two ten-model squads |
| Ripper Swarms | 3.67 | 9.0 | **no** — and above its own fill cap |
| Zoanthropes | 1.67 | 10.0 | yes |
| Tyrant Guard | 1.00 | 3.0 | not declared in the template either |
| Tyrannofex | 2.00 | 2.0 | yes, one |
| Hive Tyrant | 1.33 | 1.3 | **no** |
| Exocrine | 0.83 | 0.8 | **no** |

The two lists share three entries. The simulator omits the Trygon, all three
Primes, Old One Eye, the Maleceptor, every Ravener, the Carnifex and both
Lictors, and substitutes roughly 47 Termagants and 9 Ripper Swarms.

## Why this explains the under-pole

Tyranids are the number-one residual, 31.0 against a real 47.0. The measured
symptoms are each a direct consequence of the substitution. Card figures from
`scripts/_am_secondary_cards.py` with `SC_FACTION=Tyranids`; the whole Tyranid
secondary deficit is kill cards, while position cards favour them.

- **`bring_it_down` 0.38 against opponents' 1.81.** With no Carnifex, no Old One
  Eye and no Maleceptor, the list's entire anti-armour capability is two
  Tyrannofexes. Measured against a Toughness-10 Save-3+ target, only three of
  seven entries in the fielded list clear half a wound per activation.
- **`assassination` 0.36 against 1.19.** No Lictor, no Neurolictor and no Ravener
  package, so nothing in the list is built to reach an enemy CHARACTER.
- **`cull_the_horde` 0.12 against 2.26.** This is the sharpest one. The sourced
  list's chaff is two **ten**-model Hormagaunt squads, which can never reach the
  thirteen-model Starting Strength that concedes Cull the Horde. The substituted
  Termagant squads average about sixteen models and concede it every game. The
  simulator's Tyranids were paying a tax the real army does not pay.

It also explains a result that was otherwise puzzling. `SWEG_MELEE_CHARGE_HOLD`
doubled Tyranid charge eligibility (25.1 to 52.5 percent), more than doubled
charge connection (11 to 25 percent) and tripled Hormagaunt melee damage (1.7 to
5.1 a game), and moved the Tyranid win rate by +0.34, not decisively. Getting a
gaunt swarm into combat more reliably does not fix an army whose problem is that
it is the wrong army.

## Why the Trygon was dropped

The live template's comment explains it: "Trygon dropped to 0: post-CHARACTER-
keyword-strip (see `data/overrides.json`) it no longer tags as a leader-host and
is redundant with Carnifex/Tyrannofex as a deep-strike wrecker."

That is an internal modelling convenience, not a real-meta observation. The
Trygon is the unit the detachment is named for and the mechanism the sourced
list is built around — it is what delivers the Primes and the Raveners into the
midfield. Dropping it removed the list's engine and left the chaff behind it.

## The change

`SWEG_TYRANID_LIST_SOURCED=1` replaces `ARCHETYPES["Tyranids"]` with the sourced
template. Off, or unset, the dictionary is untouched and the seeded event-log
digest is unchanged at `4aab205fbb99635db7c607db`.

Built armies under the gate, six seeds at 2000 points: Hormagaunts 20 models,
Raveners exactly two five-model units, Hyperadapted Raveners 9.2, Zoanthropes
8.0, Carnifexes 2.3, Tyranid Primes 2.2, Lictor 1.3, Neurolictor 1.2, Old One
Eye 1.0, Tyrannofex 0.8, Trygon 0.8, Maleceptor 0.5. Total model count falls
from about 113 to about 57.

Two knowing departures, both recorded rather than hidden:

1. **Biovores have no catalogue entry**, so the sourced list's two are omitted
   rather than substituted.
2. The builder's random fill does not reproduce the list exactly — the Maleceptor
   appears in three seeds of six and the Trygon in five of six. The template
   declares counts; the builder fills to budget within caps. This is the same
   approximation every other faction's archetype runs under, not a new one.

## What this does not claim

*Written before the screen, and kept as written.* At the time this said: the
claim is only that the input was wrong, which must be fixed before any mechanics
conclusion drawn from Tyranid cells can be trusted; the screen has not been run,
so the size of the effect is unknown and the corrected list may move the number
very little.

**The screen has since run and settled it — see the VERDICT section.** The
correction was worth +9.49 and closed roughly 85 percent of the faction's error,
so the cautious reading above turned out to understate it. The caution was still
correct to record: the result was not knowable before measuring.

It is also a warning about the other twenty-one templates. This defect was found
by reading one template against its own cited sources. Nothing in the repository
checks that a template matches the list it cites, and the comment blocks in
`code/archetypes.py` record win-rate-targeted tuning iterations ("iter16 70.0
percent sim", "iter17 53.1 percent sim") alongside the source citations — which
is Stage-1 metric fitting at the input layer. Every archetype should be audited
the same way.

## Instruments

- `scripts/_archetype_fidelity_probe.py` — declared template against built armies,
  counting squads rather than model instances, flagging declared-but-never-built,
  built-but-not-declared and fill counts above cap.
- `scripts/_army_composition_dump.py` — the fielded list with each entry's damage
  per round into a Toughness-10 Save-3+ target.
- `scripts/_tyranid_price_audit.py` — catalogue price and minimum squad size per
  datasheet. Confirms pricing is sound: Norn Emissary 260, Swarmlord 220,
  Tyrannofex 200, Hive Tyrant 195, Exocrine 140, Carnifexes 90 for one model.
  The template comment's claim that a Carnifex is a "461 point minimum squad,
  too expensive to seed" is a stale Stage-2 calibrated price and is false in the
  vanilla mode the archetype actually runs in.
- `scripts/_am_secondary_cards.py`, `scripts/_am_vp_probe.py` — both now take a
  faction parameter (`SC_FACTION`, `VP_FACTION`) instead of hardcoding Astra
  Militarum, and their output labels follow it.

## VERDICT — screened, proven, adopted (2026-07-26)

Scoped screen, `data/_scr_nidlist_log.json`, N=80 paired against `sc68a`:

| frame | before | after | real | error |
|---|---|---|---|---|
| A-frame (paired_delta --scoped) | 35.9 | **45.4** (+9.49, decisive) | 47.4 | 11.5 → **2.0** |
| both-sides (`scripts/_residual_table.py`) | 31.0 | **44.6** | 47.0 | 15.9 → **2.4** |

Overall gated mean absolute error **3.21 → 2.85**. Eleven other factions drift
down between 0.3 and 1.4 points; that is the correct collateral, because their
Tyranid matchup became genuinely harder once Tyranids fielded the army the real
47 percent was earned with.

Nothing else attempted in this campaign moved Tyranids at all. `SWEG_MELEE_CHARGE_HOLD`
doubled charge eligibility and connection and tripled Hormagaunt melee damage for
+0.34. The list was the whole problem.

**Adopted.** `SWEG_TYRANID_LIST_SOURCED` is default-ON; `=0` is the kill-switch.
Re-anchor `sc69a` running.

## The verification claim in the section above was vacuous — corrected

This document previously said the gate was "byte-identical when off, digest
`4aab205fbb99635db7c607db`". That verified nothing.

`scripts/_detcheck.py` runs three pairings — Death Guard against Astra Militarum,
Aeldari against Adeptus Astartes, Orks against T'au Empire. Six factions of
twenty-two. **Tyranids never appear in it.** The canonical digest is therefore
structurally blind to a Tyranid-only change and reads identical whether this gate
is on or off. A measurement covering six factions was quoted to certify all
twenty-two — the same error class as the other retractions in this session.

`scripts/_detcheck_wide.py` now provides a second digest over all twenty-two
factions (ring pairing, each faction once per side, forty-four battles). The
canonical narrow digest is deliberately left untouched, because it is referenced
across the documentation and every prior wave's verification.

| configuration | wide digest |
|---|---|
| sourced list ON (new production default) | `f243047dbb6a7f45d64aae66` |
| `SWEG_TYRANID_LIST_SOURCED=0` (kill-switch) | `91a2c9d431b0f8e85d1712e1` |

They differ, which is the coverage proof the narrow digest could not give.

**General consequence:** any gate whose effect is confined to the sixteen factions
outside those three pairings has never been byte-identity-verified by anything.
Faction-scoped gates should be verified against the wide digest from now on.
