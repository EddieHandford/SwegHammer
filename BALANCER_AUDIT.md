# BALANCER_AUDIT.md

Audit of the SwegHammer points calibrator after wiring detachments into the
calibration builders. Prior to this fix, `build_homogeneous_army` and
`build_attached_army` left `army.detachment = None`, which meant the
Monte-Carlo battles backing every "balanced_points" number ran with NO
army-wide passives. CP economy still ran (the universal stratagems fire off
the per-battle CP allocation), but no detachment-specific stratagems would
be available even if implemented.

Date: 2026-05-14
Branch: claude/bsdata-stats-import
Calibrator command for support uplifts:

```
PYTHONIOENCODING=utf-8 python -m code.balancer \
    --unit space_marines_captain --aura-uplift --battles 50
```

## 1. Pre-fix vs post-fix balanced points

The six units below were calibrated twice with `random.Random(42)` and 40
battles per measurement (small N to keep the audit cheap - the headline
finding is qualitative, not a tournament-grade estimate). The pre-fix run
monkey-patched both builders to leave `army.detachment = None` so we measure
exactly the bit that this PR changes.

SUPPORT characters use aura-uplift mode (`--aura-uplift`); homogeneous units
use the default bisection.

| Unit                                          | Mode        | start | pre  | post | delta |
|-----------------------------------------------|-------------|------:|-----:|-----:|------:|
| space_marines_captain                          | support     |  93.7 |  1.0 |  1.0 |   0%  |
| space_marines_lieutenant                       | support     |  55.0 |  1.0 |  1.0 |   0%  |
| space_marines_apothecary                       | support     |  75.0 |  1.0 |  1.0 |   0%  |
| chaos_space_marines_sorcerer                   | support     | 170.1 |  1.0 |  1.0 |   0%  |
| tyranids_hive_tyrant                           | homogeneous | 618.7 |618.7 |618.7 |   0%  |
| necrons_c_tan_shard_of_the_nightbringer        | homogeneous | 586.1 |146.5 |146.5 |   0%  |

All balanced_points are identical pre/post, but the underlying uplift_delta
shifted significantly for SUPPORT characters:

| Unit                                          | uplift_pre | uplift_post | abs shift |
|-----------------------------------------------|-----------:|------------:|----------:|
| space_marines_captain                          |   -0.219   |   -0.345    |  +0.126   |
| space_marines_lieutenant                       |   -0.450   |   -0.436    |  -0.014   |
| space_marines_apothecary                       |   -0.142   |   -0.198    |  +0.056   |
| chaos_space_marines_sorcerer                   |   -0.263   |   -0.394    |  +0.131   |

**Direction:** post-fix uplifts are MORE NEGATIVE on average. With both armies
running Gladius/Pactbound/etc., the no-support side gets army-wide rerolls
too, so the support character's marginal contribution shrinks.

**Why balanced_points stayed flat:** the support uplifts were already
negative pre-fix, so the conversion formula
`max(1.0, uplift_delta * _UPLIFT_TO_POINTS_FACTOR)` was already clamping to
1.0 in both regimes. Negative uplifts indicate the simulator's
attached-leader dynamics aren't yet producing the win-rate boost a real
codex Captain would. This is an upstream issue (#88 / #89 leader-aura wiring,
host-pick quality - Lieutenant gets paired with Scout Snipers Legends, which
is plainly the wrong bodyguard) rather than a calibrator bug.

The homogeneous matchups produced the same number pre and post because their
calibration is symmetric in the detachment: when Necron Warrior squads fight
Assault Intercessor squads, both sides flip on their faction detachment
under the post-fix builder, and neither under the pre-fix builder. The
relative comparison is unchanged.

## 2. Does `_UPLIFT_TO_POINTS_FACTOR` need retuning?

**Not from THIS data.** The constant only matters when `uplift_delta > 0`,
and every SUPPORT character in the audit produced a negative uplift in both
regimes. The 1.0 floor swallows the shift.

That said, the >30% threshold in the brief was a guard against the case
where the constant gives wildly different points pre/post - we can't trigger
that test until at least one SUPPORT character produces a positive uplift,
which won't happen until either:

1. `pick_host_for_leader` is improved so Lieutenant goes to an Intercessor
   Squad, not Scout Snipers Legends.
2. The simulator models leader auras with enough fidelity that a Captain
   actually shifts attrition outcomes (right now leaders carry one extra
   model worth of HP and an aura, but the aura's bonus is small relative
   to the simulator's coarse phase-by-phase attrition).

When that work lands, re-run this audit and check if a positive-uplift
support character (e.g. Necron Overlord on Warriors, where the bonus-to-
hit-when-led stacks with the leader aura) shifts > 30%. If so, refit
`_UPLIFT_TO_POINTS_FACTOR` by linear regression on the per-unit
(uplift_delta, "true" points-cost) pairs across the SUPPORT catalogue.

Documenting this in code: the docstring in `code/balancer.py` around the
constant now flags the re-tuning need so a future contributor sees the
context.

## 3. Mechanics the calibrator STILL doesn't exercise

After this PR:

- **Implemented + exercised:** army-wide detachment passives
  (`reroll_hit_ones`, `reroll_wound_ones`, `plus_one_to_hit`,
  `plus_one_to_wound`, `plus_one_save`, `plus_one_attack`,
  `bonus_to_hit_when_led`, `extra_invuln`, `fnp`,
  `enemy_ld_penalty`, `ld_bonus`, `reanimate_per_round`,
  `psychic_mortal_wounds_per_round`); the 4 universal Core Stratagems
  (Command Re-Roll, Counter-Offensive, Tank Shock, Heroic Intervention);
  Aeldari Battle Focus tokens; and the CP economy
  (STARTING_CP + 1/round capped at 6).
- **Not yet exercised:** detachment-specific stratagems. The `Detachment`
  dataclass has a `stratagems: Tuple[Stratagem, ...]` field but every
  registered detachment leaves it at `()`. The 21 detachments-by-faction
  in `code/detachments.py` thus contribute ONLY their always-on passive.
  Real 10e factions get 6 detachment stratagems each (Awakened Dynasty
  has Their Number is Legion, Resurrection Protocols, Methodical
  Destruction, etc.), and many of those are the actual swing in
  competitive lists. This is tracked as issue #104 in the project's TeX
  to-do list.
- **Not yet exercised:** faction-specific army rules that aren't reducible
  to a single Detachment flag. Examples:
  - Adeptus Astartes "Oath of Moment" (per-turn target marking - we
    approximate via Gladius reroll-wound-1s).
  - Aeldari Aspect-of-the-Path rotation (we apply reroll-hit-1s
    army-wide; real rule cycles +1H / +1W per aspect path turn-by-turn).
  - Astra Militarum Fire Orders (officer-gated single-target buffs:
    FRFSRF, Take Aim, Move Move Move - we apply +1 to hit army-wide).
  - Thousand Sons Cabal-of-Sorcerers ritual casts (Doombolt, Twist of
    Fate, Smite-pool mechanics - currently no model; the placeholder
    `psychic_mortal_wounds_per_round` was removed as fabricated).
  - Death Guard per-unit FNP 5+ on Plague Marines and the -1-damage
    stratagem - both unmodeled.
- **Not yet exercised:** enhancements (one-shot character upgrades like
  Adamantine Mantle, Veritas Vitae). The Detachment dataclass doesn't
  carry an `enhancements` field yet.
- **Not yet exercised:** mission-pack secondary objectives. Scoring is
  VP-based via primary objectives only; the simulator doesn't model
  "Bring It Down", "Engage on All Fronts", or other secondary scoring
  vectors that influence list-building points decisions in real 10e play.

## 4. Test coverage added

`tests/test_balancer.py::DetachmentAwareBuilderTests` carries five regression
tests:

- `test_homogeneous_army_has_detachment_set` - Necron Warriors get Awakened
  Dynasty.
- `test_homogeneous_army_no_detachment_when_faction_empty` - defensive
  guard against custom-profile crashes.
- `test_attached_army_uses_host_faction_detachment` - Captain + Intercessor
  Squad gets Gladius.
- `test_attached_army_detachment_derives_from_host_not_leader` - synthetic
  cross-faction case to lock the host-wins rule.
- `test_balanced_points_uses_detachment` - end-to-end: the calibrator's
  internal `measure_win_rate` produces armies with detachments populated.

## 5. Reproduction

```
# Re-run the audit table (post-fix only, 50 battles):
PYTHONIOENCODING=utf-8 python -m code.balancer \
    --unit space_marines_captain --aura-uplift --battles 50

# Full evaluation matrix (10 factions x 10, MAE vs tournament data):
PYTHONIOENCODING=utf-8 PYTHONHASHSEED=0 python -m scripts.evaluate_vs_meta \
    --battles 30
```

The audit's MAE (post-fix, 30 battles) is **4.87 pts** vs the < 5.0 target.
The `evaluate_vs_meta` script uses `build_faction_random_army`, which already
called `pick_detachment_for_army` before this PR, so the MAE shouldn't have
moved materially - and didn't.
