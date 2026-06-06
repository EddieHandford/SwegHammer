# Rule-accurate implementation design for the structural residual fixes (2026-05-30)

Companion to `docs/FACTION_RESIDUAL_ANALYSIS.md` (the "why"). This is the "how",
designed to be **rule-accurate** (faithful to 10e, no fudge factors). Read-only
design — no simulations were run. Three levers, in leverage order.

---

## Lever 1 — Squad-level activation (the dominant fix; ~half the headline MAE)

**Root cause:** one `Unit` per model, so army builders loop
`for _ in range(squad_size): add_unit(profile)` (`army_builder.py:203-205, 229,
258, 541-542`; `archetypes.py:1651-1653`) → N independent Units, and both round
loops iterate per-Unit (`_run_round_vanilla_turns` simulator.py:5903-5951;
`_run_round_alternating` simulator.py:5823-5872). A 69-model Drukhari army gets
69 activations/phase vs a 10-model Knight army's 10 — the 7-9x over-activation.

**Rule:** 10e — a UNIT is selected once per phase; all its models act together
(move maintaining coherency; shoot/fight together; charge as a unit).

**Recommended approach: Option (b), squad-grouping overlay** (not a full
multi-model refactor). Keep one `Unit` per model (so `Unit.attack`,
`receive_damage`, OC/VP summation, transports, reanimation stay untouched and
already-correct), but:
1. Add a stable build-time `squad_id` (distinct per instantiated squad, even for
   two squads of the same datasheet — fixing the current `profile.name`-merge
   limitation).
2. Activate one SQUAD per slot: all its alive members resolve move/shoot/charge/
   fight within that single activation, in queue order by squad.

Full-refactor Option (a) (collapse a squad to one multi-model Unit with pooled
wounds) is faithful but rewrites the combat core (every spatial query, OC/VP,
faction gates) — rejected as too risky for a calibration branch.

**Phased plan (architect):**
- **P1 — squad_id infrastructure (no behaviour change):** `squad_id` slot on
  `Unit` (units.py:627-810); `Army._next_squad_id` + `add_squad(profile, size)` +
  `squads()` cache (army.py:122, 631, 647); convert the 4 builder loops to
  `add_squad`. `add_unit` → `add_squad(.,1)` for back-compat. Tests stay green.
- **P2 — coherent deployment:** rewrite `_deploy_line` (simulator.py:4675) to
  cluster each squad's models adjacently (prerequisite for block movement).
- **P3 — squad-block activation (the decisive edit):** `activation_queue`
  (army.py:740) yields one representative per squad; `_run_round_alternating`
  (5823) pops the next SQUAD per side per pairing and keys `*_activated` on
  `squad_id`; vanilla phases (5903-5951) iterate `squads()`. Decide squad intent
  once (leader) and apply to members.
- **P4 — supersede the `profile.name` band-aids:** re-point Acts of Faith
  (5293), Strands of Fate (6143), `squad_sibling_count` (army.py:670), blast, and
  the per-model amplification dedups to `squad_id` (they become MORE accurate).
- **P5 — re-fit:** this shifts EVERY faction's WR at once (hordes down, Knights
  up). The current 9.27 is fitted around per-model activation, so **expect MAE to
  rise on first eval**; re-fit the archetype lists afterward (the fidelity-first
  re-calibration). Treat first eval as a new baseline, not a regression.

**Rule-accuracy:** faithful to "unit activates once per phase"; no new rule flag,
so no `rule_citations` entry needed (engine representation, not a faction rule).

### P3-contained experiment result (2026-05-31) — overlay is a WASH; need Option (a)

P1 landed proven-neutral (eval 9.27, identical). A **contained P3** was then built
and measured (then reverted, per the user's "measure, don't commit" call): keep
per-model execution intact, but collapse the squad's two independent *decisions* —
move destination+intent and shoot target — to a single per-squad choice (first
member decides, contiguous squad-mates reuse it), cached per phase, injected into
`_do_move` (pick_move_intent override) and `_do_shoot` (target override). All cited
per-model gates preserved; 81 simulator tests green; one battle smoke-clean.

**Result: gated MAE 9.27 → 9.30 (+0.03, a wash).** Faction movement was mixed and
self-cancelling: over-shooters Tyranids −2.5, Sororitas −2.9, Votann −2.0, TSON
−1.7 improved ✓ and Chaos Knights +1.8 improved ✓, BUT **Drukhari got WORSE
(+36.2 → +38.0)** and Imperial Knights worse (−27.1 → −29.0), with World Eaters
+4.0 and Emperor's Children +2.3 worse.

**Why the overlay can't work:** it collapses decisions but **not firepower**. A
69-model Drukhari army still fires 69 models' worth of guns — *concentrating* that
fire merely makes it more efficient (clean kills instead of spread), so a focused
shooty horde gets BETTER, and low-model armies get worse because opponents now
focus their few big models. The shared-decision overlay never taxes horde
fragility because it never reduces the horde's activation count or attack volume.

**Conclusion: the firepower/activation-count half of Lever 1 requires the full
Option (a) refactor** — a squad becomes ONE `Unit` whose attack volume scales with
surviving models but resolves once per phase — NOT the Option (b) overlay. Option
(b)'s squad_id (P1) is still the right substrate (grouping, blast, dedups), but the
decisive MAE move needs pooled-wound single-Unit squads. That is the larger rewrite
the design originally rejected as "too risky for a calibration branch"; the
empirical wash here is the evidence that the cheaper overlay is not a substitute.
Eval artifacts: `data/wf_wave65_p1_n40.json` (neutral), `data/wf_wave65_p3_n40.json`
(the +0.03 wash).

### The actual firepower fix (2026-05-31) — damage-allocation spillover — LANDED

The overlay wash pointed at the real mechanism, which a user question then made
explicit: **the sim never allocated damage across a unit's models.** `Unit.attack`
dumped a whole volley into the single targeted model (`receive_damage` at the old
`units.py:3227`), so a Knight firing a 12-shot anti-horde gun into a 20-model brood
killed exactly ONE model and wasted the rest. That — not activation count — is the
dominant driver of the Knight under-shoot and the horde over-shoot.

Fix (rules-correct, `simulator.damage_allocation_spillover`): an allocation pointer
in `Unit.attack` that starts at the target model and advances to the next surviving
same-`squad_id` model only when the current one dies. Each unsaved wound deals the
Damage characteristic to the current model; a killing blow's **excess is lost** (10e:
"any excess damage inflicted by that attack is lost and has no effect"); the next
unsaved wound moves to the next model ("must allocate further attacks to that model
until either it is destroyed, or all the attacks have been saved or resolved"). So
**kills are bounded by the number of unsaved wounds, never the damage total** — three
unsaved wounds of Damage 6 destroy at most three one-wound models. Devastating Wounds
is a save-bypassing NORMAL hit under the same rule (excess lost), NOT a mortal wound;
true mortal wounds (which DO carry over) are a separate mechanic and are deliberately
not routed through this pointer. Lone models (`squad_id < 0`) have no siblings, so
behaviour is unchanged for them. Verified by instrumented tests: `killed ==
allocations` across ~40 trials, never more (excess never spills); a 3-attack weapon
kills at most 3 one-wound models regardless of per-shot damage.

**Result: gated MAE 9.27 → 7.78 (−1.49), raw 12.80 → 11.15.** Moved exactly the
structural-residual factions: Tyranids +16.8 → +6.4 (−10.4), Imperial Knights −27.1
→ −19.1 (+8.0), Orks +12.5 → +5.3, Drukhari +36.2 → +29.0, Chaos Knights −41.3 →
−36.5, AdMech +11.9 → +7.3. Some elite/MEQ armies drifted further over (Custodes,
Marines, Thousand Sons, Aeldari) because they now clear chaff more efficiently — a
second-order effect to chase with a later re-fit. 912 tests green; citation clean
(279/279). Eval artifact: `data/wf_wave65_spillover_n40.json`.

**This is the real Lever 1 win** — it needed the firepower/allocation rule, not the
activation overlay, exactly as the wash predicted. P1's `squad_id` is the substrate
that made it a small, contained change.

---

## Lever 2 — VP / positional credit (root cause 2)

**Finding: the win condition is ALREADY rule-accurate.** `_decide_winner`
(simulator.py:578) = tabled→loss, else higher VP, then remaining points;
"survivor count is no longer a primary criterion." Objective scoring is OC-based
with sticky objectives + the 15-VP/round primary cap. **So there is NO scoring
change to make here** — the VP model is correct.

The reason Knights/Daemons still under-shoot is that the BOARD STATE feeding the
correct scoring is wrong: (a) Lever-1 activation count lets hordes out-contest
and table low-model armies; (b) the AI doesn't *play* for objectives/positioning
(threat-tax, deepstrike pressure, screening). So Lever 2's implementation is:
- **Lever 1 (above)** fixes the board-state half.
- **The plan-level objective AI (task #12)** fixes the play half — a next-turn
  reachable-OC objective function feeding intent + activation order. Already
  scoped; it is rule-accurate (it optimises toward the existing correct VP rules,
  not a new mechanic). No scoring/citation change.

**Net: no rule-accuracy work needed on scoring; the lever is Lever 1 + #12.**

---

## Lever 3 — Thousand Sons Cabal (faction-mechanic over-model; smaller, MAE-down)

**Finding (verified):** the Cabal engine already dedupes casters per-squad, caps
each ritual once/turn, and runs a 2D6 psychic test (simulator.py:3790-3967). All
Is Dust is correctly gated (D1 + RUBRICAE only). Twist of Fate / Destiny's Ruin
are no-ops. The ONLY damage ritual, **Doombolt**, fires with **no range/LoS
check** — `_cabal_resolve_ritual` (simulator.py:3980-4004) picks
`_highest_threat_enemy(opponent)` regardless of the psyker's position, despite
Doombolt being "an enemy unit **within 24"**".

**Rule-accurate fix:** gate Doombolt's target to the highest-threat enemy
**within 24" and line of sight** of the casting psyker (use the map LoS + range);
if none in range, the ritual finds no target and deals no damage (rather than
auto-hitting the best enemy anywhere on the board every round). Faithful to the
codex range restriction; reduces TSON's unconditional ~2-5 mortal-wounds/round →
MAE-down (TSON over-shoots +19).

**Verify before touching:** confirm the current codex cadence — one ritual per
PSYKER per turn (the sim's model) vs one per ARMY per turn (a possible post-Q3
nerf flagged in the research). If per-army, additionally cap total manifestations
to 1/turn. Do not change the cadence without confirming the live rule (§10).

**Do NOT** implement Twist of Fate / Destiny's Ruin (currently no-ops) — they'd
make TSON over-shoot worse; leave them parked.

---

## Sequencing & the meta-caveat

1. **Lever 3** (TSON Doombolt range gate) is the only one landable as an
   isolated MAE-down wave under the current MAE-first gate — small, rule-accurate.
2. **Levers 1 + 2** are the structural rebuild. Lever 1 is a 5-phase build that
   **will raise MAE on first eval** and requires a subsequent archetype-list
   re-fit (the fidelity-first path — see `project-ai-frozen-under-mae-first` and
   `project-calibration-surface`). It cannot be judged by the MAE-first
   "non-regressor" gate mid-build; it's a deliberate two-stage project.
3. All three are rule-accurate by construction (no fabrications): Lever 1 mirrors
   "units activate once," Lever 3 mirrors Doombolt's 24" range, Lever 2 needs no
   rule change (scoring already correct).
