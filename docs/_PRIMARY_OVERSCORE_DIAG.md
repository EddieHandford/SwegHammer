# Primary victory-point over-score diagnostic

Read-only diagnosis of the primary-scoring channel: the simulator scores roughly
thirty-five primary victory points per player per game against a real reference
near twenty-nine (Pariah Nexus, nine thousand four hundred sixty-seven games;
Chapter Approved 2025-26 "hasn't changed much"). The question this answers: is the
gap a **rules divergence** in the primary-scoring path (a fixable fidelity bug — a
wrong cap, a wrong per-round maximum, a hold-more error, a wrong objective count),
or is it the **equilibrium** (faithful primary rules, but the simulator's games hold
markers longer than real games because of play and attrition, which is not fixable
without a knob)?

Base branch and commit: `worktree-agent-ae1a2b90a2bb25ea5` at
`7dbf193` (a descendant-free checkout of `origin/claude/sim-calibration-19`,
top commit `7dbf193`, the standing anchor `sc53a`, gated mean absolute error 3.96).

Scratch scripts (this worktree only): `scripts/_primary_diag_anchor_replay.py`
(the anchor-seeded replay below). The signature machinery is the existing
`scripts/diag_signatures.py` (`_parse_event_log` / `_compute_signatures`); the
anchor reconstruction mirrors `scripts/_ec_crater_replay.py` and
`scripts/_dura_audit_d_winshape.py` exactly.

---

## Headline verdict

**EQUILIBRIUM, not a rules divergence.** The primary-scoring path is faithful to the
printed Chapter Approved 2025-26 / Pariah Nexus rules line by line — correct
per-objective value (five), correct per-turn cap (fifteen), correct per-game cap
(fifty), correct round-one-zero and round-two opening, correct per-Command-phase
timing with the round-five going-second deferral, and all five modelled missions
score by their printed victory-point amounts and caps. There is **no wrong cap, no
wrong per-round maximum, no hold-more error, and no wrong objective count** to fix.

The over-score is the survivor-snapshot **uptime equilibrium** already documented in
`docs/_DURA_AUDIT_D_DEATHGUARD.md` and `docs/DURABILITY_OVERREWARD_INVESTIGATION.md`,
expressed through a faithful scoring channel: the simulator plays all five battle
rounds with a **flat** round-two-to-five primary trajectory (no round-five attrition
decay, no early concession), so durable pillars keep banking primary in the late
game that real ground-down or conceded games do not. Closing it faithfully is not a
Stage-1 primary-scoring lever; it is exactly the elite-over-horde pricing question
Stage 2 exists to answer. This **strengthens the pricing-floor conclusion.**

One faithful fidelity-completeness item does fall out (model the five deck missions
that currently fall back to Take and Hold), but it is faction-neutral, would lower
every army's primary roughly evenly, and would **not** close the durable over-pole —
so it is a fidelity item, not the fix for the over-pole. Detail in the decomposition.

---

## 1. Calibration-grade numbers

### 1a. The signature run (`scripts/diag_signatures.py --pairs 10 --seeds 15`, N = 150 games)

Confirms the shape the brief cited, on the current frame:

| Signature | Simulator | Real reference |
|---|---|---|
| Mean primary victory points per player per game | **35.0** | ≈ 29 (Pariah Nexus) |
| Mean secondary victory points per player per game | **14.2** | ≈ 22.7 (Pariah Nexus) |
| Going-first win rate | 56.5% (n = 147) | ≈ 49–52% |
| Round-1 primary assertion | PASS (all zero) | 0 by rule (opens round 2) |
| Fraction of player-rounds hitting the 15 cap | 20.8% | rare early, rises rounds 3–4 |
| Per-round primary trajectory | r1 = 0.0, r2 = 8.5, r3 = 9.3, r4 = 8.7, r5 = 8.9 | 0 → 5–10 → peak 10–15 → attrition-constrained round 5 |

Two facts frame the whole diagnosis:

- **The trajectory is FLAT, not peaked-then-decaying.** Real primary rises to a
  round-three/four peak and then falls in round five as armies are ground down and
  some games end early. The simulator holds a near-constant ~8.5–9 primary in every
  scoring round, round five included. The flatness — specifically the absence of a
  round-five decay — is the entire over-score, expressed as ~1.5 extra primary per
  scoring round across four rounds.
- **The simulator UNDER-scores secondary by about the same amount it over-scores
  primary.** Sim total victory points ≈ 35.0 + 14.2 = 49.2 against real ≈ 29 + 22.7 =
  51.7 — the simulator's aggregate scoring is slightly *under* real. The channel is
  **mis-mixed** (too much weight on primary, too little on secondary), not inflated in
  total. The durable over-pole lives specifically in the primary-uptime channel
  (`docs/_DURA_AUDIT_D_DEATHGUARD.md`: Death Guard wins on a +18.70 primary margin
  with a *negative* secondary margin), which is why it reads as a "primary over-score".

### 1b. The anchor-seeded replay (`scripts/_primary_diag_anchor_replay.py`, N = 315 per faction per configuration)

`scripts/diag_signatures.py` never passes a `primary_mission` and never sets
`SWEG_PRIMARY_MISSION`, so every game it runs falls through `Battle.__init__`'s
default chain to Take and Hold — the single most holder-friendly mission. The
production evaluation (and therefore the standing anchor and the headline metric)
instead draws a per-game mission from the real Chapter Approved 2025-26 ten-card deck
(`_pick_primary_mission`, default-on). So the reported 35.0 is measured under the
*wrong* mission configuration. This replay measures the production frame directly, on
the anchor's own Death Guard cells (the top durable over-pole, +17.7 over real) and
Orks cells (a ground-down horde under-pole, −13.1), first fifteen seeds per opponent,
mirroring the audit-D stratification. Winner reproduction is exact by construction
(same seeds, maps, missions as the anchor).

**Death Guard cells (315 games):**

| Configuration | Mean primary | Mean secondary | Cap-15 fraction | Trajectory (r1–r5) |
|---|---|---|---|---|
| Forced Take and Hold (the diag-signatures frame) | 35.0 | 12.9 | 21.6% | 0, 8.8, 9.1, 8.8, 9.2 |
| **Production mission-deck mix (the anchor frame)** | **33.6** | 11.5 | 17.1% | 0, 8.3, 8.7, 8.4, 8.7 |

Delta (mix − Take-and-Hold-only) mean primary: **−1.43**.

**Orks cells (315 games):**

| Configuration | Mean primary | Mean secondary | Cap-15 fraction | Trajectory (r1–r5) |
|---|---|---|---|---|
| Forced Take and Hold | 35.2 | 13.9 | 21.2% | 0, 8.8, 9.4, 8.9, 8.9 |
| **Production mission-deck mix** | **33.9** | 12.2 | 17.3% | 0, 8.3, 9.0, 8.6, 8.6 |

Delta (mix − Take-and-Hold-only) mean primary: **−1.28**.

The 35 is **robust**: two independent measurements (the mixed-faction signature run
and the Death-Guard/Orks anchor replays) all land at 35.0–35.2 under Take and Hold.
It is not a small-subset artifact of the signature run's ten matchups. And the real
production frame the anchor actually uses scores ~**33.6–33.9** primary — the mission
deck shaves only ~1.3 primary victory points, so the deck mix is **not** the driver
of the gap.

Per-mission primary means inside the production-mix run (Death Guard / Orks):

| Mission | Modelled? | Sim mean primary | Real per-turn scoring |
|---|---|---|---|
| Take and Hold | yes (rule) | 34.9 / 35.1 | 5 per marker, cap 15 |
| Scorched Earth | yes (rule) | 33.3 / 34.5 | 5 per marker, cap 10, + Burn/Raze |
| Terraform | yes (rule) | 32.1 / 32.9 | 4 per marker, cap 12, + 1 per terraformed |
| The Ritual | yes (rule) | 33.0 / 32.5 | 5 per No Man's Land marker, cap 15 |
| Purge the Foe | yes (rule) | 27.3 / 28.6 | kill-weighted, cap 12 |

Only Purge the Foe (kill-weighted, cap twelve) lands near the real ~29. Every
hold-based mission sits at 32–35. The real deck contains these same missions, so if
the simulator held the same *number* of markers for the same *duration* as real
games, the hold missions would also land near real. They do not, because the sim
holds them a full five rounds without decay.

---

## 2. The primary-scoring path, verified line by line against the printed rules

Source of truth for rule text: Wahapedia Pariah Nexus Battles and Chapter Approved
2025-26 pages (fetched this session), cross-checked against
`data/rule_citations.d/core_primary_vp_cap.json`. Code: `code/simulator.py`
`_score_objectives` (the objective loop and the per-mission victory-point formulae),
the `run` round loop, and `_run_round_vanilla_turns` (the per-Command-phase timing).

### Faithful list (each verified)

1. **Per-objective value = 5 victory points.** `code/map.py` `Objective.vp_per_round
   = 5`; awarded at `code/simulator.py:1495/1501` (`a_th_award += obj.vp_per_round`).
   Real: "5VP for each objective marker they control". FAITHFUL.

2. **Per-turn cap = 15 victory points.** Take-and-Hold branch
   `code/simulator.py:1607-1614`: after awarding, `if a_round_vp > 15: self._a_vp =
   a_vp_before + 15`. Applied per player per Command phase (see item 6), so each side
   scores at most fifteen per battle round. Real: "up to 15VP per turn". FAITHFUL.

3. **Per-game cap = 50 victory points.** `_capped_vp_pair`
   (`code/simulator.py:977-982`): `a_primary = min(a_primary, 50)` (default-on,
   `SWEG_PRIMARY_CAP_50`). Real (Determine Victor maximums): "Primary Mission 50VP …
   any excess VP awarded above these maximums are lost". FAITHFUL.

4. **Round 1 scores zero; primary opens round 2.** `run` loop gates every scoring
   call on `rnd >= 2` (`code/simulator.py:883/888`, and the Command-phase path
   `self._current_round >= 2` at `:12087`). The signature run's round-1 assertion
   PASSES on all 150 games. Real: scoring "begins in the second battle round".
   FAITHFUL.

5. **Objective count.** Nine of the ten stock maps carry five objective markers, one
   (the `take_and_hold` layout) carries four (`code/map.py`, verified by dumping
   `STOCK_MAPS`). Immaterial to the primary total: the fifteen-per-turn cap counts at
   most three markers, and both four- and five-marker layouts exceed that. Real
   Pariah Nexus layouts use five markers; no wrong-count inflation. FAITHFUL (and
   inert to the gap).

6. **Per-Command-phase, per-player timing.** `_cmd_score` default-on
   (`code/simulator.py:584`). In `_run_round_vanilla_turns` each player scores at the
   start of its own turn via `_score_objectives(only_for=active.name)`
   (`:12087-12089`), on the markers it controls at that moment, before its own
   movement — the real "End of the Command phase" timing. The `only_for` filter
   (`:1493`) increments only the active side's running total; the objective contest
   and sticky tracking still run for both. No double-count: `a_vp_before` is
   re-captured per call (`:1127`) so each side's cap is enforced independently.
   Real: "WHEN: End of the Command phase". FAITHFUL.

7. **Round-five going-second deferral.** `SWEG_R5_SECOND_LAST` default-on
   (`code/simulator.py:12082`, deferred score at `:12418-12428`): in round five the
   second player's primary is scored after its whole turn resolves, not at turn start,
   rewarding the last-turn objective grab. Real: "or the end of your turn if it is the
   fifth battle round and you are going second". FAITHFUL.

8. **Purge the Foe** (`:1543-1559`): 4 for destroying one or more enemy units, +4 for
   destroying more than the opponent did, +4 for controlling one or more objectives,
   +4 for controlling more than the opponent, `min(..., 12)`. Kill count from the
   round-start snapshots via `_units_destroyed_this_round` (`:1624`, unit destroyed
   only when its last model dies — the No Prisoners convention). Real amounts and cap
   verbatim. FAITHFUL (timing of the split Command-phase / end-of-round conditions
   approximated at the single round scoring point, faithful to the amounts).

9. **Scorched Earth** (`:1560-1569`): `min(a_th_award, 10)` hold, plus the Burn/Raze
   action resolved after the cap (`_resolve_burns`, `SWEG_SCORCHED_BURN`), 5 in No
   Man's Land / 10 in the enemy deployment zone, razed markers excluded from later
   scoring (`_razed_objectives`). Real amounts and lower ten-cap verbatim. FAITHFUL.

10. **Terraform** (`:1570-1585`): `min(4 * a_controls, 12)` hold + 1 per marker
    terraformed by that side (on top of the cap). Real: "4VP for each objective marker
    they control (up to 12VP per turn)" + "1VP for each objective marker that is
    terraformed by them". FAITHFUL.

11. **The Ritual** (`:1586-1601`): `min(5 * a_controls_nml, 15)` — only No Man's Land
    markers (`_obj_in_nml`, `:3608`) score. Real: "5VP for each objective marker in No
    Man's Land that they control (up to 15VP per turn)". FAITHFUL (the dynamic
    marker-creation action is out of scope, documented).

### Divergences found in the primary-scoring path

**None that inflate primary.** The one fidelity gap is a *completeness* gap, not a
scoring bug: five of the ten deck missions — Linchpin, Burden of Trust, Unexploded
Ordnance, Hidden Supplies, Supply Drop — are not modelled and fall back to Take and
Hold (`_PRIMARY_DECK`, `scripts/evaluate_vs_meta.py:268-279`, labelled an "HONEST
partial" in the code). Because Take and Hold is the most holder-friendly mission,
scoring these five as Take and Hold *over*-credits them relative to their real,
more-restrictive rules (Burden of Trust scores only objectives outside your own
deployment zone; Supply Drop and Hidden Supplies restrict to No Man's Land or
non-home markers; Linchpin scores 3 per marker unless you hold your deployment-zone
objective). This is a known, documented partial (`docs/DURABILITY_OVERREWARD_
INVESTIGATION.md` §3.3), it is faction-neutral, and — critically — it does not
create the durable-over-horde split; it merely raises the absolute primary mean for
everyone. See the decomposition.

---

## 3. Decomposition of the gap (production frame ≈ 33.7 vs real ≈ 29)

The brief's "35 vs 29 = 6" is the *diag-signatures* (all-Take-and-Hold) number. The
**production frame** the anchor and the headline metric actually run scores ~**33.7**
primary (33.6 Death Guard, 33.9 Orks), so the real production gap is ~**4.7**, not 6.
It decomposes into three parts, none of which is a primary-scoring rules bug:

| # | Component | Size (primary VP) | Nature | Fixable in Stage 1? |
|---|---|---|---|---|
| 1 | Mission-deck mix (already applied in the production frame) | −1.3 (35.0 → 33.7) | The real deck's lower-cap / kill-weighted missions already pull the sim down from the Take-and-Hold 35 to 33.7 | Already applied |
| 2 | Honest-partial fallback: 5 of 10 deck missions scored as Take and Hold instead of their more-restrictive real rules | ~1–2 (over-credit) | Fidelity-completeness gap, **faction-neutral** — lowers every army's primary roughly evenly | Yes as fidelity, but does not close the over-pole |
| 3 | Structural equilibrium: flat round-2-to-5 trajectory, no round-5 attrition decay, always five full rounds (no concession / time-cut) | ~2–3 (residual) | Survivor-snapshot uptime; durable-favouring; the audit-D mechanism | **No** — no faithful knob |

**Evidence for each:**

- **Component 1** is measured directly: forced Take and Hold 35.0 → production mix
  33.6/33.9 (−1.3). The deck is already default-on in production.
- **Component 2**: the modelled restrictive missions score below Take and Hold
  (Terraform 32.1/32.9, The Ritual 33.0/32.5, Purge 27.3/28.6). The five *unmodelled*
  missions currently score as Take and Hold (~35) but their real rules are as
  restrictive as (or more than) the modelled ones — several exclude home-zone markers
  entirely. Modelling them faithfully would pull the production mean down by an
  estimated one to two primary victory points, **evenly across factions** (mission
  choice is independent of faction). It would not change the Death-Guard-versus-Orks
  split, because that split is the snapshot mechanism (Component 3), not which markers
  are eligible to score.
- **Component 3** is the residual and the real story. The per-round trajectory is
  flat at ~8.5 in every scoring round including round five (real decays in round
  five). `docs/REAL_META_SIGNATURES.md` records the confound explicitly: "the sim
  always completes five [rounds]; real games sometimes cut at three or four, biasing
  real primary averages slightly downward". The simulator banks four full rounds of
  primary for a durable holder; real games lose late-round primary to attrition,
  concession, and the clock. This is precisely the survivor-snapshot uptime of
  `docs/_DURA_AUDIT_D_DEATHGUARD.md`: Death Guard out-dies its opponents (23.3% vs
  31.9% survival) yet out-scores them on primary (+5.46 overall, +18.70 in wins) with
  a negative secondary margin — the durable pillars are alive at each Command-phase
  snapshot and bank primary the whole game.

Why Component 3 has no faithful Stage-1 fix: the objective contest is faithful
ten-edition "Level of Control" (sum the objective control of models within three
inches; strictly-greater controls — `docs/DURABILITY_OVERREWARD_INVESTIGATION.md`
§2, decision-ledger line 21), the scoring timing is the real per-Command-phase
timing, and the game correctly runs five battle rounds
(`simulator.battle_length_five_rounds`). Lowering a durable holder's late-game
primary would require either nerfing faithful contest math / durability statistics
(explicitly forbidden — the forbidden-zone guardrails, and the retracted-floor
lesson) or modelling real concession / time-limit game-ending, for which there is no
public per-game ground truth to anchor (so it would be a tune-to-win-rate dial). The
clustering and kiting representation levers that target this snapshot were both
already screened and regress (`SWEG_MOVEPLAN` +0.61 worse, `SWEG_CLUSTER` +0.15
worse, `SWEG_KITE` +0.29 worse — decision ledger and `docs/STRUCTURAL_REMODEL_PLAN.md`).

---

## 4. The verdict

**EQUILIBRIUM (pricing floor), not a rules divergence.**

The primary-scoring path is faithful line by line to the printed Chapter Approved
2025-26 / Pariah Nexus rules — correct per-objective value, per-turn cap, per-game
cap, round-one-zero and round-two opening, per-Command-phase timing with the
round-five going-second deferral, and all five modelled missions correct in amounts
and caps. There is no wrong cap, no wrong per-round maximum, no hold-more error, and
no wrong objective count. The ~4.7-primary-victory-point production over-score above
real is **not** a primary-scoring bug. It is:

1. mostly the survivor-snapshot **uptime equilibrium** (the durable pillars are alive
   at every Command-phase snapshot and bank primary through a flat, no-decay,
   always-five-rounds game where real games attrit, concede, and time out — audit D's
   mechanism, expressed through a faithful scoring channel), which has no faithful
   Stage-1 knob; and
2. partly a known, faction-neutral **fidelity-completeness gap** (five of ten deck
   missions scored as holder-friendly Take and Hold), whose faithful completion would
   lower every army's primary roughly evenly and would **not** close the durable
   over-pole.

Because the durable over-pole (Death Guard +17.7, the Knights) is the uptime
equilibrium and not a scoring-rules divergence, and because the simulator's aggregate
scoring is already slightly *under* real (the over-score is a primary/secondary
*mix* shift, not a total inflation), there is **no Stage-1 primary-scoring lever
here.** This is the elite-over-horde equilibrium the points equation exists to price:
the finding **strengthens the pricing-floor / Stage-2 conclusion**.

The single faithful item that falls out — modelling the five unmodelled deck missions
(Linchpin, Burden of Trust, Unexploded Ordnance, Hidden Supplies, Supply Drop) by
their real rules — is a fidelity-completeness build, not a fix for the over-pole. It
is citation-heavy, faction-neutral, and (per `docs/DURABILITY_OVERREWARD_
INVESTIGATION.md` §3.3) blocked behind a fragile-army representation fix that does not
exist; pursue it only as fidelity, never as a lever to move the metric.
