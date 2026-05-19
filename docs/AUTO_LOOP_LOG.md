# Auto-loop log (recent)

Older iter blocks live in `AUTO_LOOP_LOG_archive.md`.

### Iter 21 (2026-05-18) — LeaderAbility fabrication audit

6 agents cross-faction sweep. 5 commits landed via cherry-pick + cross-worktree merge; Orks was clean (no fabs).

**Fabrications dropped (all citation-grounded per Wahapedia)**:
- **Necrons**: Overlord/Trazyn `plus_one_to_hit`, Plasmancer `fnp=5`. Real rules are CP discounts (Strat-econ) and offensive Crit-on-5+ (not modelled). Plus Lychguard added to Overlord bodyguard list (host_keys).
- **Marines**: Guilliman/Captain `reroll_hit_ones`, Chaplain `reroll_wound_ones`. Real rules are CP-discount/once-per-battle Battleshock-removal. Plus Shield-Captain/Brother-Captain name-collision fix.
- **Aeldari**: Yncarne `plus_one_to_hit` (proxy for reactive-teleport), Autarch `plus_one_to_hit` (CP-discount, same as Overlord pattern), Avatar `reroll_hit_ones` (real rule is +1 Advance/Charge — movement phase).
- **TSON**: ADDED 4 NEW LeaderAbilities (Ahriman, Exalted Sorcerer, Infernal Master, Sorcerer in TA) — TSON was UNDER-modelling (LeaderAbility lookup returned None). Plus Magnus "Impossible Form" (−1 to incoming Damage), Ahriman +1 Cabal Psychic test. TSON 30% → 36.1% (+6.1pt).
- **DG**: Lord of Contagion `plus_one_to_wound` (iter 20 missed), Typhus `fnp=5` (iter 20 partial). host_keys corrected per codex (Blightlord/Deathshroud, not Plague Marines).
- **Orks**: clean — no fabs.

**Cumulative iter 21 (5 commits + cross-worktree merges)**: MAE **13.73 → 13.43pt** (Δ **−0.30**). Tests 776/776, Rule citations 221/221.

**Per-faction shifts (post-iter-20 → post-iter-21)**:
- Marines +20.3 → +19.5
- Necrons **+17.6 → +14.3** (−3.3 ✅ — Overlord fab removed)
- Aeldari −6.9 → −6.6
- Tyranids −17.7 → −18.6
- Orks +4.8 → +5.1
- T'au +11.1 → +11.3
- DG +23.7 → +23.9
- Custodes −3.8 → −3.8
- TSON −24.6 → −24.3
- Votann +6.8 → +6.8

## Loop pause — PR + Ed's main rebase (2026-05-18)

User directive: wrap up after iter 21, merge progress, pick up Ed's point-cost reference fixes from main before continuing iter 22+ (aura host_keys gating, variant invuln sweep, Magnus diag, AI improvements).

Iter 22-26 plan documented above remains valid for the next loop session.

## Branch pivot — claude/sim-calibration-2 (2026-05-19)

PR #22 merged onto main at `fe9458a` (Ed's point-cost reference fixes folded in). Branched `claude/sim-calibration-2` off the updated main. Fresh baseline at N=40 archetype: **MAE 9.13** (vs 13.43 on the old branch — Ed's main work dropped MAE by ~4.3 points). Per-faction:

- Marines −3.0, Necrons −6.5, Aeldari +2.8, Tyranids +5.1, Orks +11.5, T'au +7.2
- **DG +20.9** (major over), **Custodes −18.6** (major under)
- TSON −3.2, Votann +12.6

DG combat-model over-strength and Custodes under-modeling are now the dominant outliers.

### Iter 22 (2026-05-19) — host_keys aura gate + invuln long-tail sweep

3 agents dispatched in parallel:

1. **`effective_buffs` host_keys gate** (af396da4): per-leader aura merge in `code/leaders.py` was firing army-wide regardless of `host_keys`. Typhus FNP was applying to every Death Guard within 6 inches, Lieutenant +1-to-wound to every Marine within 6 inches — same structural bug across every faction with character auras. Gate now: if `leader.host_keys` is non-empty, the attacker's catalog key must be in `host_keys` for the buff to merge. Empty tuple `()` retained as the explicit army-wide convention for MONSTER auras (Hive Tyrant Onslaught, Avatar Bloody-Handed). Reverse name lookup widened to a tuple (Plague Marines exists in both DG and CSM catalogs; gate tests set intersection). Hive Tyrant `host_keys` cleared to `()` per Wahapedia (Onslaught is broadcast). 49 leaders tests pass. Faction-neutral structural fix.

2. **Variant invuln long-tail sweep** (a6738d6f): 72 new override entries in `data/overrides.json` for units whose BSData v10.6.0 datasheet omits the Invulnerable-Save infoLink. Coverage spans every Aeldari Phoenix Lord and EPIC HERO, all Necron Lord characters, Death Guard / CSM / WE / EC HQ entries, Daemons library, Sororitas, Dark Angels HQs, Captain in Terminator Armour, Einhyr Champion. Each entry's `notes` cites the Wahapedia datasheet.

3. **LeaderAbility wide-aura audit** (ab89afd5): no code changes. Analysis-only; existing host_keys were already correct after iter 21. Discarded.

**Cumulative iter 22 (2 commits)**: MAE **9.13 → 9.20** (Δ **+0.07, flat within noise**).

**Per-faction shifts** (baseline → iter22):
- Marines −3.0 → **+0.1** (closer to zero, ✅)
- Necrons −6.5 → −7.9 (slight regress)
- Aeldari +2.8 → +1.7 (✅)
- Tyranids +5.1 → +6.2
- Orks +11.5 → **+8.7** (✅)
- T'au +7.2 → +7.2 (flat)
- DG +20.9 → **+22.8** (regress — host_keys gate removed phantom aura buffs that were partially counteracting DG over-strength)
- Custodes −18.6 → −22.2 (regress — Lieutenant-on-everyone correction made Marines stronger, Custodes look weaker by comparison)
- TSON −3.2 → −4.9
- Votann +12.6 → +10.4 (✅)

Per the iter 20 user directive (correctness > MAE), KEPT — both fixes are Wahapedia-grounded rule corrections. The two outstanding extreme outliers (DG +22.8 / Custodes −22.2) are unchanged and are the iter 23+ targets.

**Iter 23 priorities**:
1. **DG combat model audit** — Plague Marine sticky-objective, Disgustingly Resilient FNP triggering, Plague Weapons stratagem application, Mortarion deadly_demise interaction with the host_keys gate.
2. **Custodes diagnostic** — under-modeling persists from iter 20 (LOS+ablative already implemented in `code/army.py::can_target_for_ranged`); next vector is durability stack, Vexilla auras, Auric Mortalis detachment, or Trajann's per-leader buff.
3. **Magnus / TSON under-strength** — still −4.9. Magnus stat investigation from iter 21 didn't produce a fix; needs followthrough.

