# Auto-loop log (recent)

Older iter blocks live in `AUTO_LOOP_LOG_archive.md`. Per
`AUTO_LOOP_PROCEDURE.md` §E this file keeps the most recent close + the
in-flight wave only.

## Wave 64 close (2026-05-30)

Branch `claude/sim-calibration-6`. First wave of the AI-tactics-implementation
campaign — a 16-tactic audit (research real competitive 10e tactics, verify
each against the sim AI) found the AI can organically do NONE fully (11 CANNOT,
5 PARTIAL); the gaps became tasks #12-16. This wave lands the first: a
rules-correct AI capability, consolidate-onto-objective.

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Wave 63 close (`96fd68e`+docs) | 12.80 | 9.27 | 2/22 |
| Wave 64 close (`3203e35`+docs) | 12.80 | 9.27 | 2/22 |

**FIGHT-AI-CONSOLIDATE-OBJECTIVE** (`3203e35`): the 10e Consolidate move now
goes up to 3" onto the nearest objective marker when combat clears (no enemy
reachable) — previously a no-op in that case. Audit 278/278 (new
`simulator.consolidate_objective` key + citation). Headline UNCHANGED — the
trigger (combat fully cleared with an objective within 3") is low-frequency,
below the N=40 noise floor; the effect surfaces at higher N. Rules-correct,
zero regression, pytest 912 → landed.

Campaign progress: #14 done. Next #16 (Heroic Intervention already-engaged
gate + Counter-Offensive firing), #15 (target priority by VP-plan), #13
(repulsion/denial positioning), #12 (plan-level + lookahead objective function).

## Wave 63 close (2026-05-30)

Branch `claude/sim-calibration-6`. One rules-correct fix: World Eaters Blood
Tithe was over-accruing. Notable as a verify-first save and as the second
rejected→corrected attempt at the WE over-shoot.

### Headline

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Wave 62 close (`e1346a1`+docs) | 12.90 | 9.39 | 2/22 |
| Wave 63 close (`96fd68e`+docs) | 12.80 | **9.27** | 2/22 |

-0.12 gated. Clean: World Eaters down toward target, ZERO cross-faction
regression (only WE accrual touched).

### WE-BLOODTITHE-PERUNIT (`96fd68e`)

World Eaters over-shot (sim 56.4, target 47.0, gated 6.01) — a wave-61
fall-back-gate side effect that turned out to expose a real bug.
`_maybe_award_blood_tithe` awarded +1 Blood Tithe on every `UnitKilled`, but
in the one-Unit-per-model representation that fires per MODEL, while the codex
awards per UNIT destroyed. A WE squad wiping a 10-model enemy unit over-accrued
+10 BT instead of +1 — the **8th catalogued instance of
`project-one-unit-per-model-amplification`**. Fixed with the standard
last-living-model dedup (award only when no sibling sharing the victim's
profile.name survives in its army).

Result (N=40): WE gated 6.01 → 4.46 (-1.55, toward target); Emperor's Children
-0.48 and Marines -0.48 (collateral improvement — WE's opponents win their
matchups more); NO regressions. Headline 9.39 → 9.27.

### Verify-first save

The read-only WE diagnostic proposed a much larger "fix": add a D6 3+ accrual
gate, remove the friendly-WE-death trigger, and rewrite the spend table —
claiming Blood Tithe is a Khorne Daemonkin *detachment* rule. ALL THREE
contradict the sim's own cited Wahapedia rule (`world_eaters.json`): the WE
**army** rule awards on friendly death AND enemy kill, with NO dice roll, and
the spend table the sim implements (4 = Lethal Hits, 3 = +1 Command point) is
correct. The agent conflated two different rules. Checking the proposed change
against the existing citation before applying caught it — only the narrow
per-model amplification was real.

### Process — a rejected attempt first

The first wave-63 attempt (a "critically-wounded melee units may Fall Back
below 35% HP" gate, commit `88c4920`) was REJECTED: it helped WE (-1.90) and
Emperor's Children (-1.19) but regressed exactly the horde/monster factions
wave 61 had calibrated (GSC +1.91, Tyranids +1.19, Orks +0.95), net headline
9.39 → 9.52. Lesson: a faction-neutral AI gate ripples across every melee
faction; run the full per-faction gated diff before landing, not just the
headline. pytest 912 passed; audit well-formed. Eval `data/wf_wave63_n40.json`.

### Open carry-forwards into wave 64

1. **Necrons detachment fabrications** (task #9) — rules-correct but
   MAE-negative (Necrons under-shoots); handle with care.
2. **Detachment citation/comment fixes + Grey Knights deep-strike gate** (#10).
3. **Strategy roadmap #1** (task #6 review) — a plan-level objective function;
   the next big systemic lever, like the wave-61 fall-back fix.

## Wave 62 close (2026-05-30)

Branch `claude/sim-calibration-6`. One fix — the first item from the
detachment-fabrication sweep. Recovered from a stalled background agent: its
work was already committed (`91e0e33`) and cherry-picked as `e1346a1`.

### Headline

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Wave 61 close (`c4d6da6`+docs) | 12.89 | 9.36 | 2/22 |
| Wave 62 close (`e1346a1`+docs) | 12.90 | 9.39 | 2/22 |

Headline flat (within noise) — a single-detachment correctness fix, not a
systemic one like wave 61.

### CUSTODES-AURIC-CHAMPIONS (`e1346a1`)

The default Custodes eval detachment carried `melee_sustained_hits_army_wide
=True` citing "Trail of Glory" — a fabrication on two counts: the cited rule
name is wrong (the real rule is "Assemblage of Might"), AND an army-wide
Sustained Hits proxy doesn't match it. Assemblage of Might designates one
enemy unit per Command phase and grants +1 wound to ADEPTUS CUSTODES
CHARACTER units against only that target — a designate-one-target +
CHARACTER-only mechanic the Detachment schema cannot proxy without
fabricating. The flag was REMOVED (a no-op is more rules-correct than a
fabrication) and its citation deleted; the shared Orks War Horde consumer of
the same flag is untouched (its gate logic is unchanged).

Custodes over-shoots, so removing the buff is direction-correct AND
MAE-positive: Custodes sim 57.1 → 56.5 (target 52.1), gated 2.39 → 1.80 —
now near in-band. The headline didn't move because one faction's -0.59 gated
averages to ~-0.03 across 22 factions.

### Process

- Recovered a stalled async agent — its fix was committed but it never
  reported back. Cherry-picked the commit directly rather than re-running.
- pytest 912 passed; audit 277/277 (one fewer required key — the removed
  fabrication flag). Eval `data/wf_wave62_n40.json`.

### Open carry-forwards into wave 63

1. **World Eaters / CSM over-shoot** from the wave-61 fall-back gate — re-tune.
2. **Necrons detachment fabrications** (task #9) — rules-correct but
   MAE-negative (Necrons under-shoots); handle with care, don't blind-remove.
3. **Detachment citation/comment fixes** (task #10) — low-risk.
4. **Strategy roadmap #1** (task #6 review) — a plan-level objective function;
   the big systemic lever, like the wave-61 fall-back fix.
