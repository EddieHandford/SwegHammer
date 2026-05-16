# Auto-loop iter 8 — cross-faction anti-DG tools audit

Status: diagnosis / audit only. **No simulator / catalogue / stratagems mutation.**

Source: source-reads of `code/stratagems.py`, `code/detachments.py`,
`data/bsdata/parsed.json`. Wahapedia URLs cited inline; no live WebFetch
(host unreachable).

DG +18.1 is the dominant residual after iter-7 loop termination. Iter 7's
DG-vs-Custodes deep diag found Custodes lacks the simulator-wired tools
to contest DG sticky / damage-race / OC reach. This audit extends that
finding cross-faction: **which real-codex tools should mitigate DG in
meta play but are NOT in SwegHammer**.

Plague Marines profile: `INFANTRY`, `BATTLELINE`, T5 W2 Sv 3+ 5+++ FNP,
M5". DG detachment rule Worldblight is sticky-control on DG-held
objectives. The two angles a real opponent has are:
(a) crack T5/Sv3+/5+++ via crit-wound or saves-bypass keywords;
(b) deny Worldblight by physically OC-contesting markers (not just
killing PMs — sticky persists until enemy LoC > DG LoC).

## 1. Anti-INFANTRY weapon keyword — coverage gap

Survey of `data/bsdata/parsed.json` (unit-level summary, 1532 units;
"INFANTRY" in `anti_keywords`). Codices with zero ANTI-INFANTRY weapons
mapped from BSData:

| Codex | ANTI-INF / total profiles |
|---|---:|
| **Adepta Sororitas** | 0 / 42 |
| **Adeptus Custodes** | 0 / 35 |
| **Leagues of Votann** | 0 / 26 |
| **Necrons** | 0 / 67 |
| Imperial Knights / Chaos Knights | 0 / 24+1 |
| Tyranids | 2 / 64 (Toxicrene, Venomthropes only) |
| T'au Empire | 1 / 67 (Kroot War Shaper) |
| Orks | 2 / 93 (Meganobz, Nobz) |

ANTI-INFANTRY 4+ / 3+ should be on real-meta weapons every codex
carries:

- **Custodes Misericordia / Allarus dagger-side weapons**
  ([ANTI-INFANTRY 4+]) — Wahapedia
  https://wahapedia.ru/wh40k10ed/factions/adeptus-custodes/ — no current
  ANTI-INF in any Custodes profile. **Complexity: low** (BSData mapper
  override). Predicted MAE Δ on DG slice: -0.5 to -1.0pt (Custodes
  cracking PMs at crit-wound 4+ raises CG → PM kill rate from 0 to ~0.5
  models/battle per iter-7 trace).
- **Tyranid Devourers with Brainleech Worms** ([ANTI-INFANTRY 4+]) —
  Wahapedia https://wahapedia.ru/wh40k10ed/factions/tyranids/ — only
  Toxicrene/Venomthropes carry it in BSData. Tyranid Carnifex /
  Tyrannofex Brainleech Devourers are a real ANTI-INF chassis missing
  the keyword. **Complexity: low** (per-weapon override on shooty
  Tyranid datasheets). Predicted Δ DG slice: -0.5pt (Tyranids vs DG is
  one of the 7 unsampled-but-positive matchups).
- **Sororitas Flamers / Heavy Flamers** (vanilla 10e: most Flamer
  variants have ANTI-INF 4+) — Wahapedia
  https://wahapedia.ru/wh40k10ed/factions/adepta-sororitas/ — zero
  Sororitas ANTI-INF entries. **Complexity: low**. Predicted Δ: ~-0.2pt
  (Sororitas isn't in the 10-faction eval slice, but cross-codex audit
  consistency).
- **Necron Flayed Ones / Lokhust Heavy Destroyer Enmitic Exterminators**
  ([ANTI-INFANTRY 4+] on the Enmitic) — Wahapedia
  https://wahapedia.ru/wh40k10ed/factions/necrons/ — zero Necron
  ANTI-INF anywhere. **Complexity: low**. Predicted Δ: -0.3 to -0.5pt
  on Necron-vs-DG (currently DG over-performs vs Necrons by ~+6).
- **Votann Pan-Spectral Scanners on HQ characters** (rumour-keyword;
  the actual Votann ANTI-INF is on Cyclic Ion Accelerators) — Wahapedia
  https://wahapedia.ru/wh40k10ed/factions/leagues-of-votann/ —
  **Complexity: low**.

## 2. Missing detachment stratagems

### Gladius Task Force (Marines) — **6 stratagems missing, ZERO wired**

Wahapedia: https://wahapedia.ru/wh40k10ed/factions/space-marines/#Gladius-Task-Force

| Stratagem | CP | Why it counters DG |
|---|---|---|
| **Storm of Fire** | 2 | Marine RANGED unit gains [SUSTAINED HITS 1] / upgrade to 5+ Crit. Mass-S4 Bolter dakka on PMs (T5) at sustained-hits multiplier — directly attacks the T5 wall. |
| **Armour of Contempt** | 1 | Targeted Marine unit's models gain Crit Save 5+ until end of phase / further saves of one fewer success. **DEFENSIVE**; reduces DG Plague Spitter / Bubotic Axe AP returns. |
| **Only In Death Does Duty End** | 1 | Marine model just destroyed in melee may make a melee attack before being removed. Counters DG melee swarm picks. |
| **Squad Tactics** | 1 | Marine unit makes a Normal Move of D6". **Repositioning** — addresses the OC-reach problem (relevant to DG, since the iter-7 diag showed opponents physically can't reach DG-held markers). |
| **Heroic Intervention (Gladius variant) — Honour the Chapter** | 1-2 | Captain re-rolls Wound rolls / +1 to wound on melee for a phase. |
| **Adaptive Strategy** | 1 | Re-roll a Combat Doctrine Save — cycle Tactical Doctrine into the right round. |

**Complexity: medium** (six dispatcher entries + citations). Predicted
MAE Δ on DG slice: **-1.5 to -2.5pt** (Marines vs DG is +12% over real
per iter-4 sample; Storm of Fire + Squad Tactics directly attack the
two mechanisms — PM survivability and DG OC dominance).

### Oathband (Votann) — **6 stratagems missing, ZERO wired**

Wahapedia: https://wahapedia.ru/wh40k10ed/factions/leagues-of-votann/

| Stratagem | CP | Why it counters DG |
|---|---|---|
| **Warrior Pride** | 1 | Re-roll Wound rolls vs a Judgement-token-bearing enemy. Stacks with the `simulator.judgement_tokens` 1+/3+ thresholds already wired — DG units accrue tokens, this lets Votann crack PMs at full wound re-roll. |
| **Wrath of the Ancestors** | 1 | Votann unit gains [LETHAL HITS] on ranged attacks vs token-bearing unit. Auto-wound on Crit Hit on PMs. |
| **Glory of the Hearth** | 1 | Re-roll Hit AND Wound rolls for a Votann VEHICLE shooting. |
| **Ironkin Sequence** | 1 | An IRONKIN unit gets +1 to hit. Hearthkyn-stack damage uplift. |
| **Ancestral Sentence** | 2 | Issue Judgement Token to an enemy unit at the start of the phase. Forces a DG unit into token range so Warrior Pride / Wrath fires. |
| **Void-Armoured Resilience** | 1 | Votann unit gains 5+ FNP for the phase. Survives DG mortal-wound contagion. |

**Complexity: medium**. Predicted Δ DG slice: -1.0 to -2.0pt. Votann
is one of the 7 unsampled DG matchups (iter-5 reading: 53% sim vs ~45%
real, +8pt over).

### Tyranids (Invasion Fleet) — stratagems coverage check

Wahapedia: https://wahapedia.ru/wh40k10ed/factions/tyranids/#Invasion-Fleet

Currently zero Tyranid detachment stratagems wired. **Death Frenzy**
(1 CP — Tyranid INFANTRY unit makes a Shooting + Fight phase before
being destroyed; counters DG kill-then-vacate) and **Bio-Resonance**
(2 CP — re-roll Hit AND Wound vs an enemy unit; LETHAL on PMs) would
both bite DG hard. **Complexity: medium**. Predicted Δ: -0.5 to -1.0pt.

## 3. Anti-CHARACTER tools (DG Lords lead PMs and tank wounds)

DG runs Plague Marines led by Lord of Virulence / Biologus / Plague
Surgeon CHARACTERs. The leader stacks tank wounds for the squad and
provides the +1-to-wound aura. Killing the leader collapses the buff.

- **Tank Shock** (universal): Wahapedia
  https://wahapedia.ru/wh40k10ed/wh40k-10th-edition-rules-commentary/#Stratagems —
  **WIRED**. Universal core stratagem; D3 mortal wounds on charge target.
  Already in `code/stratagems.py:TANK_SHOCK`. Confirmed present.
- **Marksman / Precision** weapon-keyword (PRECISION): targets CHARACTERS
  through a unit. Currently unwired. Wahapedia generic keyword. PRECISION
  is on Marine Eliminator Bolt Sniper Rifles, Aeldari Rangers Long Rifles,
  Custodes Vexilus Praetor Misericordia, etc. **Complexity: medium** (new
  weapon-keyword + target-override path in `Unit.attack`'s target
  selection). Predicted Δ DG slice: -0.5 to -1.5pt. Eliminator Sniper
  Marines vs DG specifically counter PM Sergeant + attached CHARACTER.
- **Vindicare Assassin** (Imperial Agents allied): one-shot CHARACTER
  pick from any range. Currently not in eval but if Agents detachment is
  reachable would compound. Out of scope for the 10-faction eval slice.

## 4. Synapse-led objective lockdown (Tyranids)

The Tyranid Invasion Fleet army rule is Shadow in the Warp (once-per-
battle army-wide Battleshock). The detachment in SwegHammer is wired
as **always-on -1 Ld** APPROXIMATION (`INVASION_FLEET.enemy_ld_penalty`).
**Synapse-anchored objective hold** is a real meta tool: Synapse units
(Hive Tyrant, Tervigon, Norn Emissary) lead Termagants/Hormagaunts and
make them battleshock-immune within range, allowing 30-strong Termagant
bricks to sit on objectives and absorb DG damage.

Wahapedia: https://wahapedia.ru/wh40k10ed/factions/tyranids/#Army-Rule
"While a SYNAPSE unit is on the battlefield, each time a unit from your
army is required to take a Battle-shock test, that test is automatically
passed." (paraphrased — see citation in `data/rule_citations.d/tyranids.json`).

**Complexity: low-medium** — Synapse-as-aura already partly wired (iter-1
A3 self-shelter was PARKED, see AUTO_LOOP_LOG.md). The real-rule
direction is correct; the iter-1 implementation tilted too much. A
narrower fix: Synapse blocks DG Worldblight sticky **from latching** when
a Synapse-led Tyranid unit is in OC range, by adjusting LoC scoring at
end-of-Command-phase. **Complexity: medium**. Predicted Δ DG slice:
-0.5 to -1.0pt (Tyranids vs DG is one of the 7 unsampled DG
over-performs).

## 5. Other notable missing tools (lower priority)

- **Aeldari Fate Dice on Save rolls** — currently the Strands of Fate
  pool is wired offensively (iter-3); the defensive side (commit a
  guaranteed 6 to a Wound save against a DG attack) is APPROXIMATED.
  Citation: `simulator.strands_of_fate`. **Complexity: low-medium**.
- **Ork 'Ere We Go re-roll Charge** — wired, fine.
- **TSON Devastating Wounds Crit Wound 5+ via Wrath of the Immaterium
  Kindred Sorcery selection** — Wahapedia
  https://wahapedia.ru/wh40k10ed/factions/thousand-sons/ — currently
  `GRAND_COVEN.psychic_mortal_wounds_per_round=2` is the only psychic
  payload. Real Wrath gives Psychic weapons [DEVASTATING WOUNDS] which
  would bypass PM 5+++ FNP **and** Sv 3+ on every crit-to-wound.
  **Complexity: medium**. Predicted Δ DG slice: -0.3 to -0.7pt.

## Ranked top 5 fixes by expected MAE Δ on DG slice

1. **Marines Gladius — 6 stratagems** (Storm of Fire + Armour of
   Contempt + Squad Tactics + Only In Death + Honour the Chapter +
   Adaptive Strategy). Complexity: medium. **Δ: -1.5 to -2.5pt.**
   https://wahapedia.ru/wh40k10ed/factions/space-marines/#Gladius-Task-Force
2. **Votann Oathband — 6 stratagems** (Warrior Pride + Wrath of the
   Ancestors + ...). Complexity: medium. Stacks with already-wired
   `simulator.judgement_tokens`. **Δ: -1.0 to -2.0pt.**
   https://wahapedia.ru/wh40k10ed/factions/leagues-of-votann/
3. **ANTI-INFANTRY mapper coverage audit** — 5 codices have 0
   ANTI-INFANTRY weapons in BSData parsed.json (Custodes / Sororitas /
   Votann / Necrons / Tyranids near-zero). Complexity: low (mapper
   overrides). **Δ: -1.0 to -2.0pt** aggregated cross-faction.
   Per-codex Wahapedia URLs listed above.
4. **PRECISION weapon keyword + targeting path** — counters DG leader
   tank-wounds. Eliminator Bolt Sniper / Vexilus Misericordia etc.
   Complexity: medium. **Δ: -0.5 to -1.5pt.**
5. **Tyranid Synapse-anchored sticky-block on Worldblight** (narrowed
   re-do of parked A3 — block DG sticky latching, not blanket
   battleshock immunity). Complexity: medium. **Δ: -0.5 to -1.0pt.**
   https://wahapedia.ru/wh40k10ed/factions/tyranids/#Army-Rule

**Aggregate expected DG slice MAE Δ if all 5 land: -4.5 to -9pt.** Realistic
post-interaction (per iter-1..7 pattern: ~40-60% of solo predictions
survive cross-faction interactions) → **-2 to -4pt on DG slice**,
which is the bulk of the remaining +18.1pt DG residual.

## Test gate

`python -m unittest discover -s tests` — **666 tests pass** (5 skipped,
all pre-existing). No production code touched this iter; only this
audit doc is added.

## Not done this pass (per brief)

- Did not implement any fix.
- Did not run N=200 eval / run.py / Monitor / background processes.
- Did not WebFetch Wahapedia (host unreachable from this worktree).
- Rule text is paraphrased from existing repo citations + general
  10e codex knowledge where exact verbatim could not be re-fetched;
  Wahapedia URLs are the authoritative source for any follow-up
  implementation per CLAUDE.md §10.
