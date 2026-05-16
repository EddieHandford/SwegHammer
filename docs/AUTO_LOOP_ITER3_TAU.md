# Iter 3 — T'au Empire deep diagnostic

T'au calibration gap: **-3.9pt** (sim 50.6% vs real 54.5%).

Method: `scripts/iter3_tau_deep_diag.py` — N=30 vanilla 10e battles per
matchup vs DG / Marines / Necrons at 1000pt, capturing five hypotheses
(H_MARK, H_MK_ADV, H_STRAT, H_DMG, H_SURV).

## Results

T'au-side WR by matchup:

| vs Death Guard | vs Marines | vs Necrons | aggregate |
|---:|---:|---:|---:|
| 50.0% | 46.7% | 70.0% | 55.6% |

Gap is **matchup-asymmetric**: Marines (-3pt) and DG (flat) drag the
mean down; Necrons inflates it.

### H_MK_ADV — Mont'ka [ASSAULT] window IS being used

Advance-then-shoot count per battle, aggregated:

| R1 | R2 | R3 | R4 | R5 |
|---:|---:|---:|---:|---:|
| 1.99 | 5.42 | 4.59 | 0.39 | 0.18 |

R1-3 mean 4.0 / R4-5 mean 0.29 → **14x cliff**. The Mont'ka detachment
rule (`army_wide_assault_rounds_1_3` in `MONTKA`, simulator `_do_shoot`
gate) IS firing and producing real Advance+shoot behaviour. Not broken.

### H_STRAT — six Mont'ka stratagems fire on cadence

Aggregate per-battle fires (T'au side):

- Pinpoint Counter-Offensive: 1.83/battle (top T'au stratagem)
- Aggressive Mobility: 0.77/battle
- Focused Fire: 0.41/battle
- Combat Debarkation: 0.10/battle
- Counterfire Defence Systems: 0.08/battle
- Pulse Onslaught: 0.04/battle

CP spent ~7.6/battle. Mont'ka strats consume ~30% of T'au CP. AI gates
work; APPROXIMATED effects (Focused Fire / Pulse Onslaught both routed to
`+1 to hit shooting`) collapse the AP boost but ARE firing.

### H_DMG — Mont'ka curve is shallow

T'au dmg / round, aggregated:

| R1 | R2 | R3 | R4 | R5 |
|---:|---:|---:|---:|---:|
| 10.4 | 13.6 | 9.9 | 9.1 | 7.4 |

R1-3 mean 11.3 / R4-5 mean 8.2 → **ratio 1.37**. Below the 1.8 front-load
threshold. T'au is functioning more like a sustained-fire army than an
alpha-strike army.

### H_SURV — battlesuits over-survive, not under-survive

Riptide dies in 1-2/30 battles (median R3-5). Stormsurge dies in 1-2/30
(median R2-R3.5). Ghostkeel 1/30. Battlesuits are NOT being deleted
early; the alpha-strike window is fully available.

### H_MARK — wired-but-not-read flag

`lethal_hits_on_guided` in `code/detachments.py:131,391` is set True on
`MONTKA` but never read by `Unit.attack`. Wahapedia Markerlights:
https://wahapedia.ru/wh40k10ed/factions/t-au-empire/#Markerlights — MARKER
units (Pathfinders, Stealth Suit drones, Ethereal markerlight) mark enemy
units; in your Shooting phase, T'au ranged attacks vs Guided enemies gain
[LETHAL HITS]. Compounds with Mont'ka rounds 1-3 (real codex synergy).

## Dominant mechanism

Mont'ka [ASSAULT] saves a no-shoot lockout (mobility); it does NOT add
damage per shot. The faction's central offensive identity in 10e is
**Markerlights → Guided → [LETHAL HITS]** — every codex battlesuit and
Fire Warrior cadre gets a flat ~+8% landed wounds vs a marked target,
and it stacks with Mont'ka rounds 1-3. SwegHammer has none of it.
That is the **-3.9pt gap's primary driver**: the simulator T'au is
shooty-but-vanilla; real-meta T'au is shooty-with-LETHAL-HITS.

## Top single fix (NOT IMPLEMENTED)

**H_MARK — wire Markerlight / Guided infrastructure as a RULE_ADD.**

Wahapedia: https://wahapedia.ru/wh40k10ed/factions/t-au-empire/#Markerlights

Minimum-viable plumbing:

1. Add `Army.guided_enemy_uids: set[str]` populated at start of T'au
   Shooting phase from any T'au unit with MARKER keyword in range of an
   enemy (canonical 36" range; SwegHammer board is small enough that
   "in LoS" approximates this).
2. In `Unit.attack`, on a T'au attacker shooting at a target whose uid
   is in `attacker_army.guided_enemy_uids`, OR `effective_lethal_hits`
   to True (same hook as Drukhari Power From Pain; the branch already
   exists at `code/units.py:1054`).
3. Identify MARKER carriers via profile keyword. Existing T'au MARKER
   units (BSData): Pathfinder Team, Stealth Battlesuits, Tetras,
   Ethereal (markerlight drone), Commander Shadowsun (drones). Tag in
   `data/overrides.json`.
4. The existing `MONTKA.lethal_hits_on_guided=True` flag becomes the
   gate that *upgrades* rounds 1-3 Guided LH to army-wide (Killing Blow
   real text); outside rounds 1-3 the Guided LH still fires (it's the
   Markerlight base rule, separate from Mont'ka).

Citation: this lands two `data/rule_citations.json` entries —
`MARKER.guided_lethal_hits` (army rule) and the existing
`MONTKA.lethal_hits_on_guided` already cited.

**Expected MAE delta**: -0.7 to -1.2pt. At BS 4+ wound 4+, LETHAL HITS
swaps the ~17% of hits that crit (6 to hit) into auto-wounds where they
would otherwise face a wound roll — net +6-9% damage output on T'au
shooters firing at the army's high-priority target. T'au gap closes
from -3.9pt to ~-2.7 to -3.2pt (single fix); the rest is matchup-
specific (Marines compound stack, DG Contagions resistance) that
faction-neutral fixes own.

## Alternatives considered

- **Existing T'au rule fix**: nothing visibly broken. Mont'ka [ASSAULT]
  fires correctly; six stratagems dispatch on cadence; battlesuits
  survive. No low-hanging code bug.
- **Faction-neutral AI improvement**: Advance-then-shoot is already
  ~14x more common R1-3 vs R4-5, so the Mont'ka window IS being
  exploited. Adjacent gunline-AI tuning would help all shooty factions
  equally (Marines +13.1, T'au -3.9 → both move) — net effect on T'au
  diff unclear, could regress Marines. Defer.

Markerlights is high-infra (~150 LOC) but is the single highest-MAE-
leverage fix remaining for T'au. **Stop here; no implementation.**
