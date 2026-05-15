# Faction G8 — T'au Empire archetype seeding diagnostic

Task #174. Calibration vs the May 2026 real meta puts T'au Empire at **-4.9 pt**
under-perform. The leading hypothesis was that the curated `Kauyon` archetype
in `code/archetypes.py` was seeding a Fire-Warrior / Pathfinder-heavy list
rather than the real meta's battlesuit-heavy composition (Crisis suits,
Riptide, Broadsides, occasional Stormsurge).

## Method

`scripts/tau_diag.py` — 30 archetype instantiations at 2000 pts with deterministic
seeds, then count battlesuit appearances by category (substring match on profile
name to be robust to Crisis Fireknife / Sunforge / Starscythe variants). No
battles simulated — pure list-composition audit.

Expected from real meta:

- Riptide present in >= 20/30 trials
- Crisis present in >= 25/30 trials
- Stormsurge present in some trials (variable)

## Findings — BEFORE template fix (original Kauyon template)

```
Battlesuit         Present   Mean models   Max
--------------------------------------------------
Riptide             0/30           0.00     0
Crisis             30/30           2.03     5
Stormsurge          5/30           0.17     1
Broadside           4/30           0.33     4
Ghostkeel           6/30           0.20     1
Stealth            30/30           4.53     8
Commander          15/30           0.77     3
```

Crisis appearances (30/30) were driven almost entirely by `_random_fill`, not the
curated template — the original template seeded only one Crisis squad. The
template was seeding Strike + Breacher + 2x Pathfinder + 1 Crisis + 1 Stealth
+ 1 Broadside + 1 Commander + 1 Devilfish, which spends the 30%-of-budget seed
slice on infantry first.

## Findings — AFTER template fix

```
Battlesuit         Present   Mean models   Max
--------------------------------------------------
Riptide             0/30           0.00     0
Crisis             30/30           2.83     6
Stormsurge          5/30           0.17     1
Broadside          30/30           1.27     3
Ghostkeel          30/30           1.30     3
Stealth            30/30           4.13     8
Commander          12/30           0.57     3
```

The new template bumps Crisis Fireknife to `count=3` and Sunforge to `count=2`
so the post-G5 anchor-first sort puts battlesuits before infantry, and adds
Ghostkeel + Stormsurge as single-copy single-platform anchors. Battlesuit
presence is now realistic across Crisis / Broadside / Ghostkeel.

## Riptide cost anomaly

`t_au_empire_riptide_battlesuit` has `points_cost = 1180.58` in the catalogue —
the `sweg_balance_mc` formula output, vs Wahapedia's published 180 pts. At
1180 pts a Riptide cannot fit the 30%-of-budget seed slice at any realistic
points budget AND exceeds `_random_fill`'s per-type cap (50% of remaining), so
Riptide will never appear in any built T'au army until the cost anomaly is
fixed. Task #174 explicitly forbids bumping the cost — leaving as a follow-up
for a costing task.

## Files

- `code/archetypes.py` — template adjusted, battlesuit ratios raised
- `scripts/tau_diag.py` — diagnostic script (new)
- `docs/FACTION_G8_TAU.md` — this file
