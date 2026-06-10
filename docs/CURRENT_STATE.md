# SwegHammer calibration — current state

**WAVE 226 (2026-06-09) — scout-destination AI v2: ROLE-classified (gated `SWEG_SCOUT_AI`, default-OFF, re-screen RUNNING).**
v1 (send every scout to an objective) was flat-to-worse at N=40 (+0.30) with a confirmed flaw — it pulled the Chaos Knights War Dog (melee) off its pressure (−4.17) and stranded the Adeptus Mechanicus Skitarii (30" gun) on an open marker (−3.66), while only the short-range fragile Astra Militarum scouts benefited (+2.08). The watchdog authorised v2 (role-classify; build on the range/EV grounding, do not pre-instrument Adeptus Mechanicus; re-screen is the validation; long-range → HOLD, not cover-aware-move; park scout-AI if v2 is also flat/worse). **v2 (`_run_scout_phase`, gated `SWEG_SCOUT_AI`, default-OFF/byte-identical):** classify each scout — **(a)** melee-class (reusing the canonical `strategy._is_melee_class`, melee-DPA ≥ ranged-DPA) → pressure FORWARD toward the nearest enemy; **(b)** long-range shooty (range ≥ 24") → HOLD its firing position; **(c)** short-range / fragile shooty → forward-but-safe contestable objective (the v1 board-control move that helped Astra Militarum), never into a worse position. Citation `simulator.scout` note updated; `tests/test_scout_ai.py` rewritten to 4 cases (one per role + gate-OFF legacy). Full suite 1234 passed, audit clean, `run.py --cli` exit 0 both gates. Committed locally (`80a2359`); push delegated.
**VERDICT — scout-AI lever PARKED (metric-neutral at honest N; stays gated-OFF/inert).** The N=40 re-screen looked promising (−0.51) but the **N=80 confirm (full 80-seed paired power) is FLAT: gated MAE OFF 6.10 → ON 6.08 (−0.02)** — the N=40 −0.51 was noise. v2 fixed v1's regressions (Adeptus Mechanicus −3.66 → −0.10 flat; Astra Militarum no longer helped though — −0.47 flat at N=80) but the net headline does not move. Decisive N=80 movers are mostly wrong-direction: Aeldari +2.81 (more over), Leagues of Votann +7.59 (crosses under→over), Chaos Knights −1.58 (more under); Genestealer −3.11 trims its over-pole (good) — they roughly cancel. Per the watchdog's pre-authorised rule ("if v2 is ALSO flat/worse → PARK"), the scout-destination lever is **parked**: v2 stays committed but default-OFF. **Fidelity note (flagged for the watchdog):** v2 is genuinely more faithful scout play than charge-the-nearest-enemy; a fidelity-first case exists to flip it default-ON anyway (metric-neutral, not worse), but the Votann/Aeldari over-correction (scout objective-grab amplifying already-over factions' primary VP) makes it not a clean win — left to the watchdog to override the park if it wants fidelity-first ON. **PIVOT to a fresh lever (watchdog to pick): Sororitas −3.1 (thin scouts, own diagnosis), Genestealer +14.6 over (stat over-rating), Emperor's Children +4.3 over.** Anchor unchanged: gated-6.10 `_reservescap_on_n80_log.json`.

---

**WAVE 225 (2026-06-09) — increment 2 reframed + BUILT: scout-destination AI (gated `SWEG_SCOUT_AI`, default-OFF, A/B pending).**
The watchdog's "increment 2 = scout/infiltrate pre-game move" was the session's 4th "already built" — `_run_scout_phase` (simulator.py:7564, called line 944) and infiltrator forward-deploy (`_deploy_armies`) already execute the moves, and the data is populated (catalog: 93 scout units / 67 infiltrators). The (b)-first list-presence check (`scripts/diag_scout_presence.py`, 2000 pts × N=30 through the eval's own `build_faction_random_army(...use_archetype=True)`) confirmed the lists field scouts meaningfully: **Astra Militarum 2.03 units / 7.1 models / 100% of armies; Adeptus Mechanicus 1.30 / 12.5 / 100%; T'au 3.0 / 23 / 100%; Aeldari 1.13 / 8.4 / 83%; Adepta Sororitas THIN — 0.63 / 43%.** So the real lever is the scout-move **DESTINATION quality**, not a build: legacy `_run_scout_phase` moves each scout `_move_toward(... nearest_enemy ...)`, blindly charging the closest enemy — which suicides fragile gunline-scouts into turn-1 threat and off their own objectives. **Built (gated `SWEG_SCOUT_AI`, default-OFF → byte-identical OFF):** scout toward the nearest **forward-but-safe** contestable objective (no further than ~3" past the midline), never into a strictly worse position, else **hold** rather than charge. The Scouts move is the real rule (cited `simulator.scout`, effect note updated); the destination is the AI tactical choice, analogous to `simulator.intelligent_deployment`. Helper `_scout_destination`; `tests/test_scout_ai.py` (3 cases, decisive scenario: enemy placed behind the scout so legacy walks backward / AI walks forward). Also fixed a stale comment at simulator.py:7237 ("default OFF" → "default-ON since wave 224"). Audit clean, full suite green, `run.py --cli` exit 0 both gate states. Committed locally; push delegated to the watchdog.
**N=40 ON screen RESULT (paired/CRN vs the gated-6.10 anchor, 40 shared seeds): DO NOT FLIP — v1 is an INCOMPLETE heuristic, keep gated-OFF.** Like-to-like gated MAE OFF 6.62 → ON 6.92 (**+0.30**, flat-to-worse); signs MIXED: Astra Militarum +2.08 (right way) but Adeptus Mechanicus −3.66 (worse), and **Chaos Knights decisively DOWN −4.17** (only mover with 95% CI clear of 0). **Root cause CONFIRMED (grounded in catalogue, not assumed):** v1 redirects *every* scout to an objective, but (1) the only Chaos Knights scout is the **War Dog Stalker — MELEE (M~14.7 / S~4.7)**, an aggressive unit that should pressure forward (v1 pulls it back → −4.17); (2) Adeptus Mechanicus's dominant scout is **Skitarii Rangers — SHOOTY 30" range** (a long gun wants a firing position, not to stand on a midfield marker in the open → −3.66). Astra Militarum (short-range fragile scouts) is the case v1 helps. **NEXT = wave 226 v2 refinement (faithful, targets both regressions): classify the scout — MELEE-oriented → pressure forward toward the enemy (legacy, faithful for War Dogs); LONG-range shooty (range ≳ 24–30) → hold/minimal (already threatens midboard from the zone); SHORT-range fragile shooty → forward-but-safe objective grab.** Then re-screen N=40. **Sororitas (thin scout presence) stays a separate diagnosis.**

---

**WAVE 224 (2026-06-09) — DEPLOYMENT-AI / 10e RESERVES CAP flipped DEFAULT-ON (user "DO IT"). New standing frame gated 6.10.**
The deployment-AI lever (gated `SWEG_DEPLOY_AI`) is now **default-ON** (`simulator.py:7272`, `"0"`→`"1"`; `=0` reverts). It enforces
the Chapter Approved 2025-26 Reserves cap — *"No more than half of the units in your army can start the battle in Reserves, and the
points total of those units cannot be more than half of the points total of your army"* (cited `simulator.reserves_cap`). The dual
cap (≤50% units AND ≤50% points) governs which deep-strike / Genestealer Cults Cult-Ambush units may reserve; the AI reserves the
alpha-strikers first (lowest Objective Control) and keeps the high-OC bodies on the board to contest. **Genestealer Cults Cult Ambush
counts toward the cap — no exemption** (the user-corrected ruling; the sim previously reserved 100% of deep-strike / Genestealer
armies, an illegal-in-10e all-reserve deployment that starved them of primary victory points). **Frame chain this session:** random-fill
re-base 7.37→7.05 (wave landed default-ON) → reserves-cap dual-50% 7.05→**6.10** (−0.95, measured/verified N=80). The default-ON config
is byte-identical to the measured reserves-cap run, so **NO re-eval was needed** for this flip. **New standing frame: gated mean
absolute error 6.10.** New OFF anchor for the next A/B: `data/_reservescap_on_n80_log.json` (supersedes `data/_fillsquads_on_n80_log.json`).
**Key revelation:** with the deployment bug fixed, Genestealer Cults flips from a −21 under-pole to a **+14.6 OVER** (a stat over-rating
that was masked by the all-reserve starvation) — the Genestealer under-pole work is now obsolete; Chaos Daemons came **in-band**.
**Test maintenance (this wave):** the all-Allarus `test_custodes_mobility::test_allarus_…` test and three `test_gsc.py` Cult-Ambush
tests were un-pinned from the illegal gate-OFF all-reserve path and rewritten to the faithful **capped expectation** (a degenerate
all-deep-strike army reserves only up to the cap; the mechanic — ambush flag / Round-1 arrival / >9" landing / event — is asserted on
the reserved subset). Full pytest green, audit clean, `run.py --cli` exits 0 on the default (cap-ON) path. **Latent note for the
watchdog:** cap-promoted on-board Genestealer units keep a stale `cult_ambush_pending=True` flag — inert (only read inside
`_arrive_from_reserves`, which iterates reserves only), no production effect; a 1-line clear-on-promote is a candidate tidy, deferred.
**NEXT LEVER — deployment-AI increment 2: scout / infiltrate pre-game move** (lifts Astra Militarum −3.4 / Sororitas −3.1 — both
*worsened* by the cap — using their 10-20 currently-wasted scout/infiltrate units). Then: Genestealer +14.6 / Emperor's Children +4.3
over-pole; transport-accounting + the round-3 "units not arrived are destroyed end of Round 3" follow-up (not independently enforced).
Committed locally per the loop discipline; the outward push stays delegated to the watchdog.

---

**WAVE 218 (2026-06-08) — THROUGHPUT TOOLING is now the BLOCKING priority (user); paired/CRN eval mode core LANDED.**
Push management is delegated to the watchdog (it pushed waves 212–217; origin at `d6748a3`, pull request #41 current) — going forward the worker COMMITS EACH WAVE LOCALLY and does NOT block on a push. The user set a new blocking priority: build ALL the simulator-speed / evaluation-throughput improvements BEFORE resuming band-program waves (they compound — every one makes later waves cheaper). Speed task list (#94–#96): **#1 paired / Common-Random-Numbers evaluation mode** (the eval already runs OFF/ON on identical `pair_seed`, so measuring the PAIRED per-game delta — the flipped-games count — makes keep/reject decisive at N=40/N=20 while the absolute frame stays noisy; supersedes the matrix-halving idea and makes N=40 *reliable*, not just fast), then **#2 base-time perf** (line-of-sight per-phase cache + memoize `_durability`/`_fnp_resolved`), then **#3 standardise the robust evaluation invocation**. **#1 core LANDED (`adf9140`):** additive `--log-games` flag on `evaluate_vs_meta` (default frame byte-identical) + `scripts/paired_delta.py` join tool (per-faction field-weighted OFF/ON win rate, naive aggregate delta, paired delta + McNemar 95% confidence interval + up/down/flat verdict, each arm's gated mean absolute error), unit-tested (`tests/test_paired_delta.py`, 13 cases). STILL TO BUILD on #1: sequential early-stop (N=20 → extend only if the paired confidence interval is inconclusive) + the rolling regression sentinel. CAVEAT: paired variance-reduction scales with OFF/ON correlation, so big re-bases (random-fill) stay N=80. Sequence: finish the wave-217 Veterans gate-off confirmation (running) → finish #1 → #2 → #3 → then resume band waves (now fast) with the random-fill re-base in parallel.

**WAVE 217 (2026-06-08) — Task #92 (per-attack-type conditional invulnerable saves) A/B landed: KEEP, fidelity-first; new confirmed frame gated 7.26.**
Sims re-enabled; the deferred #92 N=80 A/B ran ON-only against the wave-213 confirmed frame as the reused OFF anchor (gated 7.21 — valid because #92-gate-OFF reverts to the verbatim old save logic and the parsed.json regen was verified additive/zero-drift). **Result: gated MAE 7.21 → 7.26 (+0.05), raw 10.44 → 10.55, band 5 → 4 — within noise.** Per-faction redistribution is small and entirely inside each faction's own noise floor (no parse crater): less over for Aeldari (−1.04 gated, faithful) and Astartes (−0.51); slightly more over for World Eaters / Custodes / Drukhari; more under for CSM / Sororitas / Daemons (the Sororitas −1.3 sim, the largest single mover, is < its 3.79 noise floor = a second-order matchup effect vs the Aeldari/Drukhari melee-invuln change, NOT a Sororitas bug). **KEPT on fidelity-first grounds** — 10e genuinely has per-attack-type invulns (Wyches 4+ melee / 6+ ranged; Ion Shield ranged-only); single-value modelling was the user-flagged mis-model; the metric cost is negligible. Default stays ON (`SWEG_COND_INVULN`). The #92 ON table (gated 7.26) is now the confirmed frame / OFF anchor for the next A/B. Full record: `data/wf_cond_invuln_ab.txt`.
**Task #92 — per-attack-type conditional invulnerable saves — BUILT end-to-end + LANDED (the user-flagged structural fidelity fix).** Per-attack `invuln_save_melee` / `invuln_save_ranged` fields, mapper-extracted from the "X+ invulnerable save against melee/ranged attacks" clauses and combined with the `invuln_ranged_only` override, read at the save step. Gated `SWEG_COND_INVULN` (default-on). Six commits: `06bd644` (Stage 1a scaffold), `d7d1d97` + `4dffc44` + `33b9b42` (Stage 1b data pipeline + parsed.json regeneration, verified additive / deterministic / zero-drift), `febc8ae` (Stage 2 save-step switch, cited `simulator.conditional_invuln_save`), `3ad2535` (behavioural test). Audit 318/318, run.py --cli exits 0 on both gate states, tests green.
**Prior — WAVES 214–216: over-pole fabrication vein EXHAUSTED.** The band program's T'au Commander (wave 212) and Chaos Space Marines leader-routing (wave 213) fixes were each faithful but small (gated 7.27 → 7.21); the over-pole fabricated-flag sweep (wave 214) concluded the CLEAN-FABRICATION vein is essentially exhausted (Drukhari, Astartes, Thousand Sons, Custodes, World Eaters already cleaned). Remaining over-pole is STRUCTURAL (positioning / representation / Stage 2).
**LOOP STATE.** Sims re-enabled. Faithful builds land gated + cited + tested, with their evaluation run via the reuse-confirmed-frame method (on-only vs the last confirmed anchor). **Wave 217 build LANDED: Chaos Space Marines Legionaries "Veterans of the Long War"** (`ca320b1`, gated `SWEG_VETERANS`, default-on) — the Legionaries datasheet ability (melee Wound-roll re-rolls, upgraded to a full re-roll when the target is within range of an objective marker), verbatim-cross-checked against Wahapedia + BSData (ability `a5ea-d708-db75-226c`). One of the per-unit Chaos Space Marines abilities the wave-213 review localised as the real bulk of the Chaos Space Marines under-pole. Audit 319 keys clean, behavioural test green, `run.py --cli` exits 0 both gate states. Its before/after evaluation (on-only vs the gated 7.26 confirmed frame) is running (`bj6lyajt8`); expect a small even-handed Chaos Space Marines lift (the under-pole bulk needs the other Dark Pact abilities too). Pushed by the watchdog (push now delegated). The Veterans gate-off confirmation (`SWEG_COND_INVULN=0 SWEG_VETERANS=0`, expect gated 7.21 — validates the reuse anchor chain AND the wave-218 additive harness change) is the next evaluation after it. Band-program builds (more Dark Pact abilities; the random-fill re-base) resume AFTER the speed tooling lands.

---

**WAVE 213 (2026-06-07) — BAND PROGRAM: Chaos Space Marines leader host-routing fixed (faithful, small lever).**
The Chaos Space Marines under-pole (−12.9) review found the Dark Apostle and Sorcerer had their `host_keys` pointing at units
absent from or marginal in the army (Traitor Guardsmen, a single Cultist Mob), so their auras fired on chaff or nothing instead of
the Legionaries / Chosen core that fights. The BSData primary source ("This model can be attached to the following units:")
confirms the Dark Apostle leads Accursed Cultists / Chosen / Cultist Mob / Legionaries and the Sorcerer leads Chosen / Legionaries.
Fix (gated `SWEG_CSM_LEADERS`, default-on; `=0` reverts): route both to the Legionaries/Chosen core (effect proxies unchanged —
this wave is a pure scope correction). The Chaos Lord is deliberately deferred: its current `+1-to-wound` aura is a fabrication
(the real "Chance for Glory" is a once-per-battle self buff, not a unit aura) that currently fires on nothing, so routing it would
inject the fabrication onto the core squad. **N=80 A/B: Chaos Space Marines 42.7 (gated 10.46) → 43.0 (gated 10.20), +0.3 / −0.26;
headline 7.23 → 7.21; even-handed (only Chaos Space Marines moved materially).** KEEP (faithful + the substrate for future Chaos
Space Marines work). **KEY FINDING: the −12.9 under-pole is mostly NOT the mis-routed leaders — a genuine routing bug recovered
only +0.3.** The bulk is the missing per-unit Dark Pact abilities (Terminators "Despoilers" full reroll, Legionaries "Veterans of
the Long War", Possessed "Unholy Bloodshed"), Abaddon's absent army reroll aura, the weak reroll-1s proxy on the Dark Apostle
(real rule is +1-to-wound-melee), OR the deeper output/durability issue the project already tracks. Committed locally; not pushed.

---

**WAVE 212 (2026-06-07) — BAND PROGRAM begins: first faithful over-pole fix lands (T'au Commander fabrication removed).**
With collision the production frame (wave 211, gated 7.27) and the push handoff done (pull request #41 open), the post-push band
program started with rules-implementation review. A static-vs-runtime double-count audit on the inflated elites returned a clean
negative (no active double-counts; Aeldari +21.9 is faithful collision-induced Fly/mobility, not an error) but surfaced a genuine
fabrication: the T'au "Coordinated Fire Plan" (Commander in Battlesuit / Coldstar) granted a **fabricated army-wide +1 to Hit**.
The real 10e rule (triple-confirmed — the citation's own quoted text, the audit, AND a pre-existing `expectedFailure` test) grants
the **led unit** a Move characteristic of 12" and the [ASSAULT] ability on its ranged weapons — no Hit bonus, led-unit-scoped. The
fix (gated `SWEG_TAU_CMD`, default-on; `=0` reverts for the comparison) removes the fabricated buff; the [ASSAULT]/Move mobility
effects are left unmodelled (the simulator does not model Movement-characteristic bonuses, and [ASSAULT] is near-inert in this
hold-and-shoot frame). **N=80 A/B: T'au +14.0 (gated 9.74) → +12.4 (gated 8.17), −1.57 gated; headline 7.27 → 7.23; perfectly
even-handed — only T'au moved materially (every other faction within ±0.7 stochastic ripple), and T'au did not over-crater (still
+12.4 over).** Kept default-on (faithful + metric-positive). A further fidelity step (scoping `host_keys` to the Crisis Battlesuit
led unit) remains as the still-`expectedFailure` follow-up. NEXT band levers: Chaos Space Marines Dark Pacts under-modelling
(under-pole), and the Drukhari static 6++ invuln check (parked — needs Wahapedia to verify it is a 9th-edition carryover). Committed
locally; NOT pushed (rule 3 — the push is held for the user; it would update pull request #41 or a follow-up).

---

**WAVE 211 (2026-06-07) — COLLISION IS NOW THE PRODUCTION BASELINE (user ruling): the Imperial Knights over-pole is FAITHFULLY
RESOLVED. New frame = collision-ON + reach-fix; re-based gated mean absolute error ~7.27 (was 5.23 pre-collision; 6.54 collision-only).**
USER RULING (verbatim): *"I want it on, figure out how to fix movement / get the over/under shooters in band with it on."* No-overlap
collision + base-edge Objective Control contest + friendly-pass-through / enemy-path-block movement are flipped **DEFAULT-ON**
(`SWEG_COLLISION`/`SWEG_PATHFIND`/`SWEG_OCCGRID`; `=0` reverts each; the make-way `SWEG_MOVEPLAN` stays OFF — it is the forbidden
horde-AI nerf). **The N=80 keep/reject (the proof the direction is right): Imperial Knights +25.1 (gated 22.17) → +1.6 (gated 0.00,
IN BAND)** — sim 72.8%→49.4% vs real 47.7%, via faithful screening + base-edge contest, NOT cratered. The #1 residual the whole
project chased is resolved by modelling the positional/screening representation gap. Also helped: CSM/AdMech/Tyranids/Necrons/World Eaters.
**Efficiency / fidelity bundle landed (4 components, all gated-reversible):** (1) collision flip default-ON; (2) bbox-cull on the
`_enemy_path_cap_t` scan (1.70×/battle → parity); (3) Objective-Control cache — per-phase incremental `_phase_our_oc`, proven
byte-identical under `SWEG_OC_CACHE_VERIFY` (the 27% hot spot); (4) the **reach-fix** (`_fan_to_goal`, gated `SWEG_REACH_FIX`,
default-ON) — a big mover whose straight end is blocked with NO enemy on the path fans a ring around the goal and takes the legal
spot closest to goal it can reach WITHOUT crossing an enemy (a fully enemy-screened goal admits no candidate → cannot undo the
Imperial Knights over-pole). **Reach-fix verified faithful but band-NEGATIVE** (collision-only gated 6.75 → +reach-fix 7.27, +0.52):
the guardrail HELD (Imperial Knights stayed in-band g0.00) but the under-pole did NOT recover — sending fragile gunline vehicles
forward to contest is a bad trade (advance → die). **KEY RE-DIAGNOSIS: the under-pole crater is NOT reach.** It is
durability / combat-output / advance-to-score AI + rules-implementation review. The reach-fix is KEPT default-ON (fidelity-first:
faithful movement-correctness AND the necessary substrate for an advance-to-score AI — units must be able to reach before the AI
can correctly decide who advances; gating it would re-mask the AI gap). **NEXT (the band program, multi-wave) — PIVOTED OFF MOVEMENT
onto:** (A) advance-to-score AI (gunlines hold-and-shoot, don't suicide-advance; even-handed); (B) rules-implementation reviews
(Chaos Space Marines Dark Pacts under-modelled; static-vs-runtime over-credit check for the inflated elites Aeldari/Drukhari/T'au);
(C) durability / combat-output (over-fragile vehicles, [[project-faction-residual-rootcause]]). Cited
`simulator.objective_control_base_range` + `simulator.collision_friendly_passthrough`. Bundle COMMITTED LOCALLY (checkpoint);
NOT pushed (rule 3 — the outward push is held for explicit user go; the frame regressed 6.54→7.27 so the push is escalated).

---

**WAVE 210 (2026-06-06) — FIDELITY-FIRST REVISIT SWEEP COMPLETE: all 6 worklist items flipped DEFAULT-ON + committed; new
honest baseline gated MAE ~5.23 (was 4.89).** Per the user-authorised sweep (docs/FIDELITY_REVISIT_WORKLIST.md), each parked
faithful mechanic / competent-play AI heuristic is now production — one flip + one N=80 A/B + verify-before-flip + commit each:
**#1 per-model weapon firing** (4.89→5.57, +0.68; un-masks the elite over-rate the averaged weapon hid) — `8108471`;
**#2 real 2-card Tactical secondary deck** (→5.72, +0.15) — `2e7619a`; **#3 per-Command-phase primary scoring** (→5.44, −0.28;
faithful timing AND a metric WIN) — `52dde93`; **#4 squad split-fire** (→5.49, neutral) — `9909d5f`; **#5 collective-crack focus
fire** (→5.44, AI-realism, spread-off-uncrackable verified) — `2c77b35`; **#6 intelligent role-split deployment** (→**5.23**,
−0.21, lifts the under-pole gunlines AM/AdMech) — `2f7ddb7`. RULE items are metric-blind keep-if-faithful; AI-HEURISTIC items
(#5/#6) are kept on AI-realism (the user's AI-piloting-first ruling). Every gate reverts via `SWEG_*=0`. Ed's UI PR #37 merged
in cleanly (`f3eca8d`, app.py+renderer.py only). NOT pushed (awaiting the user's go; local ~82 commits ahead of origin).
**KEY SYNTHESIS held:** both win-rate poles (Imperial Knights over ~22; AM/AdMech under) are the positional/representation gap,
owned by option-B (anti-walling) + Stage 2 — the sweep made the frame HONEST and AI-realistic; it did not resolve the over-pole.
**NEXT: option-B (anti-walling) — the over-pole headline the user funded — on the new 5.23 honest frame.**

---

**(superseded running note — SWEEP #1 LANDED)** Per the user-authorised fidelity-revisit sweep (docs/FIDELITY_REVISIT_WORKLIST.md),
each parked faithful 10e mechanic is now landed even though the metric RISES (the rise un-masks the over-rate the bad representation was
compensating — that's the point). **#1 per-model loadouts** (each model fires its OWN real weapons; single-model units stop
firing mutually-exclusive arm options) is now production (`SWEG_PERMODEL=0` reverts). It required completing the AI-isolation
(`strategy._score_profile`: the tactical AI scores the SQUAD aggregate, not one model's gun — offensive scorers + the
movement-role `classify`) so per-model doesn't confound targeting/movement. Net A/B (deck frame N=80): OFF 4.89 → ON **5.57**.
KEY SYNTHESIS: the faithful version HELPS Daemons (movement role correct) but HURTS the under-pole (AM/AdMech) — because faithful
gunlines hold-and-shoot (correct 10e) and score LESS primary VP than advancing. So BOTH poles are the positional/representation
gap (faithful units don't advance-to-score), the SAME root, owned by option-B (anti-walling) + Stage 2 — NOT an abilities gap.
Sweep continues #2 (Tactical deck) → #3 (Command-phase scoring) → … on the 5.57 honest frame. (Avenue-2 physics: board-wide
collision is DEAD even with pathfinding — collision+pathfind regressed 5.68→8.02 by walling big bases; pathfinding code kept as
gated/inert infra. Over-pole headline is now option-B anti-walling.)

---


---
*Wave history older than wave 210 archived to `docs/CURRENT_STATE_archive.md`.*
*Long memory of what is landed / reverted / parked / forbidden: `docs/DECISION_LEDGER.md` — read it before proposing a lever.*
