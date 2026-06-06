# TYRANIDS-SYNAPSE-AUDIT (Stage 1, iter 44) — findings

Diagnostic of the Tyranid faction-mechanic modelling magnitude after
TYRANIDS-WARRIORS-BASKET established that adding SYNAPSE bodies pushed
sim win-rate further from real (sim 70 -> 87 with +6 Synapse Warriors)
and was reverted. The composition lever was rejected; faction-mechanic
over-modelling is the remaining hypothesis. Outlier band: Tyranids
gated +18.78 pt (sim 70.0%, real 47.4%).

Branch / top commit: `claude/sim-calibration-6` / `b51bb98`.

## Lever 1 — Synapse Imperative modelled as auto-pass vs codex 3D6

**FIX-FIRST CANDIDATE.** This is the largest-magnitude over-buff in the
Tyranid faction module, and the most defensible single change.

`code/simulator.py:4694-4703` short-circuits the Battle-shock roll for
any Tyranids unit within 6" of a friendly SYNAPSE model via a `continue`
— the unit never rolls and never lands in `_battleshocked_this_round`.

`data/rule_citations.d/tyranids.json` cites "the unit cannot be
Battle-shocked" as the codex text, which is the pre-September 2024
wording. The current Codex Tyranids (Sept 2024) Synapse army rule on
Wahapedia (https://wahapedia.ru/wh40k10ed/factions/tyranids/) reads:

> Each time that unit takes a Battle-shock test, take that test on 3D6
> instead of 2D6.

— and additionally: melee attacks made by models in the unit have +1 to
their Strength characteristic. SwegHammer models NEITHER of these — it
models a stronger, older auto-pass instead.

Per-test magnitude vs the codex (Tyranid BATTLELINE Ld 8):
- Codex 3D6: P(fail) = P(3D6 < 8) = 35/216 ≈ 16% fail, ≈ 84% pass.
- SwegHammer auto-pass: 0% fail, 100% pass.
- Over-buff: +16 pt pass-rate per below-half test.

The Subterranean Assault archetype (`code/archetypes.py:254-393`) runs
Hive Tyrant + Zoanthropes (2 SYNAPSE anchors) shielding 4 BATTLELINE
chaff squads plus 2 MONSTER bricks. Across 5 rounds with ~3-4 below-half
tests/side, this compounds into chaff OC contributions retained that
would have been zeroed by the codex 3D6 path — directly inflating
primary VP via `_score_objectives` (`code/simulator.py:642-664`:
battleshocked units contribute OC 0). Architecture amplifier: each
squad member is a separate `Unit`, so a 10-model brick takes 10
auto-passes instead of one. The unmodelled +1 Strength melee on units
within Synapse Range partly offsets a fix.

Source: https://wahapedia.ru/wh40k10ed/factions/tyranids/ (army rule
"Synapse", Codex 10e September 2024).

## Lever 2 — Hive Tyrant Onslaught aura already fab-stripped (confirm)

**NEEDS-MORE-INVESTIGATION; CONFIRMED CLEAN.** TYRANIDS-DIAG-7 (commit
`d3c2588`) dropped the `reroll_wound_ones=True` proxy from the Hive
Tyrant `LeaderAbility`. Current entry at `code/leaders.py:437`:

```
("Hive Tyrant", LeaderAbility(name="Synaptic Imperative", aura_range=6.0))
```

— no offensive flags, an empty aura. The real Onslaught codex rule
(https://wahapedia.ru/wh40k10ed/factions/tyranids/Hive-Tyrant) grants
[ASSAULT] + [LETHAL HITS] on RANGED weapons of friendly TYRANIDS
within 6". The `LeaderAbility` schema has no ranged-only Lethal Hits
slot today, so the buff is structurally absent rather than fabricated
in either direction. Confirmed not an over-buff lever; documented for
future schema expansion. (Adding it later would slightly LIFT Tyranids
sim wr, not lower it.)

## Lever 3 — Shadow in the Warp -1 aura (already tightened)

**NEEDS-MORE-INVESTIGATION; LOW PRIORITY.** TYRANIDS-DIAG-5 already
collapsed an always-on 12" -1 Ld aura to a codex-correct once-per-battle
6" trigger declared at Round 2 (`code/simulator.py:4889-4932` for the
declaration, `4634-4644` and `4709-4713` for the consumer). Citation
`data/rule_citations.d/tyranids.json:13-21` matches the Wahapedia text:

> If your Army Faction is TYRANIDS, once per battle, in either player's
> Command phase, ... each enemy unit on the battlefield must take a
> Battle-shock test. Each time an enemy unit takes such a Battle-shock
> test, if it is within 6" of one or more SYNAPSE units from your army,
> subtract 1 from that test.

SwegHammer models the -1 portion but NOT the "force a test on every
enemy unit on the battlefield" portion (acknowledged in the citation as
an approximation). The unmodelled half is dominantly under-buffing
(missing forced tests on at-strength enemy units that mostly pass
anyway), so net direction is conservative. Magnitude vs Lever 1 is
small — once per battle, R2 only, conditional on 6" proximity, and the
penalty only changes 2D6 < target outcomes near the Ld boundary.

Source: https://wahapedia.ru/wh40k10ed/factions/tyranids/

## Lever 4 — Big-bug datasheet ability magnitudes

**NEEDS-MORE-INVESTIGATION; LIKELY NEUTRAL OR UNDER-BUFF.**

- **Old One Eye** (`data/overrides.json:1579-1582`) overrides `fnp: 7`
  (no FNP) citing SC5-10. Wahapedia
  (https://wahapedia.ru/wh40k10ed/factions/tyranids/Old-One-Eye) lists
  "Feel No Pain 5+" as a core ability — override may be UNDER-buffing.
  Not in the Subterranean Assault archetype, so does not drive the gap.
- **Tervigon** D3+3 Termagant respawn is NOT modelled (no in-battle
  model-revival hook), acknowledged at `code/archetypes.py:274-277`.
  Net direction: UNDER-buff.
- **Norn Emissary** Singular Purpose (re-roll hits/wounds vs nominated
  enemy OR FNP 5+ / OC 15 on an objective) NOT modelled. UNDER-buff.

None are fix-first candidates for closing the +18.78 gap.

## Recommendation

Fix-first: **Lever 1**. Replace `code/simulator.py:4694-4703` Synapse
Imperative auto-pass `continue` with a switch to a 3D6 roll (or
equivalent: P(3D6 < target) failure path). Optionally pair with +1
Strength melee on attacks from units within Synapse Range (under-buff
today) to land the full codex Synapse text. Update
`data/rule_citations.d/tyranids.json` quoted_text + effect to the
September 2024 codex wording. Leave Levers 2-4 for a separate pass.

Stage classification: Stage 1 (simulator rule fidelity vs tournament).
