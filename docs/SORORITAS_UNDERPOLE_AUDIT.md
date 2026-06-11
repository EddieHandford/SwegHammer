# Adepta Sororitas under-pole audit (wave 236, 2026-06-11)

Code-grounded diagnostic of the Adepta Sororitas residual (sim 31.3% versus real
50.8%, gated 15.68 points, number-two under-faction on the wave-236 anchor).
Conducted by a worktree agent against branch state `c2f972d`; every claim below
carries file evidence, not research priors. Finding 1 was independently
verified by the orchestrator against the effective catalogue before dispatch.

## Ranked findings

| Rank | Finding | Impact estimate | Status |
|------|---------|-----------------|--------|
| 1 | Mapper regex bug: `_INVULN_PER_ATTACK_RE` only matches the digit-first phrasing ("4+ invulnerable save"), not "invulnerable save of 4+", so `invuln_save_melee` / `invuln_save_ranged` stay 7 while the conditional-invulnerable save path (default on) reads only those fields. **120 effective-catalogue units have no invulnerable save at all** — every Terminator-armour unit, 29 of 33 Adepta Sororitas units (Sacresants 4+, Paragons 4+, Seraphim and Zephyrim 5+, Battle Sisters 6+). | Large, cross-faction (Adepta Sororitas 29 units, Space-Marine family about 78) | **Fix agent dispatched wave 236** |
| 2 | Acts of Faith capped at one per round, but the codex grants one per phase (`aof_used_this_round`, reset at round start). Cap was set conservatively when the faction over-performed; the faction is now deeply under. BSData verbatim: "each unit from your army with this ability can perform one Act of Faith per phase." | Moderate offensive uplift | Queued — simulator phase-tracking change |
| 3 | Retributor Squad "Storm of Retribution" entirely missing: re-roll Hit rolls of 1 and Wound rolls of 1 for ranged attacks, escalating to +1 to Hit and +1 to Wound against an enemy unit that has destroyed a friendly Adepta Sororitas unit. The unconditional half is a small override; the escalating half needs a new gate. | Moderate (the faction's heavy anti-tank carrier) | Queued — land both halves together |
| 4 | Paragon Warsuits "Righteous Paragons" entirely missing: +1 to Hit and +1 to Wound against MONSTER and VEHICLE targets. | Moderate in vehicle matchups | Queued — new conditional per-attack modifier |
| 5 | Bringers of Flame detachment ships with no flags (Fervent Purgation: army-wide ASSAULT on ranged weapons plus Strength +1 within six inches), and the detachment is drawn in half of Adepta Sororitas games — those games get no detachment benefit at all. | Low–medium plus dilution of Hallowed Martyrs | Queued — ASSAULT army-wide flag is the bulk |
| 6 | Canoness and Palatine "Litanies of Faith" missing: one extra Miracle die per Command phase on a passed Leadership test while the bearer is alive (about 0.58 dice per round per character). | Low | Queued — leader Command-phase hook |
| 7 | Morvenn Vahl "Abbess Sanctorum" approximated as re-roll-ones; the codex grants full re-roll of Hit and Wound rolls. Citation already flagged as an approximation. | Low | Queued — LeaderAbility field |

## Standing notes

- Finding 1 is the only item landing in wave 236; it changes default behaviour
  for about 120 units across many factions, so it lands inside the wave-236
  default-changing batch and is covered by the fresh full re-anchor.
- Findings 2 through 7 are Adepta-Sororitas-scoped and should be re-ranked
  against the post-fix residual before any of them is built — Finding 1 alone
  may move the faction substantially.
- Full agent report with verbatim BSData quotes and exact file:line references
  lives in the wave-236 session transcript; the quotes above are the
  load-bearing ones.

## Re-rank on the `0550475` frame (wave 238, 2026-06-11)

Finding 1 landed (`299aefc`) and moved the faction −19.1 → −17.1 (gated 13.4)
across two frame changes. A read-only re-rank agent re-verified findings 2–7
against the current code: all still valid, none invalidated by the
defender-allocation or displacement landings. Dispatch order for wave 239+,
ranked by expected impact with build cost as tiebreaker:

| Order | Finding | Expected impact | Build cost | Pre-build gate |
|-------|---------|-----------------|------------|----------------|
| 0 | F2 Acts of Faith per-phase | +2 to +4 points | ALREADY BUILT (`SWEG_AOF_PER_PHASE`, `620a586`) | Paired A=80 A/B queued behind the displacement Stage 2 arm; evaluate only against the current anchor (the cap was set on a frame without Blood of Martyrs or the invulnerable-save repair) |
| 1 | F5 Bringers of Flame, ASSAULT leg | +2 to +4 points | Small code: one Detachment flag + `_do_shoot` check (pattern: Mont'ka `army_wide_assault_rounds_1_3` minus round/faction gates) | Rule text verbatim in `detachments.py` notes; needs the `rule_citations` entry at commit. The detachment is drawn in half of all games with ZERO flags today — fixing it also removes that dilution |
| 2 | F3 Retributor Storm of Retribution, unconditional half | +2 to +3 points | Data-only: `reroll_hit_ones`/`reroll_wound_ones` override | Verify Wahapedia/BSData citation first; escalating half (+1/+1 versus a unit that killed friendly Sororitas) is a follow-up code build |
| 3 | F4 Paragon Warsuits Righteous Paragons | +1 to +2 points | Small code: per-unit +1 hit/+1 wound versus MONSTER/VEHICLE gate in `Unit.attack` | Verify citation first |
| 4 | F7 Morvenn Vahl full re-roll | +0.5 to +1.5 points | Small code: `reroll_all_hits`/`reroll_all_wounds` LeaderAbility fields wired into the existing `att_reroll_all_hits` machinery | Citation already in `leaders.py` |
| 5 | F6 Litanies of Faith | +0.5 to +1.5 points | Small code: Command-phase Leadership-test hook granting a Miracle die | Verify the exact Leadership-test wording first |

If the Acts of Faith A/B lands positive, the F2+F5+F3 stack alone plausibly
closes 7–11 of the −17.1 residual. The S+1-within-six-inches leg of F5 and the
escalating half of F3 are held as low-increment follow-ups.
