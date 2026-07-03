# Pilot-loop findings — can good piloting bring the under-pole to its real win rate?

Continuous experiment (user goal, 2026-06-27): pilot the UNDER-pole by hand against
the AI over-pole, find tactics that lift its win rate toward the real (Warp Friends)
rate. Frame the user set: **under-pole-only / asymmetric is fine** (an upper-bound
study of how far piloting can close the gap); **single matchup** for fast iteration;
**switch to the next under-pole when the target is hit or tactics are exhausted**;
**harness-only — no edits to `strategy.py`/`simulator.py`**, just a ranked playbook.

Tool: `scripts/pilot_manual.py` wraps the AI's `pick_move_intent` and
`pick_charge_target` for army A only (army B keeps the real AI). Paired on seed
(the sim is deterministic once the global RNG is seeded per game), so a tactic's
effect reads as win-flips vs the baseline.

## Real win-rate goalposts (data/warpfriends_rolling.json)

| Under-pole | real win rate | notes |
|---|---|---|
| Astra Militarum | **45.28%** | dominant sim under-pole; durability-in-contest wall |
| Chaos Knights | 44.71% | sim under-pole, same chassis as the IK over-pole |
| Leagues of Votann | 48.04% | |
| Drukhari | 52.36% | sim under-pole but a real OVER-pole — mobile glass cannon, likely the most piloting-sensitive |
| Aeldari | 41.55% | lowest real rate of any faction |

Over-pole reference: real Imperial Knights is only **47.71%** — barely over 50 in
reality; the sim's IK over-pole is itself the artifact under study.

## Method note (a real lesson, banked)

The first attempt used a non-deterministic harness (the sim's combat uses the
GLOBAL `random` module; it was not re-seeded per game, so the same seed run twice
diverged). The `all-off == baseline` self-check (0 flips) caught it — the same
byte-identity discipline the eval protocol enforces. Fixed by `random.seed(seed)`
per game. **The earlier N=16 matrix (charge +6, heavy -19, contest -6) was measured
on the buggy harness and is discarded; all numbers below are from the clean,
deterministic, paired harness.**

## Matchup 1 — Astra Militarum vs Imperial Knights (target 45.28%)

Baseline (AI pilots both): **A win 25%** (the render shows 63 AM models clumped in
the home corner holding 2 markers while 8 Knights hold 3 — Centre/NW/NE — almost
entirely uncontested; the move log shows AM at OC 0 on NW/NE all game).

Tactics under test (paired battery, results pending the N=40 run):
- `charge_durable` — decline charges into Knight-class (toughness >= 9).
- `charge_futile` — decline charges that can't remove even one model
  (`_kill_potential_wounds` < target per-model wounds).
- `heavy_hold` — artillery holds and shoots instead of advancing (re-test; the
  buggy-harness reading was a crater — needs clean confirmation).
- `contest_spare` / `surgical_contest` — spare backfield units push to a contested
  marker (surgical = only markers one body flips).
- `screen_home` — a spare unit reinforces our nearest held marker that an enemy is
  approaching (early N=8 read: net +1 win — most promising so far).

Blocked tactic: **shoot-focus** (kill the cheap Armigers holding NW/NE rather than
wasting fire on the Castellan) is the theoretically strongest lever but the shoot
target selection is inline in `_do_shoot` with no hookable function — it would need
a `simulator.py` refactor, which the harness-only frame forbids. Recorded for the
"propose" pile. (Note: the AI shoot picker already biases toward objective-
contesters + lowest-HP, so it is less naive than the raw move log suggested.)

### Result — clean paired N=40 (`data/_pilot_loop_am.txt`)

Baseline A win 22.5% (9/40). `all-off` reproduced it at 0 flips (determinism OK).

| Tactic | A win% | Δpp | L→W | W→L |
|---|---|---|---|---|
| charge_durable | 22.5 | +0.0 | 0 | 0 |
| charge_futile | 22.5 | +0.0 | 0 | 0 |
| heavy_hold | 7.5 | −15.0 | 1 | 7 |
| contest_spare | 17.5 | −5.0 | 4 | 6 |
| surgical_contest | 22.5 | +0.0 | 1 | 1 |
| screen_home | 20.0 | −2.5 | 6 | 7 |
| stacks (cd+futile+screen, etc.) | ≤20.0 | ≤−2.5 | 6 | 7 |

**Conclusion: movement+charge piloting cannot lift Astra Militarum vs Imperial
Knights.** Nothing nets positive. Key corrections to the earlier (buggy-harness)
read: **charge-decline is INERT** (0 flips — the Death Riders bouncing off the
Castellan look like a misplay but flip zero games); `heavy_hold` cleanly craters
(the AI's tank movement is good, not wasteful); `screen_home`/`contest` are
*active* (flip ~13 games) but **symmetrically** (~6 won / ~7 lost), netting
negative — the "good play is over-pole-favouring" effect, reproduced cleanly. The
one lever that could plausibly help (shoot-focus) is blocked by the harness-only
frame. **AM-vs-IK exhausted; the under-performance is the structural
durability-in-contest wall, not a movement/charge piloting gap.**

## Matchup 2 — Drukhari (target 52.36%, sim aggregate ~44.8%)

Drukhari is a real OVER-pole (52.36%) but a sim under-pole — a mobile glass cannon
whose under-rating is far more likely a real piloting gap than a structural wall.

**Methodology correction (important).** Drukhari vs Imperial Knights baselines at
**77.5%** (`data/_pilot_loop_drukhari.txt`) — Drukhari CRUSHES Knights in the sim.
So vs-IK is NOT a valid under-pole test for Drukhari: its aggregate under-rating
comes from its BAD matchups, not IK. **A single-matchup test only works if the
matchup is one where the faction genuinely under-performs.** Added a `scan` mode to
`pilot_manual.py` to find each under-pole's worst matchup before running the battery.

Side-finding from the IK run (kept): **`screen_home` nets +5pp / +2 wins for
Drukhari** (5 L→W, 3 W→L, +7 mean VP) — the FIRST lever to net positive anywhere.
It reinforces a held marker an enemy is approaching; it helps a *mobile* army
(which can spare a body to defend) where it did nothing for the AM gunline. Worth
re-testing on Drukhari's real bad matchup.

### Worst matchup found (scan, `data/_pilot_scan_drukhari.txt`)

Drukhari baseline win%: vs Astra Militarum 93.8, Chaos Space Marines 68.8, Necrons
62.5, Imperial Knights 62.5, Leagues of Votann 56.2, World Eaters 56.2, Tyranids
50.0, T'au 43.8, Adeptus Astartes 43.8, **Adeptus Custodes 31.2 (worst)**. The
under-rating lives in the durable-elite matchups.

### Result — Drukhari vs Adeptus Custodes, clean paired N=40 (`data/_pilot_loop_dru_custodes.txt`)

Baseline 35.0%. **FIRST positive tactics found:**

| Tactic | A win% | Δpp | L→W | W→L |
|---|---|---|---|---|
| kite | 10.0 | **−25.0** | 1 | 11 |
| charge_durable / charge_futile | 35.0 | +0.0 | 0 | 0 |
| contest_spare | 35.0 | +0.0 | 7 | 7 |
| **surgical_contest** | 42.5 | **+7.5** | 6 | 3 |
| **screen_home** | 42.5 | **+7.5** | 7 | 4 |
| kite + anything | ≤22.5 | ≤−12.5 | — | — |

**`kite` is refuted hard (−25pp)** — fleeing melee cedes objectives; the glass
cannon must PLAY objectives, not run. The winners are **aggressive objective
micro**: `surgical_contest` (move a spare body to a marker one body flips) and
`screen_home` (reinforce a held marker an enemy approaches), each +7.5pp / +3 net
wins. A MOBILE army can execute these where the AM gunline could not — so the
pilot lever that lifts an under-pole is **mobility-for-objectives**, faction-shape
dependent. `charge_*` inert again; blind `contest_spare` net-zero (surgical beats
it). Next: do surgical+screen STACK, hold at higher N, and generalize to Drukhari's
other bad matchups (T'au, Astartes)?

### Result — same matchup, N=60: THE N=40 SIGNAL WAS NOISE (`data/_pilot_dru_cust_n60.txt`)

Baseline 38.3%. The "+7.5pp winners" wash out:

| Tactic | A win% | Δpp | L→W | W→L |
|---|---|---|---|---|
| surgical_contest | 40.0 | +1.7 | 7 | 6 |
| screen_home | 38.3 | +0.0 | 8 | 8 |
| surgical+screen | 40.0 | +1.7 | 10 | 9 |
| screen+contest | 30.0 | −8.3 | 7 | 12 |

The flip counts are the finding: the tactics are **very active** (8–10 games flipped
EACH way) but **symmetric** — net ≈ 0. **The N=40 +7.5pp was a favourable noise
draw.** This is the SAME symmetric-flip pattern as AM: piloting reshuffles WHICH
games are won, not HOW MANY. **Methodology lesson banked: N=40 is too small for a
~38% high-variance matchup; trust nothing under N≈100.** Running an N=100
confirmation on the best contenders to settle whether any small robust effect
survives.

### Result — same matchup, N=100: CONFIRMED WASH (`data/_pilot_dru_cust_n100.txt`)

Baseline 39.0%. `surgical_contest` −4.0 (9 L→W / 13 W→L); `screen_home` **+0.0
(13 / 13 — perfectly symmetric)**; `surgical+screen` +2.0 (16 / 14 = noise). The
objective-micro tactics flip ~25–30% of games but symmetrically — **net zero**.

---

## Overall conclusion (matchups 1–2)

**Piloting the under-pole via the available movement + charge levers does NOT
net-lift its win rate.** Tested on two opposite army shapes — a static gunline
(Astra Militarum vs Imperial Knights) and a mobile glass cannon (Drukhari vs
Adeptus Custodes) — at N = 40 / 60 / 100. Every tactic either does nothing or
flips many games **symmetrically** (wins ≈ losses), netting ≈ 0.

**The mechanism is the finding:** if the AI were systematically MIS-piloting the
under-pole, a better pilot's fixes would net positive. They don't — they reshuffle
WHICH games are won, not HOW MANY. So there is **no systematic piloting gap to
close**; the under-pole's low win rate is structural (representation / matchup),
not a piloting deficiency. This independently confirms the wave-260 self-veto
(durable over-holds are 80% uncontested, a representation gap) from the opposite
direction — a human pilot trying hard and failing to out-play it — and explains why
the project's `SWEG_ADVANCE_DISCIPLINE` / `SWEG_CHARGE_DISCIPLINE` pilot gates
regress the calibration metric (symmetric / over-pole-favouring play).

**Refuted "obvious" misplays (clean, at adequate N):**
- `charge_decline` (don't bounce chaff/characters off Knights) — **inert** (0 flips).
  The futile charges look wrong but flip no games; keeping the bodies alive changes
  nothing. (The earlier "+6pp" was buggy-harness noise.)
- `heavy_hold` (artillery holds + shoots instead of advancing) — **−15pp**. The AI's
  tank movement is genuinely good; freezing it craters the army.
- `kite` (glass cannon flees melee) — **−25pp**. Fleeing cedes objectives; a mobile
  army must PLAY objectives, not run.

**Method discipline banked:** the global-RNG determinism bug (caught by the
`all-off == baseline` 0-flip self-check) and the N=40→N=100 noise collapse — trust
nothing under N≈100 in a high-variance matchup.

**The one untested lever that could break symmetry: shoot-focus** — concentrate the
under-pole's fire to KILL the durable army's cheap objective-holders (the Armigers /
elite squads sitting uncontested on markers), attacking the structural over-hold
directly rather than trying to out-position it. It is BLOCKED by the harness-only
frame (target selection is inline in `simulator._do_shoot`, no hookable function);
testing it would require editing `_do_shoot`. This is the top item on the
"propose / needs-unblocking" pile.

**Status:** matchups 1–2 exhausted for movement/charge; piloting is confirmed not
the under-pole gap *via those levers*. The one untested lever (shoot-focus) was
then unblocked — see below.

## Shoot-focus (user unblocked the harness-only frame for this one lever)

Added a minimal, default-OFF, byte-identical hook in `simulator._do_shoot`
(`Battle._pilot_focus`, set only by the harness; production never sets it →
unchanged; `all-off` self-check stays 0 flips). The tactic: army A targets the
**most-wounded enemy objective-holder ANYWHERE** — including the durable army's own
uncontested home markers, which the AI picker never shoots (it only focuses
contesters of OUR markers). Removing the uncontested holder attacks the structural
over-hold directly.

### Result — Astra Militarum vs Imperial Knights, N=100 (`data/_pilot_am_shootfocus_n100.txt`)

Baseline 22.0%.

| Tactic | A win% | Δpp | L→W | W→L |
|---|---|---|---|---|
| **shoot_focus** | 25.0 | **+3.0** | **3** | **0** |
| surgical+screen | 20.0 | −2.0 | 12 | 14 |
| shoot_focus+surgical+screen | 20.0 | −2.0 | 12 | 14 |

**FIRST asymmetric lever: `shoot_focus` is +3.0pp with 3 L→W and 0 W→L — purely
one-directional.** Every movement/charge tactic flipped games symmetrically (net
~0); this one only ever helps, because it attacks the structural over-hold directly
instead of reshuffling position. Small (+3pp) but real. It must run **alone** —
combined with the washy movement tactics it drops to −2.0 (their symmetric churn
drowns the gain).

### Confirmation + ceiling

- **AM vs IK, N=200:** baseline 26.0% → shoot_focus **28.5% (+2.5pp), 5 L→W / 0 W→L**
  — asymmetry CONFIRMED robust.
- **Tight army-level focus (all guns concentrate one holder), N=200:** identical
  (+2.5pp, 5-0) — the per-gun version already converges on the same weakest holder,
  so **+2.5pp is the hard ceiling.**
- **Drukhari vs Custodes, N=100:** shoot_focus −1.0 (1 flip) — **INERT.** Drukhari's
  short range can't reach Custodes' backfield holders. Shoot-focus is **reach-gated**:
  it needs guns that can hit the uncontested holders (AM's artillery / indirect fire),
  which a short-ranged army lacks.

---

# FINAL ANSWER — can piloting bring the under-pole to its real win rate?

**No.** A skilled pilot, trying every available lever across two opposite army
shapes at N up to 200, cannot close the under-pole gap:

| Lever class | Effect | Why |
|---|---|---|
| Movement (contest / screen / kite / heavy-hold) | **symmetric wash, net ≈ 0** (or worse) | flips many games each way; no systematic AI mis-pilot to fix |
| Charge (decline durable / futile) | **inert** | the futile charges flip 0 games |
| **Shoot-focus** (kill uncontested holders) | **+2.5pp, asymmetric** | the ONLY genuinely-positive lever — attacks the structural over-hold directly |

Against AM's ~20pp gap (26% → real 45%), the best lever closes ~1/8 of it, and only
for a long-ranged faction. **The under-pole gap is structural (representation), not a
piloting deficiency** — confirmed from the opposite direction (a human pilot failing
to out-play it), corroborating the wave-260 self-veto and explaining why the
`ADVANCE`/`CHARGE_DISCIPLINE` pilot gates regress the metric.

## The one portable, propose-to-AI candidate

**Extend the AI shoot-target picker to also target the enemy's uncontested
objective-holders** (enemies on the enemy's OWN markers), not just contesters of our
markers. Small (+2.5pp), asymmetric (no measured downside), faithful, reach-limited
to ranged factions. The default-off `Battle._pilot_focus` hook in
`code/simulator.py:~12152` is the experimental implementation (byte-identical off,
UNCOMMITTED). To productionise it would mean folding the "shoot any objective-holder"
bias into `_do_shoot`'s picker as a gated lever and screening it via the calibration
metric (it may also help over-poles, so the net metric effect needs measuring) — a
Stage-1 calibration task, not a harness experiment. Left for review per the
no-commit rule.

## Harness + artifacts
`scripts/pilot_manual.py` (paired, deterministic, self-checking loop engine with
`scan` mode); raw runs in `data/_pilot_*.txt`.

---

# Anti-Knight strategy experiment (researched real playbooks vs Imperial Knights)

User asked to research real competitive anti-Imperial-Knights tactics for under-pole
factions and play them. The StatCheck per-matchup data first localized the real
losers vs Knights: **Astra Militarum and Chaos Knights** (the only under-poles the
sim has losing to Knights; see the sim-vs-StatCheck table — both ~−27 vs real,
`scripts/diag_log_vs_ik.py`). Researched playbooks (workflow `anti-knight-research`,
sourced from Goonhammer / Wahapedia / tabletopbattles): all three factions share
**absolute focus-fire on one Knight** + **exploit the low activation count (flood
objectives)** + **melee the Knight where its 5++ is ranged-only**.

Implemented as harness levers (re-added a default-off `Battle._pilot_focus` shoot
hook): `anti_knight_shoot` (concentrate ANTI-TANK fire on the most-damaged big Knight,
toughness>=11; anti-infantry weapons defer), `force_melee_knight` (melee units charge
the Knight — the no-melee-invuln exploit), plus the existing contest/screen/charge.

**Invuln mechanism check (the melee exploit is data-supported):** the sim correctly
models the Ion Shield as ranged-only — core Questoris (Castellan, Valiant, Crusader,
Paladin) carry `invuln_save_melee=7` (none) / `invuln_save_ranged=5`, gated
`SWEG_COND_INVULN` default-on. So melee bypasses the Knight's invuln. **Datasheet
anomalies queued for the over-credit pass:** Cerastus Knight Acheron has NO invuln
(`inv_ranged=7` — missing Ion Shield); Knight Defender / Acastus Knights carry a
melee invuln (`inv_melee=4/5`) they likely should not.

### Results (paired, N=80 then N=160 confirm)

**Astra Militarum vs IK — WASHES.** Baseline 23.8%. `focus_knight` −2.5,
`AM_full` +0.0 (11 L→W / 11 W→L, symmetric). AM cannot crack Knights with focused
fire, so forcing its guns onto the durable Knight wastes them; its vs-Knights deficit
is the structural durability-in-contest wall, not a tactical gap.

**Chaos Knights vs IK — a real, modest lift.** Baseline ~26-30%. At N=160:
`focus_knight` **+3.1pp, asymmetric 7 L→W / 2 W→L** (confirmed). `force_melee` adds
nothing on top (the AI already engages); contest just adds churn (CK_full +3.1, 14-9).
**The whole lift is concentrating anti-tank fire on one Knight** — and the SAME lever
*hurt* AM, because Chaos Knights can actually crack a Knight with focused fire and AM
cannot. A faithful, sensible result, but it closes only ~1/7 of the gap to real (CK
real vs IK 53%); the bulk of Chaos Knights' −27 deficit is structural (composition /
durability-in-contest, per the decision ledger).

**Verdict:** real anti-Knight tactics partially work where the faction has the tools
to crack Knights (Chaos Knights focus-fire, +3pp asymmetric) and wash where it does
not (AM, structural). The generic AI under-commits to focus-fire for the faction that
benefits — a small, real, faction-specific gap — but neither closes the structural
divergence the StatCheck comparison localized. (`data/_ak_strategies.txt`,
`data/_ak_ck_confirm.txt`.)

### CORRECTION — the pilot harness was UNFAITHFUL to the calibration (2026-06-28)

`pilot_manual._winner` decided the winner on RAW victory points and used the DEFAULT
primary mission — but the calibration (`scripts.evaluate_vs_meta._play_pairing`)
rotates a CA-2025-26 PRIMARY MISSION per game and decides via the sim's official
`BattleResult.winner`. This made harness win rates diverge from the anchor log by
20+ points (e.g. Votann-vs-IK read 59% raw-VP vs 40% faithful/anchor). FIXED:
`_winner` now seeds + rotates the mission + returns `r.winner`. Validated: Votann
40.0% (anchor 40), Drukhari 52.5 (51), AM 15 (19) — now within a few points (the
residual is the exact pair_seed→mission scheme). **All pre-fix absolute pilot numbers
are raw-VP; the paired deltas stay valid but were re-run on the faithful frame.**

**Faithful re-test (N=80, then Chaos Knights confirmed N=160):**
- **Chaos Knights anti-Knight strategy: +6.9pp (27.5 → 34.4, asymmetric 18 L→W / 7
  W→L, N=160).** Bigger than the raw-VP harness showed (+3.1). The drivers are
  `force_melee_knight` (War Dog Karnivores melee the Knight, bypassing the ranged-only
  5++) + objective contest. Closes ~1/3 of the gap to real (53%). The one large
  tactical gap the AI misses.
- All other tested factions WASH or HURT: Leagues of Votann −6.2, Thousand Sons −3.8,
  Drukhari −2.5, Chaos Space Marines +0.0. The anti-Knight battery helps ONLY Chaos
  Knights. (`data/_ak_faithful.txt`, `data/_ak_ck_faithful_n160.txt`.)

---

# Productionising shoot-focus as a calibration lever (`SWEG_SHOOT_HOLDERS`)

User authorised taking the one positive lever into the AI and screening it on the
calibration metric. Replaced the experimental `Battle._pilot_focus` hook with a
gated, all-armies lever `SWEG_SHOOT_HOLDERS` in `code/simulator.py` `_do_shoot`
(default-OFF, byte-identical off).

**Adversarial verification first (5-agent workflow `verify-shoot-holders`), before
spending the N=80 screen — and it earned its keep:**
- Byte-identity off: confirmed definitively (the `== "1"` clause short-circuits).
- **Scope flaw caught (high severity):** the first cut placed the gate at priority 0,
  overriding the default-ON anti-armour focus-fire (`SWEG_FOCUSFIRE`) and squad
  split-fire for BOTH armies. Symmetrically that **wastes anti-tank** — T'au Railguns
  / AM Demolishers / Imperial Knights Titanic guns redirected onto 1-wound chaff
  holders (overkill), degrading shooting factions and indirectly inflating
  durable-brick factions (Tyranids, Necrons, Chaos Space Marines).
- **Ledger prediction:** this is in the EXHAUSTED on-table lever family —
  `SWEG_FOCUS_MELEE` rejected (Astartes −9.7 / T'au −5.0), threat-priority targeting
  wrong-direction (wave 189), wave 260 proved the over-pole structural. Prior work
  predicts **wash or wrong-direction**.
- Citation: not needed for a screen (default-off, not in `audit_rules` keys); only
  if adopted.

**Corrected design (the screened version):** the gate now fires only for
**non-anti-armour weapons** (`not _is_antiarmour_weapon`) — bolters/lasguns clear
chaff holders off markers, while anti-tank weapons fall through to focus-fire and
keep cracking durable bricks. This preserves the holder-clearing benefit without the
anti-tank misdirection.

**Both-off validation:** gate-off paired vs sc17a — **0 flips across all 22
factions, gated MAE delta +0.00** (`data/_sh_screen.txt`). The tree reproduces the
anchor exactly; byte-identity confirmed (and variant-independent, so it covers the
corrected gate too).

**Screen result — REJECTED (`data/_sh_c_paired.txt`, N=80 paired vs sc17a):**

**gated mean absolute error 3.45 → 3.61, delta +0.16 — WRONG DIRECTION.**

| Decisive mover | Δ | reading |
|---|---|---|
| Death Guard | +1.83 UP | durable-brick over-pole inflated further |
| Chaos Space Marines | +1.62 UP | durable-brick over-pole inflated further |
| Genestealer Cults | −1.22 DOWN | |

The durable-brick factions (Death Guard, Chaos Space Marines, Necrons +1.1, Tyranids
+1.5) rose — their bricks survive because opponents now shoot chaff holders off
markers instead. The under-poles did **not** lift: Astra Militarum −0.2 (flat),
Drukhari −1.2 (down), Chaos Knights flat, Leagues of Votann −0.6. **The +2.5pp
army-A-only pilot gain did not survive symmetric application** — applied to both
sides, the durable factions exploit it MORE (the same over-pole-favouring asymmetry
that defeats every on-table AI lever, waves 251/260). Exactly the ledger prediction.

**Disposition: gate DELETED** (reverted `code/simulator.py` to the original picker,
restoring byte-identity; housekeeping rule — no rejected gates left default-off). The
experimental `Battle._pilot_focus` hook is gone too.

## Final verdict of the whole investigation

Piloting cannot bring the under-pole to its real win rate. Movement/charge tactics
wash symmetrically; the one asymmetric lever (shoot uncontested holders) gives a
small army-A-only gain that **regresses the calibration metric when applied
faithfully (symmetrically)**, because clearing chaff protects durable bricks. The
under-pole gap is **structural (per-model representation)**, independently confirmed
three ways: the wave-260 self-veto, a human pilot failing to out-play it, and now a
faithful productionisation of the best lever regressing the metric. The on-table /
AI-piloting lever family is exhausted (consistent with the standing ledger
conclusion). The remaining addressable work is **not** a representation re-model —
that phrase was retired 2026-06-28 (see `docs/STRUCTURAL_REMODEL_PLAN.md` top block:
the squad-frame piece is done, the clustering piece is built and predicted to wash,
and the load-bearing piece was never defined). The genuinely open lead is the
going-first / per-round-tempo over-reward (`SWEG_KITE`, built, unscreened), not a
piloting or representation fix.

---

# Batch 2 — faction loop (anti-Knight pilot + fabrication audit)

Continuation of "find a strategy, test it, watch for fabrications" across the
remaining factions. Pilot harness is the faithful `scripts/pilot_manual.py`
(mission rotation + `BattleResult.winner`, paired Common Random Numbers).

## Pilot sweep vs Imperial Knights (`data/_ak_batch2.txt`, N=80)

| Under-pole (piloted) | Baseline win% vs Knights | best tactic delta | reading |
|---|---|---|---|
| Orks | 50.0 | all −1.2 | structural wash |
| Genestealer Cults | 62.5 | −7.5 to −8.8 | already *over*-performs vs Knights; tactics hurt |
| Tyranids | 63.8 | +1.2 / +0.0 | wash; also over-performs |
| Astra Militarum | 18.8 | −1.2 / +0.0 | wash even at the most extreme under-pole |
| Grey Knights | 50.0 | −5.0 | tactics actively regress |
| Adeptus Mechanicus | 61.2 | +2.5 | tiny gain, but already over-performs (61%) |

Same verdict as batch 1: movement/charge/focus tactics **wash or regress**
symmetrically. No batch-2 faction shows a Chaos-Knights-style real, useful gap
(Chaos Knights +6.9pp remains the lone exception). The two small positives
(Tyranids +1.2, Adeptus Mechanicus +2.5) land on factions that *already*
over-perform vs Knights (63.8%, 61.2%) — they are not under-poles in this matchup,
and the gain is the same magnitude as the army-A-only artifact that did not survive
symmetric application (`SWEG_SHOOT_HOLDERS`, rejected). Note several "under-poles
overall" are actually **over-poles specifically vs Imperial Knights** in the sim
(Genestealer Cults 62.5%, Tyranids 63.8%, Adeptus Mechanicus 61.2%) — the
body/durable-objective factions beat the single big Knight in the survivor-snapshot
contest. Consistent with durability-in-contest.

## Fabrication audit — systematic findings

Approach this time was mechanical-first (enumerate every fabrication-prone flag
catalogue-wide, then verify the anomalies against Wahapedia) rather than per-unit.

**Negative results (important — the broad heuristics are mostly *correct data*):**
- **Duplicate top-level keys in `data/overrides.json`:** exactly one
  (`chaos_space_marines_legionaries`, the veterans-of-the-long-war drop already
  gated as `SWEG_CSM_VETERANS`). That fabrication class is fully covered.
- **Blanket vehicle/infantry invulnerable saves** (88 units at 6++, 270 at 5++,
  384 at 4++): spot-checked Trukk, Battlewagon (Orks), Windriders (Aeldari) against
  Wahapedia — **all real** (10e handed most vehicles a 6++; the mapper read them
  correctly). The "has-a-flag" heuristic is too noisy to be a fabrication signal on
  its own; real fabrications need a per-rule comparison.
- **Asymmetric melee≠ranged invulns:** almost all are the correct ranged-only
  Ion-Shield pattern (every Imperial / Chaos Knight: melee 7, ranged 5).
- **Cadian Shock Troops sticky objective:** **real** ("Shock Troops" datasheet
  ability) — correctly modelled, not a fabrication.

**THE big finding — systematic prose-walk Feel No Pain leak (mapper `extract_fnp`
fallback path 3).** When a unit has no canonical Feel No Pain infoLink and no
"Feel No Pain"-named abilities profile, the mapper falls back to a legacy walk that
scans *all* characteristic text for the string "Feel No Pain N+". This pulls the
number out of **leader/bodyguard abilities that grant the save to a *different*
model**, and out of **Crusade Relics / Battle Traits / Crusade Honours** (narrative
upgrade content that is not the matched-play datasheet). The walk prunes
`type="upgrade"` Enhancement subtrees but, by design, still recurses through
`selectionEntryGroup` containers — which is where Crusade content lives. Result: a
unit's personal `fnp` is fabricated. 34 clear leaks across the catalogue
(diagnostic in `data/`); the concentrated, highest-value case:

- **Adeptus Custodes — 30 of 31 datasheets carry a fabricated Feel No Pain** (24 at
  5+++, 1 at 6+++, 5 at 3+++). Custodes have **no base Feel No Pain in 10e matched
  play** (Wahapedia Custodian Guard: no Feel No Pain ability; "Feel No Pain can only
  be granted through specific Stratagems"). The leak source is the Custodes book's
  Crusade Relics / Battle Traits ("The bearer has the Feel No Pain 5+ ability";
  "**Character** models in this unit have the Feel No Pain 5+ ability"). The
  simulator applies `fnp` unconditionally, so this inflates an **over-pole**
  faction's durability by ~17% against *all* damage. The 5×3+++ units are the
  Sisters of Silence Anathema Psykana models, whose real Feel No Pain 3+ is
  **conditional** (vs Psychic Attacks / mortal wounds only) — also a fabrication
  when modelled unconditionally (the phantom-proactive-FNP class).
- **Other clear personal-stat leaks** (FNP belongs to a different model than the one
  carrying it): Death Guard **Deathshroud Terminators** fnp 4 (Silent Bodyguard →
  the *leader* gets it); Necrons **Cryptothralls** fnp 4 (Bound Creation → the
  *Cryptek* gets it); Tyranids **Tyrant Guard** fnp 5 (Guardian Organism → the led
  *Character* gets it); Genestealer Cults **Locus** fnp 4 and Ynnari **The Visarch**
  fnp 4 (Bodyguard → *other* Characters get it); Adeptus Mechanicus **Kastelan
  Robots** fnp 4 (Robotic Bodyguard → the *Datasmith* gets it). Several land on
  over-poles (Necrons 62.4%, Death Guard 57.1%), so removing them should help.

### Gate built and screened — `SWEG_CUSTODES_NO_FAKE_FNP`

`code/units.py` loader gate (default-off, byte-identical off, verified OFF→30
fabricated / ON→0): resets every Adeptus Custodes unit to `fnp=7`. Permanent fix is
in the mapper (prune Crusade/Battle-Trait subtrees in `extract_fnp`, model
conditional Feel No Pain as conditional); this gate screens the effect first.
Screen queued (paired vs sc17a, reusing the standing anchor as the OFF arm per
`docs/EVAL_PROTOCOL.md`); result lands in `data/_cust_fnp_paired.txt`. Hypothesis:
Custodes 57.6% → down toward real, gated mean absolute error improves.

A companion gate `SWEG_FIX_BODYGUARD_FNP` handles the live per-unit bodyguard leaks
(Cryptothralls, Deathshroud Terminators, Locus, The Visarch → fnp 7; Tyrant Guard
and Kastelan Robots were already corrected via `data/overrides.json` in prior waves).
Result lands in `data/_bg_fnp_paired.txt`.

## Screen results

**`SWEG_CSM_VETERANS` (under-model, restores the duplicate-JSON-key-dropped
veterans-of-the-long-war melee reroll) — `data/_csm_paired.txt`, N=80 paired vs
sc17a:** gated mean absolute error **3.45 → 3.42 (−0.04)**, correct direction but
small. Chaos Space Marines itself barely moves (54.7 → 55.0) and is extremely noisy
(ci95 1.83, 125 flips — the melee reroll swings individual games hard). The one
decisive mover is **Death Guard −0.57** — a correct second-order effect: a stronger
Chaos Space Marines beats the factions it fights. Adopt-worthy on **correctness**
(it restores a real cited ability silently dropped by a data bug), with a small
calibration bonus.

**`SWEG_CUSTODES_NO_FAKE_FNP` (over-model, removes the fabricated faction-wide Feel
No Pain) — `data/_cust_fnp_paired.txt`, N=80 paired vs sc17a:** the two metrics
disagree in sign, and the reason is the headline of the result.

| Metric | OFF | ON | delta |
|---|---|---|---|
| **Gated** mean absolute error (noise-floored, the project headline) | 3.45 | **3.32** | **−0.13 (better)** |
| Ungated mean absolute error | 6.31 | 6.47 | +0.16 (worse) |

Adeptus Custodes collapses **57.9 → 46.1** (decisive, −11.8; real Warp Friends target
52.1). So the fix **overshoots**: Custodes' own error is essentially unchanged
(5.8 over → 6.0 under). The gated improvement comes entirely from **coupling** — a
weaker Custodes lifts the genuinely-off under-poles it beats past their noise floors
(Grey Knights err 2.9→1.8, Astra Militarum 18.2→17.6, Drukhari 4.5→3.9, Leagues of
Votann 1.7→1.1), while the factions that worsen (Adepta Sororitas 0.7→1.6, Chaos
Space Marines 1.9→2.7, Thousand Sons 2.5→3.0) move *within* the noise band where the
gated metric discounts them.

**Interpretation — the fabrication was masking a Custodes under-model.** The Feel No
Pain is unambiguously fabricated (Custodes have no base Feel No Pain; confirmed
Wahapedia) and must be removed on correctness grounds. But once it is gone the sim
**under-rates** Custodes by ~6pp — the fake save had been compensating for genuine
Custodes durability/lethality the sim does not capture (2+ save plus 4+ invulnerable
plus high wounds plus Martial Ka'tah melee). The clean two-part fix is: remove the
fabrication **and** find the real missing Custodes durability so it lands near 52,
not 46. Adopting the gate alone is gated-metric-positive and correctness-positive but
leaves Custodes overshot — a user adoption call, not an auto-adopt.

**`SWEG_FIX_BODYGUARD_FNP` (over-model, removes 4 live bodyguard Feel No Pain leaks)
— `data/_bg_fnp_paired.txt`, N=80 paired vs sc17a:** the cleanest of the three —
**both** metrics improve and there is no overshoot.

| Metric | OFF | ON | delta |
|---|---|---|---|
| Gated mean absolute error | 3.45 | 3.40 | −0.05 |
| Ungated mean absolute error | 6.31 | 6.28 | −0.03 |

Both intended targets are big over-poles and move toward real: **Death Guard
56.9 → 56.4** (real 46.1, error 10.8→10.3) and **Necrons 62.9 → 62.7** (real 53.2,
error 9.7→9.5). Magnitude is modest because Cryptothralls / Deathshroud appear in
only a fraction of the sampled archetype armies. Adeptus Custodes ticks up +0.55
(coupling — its weakened opponents). No overshoot anywhere. Adopt-worthy on both
correctness and calibration.

## Consolidated scorecard (screened paired vs sc17a anchor)

| Change | Class | Gated MAE Δ | Ungated MAE Δ | Verdict |
|---|---|---|---|---|
| Legionaries veterans (`SWEG_VETERANS` already default-on) | under-model (dropped real ability) | −0.04 | ~0 | adopt on correctness |
| `SWEG_FIX_BODYGUARD_FNP` | over-model (4 bodyguard leaks) | **−0.05** | **−0.03** | **clean adopt** |
| `SWEG_CUSTODES_NO_FAKE_FNP` | over-model (30-unit faction-wide leak) | **−0.13** | +0.16 | correct; overshoots → pair with a Custodes under-model fix |

All three remove genuine data fabrications or restore genuine dropped rules; none is
a behavioural invention. The bodyguard correction is unconditionally good; the
Custodes correction is the biggest gated-metric mover and the most informative (it
exposes a masked under-model).

## Adopted (2026-06-28)

Per user instruction ("adopt, note the undermodel for later, audit the others"), all
three corrections are now live by default:

- **Chaos Space Marine Legionaries veterans-of-the-long-war**: the two duplicate
  `chaos_space_marines_legionaries` keys in `data/overrides.json` were **merged** so
  the `veterans_of_the_long_war` flag survives `json.load` (it had been silently
  dropped). The melee wound-reroll mechanic was already wired and default-on via
  `SWEG_VETERANS`, so no loader gate is needed; the screening gate
  `SWEG_CSM_VETERANS` was removed.
- **`SWEG_CUSTODES_NO_FAKE_FNP`** and **`SWEG_FIX_BODYGUARD_FNP`**: flipped to
  **default-on with a `=0` kill-switch** (the project's adopted-correction pattern,
  matching `SWEG_VETERANS`). Verified: default catalogue has Custodes fnp=7 (30
  units) and the 4 bodyguard units fnp=7; `=0` restores the fabricated saves;
  `run.py --cli` exits clean; `scripts.audit_rules` passes.

Re-anchored to `data/_anchor_sc18a_n80_log.json` (fresh baseline with the adopted
defaults) so subsequent fabrication screens measure marginal effect on top of the
adopted state.

### Deferred follow-ups (noted, not done)

1. **Custodes under-model.** With the fabricated Feel No Pain removed, Custodes sits
   at sim 46.1 vs real 52.1 — under-rated by ~6pp. The fake save had masked genuine
   durability/lethality the sim does not capture (2+ armour save plus 4+ invulnerable
   plus high wounds plus Martial Ka'tah melee). Find and restore the real mechanic so
   Custodes lands near 52. This is the single most informative open Stage 1 thread.
2. **Permanent mapper fix for the prose-walk Feel No Pain leak.** The root cause of
   both Feel No Pain corrections is one bug — `code/bsdata/mapper.py extract_fnp`'s
   legacy prose walk pulling Feel No Pain numbers from leader/bodyguard abilities and
   Crusade / Battle-Trait `selectionEntryGroup` content. Fixing it (prune those
   subtrees; model conditional Feel No Pain as conditional) plus a `parsed.json`
   regeneration would subsume both default-on loader corrections and also fix any
   other faction the leak touches. Kept as a separate, broader change because it
   moves more than the screened unit set.

---

# Thousand Sons ranged-hold — watched-replay lever (2026-07-03)

Owner directive: derive an army-scoped artificial-intelligence lever for Thousand
Sons FROM WATCHED PILOTED GAMES (sim win rate 48.2 vs real 54.6, the
second-largest under-pole once Astra Militarum is covered). Method: the
pilot-comparison harness `scripts/diag_pilot_am_vs_ik.py` run for three games
across opponent classes, reading the per-round board renders alongside the
per-round move log.

## Games watched

| Seed | Opponent | Map | Result (A = Thousand Sons) |
|---|---|---|---|
| 0 | Imperial Knights (durable gunline) | Crucible of Battle | A win 55-34 |
| 1 | Orks (melee pressure) | Take and Hold | **A LOSS 20-48 (blow-out)** |
| 2 | Necrons (mid-range attrition) | Hammer and Anvil | A LOSS 54-58 (close) |

## The observed misplay — the gunline Advances into melee and forfeits its guns

In every one of the three games the Thousand Sons shooting core Advanced its whole
line forward in round 1, and repeatedly after, forfeiting its Shooting phase (a
unit that Advances cannot shoot non-[ASSAULT] weapons). Named, concrete instances:

- **Orks seed 1, round 1:** all 25 Rubric Marines activations ADVANCED (move log
  lines 7-37); none fired. The line then marched INTO the 100-model Ork horde and
  was ground up in melee across rounds 2-4 (Ahriman dead by round 3, Tzaangors and
  Rubrics deleted wholesale). Final 20-48. A real Thousand Sons player holds the
  Rubrics back and thins the horde with 24" inferno-bolter fire (their All-Is-Dust
  2+-vs-Damage-1 save makes them far more durable than Boyz in a firefight) before
  contact — exactly the durability the Advance-into-melee throws away.
- **Imperial Knights seed 0, round 5:** ~20 Rubric Marines activations ADVANCED
  (lines 454-473) in the final round with Knights still alive.
- **Necrons seed 2, round 1:** the whole Rubric line + Ahriman + Sorcerers + both
  Mutaliths ADVANCED (lines 9-38), pushing into the Necron gunline's fire.

The Advance-into-melee is the same class of mis-pilot the wave-260 Astra Militarum
comparison found (the generic `SWEG_ADVANCE_DISCIPLINE`), and the same one the
adopted `am_advance_discipline` / `ck_ranged_hold` / `votann_ranged_hold`
faction-scoped levers correct for their armies.

## What is NOT the gap (checked, so no lever is forced there)

- **The Cabal of Sorcerers / psychic economy IS modelled.** The default Thousand
  Sons detachment built by the archetype is Rubricae Phalanx, whose
  `psychic_mortal_wounds_per_round=0` is a deliberate, documented design choice
  (the psychic teeth lives on the opt-in Grand Coven). The Cabal Rituals
  (Doombolt / Temporal Surge / Destiny's Ruin / Twist of Fate), Ahriman, and
  Magnus are all wired (`data/rule_citations.d/thousand_sons.json`). Psychic
  absence is not the deficit.
- **All Is Dust is modelled** (`all_is_dust=True`; +1 armour save vs Damage-1
  attacks). The durability the Advance throws away is real and represented.

## The lever built — `SWEG_TSONS_RANGED_HOLD` (default-OFF)

A fifth Thousand-Sons-scoped entry point (`_ad_tsons`) on the shared
`_suppress_advance` block in `code/simulator.py` `_do_move`, identical in logic to
`_ad_am` / `_ad_ck` / `_ad_votann`: a moving Thousand Sons unit seeking an
objective (CAPTURE/STEAL), carrying no [ASSAULT] weapon, with ranged damage per
activation >= 2.0 and range >= 18", that has a damageable target within a Normal
move's reach, HOLDS and Normal-moves (keeping its shot) rather than Advancing. The
shared filter selects exactly the shooting core — Rubric Marines (rDPA 4.0 / 24"),
Scarab Occult Terminators (2.0 / 24"), Mutalith Vortex Beast (6.34 / 36"), Ahriman
/ Exalted Sorcerer / Infernal Master (6.66-7.0 / 18") — and leaves the melee chaff
(Tzaangors, Chaos Spawn, range 0) free to Advance to objectives. Cited
`simulator.tsons_ranged_hold`, registered in `scripts/audit_rules.py`.

Mechanism confirmation (harness, seed 1 vs Orks, gate OFF vs ON — mechanism
evidence only, NOT rate evidence, the harness seed scheme diverges from the eval
pair-seed scheme): the gunline held and thinned the horde, and the Orks' final
capped victory points fell from 48 to 34 (result 20-48 to 24-34).

## Screen (N=20 Thousand-Sons-scoped, paired vs the standing anchor `sc48a`)

- **Byte-identical-off:** gate unset, 0 flips across all 22 factions
  (`data/_tsons_off_check.json` vs the anchor) — the OFF path does not leak.
- **`SWEG_TSONS_RANGED_HOLD=1` alone (== combined; single lever):** Thousand Sons
  49.5 -> 51.5, paired delta **+2.0 toward real 54.6 (correct direction)**, 147 of
  840 matched games flipped (highly active, not inert). At N=20 the paired CI still
  spans 0 (not yet decisive) — the same signature the votann / Chaos Knights / Astra
  Militarum ranged-holds showed before they landed decisively at N=80. The N=80
  adoption screen (owner-run) is the deciding measurement; per-lever collateral is
  not reliably readable at N=20-scoped (each opponent appears in only a handful of
  games). Recommendation: promising, precedent-backed, correct-direction — advance
  to the N=80 adoption screen.
