**WAVE 244 (2026-06-12, CLOSED) — first batch-screen wave (user-set methodology, now `AUTO_LOOP_PROCEDURE.md` §I): three levers screened against one shared anchor, ALL THREE ADOPTED, defaults flipped together (`2c5a7c4`), single N=80 re-anchor gated 5.90 (−0.80 vs sc9c, best honest frame yet).**

**The three levers:** (1) leader-stack seed priority `SWEG_SEED_LEADERS` — seed walk now seeds the template's documented leader stack first; fourteen-faction fraction overrides, superset re-derivation, menu factions scoped out. Alone it crashed Astra Militarum to 30.44 (unpiloted officers = dead points) — the non-additivity proof for the combined-run rule. (2) Officer attachment + stay-near piloting `SWEG_OFFICER_FOLLOW` (`code/leaders.py` ~1388, `code/strategy.py` ~3006): combined 1+3 screen 7.22 → 7.20 wash with the crash recovered −5.27; adopted on fidelity. (3) Melee weapon-keyword mode routing (data-driven, no gate): ranged-only keywords (anti-keywords / devastating wounds / twin-linked) no longer contaminate melee profiles on 242 units; screen 7.20 → 6.77 (−0.43) — Adeptus Custodes −4.03, Adeptus Mechanicus −3.40, Death Guard −3.16 toward; Emperor's Children +2.93, World Eaters +2.16 away (fabricated melee output removed, faithful direction).

**Re-anchor (N=80, flipped frame):** gated 5.90, raw 9.19, 3/22 in band. Movers vs sc9c: Adeptus Custodes 20.05 → 8.97, Necrons 9.72 → 4.04, Genestealer Cults 4.71 → 0.30, Chaos Knights 6.53 → 1.30, Grey Knights 7.38 → 4.91, Leagues of Votann 3.80 → 1.81 toward; Astra Militarum 19.01 → 22.97 AWAY (accepted fidelity cost — remaining-gap diagnostic in flight: order value chain / indirect-fire artillery / per-unit dead weight / defensive orders), Imperial Knights 5.80 → 9.21, Emperor's Children 12.05 → 14.44 away.

**WAVE 243 (2026-06-12, CLOSED) — Astra Militarum Voice of Command rebuilt end-to-end (real REGIMENT/SQUADRON keywords + First Rank Fire rapid-fire gate + squad-level Order dispatch) plus per-model flag parity: ALL FOUR PARTS ADOPTED, headline 7.10 → 7.22 at N=40 with every faction flat. The −19 Astra Militarum residual is NOT orders plumbing — the archetype builder drops two of the three officers.**

**Four parts, all faithful:** flag parity `f37d646` (indirect_fire/one_shot/precision now copied in per-model promotion, 168 units corrected; +0.05 wash, Aeldari −2.15 toward target); REGIMENT/SQUADRON first-class keywords `ead486d` (31/44 units from BSData categoryLinks, BATTLELINE proxy removed; screen 7.28 with Astra Militarum −1.94 AWAY → exposed part 3); rapid-fire gate `e265fdf` (First Rank Fire was a verbatim no-op issued to tanks with no Rapid Fire weapons; 7.26, only +0.6 recovered → exposed part 4); squad-level dispatch `384c111` (an Order buffed ONE model-instance not the codex unit — a ten-model block received one tenth of the value; no-stacking now per squad, Take Cover! damage branch now reachable, probe shows a real-Command-phase order stream).

**Measurement (combined orders frame vs flag-parity frame, paired N=40, 18,480 matched games):** gated 7.10 → 7.22 (+0.12), all twenty-two factions flat; Astra Militarum 22.9 → 21.9 (−1.05 ± 2.07) on 101 flipped games — Orders now churn its games at full squad strength with no net direction. N=80 re-anchor: gated 6.70, raw 10.05, 5/22 in band (Thousand Sons newly inside), `data/_anchor_sc9c_n80_log.json` promoted as standing anchor; Astra Militarum gated 19.01 (was 18.99), unchanged as the officer-omission diagnostic predicts.

**Diagnostic (banked):** the BUILT Astra Militarum archetype army carries ONE officer, not the template's three — the `(-count, -cost)` seed walk (`code/archetypes.py:1444`) spends the 1100-point seed budget on the tank spine, the EPIC HERO anchor misses its overflow cap by 25 points, and the CHARACTER anchor rescues only the cheapest officer (Cadian Castellan, 55 points: ceiling 2 Orders/round vs template-intent 8). Compounding: officers have no leader attachment (`code/leaders.py` has no Astra Militarum entries), so the lone Castellan drifts 8.5–14.2 inches from the nearest eligible squad by round 3 and issues NOTHING after round 2 — three Orders per battle. Dedup and eligibility logic verified correct. [Wave-244 levers 1+3 built exactly this.]

**WAVE 242 (2026-06-12, CLOSED) — charge-path legality (10e "Charge Move" non-target rule) built, measured, ADOPTED AS DEFAULT: headline wash (+0.14) with T'au and Imperial Knights decisively toward target. Astra Militarum root cause found (orders never reach the army); wave-243 build dispatched.**
**The diagnosis (systemic, before per-faction work per the wave-241 next-levers ranking):** the charge-target picker had NO path legality — chargers reached gunlines straight through screening bodies, a verbatim core-rule violation already noted in `docs/CORE_RULES_AUDIT.md`. **The build (`884a8b8`):** gated `SWEG_CHARGE_PATH` in `pick_charge_target` — (part a) non-FLY chargers excluded from candidates their straight-line move would carry within Engagement Range of a non-target (new pure-geometry point-to-segment helper `_charge_path_screen_gap` in `code/sim/geometry.py`); (part b) ALL chargers including FLY excluded when the approximate end spot itself sits within Engagement Range of a non-target. Excluded candidates fall out of the scorer, so redirection onto the screen emerges from the existing kill-value ranking. Cited `simulator.charge_path_non_target` (verbatim Wahapedia Charge Move text), zero extra random draws, gate-off byte-identical, six new tests. Default-flip test fallout: two collinear-staging tests re-spread (gate never pinned off), and a pre-existing vacuous-assertion bug fixed in `tests/test_charge_picker_wont_crack.py` (uid comparisons were "" == "" without a Battle; real `assertIs` assertions now pin genuine squishy-preference and the no-veto fallback).
**Measurement (paired, common random numbers):** N=40 screen +0.09 wash with three decisive movers all toward target (T'au +4.75, Imperial Knights −7.20, Death Guard −4.76). N=80 confirm (36,960 matched games): **headline 6.38 → 6.52 (+0.14); decisive — T'au +3.85 toward target (enters the noise band), Imperial Knights −5.46 toward target (gated 10.61 → 5.15), Genestealer Cults +3.63 AWAY (new carried residual: horde screens now also protect the Cults' own melee).** Death Guard's screen-time improvement did not confirm. **ADOPTED default-ON (fidelity-first: verbatim core rule at wash cost with two structural wins). NEW STANDING ANCHOR: `data/_anchor_sc9b_n80_log.json` (gated 6.52, raw 9.88, 4/22 in band) — the ON arm promoted at zero eval cost (config equality).**
**Astra Militarum prediction FAILED → root cause FOUND:** the screen-bypass hypothesis predicted Astra Militarum up; it moved +0.24 (flat). Fresh read-only diagnosis (orchestrator-verified against code and the BSData cache): the Orders system proxies the codex REGIMENT/SQUADRON target keywords as BATTLELINE+INFANTRY / BATTLELINE+VEHICLE (`code/orders.py` ~318-374), but BSData v10.6.0 grants BATTLELINE to almost nothing — ZERO Astra Militarum vehicles carry it, so **Leman Russ Commander / Rogal Dorn Commander / Sentinel Commander issue zero orders every game, Lord Solar's SQUADRON and TITANIC legs never fire, the Flexible Command stratagem check returns early unconditionally, and Kasrkin / Tempestus Scions / Heavy Weapons Squads can never receive orders.** The cache carries the REAL keywords as categoryLinks (Regiment ×33, Squadron ×45). Wave-243 build dispatched: REGIMENT/SQUADRON as first-class tracked keywords + orders plumbing switched off the proxy (BATTLELINE deliberately untouched — it keys archetype list-generation caps). Second bundling candidate: Wyvern primary weapon misidentified as Heavy bolter (the anti-tank-picker-bias class) — the dedicated indirect-fire artillery piece has no indirect fire.
**Fork resolved without escalation:** the fight-alternation re-test is already authorized as watchdog-queue item 9 (T3, 2026-06-10) — the "Genuinely REFUTED" worklist tag predates ~60 waves of frame change; build shape decided at re-test time.
**Residual surface on the new anchor (sim vs real, gated points):** OVER — Adeptus Custodes 19.96, World Eaters 16.27, Death Guard 12.43, Emperor's Children 11.95, Chaos Daemons 10.03, Necrons 9.43, Grey Knights 7.09, Imperial Knights 5.15, Aeldari 4.80, Genestealer Cults 4.24, Adeptus Mechanicus 3.86. UNDER — Astra Militarum 18.99, Chaos Knights 6.41, Drukhari 4.03, Leagues of Votann 3.49. In band (4): Adeptus Astartes, T'au, Chaos Space Marines, Adepta Sororitas.
**NEXT LEVERS (wave 243):** (1) **Astra Militarum 18.99 under — land the REGIMENT/SQUADRON orders fix (build in flight)**, scoped paired A/B, with the Wyvern weapon correction as the bundling candidate; (2) **melee over-pole cluster (Custodes 19.96 / World Eaters 16.27 / Death Guard 12.43 / Emperor's Children 11.95 / Daemons 10.03)** — charge-path legality barely dented it; the queued fight-alternation re-test (watchdog item 9) is the standing candidate; (3) Genestealer Cults 4.24 (new, charge-path side effect) + Necrons 9.43 carried.

---

**WAVE 241 (2026-06-11, CLOSED) — CRITICAL FIX: wave 240 shipped the charge placement WITHOUT its measurement half — melee was structurally disabled under the adopted default. Fixed, validated, checkpoint pull request 73 opened; honest re-anchor gated 6.38.**
**The bug:** new diagnostic `scripts/diag_fightgate_check.py` (toolbox-registered) found that under the adopted `SWEG_CHARGE_BASEEDGE` default a successful charge NEVER produced a melee swing — **18 charges / 0 fight activations / 0.0 melee damage** (seed-7 bundle). The charger ends one inch from the target's base EDGE (~2.26 inches centre for two 32-millimetre bases), but every Engagement Range check still measured CENTRE distance against one inch: fight eligibility, the shooting melee-lock, Fall Back, and the charge-candidate filter all judged the charger "not engaged" at its own legal charge-end spot.
**The fix (the measurement half of the same rule):** gate-aware `_er_gap()` primitive in `code/sim/geometry.py` (ON: base-edge gap; OFF: plain centre distance, legacy byte-identical), converted at twelve simulator + five strategy sites together; the charge-roll requirement is now the REAL move (`max(0, gap − 1")`), not the centre distance. Cited `simulator.engagement_range_base_edge`; audit green 343/343. Diagnostic after the fix: **gate ON 18 charges / 20 swings / 10.0 melee damage** (OFF 19/16/7.0). Eight new `EngagementMeasurementTests`; fourteen centre-distance-era test scenarios spread past the new threshold (production default stays the tested path).
**Consequence — measurement integrity:** the combined-collision confirm (gated 5.13, 8/22 in band) and standing anchor `data/_anchor_sc8c_n80_log.json` were measured with melee structurally disabled in the ON arm. The melee-faction drops in that confirm (World Eaters, Chaos Daemons, Death Guard) were the bug's signature, not the mechanic's. The collision-pair ADOPTION stands (faithful placement, measurement now matches), but the headline, in-band count, and residual surface from that confirm are all VOID. **Honest re-anchor LANDED: gated 6.38 (raw 9.88, 4/22 in band) — NEW STANDING ANCHOR `data/_anchor_sc9a_n80_log.json`** (covers the fight fix AND the already-landed held-build harvest: Strands write-back, Yncarne on-kill heal, Chaos Space Marines + Aeldari reshapes, movement-event sweep). Paired decomposition versus the last honest frame (sc8b, 5.08): **the +1.30 is the cost of melee actually working** — melee factions up decisively (Chaos Space Marines +17.31, Chaos Daemons +13.00, Death Guard +12.58, World Eaters +12.47, Grey Knights +9.70, Adeptus Custodes +8.63, Emperor's Children +7.25, Thousand Sons +6.69), shooty factions giving back bug-flattered wins (T'au −14.80, Aeldari −9.46, Leagues of Votann −5.65, Adeptus Mechanicus −4.74). **Fidelity wins on the honest frame: Chaos Space Marines 21.28 → 0.00 IN BAND (reshape), Adepta Sororitas in band (Bringers of Flame survives), Aeldari gated 2.39 (reshape + Strands + Yncarne).** The broken-melee Astra Militarum windfall was bug-flattered — back to 17.48 gated under. Headline rising for faithful mechanics is expected and authorised (fidelity-first).
**Residual surface on the new anchor (sim vs real, gated points):** OVER — Adeptus Custodes 21.56, World Eaters 15.07, Death Guard 14.02, Imperial Knights 10.61, Necrons 9.56, Emperor's Children 9.50, Chaos Daemons 9.10, Grey Knights 7.10, Tyranids 4.09, Adeptus Mechanicus 4.00. UNDER — Astra Militarum 17.48, Chaos Knights 4.42, Leagues of Votann 4.13, T'au 3.55, Aeldari 2.39, Drukhari 2.09. In band (4): Adeptus Astartes, Thousand Sons, Chaos Space Marines, Adepta Sororitas.
**NEXT LEVERS (wave 242):** (1) **melee over-pole cluster first** (Custodes 21.56 / World Eaters 15.07 / Death Guard 14.02 / Daemons 9.10 / Emperor's Children 9.50 / Grey Knights 7.10) — before any per-faction work, diagnose whether base-edge placement + working melee now over-rates charge reach or fight output SYSTEMICALLY (one mechanic, many factions; e.g. charge-success rate vs real-game expectations, overwatch/screening counterplay the sim lacks); (2) **Astra Militarum 17.48 under** — banked structural displacement diagnosis, no longer masked by broken melee; (3) Imperial Knights / Necrons over-poles (pre-existing, carried).

---

**WAVE 240 (2026-06-11) — workflow-orchestrated agenda wave: Bringers of Flame adopted (gated 5.08 best-ever), collision pair adopted default-ON, held-build harvest next. [Wave-241 correction: the collision-pair confirm numbers and the 5.13 anchor below were measured on broken melee — VOID, see wave 241 above.]**
Five wave-240 agenda builds cherry-picked onto this branch via the user-requested Workflow run (per-item worktree agents + adversarial per-commit review): **`SWEG_CHARGE_BASEEDGE`** (charge ends one inch from the target's base EDGE at a collision-legal spot, default-OFF), **`SWEG_DEPLOY_COLLISION`** (deterministic deployment push-apart relaxation, default-OFF), **`SWEG_BOF_ASSAULT`** (Bringers of Flame army-wide ASSAULT leg, default-OFF), **Retributor Storm of Retribution** (ungated, re-roll ones to hit/wound on ranged), **Paragon Warsuits Righteous Paragons** (ungated, plus one to hit/wound versus MONSTER/VEHICLE). Review findings fixed in `8ca2f8a` (non-vacuous relaxation + Bringers of Flame gate-on tests; Retributor citation scope + loader access). Full suite 1536 green, demo exit 0, pushed.
**Retributor+Paragon measured (Sororitas-scoped N=80, `paired_delta.py --scoped`): Adepta Sororitas +1.99 decisive toward target (141 flips, confidence interval ±1.57), Death Guard −0.22 decisive (tiny), all else flat → gated MAE 5.85 → 5.75. NEW STANDING ANCHOR: `data/_anchor_sc8a_n80_log.json` (minted by merging the scoped cells into the 5.85 anchor; merge self-checked — unscoped pairing reproduces the scoped report exactly).**
**Charge-baseedge N=40 screen DONE: headline regression +0.65 (matched-subset 5.95 → 6.59; melee factions down, shooty up) BUT `diag_overlap_audit` corroboration shows the mechanic hits its physical target (seed-5 live overlaps 217 → 100, cross-army 49 → 7). Fidelity-first: not discarded — adoption call moves to a combined-collision N=80 confirm.**
**Deploy-collision N=40 screen DONE: right-direction WIN — matched-subset 5.95 → 5.79 (−0.15); decisive movers BOTH toward target: Astra Militarum +8.25 (under-pole), Imperial Knights −5.75 (over-pole). The avenue-2 physical-board-control prediction landing as forecast.**
**BRINGERS OF FLAME [ASSAULT] ADOPTED AS DEFAULT (`e5d523d`): Sororitas-scoped N=80 measured Adepta Sororitas +16.19 decisive toward target (35.0 → 51.2 vs real ~52.8, 364 flips) — the faction leaves the under-pole for the noise band. Gated mean absolute error 5.75 → 5.08, BEST EVER. NEW STANDING ANCHOR: `data/_anchor_sc8b_n80_log.json` (self-checked).**
**COLLISION PAIR ADOPTED AS DEFAULT (both gates default-ON):** the combined `SWEG_CHARGE_BASEEDGE=1 SWEG_DEPLOY_COLLISION=1` N=80 confirm vs the 5.08 anchor came back **metric-neutral (gated 5.08 → 5.13, +0.04)** with the **in-band count rising 5/22 → 8/22** (World Eaters, Orks, Emperor's Children enter). Astra Militarum gated 14.8 → 3.89 (+11.31 toward target — the banked displacement diagnosis paying out), Adeptus Custodes 13.0 → 8.63 (−4.30 toward); cost concentrates on existing over-poles (Necrons, Adeptus Mechanicus, T'au) and Chaos Space Marines deepens to 21.28 (reshape already built and queued). Physical corroboration on the adoption config (`diag_overlap_audit` seed 5): live overlaps **217 → 53**, cross-army **49 → 2** — the user-flagged stacking bug substantially closed; residual same-army overlaps are pile-in/consolidate sites (future lever). Fidelity-first adopts. **NEW STANDING ANCHOR: `data/_anchor_sc8c_n80_log.json` (gated 5.13, raw 8.03, 8/22 in band)** — ON-arm log promoted at zero eval cost (config equality).
**Residual surface on the new anchor (sim vs real, gated points):** UNDER — Chaos Space Marines 21.28, Chaos Knights 6.26, Astra Militarum 3.89. OVER — Adeptus Mechanicus 17.69, Necrons 14.09, Aeldari 10.32, Imperial Knights 9.81, T'au 8.73, Adeptus Custodes 8.63, Genestealer Cults 5.14, Adeptus Astartes 4.09. In band: 8/22.
**Next: held-build harvest** (cherry-pick order: Strands `04c10f0`+`2cb9583`, Yncarne `59348ee`, Chaos Space Marines reshape `0fdb1eb`, Aeldari reshape `a7c98fc`, movement-event sweep `3774528` — known charge-hunk conflict with the `1b04961` rewrite, re-apply emission inside both placement branches). The two reshapes are frame changes, so ONE fresh full N=80 re-anchor after the batch covers all five builds.
**Held builds ALL DELIVERED and pre-reviewed (orchestrator pass while the confirm runs):** Strands of Fate charge fix `04c10f0` + orchestrator fixup `2cb9583` (FATE-CHARGE-V2 write-back — the budget gate alone split the squad; gate and write-back are complements), Yncarne on-kill D3 heal `59348ee` (passes review), Chaos Space Marines reshape `0fdb1eb` (passes review; frame change → fresh anchor on land), movement-event sweep `3774528` (passes review; charge hunk will conflict with the `1b04961` rewrite at cherry-pick). **Aeldari archetype reshape DELIVERED** (`a7c98fc`: "Battle Host"→"Warhost", Phoenix Lord trio template, tests rewritten; 1535 green in its worktree, demo exit 0). Modularization Stage B complete on `claude/sim-modularization-stage-b` (fingerprint-identical motion proof) — awaiting the user's go to push and open its pull request.

---

**WAVE 239 (2026-06-11, CLOSED) — Acts of Faith per-phase ADOPTED AS DEFAULT (metric-neutral, fidelity-first) + modularization Stage A folded with fingerprint proof + NEW STANDING ANCHOR gated 5.85 at zero eval cost. Chaos Space Marines archetype reshape still in build.**
**Acts of Faith per-phase (`SWEG_AOF_PER_PHASE`) measured and adopted default-ON** (`7834b75`): N=80 paired vs the 5.83 anchor came back **metric-neutral** (headline +0.03; Adepta Sororitas −0.62 inside the ±0.90 confidence interval, 31 flips; every other faction byte-flat) — the expected +2-4 uplift did NOT materialize, but the per-phase grant is the verbatim codex rule and the conservative cap's justification died with the invulnerable-save mapper fix, so it adopts on the fidelity-first precedent (conditional invulnerable saves). Legacy path behind `=0`. **Stage A fold:** Ed merged pull request 71; `origin/main` folded at the wave boundary, and the motion-proof fingerprint run on THIS branch's tree pre- and post-merge is identical (`45df5b56…`) — behaviour unchanged, anchor survives. Full suite 1500 green on the merged tree, demo exit 0. **NEW STANDING ANCHOR: `data/_anchor_sc7d_n80_log.json` (gated 5.85, raw 8.81, 5/22 in band)** — the Acts-of-Faith ON arm promoted directly (its config equals the new production default exactly; zero new battles). GitHub hygiene on the user's direction: Stage-2-function issues relabelled + `blocked` (#45-#49, #51), milestones "Stage 1 completion" (#44/#52/#61/#63) and "Post-convergence" created. **Residual surface (sim vs real, gated points):**
- **UNDER-pole:** Chaos Space Marines −19.3 (g16.8, archetype reshape IN BUILD), Astra Militarum −18.0 (g14.8, BANKED structural), Adepta Sororitas −17.8 (g14.0, findings F5/F3/F4/F7/F6 queued).
- **OVER-pole:** Adeptus Custodes +15.6 (g13.0), Imperial Knights +15.5 (g12.5), Aeldari +15.4 (g12.3, issue #44 diagnostic queued wave 240), Necrons +12.5 (g9.3), Adeptus Mechanicus +13.3 (g9.1).
- **In band (5):** Thousand Sons, Leagues of Votann, Chaos Daemons, Grey Knights, Drukhari.
**Late-wave additions (user session):** replay renderer victory-point display + army-table composition column built and verified (display-only); collision root cause FOUND by new `scripts/diag_overlap_audit.py` — `_do_charge` (code/simulator.py:11763-11772) places chargers one inch from target CENTER with no collision check and no movement event (REAL overlap 80–114/game + REPLAY drift up to 9.99 inches); deployment also skips collision. Movement-event emission sweep (telemetry-only) dispatched; behaviour-changing halves queued wave 240.
**NEXT:** (1) Chaos Space Marines archetype reshape lands (frame change → fresh anchor); (2) wave-240 gated collision levers: charge-end placement legality (one inch from base EDGE, collision-legal via `_collision_kwargs(attacker, allow_engagement=True)`) + deployment collision spacing, both gated + paired A/B; (3) Sororitas F5 Bringers of Flame ASSAULT leg; (4) Aeldari #44 scoped diagnostic; modularization Stage B build (own branch off main) when a slot frees.

**WAVE 238 (2026-06-11) — re-anchor on the defender-allocation frame: NEW STANDING FRAME gated MAE 5.83 + displacement Stage 2 recovered/verified/harvested (`724252e`, paired A/B in flight) + simulator modularization Stage A pull request 71 opened.**
Ed's defender wound allocation (pull requests 69+70, `SWEG_DEFENDER_ALLOC` default-ON) landed mid-wave; both in-flight anchors killed stale, merges folded and validated at wave boundaries. **Fresh N=80 re-anchor on `0550475`: gated 5.83** (raw 8.78, 5/22 in band). **NEW STANDING ANCHOR: `data/_anchor_sc7c_n80_log.json`.** Headline 5.71 → 5.83 is re-base churn (frame change, not keep/reject); the shape moved the right way — over-pole softened with defenders protecting objective-holders. **Displacement Stage 2** survived its build agent dying (WIP preserved `475c3c8`, completeness-verified: gate-off byte-identical, full-cluster objective-control rail, no-suicidal-feed rail, 6 tests green) and is cherry-picked as `724252e`; the `SWEG_DISPLACE_SWARM=1` N=80 paired A/B vs this anchor measured a **WASH MISSING ITS TARGET** (gated 5.83 → 5.90, +0.07; Adeptus Custodes −0.05 flat, Imperial Knights +0.83 wrong-direction; decisive movers Adeptus Astartes −1.06 toward target / Astra Militarum −0.83 away / Chaos Knights −1.21 away; ~100 flips concentrated in body-army factions = fires-but-churns) — **PARKED default-OFF**, code + tests kept; re-test candidate after the Chaos Space Marines archetype reshape changes body-army composition. **Modularization Stage A** opened as pull request 71 on the user's go (pure code motion, fingerprint-proven). Incident logged: false "anchor dead" read → redundant duplicate eval launched and killed; declare evals dead only from CPU-time-bearing process listings. **Residual surface (sim vs real, gated points):**
- **UNDER-pole:** Chaos Space Marines −19.3 (g16.8, deepened — positional re-diagnosis next), Astra Militarum −18.0 (g14.8, BANKED structural — displacement), Adepta Sororitas −17.1 (g13.4, findings 2–7 re-rank pending).
- **OVER-pole:** Adeptus Custodes +15.6 (g13.0, improved 2.0 — defender allocation), Aeldari +15.4 (g12.3, worsened 1.1), Imperial Knights +15.4 (g12.5, BANKED structural — Stage 2 A/B in flight), Necrons +12.5 (g9.3, improved 2.7), Adeptus Mechanicus +13.3 (g9.1, worsened).
- **In band (5):** Thousand Sons, Leagues of Votann, Chaos Daemons, Grey Knights, Drukhari (Death Guard g1.72, Chaos Knights g1.42 close behind).
**NEXT LEVERS (wave 239):** (1) **Acts of Faith `SWEG_AOF_PER_PHASE=1` paired A/B** vs the 5.83 anchor (IN FLIGHT; if positive, flip default-ON + re-anchor); (2) **Chaos Space Marines archetype reshape** (Pactbound Zealots real-list per `docs/FACTION_RESIDUAL_ANALYSIS.md` re-diagnosis — build agent in flight; frame change, fresh anchor on land); (3) **Sororitas findings 2–7 builds** per the dispatch table in `docs/SORORITAS_UNDERPOLE_AUDIT.md` (F5 Bringers of Flame ASSAULT leg first). Parked: Stage 2 displacement swarm (wash, see ledger); Warp Friends target refresh; Plasmancer Harbinger of Destruction rebuild; mapper extract_fnp structural fix; SWEG_FIGHTALT paired re-test.

---

**WAVE 227 (2026-06-10) — CSM per-unit Dark Pacts abilities BUILT + scoped A/B (faithful keep; gated default-OFF, flip+re-anchor pending). Standing anchor is STALE.**
Pivot from the parked scout-AI to the watchdog's pick: Chaos Space Marines (−15.1, 2nd-biggest residual, single-faction → scoped ~5-min A/B). Delegated the build to a Sonnet sub-agent; **I verified all four citations verbatim against the BSData cache — zero fabrication.** Four real datasheet abilities, gated `SWEG_CSM_ABILITIES` (default-OFF, byte-identical OFF), committed `d8df4e3`: **Despoilers** (Chaos Terminators, full Hit re-roll on Dark Pact), **Unholy Bloodshed** (Possessed, once-per-battle Devastating Wounds on Dark Pact), **Dark Zealotry** (Dark Apostle — replaces the weak reroll-1s proxy with the real +1-to-wound-melee; OFF keeps the proxy; wave-213 host-routing preserved), **Paragon of Hatred** (Abaddon army-wide Hit re-roll aura, was absent; honest under-proxy as a Warmaster one-of-N pick). Audit 327/327, full suite 1244 passed, both-gate CLI exit 0, flags via overrides.json (rules 7/9). **Scoped A/B (N=80, both arms fresh, --factions "Chaos Space Marines", paired): Chaos Space Marines +1.89 (faithful, even-handed — no opponent moved decisively); global gated MAE ~6.10 → ~5.99 (−0.11, slightly confounded by anchor drift).** A faithful KEEP (real cited rules, lifts the under-pole, harms no one) — the bulk of the CSM under-pole is deeper (output/durability), so +1.9 is a partial bank as expected.
**STALE-ANCHOR FINDING (important for the loop):** the OFF byte-identical check showed the fresh current-code gated-OFF run differs from the standing anchor `_reservescap_on_n80_log.json` by **83 flips / CSM 40.6→40.0** — the anchor is 4 waves old (pre-scout-AI vintage) and has drifted ~0.6 (within noise, but real). Reusing it as OFF introduces small error; running both A/B arms fresh (as done here) is the correct workaround. **NEXT (frame action, watchdog to time): flip `SWEG_CSM_ABILITIES` default-ON (3 code sites `== "1"` → `!= "0"` + update the OFF tests) AND run a clean full N=80 re-anchor at current defaults (deploy-AI ON, scout-AI OFF, CSM-abilities ON) → fresh standing anchor + frame, resolving the drift for the AM/GSC/IK levers.** Then the queue: Astra Militarum −17.5 (biggest), Genestealer +14.6 over (metric-tuning guard), Imperial Knights +17 over.

---

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

**WAVE 210 (2026-06-06) — DECISION POINT FOR THE USER: the fork-agnostic levers are exhausted; the substantive residual is
the POSITIONAL/PHYSICS axis, blocked on your scale-fork call.** Production frame = the real CA-2025-26 deck rotation
(`SWEG_PRIMARY_DECK` default-ON), gated MAE **~4.89**. The session worked three big tracks to faithful conclusions, all
recorded and all leaving the baseline untouched (every experiment gated):
- **Avenue 1 (mission/scoring deck) — LANDED, faithful −0.30.** The CA-2025-26 rotation (Take and Hold / Purge / Scorched-Burn
  / Terraform / The Ritual) is the production frame (5.19 → 4.89), after catching a mission↔map measurement confound that had
  hidden its value.
- **Avenue 2 (physical board control) — BLOCKED on a USER scale-fork.** Board-wide no-overlap collision is DEAD for this
  one-Unit-per-model greedy-no-pathfind representation (4 faithful make-way attempts all strand big-base Knights, reach
  64%→16-20%; the N=80 A/B regressed 4.89→6.81 by global reach-loss). The terrain pair shares the SAME big-base-navigation
  dependency for its movement half, and its line-of-sight half is UNFAITHFUL (10e ruins block the whole footprint — "cannot
  see over or through" — so doorway-LoS is a regression, dropped). All collision/terrain code is gated default-OFF + inert.
  **The scale fork (invest in big-base pathfinding vs marker-only abstraction vs shelve physics) is yours to call.**
- **Under-pole ABILITY hunt — EXHAUSTED.** Astra Militarum / Adeptus Mechanicus combat is wave-86-VETTED-FAITHFUL (their gap
  is positional, not an ability); CSM Dark-Pacts coverage was REFUTED as a lever (3 attempts incl. true Lethal/Sustained
  Hits, all net-negative on self-damage; reverted). The remaining un-vetted under-shooters are mild (Daemons gated 1.31).
- **Net:** both poles (Imperial Knights over ~19.4; Astra Militarum / Adeptus Mechanicus under, ~half positional) reduce to
  the positional/physics representation — which is blocked on the scale fork.
- **ONE live fork-agnostic DECISION remains (not a cleanup): land per-model weapon firing?** The per-model loadout mechanic
  (`SWEG_PERMODEL`, Stages 1-4 built, Stage 5 unbuilt) is FAITHFUL — each model fires its own real weapons + rolled dice;
  single-model units stop firing mutually-exclusive arm weapons (the Wraithknight fired BOTH arm cannons; 523/907 over-collected).
  It is gated-OFF only because wave-99 measured it REGRESSING +0.27 (it un-masks elite over-rate — Votann/Chaos Knights fire
  their real stronger guns and over-shoot more; Imperial Knights stay flat, so it does NOT fix the over-pole). **But that
  "leave gated" call predates the user's 2026-06-03 fidelity-first rail ("never gate a faithful mechanic off to protect the
  metric").** So whether to land it default-ON (faithful, regresses the frame while the compensating positional root is
  scale-fork-blocked) vs keep it gated (clean frame until the fork lands) is a genuine user fork — escalated, with a fresh
  deck-frame N=80 A/B in flight to decide on CURRENT data.

---

**Last updated:** Wave 218 (2026-06-08) — throughput tooling is the BLOCKING priority (user); paired/Common-Random-Numbers eval mode core LANDED (`adf9140`, `--log-games` + `scripts/paired_delta.py`, 13 tests). Push delegated to watchdog (commit locally, don't block). Sequence: Veterans gate-off confirmation → finish speed #1 (sequential + sentinel) → #2 → #3 → resume band waves.
Gated MAE **5.76 → 5.19** (objective-game arc), then the user-greenlit displacement re-model's avenue 1 (Scorched Burn +
Terraform + The Ritual + the CA-2025-26 deck rotation). A measurement CONFOUND (the deck locked each mission to one map via
the shared seed) had made the rotation look metric-neutral; **fixed (mission draw decoupled from the map), the clean
decoupled deck = gated 4.89, a real −0.30 vs the 5.19 baseline.** Drivers: The Ritual's No-Man's-Land-only scoring compresses
the camping over-shooters toward target (Emperor's Children / Thousand Sons / Sororitas down) AND IK is net-DOWN
(70.4 / 19.70), so Purge's re-inflation is outweighed. 4 of 10 real primaries now score by their real rule (Take and Hold /
Purge / Scorched-Burn / Terraform / The Ritual), all faithful.

**METRIC RE-BASE (wave 203, watchdog-adopted): the deck is now the production eval frame (`SWEG_PRIMARY_DECK` DEFAULT-ON).**
The real Chapter Approved 2025-26 rotation is the CORRECT frame (the Warp Friends target win rates were generated under the
real rotation, not all-Take-and-Hold). **Post-adoption headline gated MAE is ~4.89 on a NEW deck-frame scale — NOT comparable
to the pre-adoption all-Take-and-Hold 5.19** (same kind of deliberate re-base as wave-145's live-target/field-weighting
re-base; numbers before and after the adoption are different scales). Out-of-band scan confirmed net-faithful (over-shooters
compressed toward target, Imperial Knights eased 20.84→19.70, under-pole unchanged, none cratered). Reversible:
`SWEG_PRIMARY_DECK=0` restores the legacy all-Take-and-Hold frame for an audit/A-B. The remaining 5 primaries (Unexploded
Ordnance / Supply Drop / Hidden Supplies / Linchpin / Burden of Trust) are an opportunistic follow-on to complete the frame
(minor, non-blocking).

**Avenue 2 (physical board control) — wave 204-208.** Instrument-first (`diag_boardcontrol`, gated `SWEG_BOARDCTRL_INSTR`):
the over-pole has two physical-board gaps — OC over-packing on contested markers (145%, a Knight's 170mm base over-fills the
3" ring) and 50% of big VEHICLE/MONSTER models sitting inside ruins they should be walled out of. **Collision sub-lever
REJECTED (wave 208):** board-wide no-overlap collision + make-way (3 attempts: ring-fill / distinct-slot / sidestep) N=80
A/B regressed 4.89→6.81 — it strands the big-base Knights (reach 52%→20%, both Knights crater) and inflates the mobile shooty
cluster (global reach-loss in this greedy-no-pathfind one-Unit-per-model representation, not selective displacement). Kept
gated default-OFF (`SWEG_COLLISION`/`SWEG_MOVEPLAN`), production deck frame 4.89 unaffected. The marker-only-collision variant
is escalated to the user (departs from the board-wide directive). **Now: the TERRAIN pair (Stages 3-4, `SWEG_RUINWALLS`) —
the other high-leverage board-control lever (50% big-in-ruin), independent; non-INFANTRY can't cross ruin walls >2" (sourced).**

**What landed (default-ON, env-gated for isolation):**
1. **Damaged-bracket generalization** (`SWEG_DMGBRACKET`, wave 191, commit `adb3000`): the 10e "Damaged: 1-X Wounds
   Remaining" datasheet bracket (OC + −1-to-Hit) is now data-driven from BSData for **all 260 catalogue units with a real
   bracket**, replacing the Knight-only wave-85/188 heuristic. The mapper resolves link-referenced shared Damaged abilities
   via the registry (`extract_damaged_bracket` / `_gather_damaged_profiles` — caught a bug where only 1/42 Knights extracted
   inline). Even-handed, metric-neutral (5.76→5.71), removed a Knight-only metric-favorable bias.
2. **Balanced objective-contest AI** (`SWEG_CONTEST`, wave 192, commit `2ef7c4c`): refines the STEAL value in
   `pick_move_intent` so a SPARE body contests a WINNABLE (bracket-aware effective-OC) enemy-held marker — JUST-ENOUGH +
   AFFORDABLE (the hold-check) guards = the faithful contest, NOT the rejected wave-95 Stage-E flood. **First lever in many
   waves to move the over-pole DOWN: Imperial Knights gated 25.63 → 21.19; headline 5.71 → 5.52.** Over-flood tell passed.
3. **Free-contest extension** (`SWEG_FREECONTEST`, wave 193, commit `dad5ac3`): a spare IN-range gunline contests a
   winnable+shootable enemy marker while STILL shooting (zero shot-cost). Recovered the shooty factions the pure contest
   over-corrected (Aeldari/T'au/Necrons back toward target). Headline **5.52 → 5.19**.

**Where the residual is now (the diagnosis, waves 194-199 — instrument-first, both poles):** the over-pole plateaued on the
contest family at gated ~21 (IK still #1). The cheap COMBAT axes are EXHAUSTED on BOTH poles and the residual is ONE
characterised missing fidelity — **DISPLACEMENT / board-pressure representation**:
- OVER-shooters (TSons/EC/WE/Custodes/Sororitas/Votann/Drukhari, sim 60-68% vs ~50-54% real): over-SCORE primary VP (~+20/g)
  the SAME way the field does — combat is faithful (output in-line / WE melee faithfully-high; durability faithful; the
  over-score is NOT a clean (i)/(iii) lever, diag_overscore/overshooter/melee_output).
- UNDER-shooters (AM/AdMech, sim 28-29% vs 44-45% real): durability FAITHFUL (vehicles get cover MORE, better effSv, more
  invuln — diag_durability REFUTED the over-fragile hypothesis; the "+26% taken" was a 3-opponent-slice artifact, field-avg
  taken is normal). Output genuinely low (AM 56 / AdMech 49 vs control 80 field-avg) but FAITHFUL (low-output-per-point
  durable armies; keywords parity, Orders/Doctrinas modelled, screening = field-rate 12%). Reality wins 45% with the SAME
  low output → the gap is HOW they hold despite losing the firefight.
- **Both poles = the sim resolves objective-holding by raw model SURVIVAL; real 10e DISPLACES out-fought armies off
  objectives (pressure / maneuver / fall-back / the threat of being charged) — UNMODELLED.** Diagnostic instruments (all
  gated, read-only): `scripts/diag_ocflip / diag_overscore / diag_overshooter / diag_delivery / diag_durability /
  diag_underoutput / diag_shootloss / diag_melee_output / diag_contest_faction`.

**STRATEGIC FORK — escalated to the user (2026-06-05), headline blocked pending the decision:**
(a) the DISPLACEMENT re-model (the genuine remaining fidelity, but DIFFUSE — the whole board-control/maneuver layer, high
cost + uncertain) vs (b) BANK ~5.19 as the practical Stage-1 floor and move to Stage 2. Watchdog's flag to the user: 5.19 is
a SYSTEMATIC bias (durable-holder over / broad-gunline under), NOT noise — banking it into Stage 2 would distort the points
equation (re-fit-poisons-Stage-2). Watchdog lean = one BOUNDED faithful displacement probe before committing, banking-with-
documentation as fallback. **The loop worker is HOLDING; the watchdog is doing the user's UI workstream (worktree
`claude/ui-improvements`) as fill.** No cheap combat lever remains — the idle-default "unmodelled under-shooter rules" does
NOT apply (the rules ARE modelled; the gap is displacement).

---

**Earlier — Wave 183 (2026-06-04):** ANTI-TANK PICKER FIX LANDED (faithful) but a HONEST NEGATIVE RESULT: the
combat/loadout track is EXHAUSTED. After diagnosing the #1 under-side lever across waves 177-182 (the BSData mapper picks
weapon choices by expected-damage-vs-a-Marine, so it drops anti-tank options — durable gun-platforms under-fire their real
anti-armour), the fix landed as **14 cited per-unit anti-tank loadout corrections** in `data/overrides.json` (commit
`4340e3b`; BSData-sourced from the parsed `secondary_weapon` fields, spot-checked un-fabricated; the weak 3-profile mix
fallback was correctly dropped at 40% accuracy). **N=80 A/B: gated 5.84 → 5.80 = NEUTRAL (−0.04, within noise), and
Imperial Knights FROZEN-UNDER (76.7% sim, gated 26.0, no fall).** The "unified lever" hypothesis (arming opponents' anti-
tank drops the durable Knight) is **REFUTED — now twice (wave-107 N=40 + wave-183 N=80, de-flattered).** The under-shooters
(Astra Militarum 13.54→13.03, AdMech 11.92→12.40) did NOT rise either, even though the Onager (an AdMech platform) was
among the corrected guns — because the fix is EVEN-HANDED (their opponents armed up too, so the win rate washes). **KEPT
all 14 as faithful data-fidelity hygiene (the sim now fires the real competitive guns); did NOT re-fit** (watchdog rail).
**CONCLUSION: both poles of the residual are the POSITIONAL/REPRESENTATION floor, not combat/loadout/output levers** —
Imperial Knights = durable TITANIC objective over-hold; AM/AdMech = the deeper durable-SHOOTY-VEHICLE under-valuation that
anti-tank did NOT touch. The faithful combat track is at its floor (~5.8 gated). **Accounting (14-vs-the-56-flagged, no
silent cap):** 16 non-Legends genuine corrections identified (the scope doc's detailed table; its summary "26" was an
inconsistent overcount) → 14 applied this wave + 2 already-correct from wave-107 (Ravager, Talos) = all 16 pinned; the
other 40 flagged groups = 21 Legends (deferred, not fielded), 5 picker-already-correct + 4 transports + trivial sub-groups
(correctly EXCLUDED). Minor catalogue-hygiene gap: CSM / Emperor's Children Defiler variants not pinned (only the World
Eaters Defiler was scoped). **NEXT LEVER (watchdog re-frame): the durable-shooty-vehicle under-valuation, instrument-first,
beyond anti-tank** — OR the hard positional-representation re-model (user-authorised, high-risk, washed before), OR declare
the faithful track at its floor and document the structural residual. Watchdog's call. [Wave 175-176 de-flattering detail
below.]

**Wave 175-176 (2026-06-04)** — SYSTEMATIC LIST-REALISM PASS LANDED (user-ruled, commit `6c6cb6d`):
the eval now fights with the REAL competitive lists for every fixed-core faction. **HONEST DE-FLATTERED BASELINE: N=80
gated 5.87** (`data/wf_wave175_listrealism_n80.txt`), 4/22 in band — UP from the flattered 3.93/4.05, which were an
ARTIFACT of fake fragile lists (the archetype builder's 0.3 seed slice dropped each faction's cited durable/support core
and random-filled cheap fragile units). Per-faction SEED_FRACTION overrides (precedent: Votann/Custodes) now realize the
real cores, even-handed: AdMech 0.65, Astra Militarum 0.55, CSM 0.65, Sororitas 0.55, Grey Knights 0.45, T'au 0.55
(MENU seeds IK/CK/Daemons/EC/Aeldari/WE/Tyranids LEFT alone; Death Guard deferred — Mortarion eats the seed budget).
**THE DE-FLATTERED LANDSCAPE LOCALIZES THE #1 LEVER — the sim's durable-unit valuation is INCONSISTENT:** durable SHOOTY
VEHICLES under-rated (Astra Militarum gated 13.54 / Sim 28.6, AdMech 11.92 / 28.3, CSM 11.94 / 41.2 — gun platforms that
under-output + over-die), while durable TITANIC/MELEE over-rated (Imperial Knights 26.11, World Eaters 14.31, Votann
8.42, Tyranids 7.45 — objective over-hold + the melee floor). Fixing the shooty-durable-vehicle under-valuation would
close AM+AdMech+CSM TOGETHER = the single biggest under-side lever (a Custodes-style elite-low-model issue, but for
gun-platforms). NEXT: diagnose the durable-shooty-vehicle under-valuation (instrument-first); CSM Dark Pacts (#52) sits
behind it. The over-side bounding-fidelity-track + Death Guard list-realism are parked. [Wave 170-171 coherency flip
detail below.]

**Wave 170-171 — COHERENCY FLIPPED TO DEFAULT-ON (user-greenlit; Stage B is now the
default, commit `73ee2f4`). HONEST BASELINE at the time: N=80 gated 3.93 (later de-flattered to 5.87 by the wave-175
list-realism pass; `data/wf_wave170_cohere_default_n80.txt`).
Faithful 10e Unit Coherency, cited; the OFF path (`SWEG_COHERE=0`) still reproduces 4.05 byte-identical. The symmetry the
positional rebuild predicted is CONFIRMED at N=80: **Imperial Knights 78.0→74.8 (gated 27.45→24.09, −3.3 above noise** —
body squads contest the marker) and the under-HOLDER **Necrons rose (gated 4.88→3.27)**, Sororitas 4.05→2.29. Accepted
collateral (M4-inseparability, the over-side floor): Adeptus Astartes left band (0→2.52, Marine over-hold), World Eaters
10.0→11.57. Net +0.12 improvement. **REFINEMENT:** Astra Militarum did NOT rise (~flat 2.79→3.03) — Guard is NOT a clean
under-holder; its gap is output/screening/list, re-segment in UNDERSHOOTER_PLAN. Over-side Group-2 melee levers all
EXHAUSTED (attacker-count refuted / split-fire neutral / fight-alternation rejected `SWEG_FIGHTALT` / battle-shock null);
the over-side bounding-fidelity-track-vs-accept-floor fork is parked (user's call). **Current axis = UNDER-SIDE**
(UNDERSHOOTER_PLAN): AdMech deep diagnostic running on the new baseline (Thread B), CSM Dark Pacts holistic (#52). Stage-2
re-price (balancer gate-off-vs-on) queued. [Wave 168 fight-alternation reject detail below.]

**Wave 168 — COMBAT REBUILD (fight-phase alternation) user-greenlit, order CORRECTED to
verified 10e (chargers first; Remaining step starts NON-active/defender; commit `afdd2a3`), fairly A/B'd → DEFINITIVELY
REJECTED. Corrected-order alt-only N=40 gated **7.31** (vs OFF 4.20 — even worse than the wrong-order 6.70). Same severe
backfire: durable melee/elite UP (World Eaters +23.4, **Imperial Knights +39.7 / gated 36.7**, Chaos Knights, Death
Guard, Custodes, Daemons), fragile shooters crushed (Necrons, T'au, Astra Militarum, AdMech). The DOUBLING (faithful 10e
= locked units fight twice/round) dominates; sim melee already calibrated to once/round → unfaithful-in-effect.
`SWEG_FIGHTALT` kept gated default-OFF. The fight-phase lever is DEAD.
[Wave 166 build detail below.]

**Wave 166 — GROUP-2 #2 fight-phase alternation, variant (a) full-faithful-doubling BUILT
(gate `SWEG_FIGHTALT`, cited, OFF byte-identical, commit `c306932`) + A/B'd + REJECTED (wrong order; superseded by the
wave-168 corrected-order definitive reject above). alt-only N=40 gated **6.70**
(vs OFF 4.20) — severe backfire: the DURABLE-melee/elite armies went UP (World Eaters 64→69, Imperial Knights gated
34.3, Chaos Knights, Death Guard, Custodes, Daemons) and the fragile shooters DOWN (Necrons 11.7, Astra Militarum 9.7,
T'au, AdMech). Faithful 10e ~doubles fight frequency for locked combats and the DOUBLING dominated the in-phase-
retaliation rein. REJECT (not metric-protection): real tournaments use twice-per-round melee yet show WE at +13.9 not
+24.5, so naive doubling moves the sim FURTHER from reality — the sim lacks the bounding fidelity (Fall-Back disengage,
most combats resolving in one exchange). Kept gated default-OFF. **The lever isn't dead, the DOUBLING is** — STEP-1's
over-credit is real (WE denies 56.5/btl), so NEXT is variant **(b)**: defender retaliates in-phase WITHOUT the second
own-turn fight (isolates the rein, no doubling). If (b) also fails → fight-phase lever dead → #3 battle-shock crumbling.
Honest baseline N=80 gated **4.05** (default) / **3.93** (Stage B on). [Wave 162 diagnostic detail below.]

**Wave 162 — GROUP-2 MELEE DIAGNOSTIC: candidate #1 (per-model melee attacker-count cap)
REFUTED; the real lead is #2 fight-phase alternation. Instrumented melee (read-only): (1) the sim IS one-Unit-per-model
(`add_squad` builds `size` Units sharing `squad_id`), BUT (2) the archetype lists are size-1 SWARMS universally — 65-78%
of units sit in size-1 squads across ALL factions (World Eaters 69%, Astra Militarum 77% — the under-shooter is
HIGHEST), so no large-squad melee over-count exists AND the representation is faction-neutral; (3) attacker-models-in-
Engagement-Range per defender-model ≈ 1.0-1.95 (plausible, no gross over-count). → #1 has no lever. **THE REAL LEAD:
the Fight phase iterates ONLY `active.units` — the active player fights ALL its units and the defender doesn't swing
back until its OWN turn (no 10e alternation), which differentially favours MELEE AGGRESSORS = the Group-2 over-shooters.**
NEXT: instrument + (watchdog-confirmed) build 10e fight-phase alternation (#2). Honest baseline N=80 gated **4.05**
(default) / **3.93** (Stage B on). Squad rebuild concluded (B faithful+positive, D faithful-neutral, E rejected); the
floor residual is now being worked via the over-shooter diagnostic. [Wave 161 Stage D detail below.]

**Wave 161 — SQUAD REBUILD COMPLETE (behavioural investigation concluded). Stage D
(unit-orchestrated split-fire shooting, gate `SWEG_SQUADSHOOT`, cited `simulator.split_fire`, commit `a9f87bf`) BUILT +
A/B'd: D-only N=40 gated 4.19 (wash), B+D N=40 4.17, B+D N=80 **4.03** vs B-only N=80 3.93 / OFF 4.05. D's effect FLIPS
sign across N → within noise → **faithful + metric-NEUTRAL** (the over-shoot is a MELEE representation issue, not
shooting inefficiency, so split-fire structurally can't reach it). D LANDS gated default-OFF (keep-if-faithful); NOT in
the metric default (B alone 3.93 is the gain; B+D 4.03 adds noise → any future flip is B-only).

**REBUILD OUTCOME (the user's Q11=(c) positional re-model, waves 157-161):** C+A infrastructure (byte-identical) →
**B coherency = faithful + metric-POSITIVE** (the one real gain: N=80 4.05→3.93, Imperial Knights −3.3 / 27.45→24.09;
flip-to-default pending USER) → **D split-fire = faithful + metric-NEUTRAL** (lands gated) → **E cohesive-hold =
unfaithful-in-effect + REJECTED** (reverted). The rebuild DENTS the Knight floor (27→24) but does NOT close it — the
residual is the MELEE one-Unit-per-model over-representation, which a positional/shooting rebuild structurally cannot
reach. Honest baseline: N=80 gated **4.05** (default) / **3.93** (Stage B on). **NEXT lever: the Group-2 / OVERSHOOTER_
PLAN melee-representation work (melee attacker-count), or Stage 2** — per the watchdog. Stage-B flip-to-default is the
USER's call (routed via watchdog). [Wave 160 Stage E + Wave 159 Stage B detail below.]

**Wave 160 — SQUAD REBUILD STAGE E TESTED + REJECTED (net regression, reverted). Stage E
(promote `_m4_cluster_intent` to a general squad-hold default, gate `SWEG_COHEREHOLD`) was built + gate-tested, then
A/B'd: E-only N=40 gated 4.73, B+E N=40 gated 4.49 — both regress vs OFF/B-only 4.20. It crushes Imperial Knights
(79.5→62.9) but by over-flooding markers with cheap-Objective-Control hordes (Drukhari +12, Orks +9) while cratering
Daemons/Astra Militarum/T'au — an UNFAITHFUL sledgehammer that amplifies the horde over-representation, not a fix. NOT
metric-protection: E makes the sim less faithful, so it is rejected. Reverted to wave-159 `644efef`. [Wave 159 Stage B
detail below.]

**Wave 159 — SQUAD REBUILD STAGE B LANDED (first behavioural stage, gate `SWEG_COHERE`):
mid-game Unit Coherency enforcement. After every model has taken its individual move, `Battle._enforce_squad_coherency`
pulls any model left >2" from its nearest squadmate back toward the squad centroid within its remaining move
(deterministic; lone / Advanced / Fell-Back models skipped). The faithful 10e core rule the one-Unit-per-model
representation breaks. Cited `simulator.coherency_enforcement`. Default-OFF, OFF byte-identical (N=80 OFF reproduces
4.05 exactly). **N=80 A/B: gated 4.05 → 3.93 (−0.12 improvement); Imperial Knights 78.1→74.8 (gated 27.45→24.09,
−3.36, above noise) — the #1 residual moving the intended way (body squads mass Objective Control, contest the Knight).**
Collateral: Adeptus Astartes leaves band (tighter Marine squads over-hold, gated 0→2.52); in-band 9→5 overstated
(Orks/T'au/Death Guard only 0.12–0.31 over the edge). N=40 was a noise wash (4.20→4.20); N=80 is the robust read.
HONEST: this DENTS the floor (Knight still +27), not a resolution — full lever is B+E+D + over-shooter fidelity.
Audit clean, run.py exit 0 both paths, 1124 tests green (5 new). Migration order: C (157) → A (158) → **B (done,
this wave)** → E (cohesive hold, reuses `SWEG_COHERE`) → D (split-fire, `SWEG_SQUADSHOOT`). OPEN FORK for watchdog:
flip `SWEG_COHERE` default-ON now (faithful AND improves headline) vs hold for the combined B+E landing. NEXT: Stage E.
[Wave 158 Stage A + Wave 157 Stage C + Wave 156 TITANIC-overwatch detail below.]

**Wave 158 — SQUAD REBUILD STAGE A LANDED (byte-identical scaffold): per-squad
activation substrate behind gate `SWEG_SQUADACT`. `Battle.__init__` gains `_squad_move_intent: dict` +
`_squad_activated_this_phase: set` (reset each Movement phase); when the gate is ON, the Movement loop computes
`pick_move_intent(...)` ONCE per squad on its first alive model (keyed by `squad_id`, `id(unit)` fallback for
single-model units), caches it, and emits one `UnitActivated` per squad — but every model still runs its own
`_do_move`, so the cached intent is **unread** and the scaffold is inert. Byte-identical because `pick_move_intent` is
deterministic and `UnitActivated` is renderer-only telemetry the evaluator never reads. **Verified three-way
byte-identical** (clean-base == gate-OFF == gate-ON N=40, all 2213 bytes, gated 4.20, 8/22 in band), audit clean,
run.py exit 0 both paths, 1119 tests green. This is the activation substrate the behavioural stages read.
[Wave 157 Stage C + Wave 156 TITANIC-overwatch detail below.]

**Wave 157 — SQUAD REBUILD STAGE C LANDED (byte-identical infra, commit `f43f862`): the
four bespoke once-per-codex-unit-per-round gate sets (Acts of Faith + 3× Strands of Fate) generalized into one
`Army._unit_budget_used` dict + `unit_budget_available(effect,key)` / `mark_unit_budget(effect,key)` (key = squad_id
or profile.name, identical). **Byte-identical (empty N=40 eval diff before/after)**, net −24 lines, 1119 tests green.
This is the FOUNDATION for Stage A (per-squad activation reuses this budget). The squad rebuild (user's Q11=(c)
authorised positional re-model) is the systemic lever for the per-model representation floor.

**Wave 156 — TITANIC OVERWATCH BUG FIXED → honest baseline 4.17 → **N=80 gated 4.05**
(9/22 in band). 10e: TITANIC units CANNOT Fire Overwatch (verbatim "You cannot target a TITANIC unit with this
Stratagem" — the TARGET is the FIRING unit; user-corrected). Excluded TITANIC from `_fire_overwatch`'s eligible
shooters → removes the illegal Knight overwatch that inflated them when Overwatch went default-ON: Chaos Knights
+12.7→+9.3, IK +31.8→+30.4. A faithful over-side improvement (not a knob). **4.05 is the new honest reference
baseline** (net of waves 155-156: 3.90 flattered → 4.17 honest-with-bug → 4.05 honest-fixed). 1119 tests green.
NEXT: the squad rebuild Stage C (user's Q11=(c) positional re-model, pure-infra first stage) on 4.05 + the
user-requested stratagem-fidelity cleanup batch (7 items, behind the rebuild). [Wave 155 flip detail below.]

**Wave 155 — HONEST RE-BASE: Fire Overwatch + Go To Ground FLIPPED to default-ON
(user-authorised fidelity-first baseline; audited faithful wave 154). **New honest N=80 baseline: gated MAE 4.17, 9/22
in band (UP from 6)** (`data/wf_wave155_honest_baseline_n80.txt`) — the prior 3.90 was FLATTERED by suppressing two
universal core mechanics. This is an honest RE-BASE, not a regression: the distribution is MORE accurate (3 more
factions correctly placed); the MAE rose only because the already-out-of-band Knights widen under faithful Overwatch
(IK 28.82, Chaos Knights 9.40). **4.17 is the new reference baseline for all rebuild A/Bs.** Gate semantics:
`SWEG_OVERWATCH`/`SWEG_GTG` now default-ON, disable via explicit `=0`. 1119 tests green. AdMech diagnostic: archetype
MISSING Kastelan Robots + Hastarii (durable anchors — list-fidelity gap, held for after the rebuild); the N=40
AdMech-GtG improvement WASHED at N=80 (AdMech −12.2). **NEXT: the squad rebuild (user's Q11=(c) authorised positional
re-model) on the honest 4.17 baseline** — the systemic lever for the IK + over-shooter representation floor. The
per-faction faithful-rule dive remains complete; this re-base + the rebuild are the remaining structural levers.
[Wave 154 audit detail below.]

**Wave 154 — CORE-MECHANIC AUDIT: the 3.90 baseline is itself slightly UN-faithful. Fire
Overwatch (`SWEG_OVERWATCH`) + Go To Ground (`SWEG_GTG`) are BOTH faithfully implemented (audited vs 10e — 1 CP, correct
triggers/restrictions, even-handed) but suppressed default-OFF. **Both-on A/B regresses (N=40 4.15 → 4.29; GtG-alone
4.30)** because the OVER-RATED armies exploit them: Fire Overwatch inflates the durable Knights (big-gun 6s-overwatch;
Chaos Knights +6.3→+13.9), and GtG protects the INFANTRY over-shooters' bodies (WE +14.7→+17.7, Tyranids/Sororitas/
Drukhari up) MORE than it helps the infantry under-shooters. So the honest faithful baseline (both-on) is ~0.15 HIGHER
than the suppressed 3.90 — the 3.90 has been flattered by gating-off faithful mechanics the over-shooters exploit. 5th+6th
line of evidence for the per-model representation floor. **The FLIP (turn both on, fidelity-first, re-bases the headline
up) is the USER's call — NOT flipped (both stay gated default-OFF); watchdog carries it.** NEW under-side lead: GtG
closing AdMech (−12.6→~−6) means AdMech's structural gap is partly infantry shooting-fragility. [Wave 153 over-side
conclusion below.]

**Wave 153 — OVER-SIDE diagnosis CONCLUSIVE; per-faction + counter-play exploration
EXHAUSTED at N=80 gated 3.90. Four waves (150-153) confirmed the over-shooter cluster + IK floor + AdMech structural
= the one-Unit-per-model MELEE REPRESENTATION over-rating, via 4 independent lines: WE rule-audit (all buffs
conservative/clean, no knob), CSM holistic re-scoped (Marks need per-unit mark-assignment infra; Dark Apostle
mitigation doesn't exist), and the **kiting counter-play A/B REGRESSED (`SWEG_KITE` headline 4.15→4.50, WE +14.7→+16.5
WORSE — focusing durable Berzerkers wastes shots; the problem is per-model OUTPUT not target selection)**. SWEG_KITE
kept gated default-OFF (documented experiment; OFF baseline unaffected). **The path below 3.90 is the SYSTEMIC
representation work — the squad-rebuild / Q11 positional re-model (needs explicit USER build-go; re-prices Stage 2) or
screening AI (complex/regression-prone). That fork is WITH THE USER (watchdog surfaced it).** Remaining per-faction
micro-levers are tiny/under-side (Daemons #49 ~in-band). **The faithful autonomous per-faction dive is essentially
complete; the big remaining lever needs a user strategic decision.** [Wave 149 N=80 confirmation detail below.]

**Wave 149 (N=80 CONFIRMED) — **N=80 gated MAE 3.90** (`data/wf_wave149_postdive_n80.txt`),
down from the 4.09 N=80 baseline before this stretch's wins. The abilities dive (waves 144-149) net-closed ~0.19 at N=80
on top of the P0 fixes (which took it ~4.55→4.09). **T'au markerlights HELD at N=80** (−8.5 → −5.2, gated 4.30 → 0.95 —
the base +1 BS + [SUSTAINED HITS 1] vs Guided buff was genuinely unmodelled; committed `e980bf4`). **AdMech abilities
WASHED at N=80** (−12.2 → −12.6 — the N=40 Machine Vengeance +1.0 was noise; AdMech's −12.6 is confirmed STRUCTURAL, not
abilities — the AdMech abilities dive is exhausted). Abilities-dive tally: faithful wins = Necrons Relentless Onslaught,
Daemons faction-fix, T'au markerlights; modest/neutral = AdMech Machine Vengeance (kept, reusable substrate) + leader
auras (kept fidelity); dead-end handled honestly = CSM Dark Pacts (over-modelled → holistic #52).

**Honest N=80 landscape (3.90), biggest actionable gated errors:** IK 26.82 (representation floor) · **World Eaters
10.00** · **AdMech 8.42** (structural) · CSM 6.63 · **Votann 6.61** · Drukhari 5.40 · Tyranids 4.27 · Sororitas 4.05 ·
Necrons 3.18. **The OVER-shooter cluster (WE/Votann/Drukhari/Sororitas/Tyranids ~30 gated pts combined) now dominates
the remaining actionable error** — the highest-leverage remaining direction is the over-shooter DIAGNOSIS (are any
over-MODELLED, like CSM Dark Pacts was? if so, removing faithfully LOWERS them). NEXT: diagnose World Eaters +13.4
(Blessings of Khorne / Blood Tithe / Berzerker abilities / detachment for an over-model), then Votann; CSM holistic
(#52) remains the biggest under-shooter lever. [Wave 148 detail below.]

**Wave 148 — AdMech MACHINE VENGEANCE lands (the watchdog's top AdMech lever):
Belisarius Cawl's per-target designation (army-wide re-roll Hit vs one designated enemy while Cawl alive), built by
MIRRORING the Oath of Moment substrate (commit `0407e09`). **N=40 A/B: AdMech −10.8 → −9.8 (gated 6.66 → 5.64),
headline 4.27 → 4.23** — the FIRST AdMech lever to move the needle, validating the watchdog's refined thesis
(army-wide designation mechanics > single-unit leader auras, which were neutral in wave 147). KEPT (faithful, no
over-application, metric-positive). The per-target-designation SUBSTRATE is now reusable for T'au markerlights,
Necrons Worthy Foes, Lord Discordant Spirit Thief. AdMech still −9.8 under → the BULK of its gap is structural
(output/durability vs field, or representation), not abilities. **N=80 baseline (29eba8e, pre-MV) = gated 4.09**
(`data/wf_wave147_baseline_n80.txt`); biggest gated errors IK 27.32 (representation floor), WE 9.87, AdMech 8.07,
CSM 6.63. NEXT: extend the reusable designation substrate (T'au markerlights, T'au −4.4 under) OR diagnose the
over-shooter cluster (WE +14.4). [Wave 147 detail below.]

**Wave 147 — ABILITIES DIVE on the under-shooters, re-targeted on a fresh N=80
table. **N=80 baseline = gated 4.09** (`data/wf_wave147_baseline_n80.txt`; post measurement-fix + faction-fix +
Relentless Onslaught). Biggest actionable gated errors: IK 27.32 (representation floor), World Eaters 9.87,
**AdMech 8.07**, CSM 6.63, Drukhari 5.86, Votann 5.97, T'au 4.30. Two abilities-dive findings this stretch, BOTH
showing the watchdog's "under-shooter = unmodelled abilities" thesis is only PARTIALLY right where the ability is
already (mis)modelled or too small: **(146) CSM Dark Pacts** is already OVER-modelled (a +1-hit/+1-wound
double-proxy inflating CSM); the faithful per-unit/one-keyword fix REGRESSES in isolation (band-aid pattern) — must
be done holistically with Marks of Chaos + Dark Apostle (task #52), REVERTED. **(147) AdMech leader auras** built
faithfully (commit `3caecdd`: Manipulus Galvanic Field [Lethal Hits] + Dominus FNP re-pointed to a single
Kataphron, both single-occurrence so no over-application; verified verbatim at BSData, correcting the watchdog's
specs; the AdMech +1-hit army rule Doctrina is already modelled) — **METRIC-NEUTRAL (AdMech −10.8→−10.6, headline
4.27→4.26)**, KEPT as fidelity. Two single-unit buffs can't close a −12 gap → the AdMech under-shoot is mostly
elsewhere (output/durability vs field, or representation). NEXT: re-target the dive (World Eaters over-shoot
diagnose-first, T'au under, deeper AdMech/CSM). [Wave 145 P0 detail below.]

**Wave 145 — TWO P0 LANDINGS (watchdog wide-investigation re-prioritised queue):
**(B) the CSM/Daemons faction-misassignment DATA BUG** — the highest-leverage item — root-caused to a clean BSData
faction-keyword name mismatch ("Heretic Astartes" ≠ "Chaos Space Marines"), so 31 generic Chaos-Marine datasheets
(Legionaries, Chosen, Havocs, Chaos Lord, Possessed, Cultists, etc.) were filed faction="Chaos Daemons": CSM could
not field its own battleline (fake cult-marine soup) AND the marines polluted the Daemons random-fill pool. Fixed
with a 3-line mapper alias (`FACTION_KEYWORD_ALIASES` in factions.py + `canonical_faction_keyword` in
`iter_unit_entries`), regenerated parsed.json (EXACTLY 31 units re-keyed `chaos_daemons_*`→`chaos_space_marines_*`,
0 other content changes), re-keyed 2 overrides + 3 Stage-2 data files (pure re-key, prices unchanged), rebuilt the
CSM "Pactbound Zealots" archetype around the real Legionaries backbone. **N=40 A/B (both P0 fixes): headline gated
4.55 → 4.27; Chaos Daemons −14.8 → −4.1 (gated 11.68→0.95, nearly in-band — the residual was a data-contamination
artifact, the watchdog's prediction); CSM −9.0 → −12.0 (WORSE but FAITHFUL — real Legionaries list under-shoots
where the killier cult soup over-performed; the residual is now a clean target for the unmodelled Dark Pacts rule,
#48).** Kept per the prime directive (a real army beats a fake soup regardless of metric direction). 1117 tests
green, audit clean. **(A) MEASUREMENT FIDELITY** (committed `7f8ed76`): live tournament target + field-weighted
matchups re-based the honest baseline 4.14 → 4.55 (the old measurement flattered the sim). NEXT: the abilities dive
on the now-honest under-shoots — **#48 CSM Dark Pacts** (targets the −12 this exposed) and **#47 AdMech leader
auras** (−10.8/6.66). [Wave 145 (A) measurement-fidelity detail below.]

**Wave 145 (A) — P0 MEASUREMENT FIDELITY (watchdog wide-investigation re-prioritised
queue): the eval's comparison was subtly wrong in two faithful-to-fix ways, so the residual table was an
artifact. (1) `TOURNAMENT_TARGET` was a stale hand-transcribed dict that had drifted from the live Warp Friends
scrape (Chaos Space Marines hardcoded 52.8 but 55.6 live; Emperor's Children 47.9 vs 53.3; Aeldari 44.4 vs 41.6)
— now read LIVE from `data/warpfriends_rolling.json` (one self-consistent source with the noise floor + game
counts). (2) `run_matrix` averaged each faction's 21 matchups UNIFORMLY, but the real field is skewed (Adeptus
Astartes ~21% of games, Adeptus Mechanicus ~1.7%) and the Warp Friends per-faction win rate is itself measured
against that skewed field — now FIELD-WEIGHTED by opponent game share (apples-to-apples). The sim is byte-identical,
so this is a corrected MEASUREMENT, not a regression. **RE-BASED baseline: gated MAE 4.14 → 4.55** (raw 7.89,
6/22 in band) — the honest number; the old measurement was flattering the sim. The corrected table SHARPENS the
targets: **IK +30.5/gated 27.58** (representation floor, unchanged), **Chaos Daemons −14.8/11.68** (worst
actionable under-shoot), **AdMech −11.3/7.12**, **Necrons −10.2/6.97**, **World Eaters +13.1/9.65**, **CSM
−9.0/6.57** (deeper than the old target showed). NEXT (re-prioritised): **P0 faction-misassignment data bug**
(#51 — 10 CSM datasheets Legionaries/Chosen/Havocs/Terminators/Chaos Lord etc. mis-filed `faction=Chaos Daemons`
because the BSData `Chaos - Chaos Daemons.cat.gz` catalogue includes them and `faction_of()` keys on the cat file;
CSM cannot field its own backbone → fake cult-marine soup; also pollutes the Daemons fill pool — fixes the #1+#5
actionable under-shoots at once), then abilities dive (#47 AdMech / Dark Pacts) on whatever's still under,
enhancements/stratagems coverage, then P2. Audit clean, run.py exit 0, phase5 green. LOOP_QA wave-145.

**Wave 144** — UNMODELLED-ABILITIES DIVE (watchdog/user new direction): the
under-shooter residuals are UNMODELLED faithful abilities (leader auras / army+detachment rules / datasheet),
NOT the representation floor — real headroom. #1 Necrons Cursed Legion RELENTLESS ONSLAUGHT built (BSData-verified
+1-to-hit vs targets near objectives + ASSAULT on VEHICLE/MOUNTED; cherry-picked dd79371): **Necrons gated
−11.2 → −7.4, headline 4.34 → 4.14** (old measurement) — the FIRST metric-reducing faithful lever since the floor;
thesis VALIDATED. [Earlier waves 137-143 below.] Wave 136 — WHOLLY-WITHIN squad-granularity
fix for Engage/BEL (user catch)
completes the authentic secondary: `score_position_delta` (gated `SWEG_SECONDARY`) now counts a quarter only
when ALL a squad's models are wholly within it + >6" from centre (BEL: wholly within enemy DZ), correcting the
one-Unit-per-model over-credit. Faithful, even-handed, FAVOURS the compact Knight (N=40 deck+secondary 4.04 →
3.97, IK +26.8 unchanged) — reinforces that position cards aren't the Knight-penalty. Cited; 57 tests green; OFF
byte-identical. **NEXT PHASE (user directive): the MULTI-METRIC FIDELITY REVIEW** (turn-by-turn primary/secondary
VP, kills, survivors, tabling vs real data; watchdog-led, worker builds fixes; memory
`project-multi-metric-fidelity-review`). The anti-Knight package conclusion stands (representation floor). LOOP_QA
wave-136.

**Wave 135 N=80 VERDICT** — **the ENTIRE anti-Knight package (waves 123-135) is
EXHAUSTED faithfully.** N=80: deck+authentic-secondary 3.55 with IK +26.6 UNCHANGED (the secondary does NOT fix
the Knight — hypothesis REFUTED); combined (M4+secondary) 4.41, WORSE than either half (M4's frozen-under
dominates + the two fight over spare units). Built to the rules, NEITHER board control (M4, regresses) NOR the
secondary economy (neutral on IK) fixes the Knight's aggregate over-rate → it is a one-Unit-per-model
REPRESENTATION FLOOR. Per the §7 criteria: report the floor + STOP the package; all components gated default-OFF;
no knob/re-fit/gate-reach-back. The authentic secondary is faithful (possible small default-on, separate from the
anti-Knight goal, pending a clean A/B). Loop continues on post-package hygiene (#41 tabling). LOOP_QA wave-135.

**Wave 135 (build)** — SECONDARY economy REBUILT AUTHENTICALLY (Opus agent `73e30fb`) after
the user+watchdog caught the dedication scoring-gate was a fabricated knob: reverted the gate (position cards
auto-score on occupancy), positioning-bias only, rules-clean ACTION COST for Cleanse/Sabotage (OC>0 + not-in-
engagement + forgo shoot/charge + survive; Knight can't spare a unit → 0, emergent). **A/B: the authentic
secondary is NEUTRAL** — deck-only 4.07 → deck+secondary 4.04 (within noise; IK +26.3 → +26.7, NO drop), and
combined 4.13 (worse than M4-stack 4.03; the positioning bias fights M4 over spare units). Confirms the
watchdog's prediction (the authentic Knight secondary weakness is negligible). 1104 tests green, OFF
byte-identical. Running combined N=80 (decisive). Layer-3 timing + 3 new action cards unbuilt (likely won't flip
it). LOOP_QA wave-135.

**Wave 134** — SECONDARY Stage A built (deliberate-dedication, gated `SWEG_SECONDARY`,
Opus worktree agent `7d962ad`) + A/B. The dedication mechanism was MIS-TARGETED at POSITION cards (Engage/BEL):
net-negative (deck-only 4.07 → deck+dedication 4.20; IK +26.3 → +29.5, the OPPOSITE of the hypothesis) and it
LOST the M4 IK fix in the combined (the planner diverts spare units OFF the markers M4 massed them onto). ROOT
CAUSE: Engage/BEL are POSITIONAL (occupancy already captures the few-units weakness), not actions — gating them
on dedication is unfaithful. The substrate (dedicated_card + planner + even-handed spare predicate) is correct +
reusable. RE-SCOPE (Stage B): apply dedication/action-cost to the ACTION cards (Cleanse/Sabotage + 3 new), keep
position cards on occupancy. All gated default-OFF. LOOP_QA wave-134.

**Wave 133** — SECONDARY ECONOMY plan written (`docs/SECONDARY_ECONOMY_PLAN.md`),
the package's OTHER half (user-authorised authenticity rebuild). 3 layers: (1) action cards cost a unit, (2) THE
CRUX — scoring from DELIBERATE DEDICATION (a `dedicated_card` field + AI dedication planner; position/board
scorers gate on dedication so incidental presence no longer scores → a 5-6-unit Knight can't spare units →
scores less; even-handed, emergent from unit count), (3) per-turn timing. Asymmetric on a DIFFERENT axis
(low-MODEL armies can't churn/dedicate) → may pull down the OTHER low-model elites M4 inflated (Chaos Knights,
Custodes), breaking the primary-half inseparability — EMPIRICAL via the combined test. Build: Stage A (Layer-2
CRUX, gated `SWEG_SECONDARY`) → B (action cards) → C (timing) → D (combined M4+secondary, ablated, N=40→N=80).
LOOP_QA wave-133.

**Wave 132** — corrected the gunline exemption to the watchdog's NARROW rails
(move-costs-a-shot; pull hold-and-shoot). N=80 confirms the PRIMARY-half inseparability on the correct rails: IK
fix KEPT (+17.0) but NO aggregate gain (gated 4.26 vs baseline 3.83); Astra is FROZEN-UNDER not gunline-
disruption (exemption can't recover it). The 3 exemption versions triangulate: broad loses IK, narrow keeps IK
but recovers nothing → **board-control is exhausted as a PRIMARY-VP lever.** Narrow exemption kept (faithful,
gated default-OFF). **PIVOT (watchdog sequence): build the SECONDARY ECONOMY** (user's authenticity directive #44
— action-cost + DELIBERATE-DEDICATION scoring + per-turn timing), the package's OTHER half; the user's
hypothesis is the secondary half makes the few-units weakness bite. Plan-first wave 133. LOOP_QA wave-132.

**Wave 131** — **VERDICT: the anti-Knight package WASHES at N=80** (representation
floor). The M4-α gunline refinement (exempt productive shooters) RECOVERED the over-shooters (Drukhari
+16.2→+11.1, Chaos Knights recovered) but KILLED the IK fix (+16.1→+24.9) — **the board-control fix and the
frozen-under inflation are INSEPARABLE** (exempting the shooters exempts the very models massing to contest the
Knight). Refined N=80 4.13 / unrefined 4.16 vs baseline 3.83 (+0.30/+0.33). The fix is REAL+faithful (halves the
two biggest residuals) but can't net-improve without a knob. Per the §7 criteria: report the floor + STOP, no
further metric-chasing; all components gated default-OFF. The user's WIN-vs-wash call surfaced (keep the
unrefined stack for the target fix at the aggregate cost, or declare the floor). Per-faction representation work
is exhausted as an aggregate lever. LOOP_QA wave-131.

**Wave 130** — full-stack A/B (M4+Tarpit+`SWEG_FOCUS`) + ablations. **N=40 LANDED
(4.34→4.03) but N=80 REVERSED it (3.83→4.16, +0.33) — the N=40 move was NOISE.** The package ROBUSTLY fixes the
targets at N=80 (Imperial Knights +25.1→+16.1 −9, Chaos Daemons −9.3→−3.9 −5.4) but regresses the aggregate via
side-effects, DOMINATED by the **Astra gunline-disruption** (M4-α drags lascannon teams off firing lines, gated
+6.25 ≈0.28 of the +0.33) — a FIXABLE artifact, not frozen-under. Tarpit is NOT inert (adds −0.24 in the stack;
the pin fires end-to-end). All gated default-OFF. NEXT (wave 131): M4-α refinement (exempt productive shooters)
+ re-run stack N=80; tips-positive → land, else report the floor. LOOP_QA wave-130.

**Wave 129** — built anti-Knight stack **component 2: Tarpit-charge** valuation
(`SWEG_TARPIT`, default-OFF): an expendable chaff unit pinning a durable high-ranged brick it can't crack is
valued by the enemy shooting it DENIES (Big Guns Never Tire) instead of suppressed. **A/B: INERT** — Tarpit
alone is a wash (4.34→4.43) and does NOT move Imperial Knights (+24.8→+25.0); M4+Tarpit ≈ M4-alone (4.64≈4.65),
claws back NONE of the over-shooter inflation. Re-confirms (4th angle) the IK residual is POSITIONAL, not
combat — so the package's combat half is inert and the verdict hinges on M4-α. 8 tests + suite green; kept
gated default-OFF. NEXT: component 3 (`SWEG_FOCUS`) + full-stack A/B + ablations N=40→N=80. LOOP_QA wave-129.

**Wave 128** — built anti-Knight stack **component 1: M4-α** squad-cluster
positioning (`SWEG_M4`, default-OFF): a near-marker OC model not in melee genuinely moves into the 3" band so
a squad masses its OC on the objective. **N=40 A/B HALVES the target axis** (Imperial Knights +24.8→+13.3,
Chaos Daemons −14.6→−8.8, neither overshooting) **but REGRESSES the aggregate** (gated 4.34→4.65) — the
frozen-under spread inflated other factions. Expected for M4-alone (value is the STACK); kept gated
default-OFF. 7 tests + strategy suite green; cited. NEXT: component 2 Tarpit (`SWEG_TARPIT`), then the
full-stack A/B. LOOP_QA wave-128.

**Wave 127** — **USER DECISION (A): run the combined anti-Knight PACKAGE** (M4-plan
§7); the M4 hard-gate is LIFTED. Building a STACK of three faithful env-gated components — (1) M4-α `SWEG_M4`
(on-objective squads genuinely move models to cluster in the 3" band, faithful A1 not A2), (2) Tarpit-charge
`SWEG_TARPIT` (pin a durable Knight, value by enemy output denied), (3) `SWEG_FOCUS` (existing anti-armour
redirect) — each plan-first + own A/B, then a decisive full-stack run + ablations N=40→N=80. Pre-agreed: lands
→ keep + flag Stage-2 re-derivation; washes → report the floor and STOP (no knob/re-fit). This wave wrote the
component-1 build plan (`docs/M4A_BUILD_PLAN.md`); build next. LOOP_QA wave-127.

**Wave 126** — wired the universal **Insane Bravery** core stratagem (was
catalogued-but-no-op): in `_run_battleshock_phase`, a squad that would fail its Battle-shock test while
contesting an objective spends 1 Command Point to auto-pass, once per battle, even-handed, gated `SWEG_INSANE`
(default ON), cited `simulator.insane_bravery`. Faithful + bounded; N=40 A/B OFF 4.41 (== baseline) → ON 4.34
(−0.07, within noise) — landed default-ON as fidelity, not a metric claim. Full suite green (1046). A real
absent mechanic cleared while M4 holds for the user. LOOP_QA wave-126.

**Wave 125** — worked the watchdog's "while-holding" hygiene: fixed the stale
`primary_vp_cap_15` citation `_comment` (Leviathan → CA-2025-26) and did the Drukhari anti-tank read. The
anti-tank picker bias is REAL + systemic (mapper scores options vs a baseline Marine → anti-tank options lose)
but a WEAK IK lever (wave-107 A/B moved IK only +27.3→+26.6, within noise; Drukhari +4.6→+9.0) — so opponents'
firepower deficiency is NOT the IK cause; M4 (positional) is re-confirmed from a 3rd angle (after terrain w97 +
per-model w99). Faithful fix (target-aware firing-time weapon selection, per-model Stage 5 territory) queued
task #38, headline-weak, not built while M4 awaits the user. Floor holds; M4 is the user's call. LOOP_QA
wave-125.

**Wave 124** — detachment fab AUDIT (layer CLEAN: 29/34 faithful, 2 minor fabs
queued task #37) + corrected the STALE watchdog queue: P0 Candidate B (`SWEG_MASS`) LANDED wave 95, P1
terrain-realism DONE wave 97 + REFUTED (realistic terrain made IK WORSE). So every faithful lever around the
representation is confirmed exhausted — terrain refuted, per-model neutral, mission neutral, massing landed,
detachment layer clean. **M4 is the only headroom lever and it is user-gated; the loop is at the faithful
floor** (not silently ending — LOOP_QA asks the watchdog to re-prioritize for the next non-M4 lever, e.g.
Strategic Reserves variety, or confirm the floor). LOOP_QA wave-124.

**Wave 123** — M4 representation PLAN written (`docs/M4_REPRESENTATION_PLAN.md`),
plan-first + hard-gated. The reconnaissance reframed M4: the faithful MOVEMENT half already LANDED (Candidate B
`SWEG_MASS`, default-ON, gated 4.15 → 3.81, already in the N=80 3.69 baseline); the geometry half was REVERTED
(`SWEG_CLUSTER`, regressed + unfaithful); the OC contest + scoring timing are verified faithful; and the whole
mission/secondary economy is net-neutral. So every faithful lever AROUND the representation is exhausted — the
residual IS the one-Unit-per-model representation. The plan defines the deep change (M4-α: a squad holds a
marker as a COHERENT board-control actor, combat still per-model), its Stage-2 tie-in (forces a pricing
re-derivation), the frozen-under prior (likely wash), and the honest alternative (M4-β: declare the
representation FLOOR and stop). **The fork — (A) build M4-α vs (B) declare the floor — is the user's decision;
do not begin coding M4 until they pick.** The loop continues on the next faithful lever meanwhile. LOOP_QA
wave-123.

**Wave 122** — AI-PURSUIT LAYER BUILT + measured INEFFECTIVE → decoupled to
default-OFF. The watchdog-prescribed layer (`_assign_card_pursuit`: send ≤2 spare chaff toward a held card's goal
— enemy deployment zone for Behind Enemy Lines, forward objective for Cleanse — via a `pursue_target` honoured by
`pick_move_intent`; even-handed by capability, a Knight has no chaff) was built (cherry-picked `b98b460`, 20
tests). **The 3-way A/B settles it: N=40 deck+pursuit 3.96 (−0.17) WASHED at N=80 (deck-only 3.62 → deck+pursuit
3.60, −0.02), and the achieve-rate instrumentation is decisive — pursuit did NOT raise Behind Enemy Lines /
Cleanse achievement (35%→34% / 27%→24%, UNCHANGED).** The redirected chaff cannot reach the lethal enemy
deployment zone or hold an uncontrolled forward objective, so the small N=40 move was noise + a combat-cost
artifact (diverting chaff weakened the pursuer). **Not a faithful recovery → pursuit decoupled to explicit opt-in
(`SWEG_TAC_PURSUE` default-OFF); the deck (M2) runs deck-only by default.**

**CONVERGENT CONCLUSION (the headline of the whole mission-layer arc): the ENTIRE mission-scoring layer — M1
primary 50-cap (real rule, inert), M2 tactical deck (net-neutral), M3 per-Command-phase scoring (net-neutral),
the AI-pursuit layer (net-neutral) — is GATED by the one-Unit-per-model board-control REPRESENTATION (M4).**
Fragile distributed bodies cannot reach/hold objectives → they under-hold PRIMARY (the Imperial Knights +27
mirror) AND cannot achieve board-control OR action/position secondary cards. **M4 is the SINGLE remaining root for
the whole per-faction residual.** Per the watchdog it is an ARCHITECTURAL change (how Objective Control / board
control is represented), warranting **plan-first + a watchdog/user check** (its size + the Stage-2 tie-in), NEVER
a per-faction OC knob. M2 + pursuit kept gated default-OFF (faithful mechanics, net-neutral, defeated by the
representation). **M4 is the next big lever — surfacing for the user's go before the build.** LOOP_QA wave-122.

**Wave 121** — AI-PURSUIT PLAN written (`docs/AI_PURSUIT_PLAN.md`) for the M2
artifact, with a key strategic fork. The pursuit layer (move a SPARE unit to pursue a held Tactical card — into
the enemy DZ for Behind Enemy Lines 37%, onto a forward objective for Cleanse 28%; Engage 89% already pursued) is
a faithful, even-handed, ONE-SIDED secondary lever (broad armies have spare bodies, Knights don't). **BUT its
upside is BOUNDED: 5 of the 9 deck cards are board-control (secure/defend/extend/storm/area_denial, stalling
9-50%), and that stall is the one-Unit-per-model REPRESENTATION gap — the SAME root as the IK primary over-hold.**
So the representation gap (M4) gates both the primary residual AND ~5/9 of the secondary deck. Fork surfaced to
the watchdog: (a) build the AI-pursuit layer now (bounded upside, prescribed) then M4, or (b) go straight to M4
(the deeper root). Default (non-blocking): build (a). Plan-first this wave; build next. M2 gated default-OFF.
LOOP_QA wave-121.

**Wave 120** — M2 at N=80 + hold-vs-achieve instrumentation (watchdog steer). **The
N=40 −0.28 was NOISE: N=80 OFF 3.69 → ON 3.62 (−0.07, neutral), band 7→5 (worse).** The instrumentation CONFIRMS
the AI-pursuit ARTIFACT: under M2-ON, Daemons/Astra are on TACTICAL and score only ~10 secondary (real ~25-35) —
their 2-card hands STALL (defend_stronghold 11% / extend_battle_lines 9% / area_denial 16% achieved; even
cleanse 28%, behind_enemy_lines 37%) because the combat AI doesn't PURSUE held cards. Grey Knights/IK are on
FIXED scoring a moderate ~17 (not inflated) — **the GK +11.8 overshoot is its TACTICAL opponents UNDER-scoring,
not GK over-scoring.** So M2's faithful mechanic is defeated by the AI-pursuit artifact → net-neutral. **Next
build: the even-handed AI-PURSUIT LAYER** (AI plays toward its held Tactical card — spread for Engage, push for
Behind Enemy Lines, commit to Cleanse — when its units CAN) → Tactical armies recover while the over-shooter
correction stays → M2(+pursuit) net-improves. M2 KEPT gated default-OFF (don't flip without pursuit). IK isolated
to the board-control REPRESENTATION (M4), not the mission layer. LOOP_QA wave-120.

**Wave 119** — M2 BUILT (real 2-card Tactical secondary deck, gated `SWEG_TAC_DECK`,
via dispatched Opus agent, cherry-picked `bbab0f2`): per-card dispatcher + Fixed-OR-Tactical track (FIXED = 2
kill cards; TACTICAL = 2-card hand draw/achieve/redraw — at most 2 sources not ~9-11), even-handed unit-count
choice, deterministic, OFF byte-identical, cited, 19 tests, suite green (1020). **THE FIRST FAITHFUL LEVER ALL
SESSION TO MOVE THE HEADLINE: N=40 A/B OFF 4.41 == baseline, ON gated 4.13 (−0.28), band 6→7.** Tightens the
spread faithfully (Votann/Custodes/AdMech/CSM toward band). Blemishes: **Grey Knights +11.2 OVERSHOOT, Daemons
−4.7, and IK did NOT drop (+1.1 — it's on the FIXED kill track)**. These point to the one fidelity gap: **the
real per-Fixed-card 20-VP/game cap is missing** (kill-elite Fixed cards over-score) — the immediate refinement
(M2b), a real CA-2025-26 rule. KEPT M2 gated default-OFF (faithful + net-positive; add the 20-cap + N=80 confirm
before flipping ON). Stage C (~6 missing action cards) TODO. Live baseline 4.41. LOOP_QA wave-119.

**Wave 118** — M2 PLAN written (`docs/M2_TACTICAL_DECK_PLAN.md`): the real 2-card
Tactical secondary deck, the watchdog's leading lever now that scoring-timing/(iii) is off the table. Confirmed
in code: the sim over-generates ~9-11 secondary sources/round (2 Fixed + 2 position + Cleanse + Sabotage + all 5
Board Tier-A all scored), so both armies max the 40 cap = "the wash". Real CA-2025-26 = 2 Fixed OR a 2-card
Tactical hand (draw/achieve/redraw) — at most 2 sources. Plan: (A) the hand state machine, (B) Fixed-vs-Tactical
choice (even-handed, unit-count-driven), (C) add the ~6 missing action cards (the broad army's tools), (D)
measure + keep-if-faithful. Env-gate `SWEG_TAC_DECK`. Hypothesis: the low-model Knight can't churn a 2-card deck
→ its secondary drops vs broad armies → +27 narrows; if it washes, points to the one-Unit-per-model
representation. Plan-first this wave; build (Stage A) next. Live baseline 4.41. LOOP_QA wave-118.

**Wave 117** — M1 (Primary 50-VP total cap, watchdog/user-approved mission-pack
audit): the sim only had the 15/round cap so primary could run to 60; added `min(primary,50)` in `_decide_winner`
(real CA-2025-26 rule, kept ON by default, `SWEG_PRIMARY_CAP_50=0` to isolate, cited; fixed stale
`primary_vp_cap_15` citation). **N=40 A/B EXACTLY ZERO across all 22 factions (IK +26.5 → +26.5)** — metric-inert
because primary tops out ~44 and capping a high game 60→50 doesn't flip the durable Knight's win. **M1 + the
wave-116 M3 (net-neutral) prove VP-MARGIN levers (cap, timing) do NOT move the win rate; the lever must make the
OPPONENT out-score the Knight — that is M2 (the real 2-card Tactical deck; the sim over-generates ~9 secondary
sources/round → both max 40 = the "wash", hiding the Knight's real secondary weakness).** M2 is next (plan-first).
Suite green (1001). Live baseline 4.41. LOOP_QA wave-117.

**Wave 116** — DOUBLE CORRECTION to the diagnostic arc. (1) The eval ALREADY runs
vanilla IGOUGO per-player turns (verified: 0 alternating calls), NOT the alternating model — so (iii) was never
a "foundational un-interleaving" the user must authorise; the IGOUGO machinery exists. (2) Built the REAL
per-Command-phase primary scoring (gated `SWEG_CMDSCORE`, default-OFF, `_score_objectives(only_for=...)` inside
the IGOUGO loop, cited): **clean N=40 A/B is NET-NEUTRAL (OFF 4.41 == baseline, ON 4.41)** — it redistributes
(helps static holders Grey Knights/Astra, brings over-shooters Sororitas/Orks/Tyranids down, but HURTS mobile
takers Chaos Daemons −14.6 → −20.8) and **does NOT fix Imperial Knights (+26.5 → +27.3): the durable Knight
tightens its primary margin but still WINS, so its win rate is robust to the timing.** **REFUTES "scoring-timing
is the IK lever" — the IK over-shoot is a one-Unit-per-model durable-concentrated-holder REPRESENTATION limit,
not a timing artifact; the user does NOT need to authorise a foundational (iii) change.** `SWEG_CMDSCORE` kept
gated default-OFF (faithful real timing, net-neutral, +1 band). The faithful sim levers (timing, positional AI,
combat) are now ALL exhausted/net-neutral on the convergent residual — the genuine structural floor. Suite green
(1001). `docs/RESIDUAL_CONVERGENCE_2026-06-02.md`, LOOP_QA wave-116.

**Wave 115** — CONVERGENCE UNIVERSALLY CONFIRMED: batch-checked the 8 remaining
out-of-band factions; across ALL 14 diagnosed factions the primary-VP delta tracks the win rate one-to-one
(Leagues of Votann +13.8 / Sororitas +11.1 over-hold and over-shoot; Astra Militarum / Grey Knights / AdMech
−2.7/−3.0 under-hold and under-shoot; tabling negligible, secondary a capped wash everywhere). **The whole
per-faction residual is ONE axis — primary board-control — and the single faithful lever is the user-gated (iii)
un-interleaving. The headline is genuinely blocked on the user's (iii) decision.** `docs/RESIDUAL_CONVERGENCE_2026-06-02.md`.

**Wave 114** — CONVERGENCE: diagnosed Necrons + spot-checked CSM / World Eaters /
Thousand Sons; the WHOLE per-faction residual reduces to ONE axis — primary board-control / mission fidelity.
ALL never tabled, secondary always a 40-cap wash, primary the whole differential. Durable elites OVER-hold
(Imperial Knights +27, Thousand Sons +9); mobile-melee + out-massed holders UNDER-hold (Daemons, World Eaters,
Necrons −13.9, CSM −9). **No separable faction-specific mechanic anywhere — the user-gated (iii) un-interleaving
is the dominant remaining lever for the whole board, and the loop is genuinely blocked on the user's (iii)
decision.** Secondary contributing factor (noted, not pursued): every army maxes the 40 secondary cap, erasing
the secondary differentiator. Writeup `docs/RESIDUAL_CONVERGENCE_2026-06-02.md`. Live baseline ~4.41. LOOP_QA
wave-114. Prior wave 113 detail follows.

**Wave 113** — over-arming sweep (watchdog hygiene): audited the 27 secondary-blanking
overrides; the prior MUTEX-SWEEP handled the genuine choices, ONE genuine under-arming found + fixed — the
Adeptus Mechanicus **Skorpius Disintegrator** had its real fixed Disruptor missile launcher (S9 AP-2 D3.5 A3
twin-linked) wrongly dropped for a blanket convention; RESTORED it (cited, Belleros main-cannon mutex kept
suppressed). Non-gated N=40 A/B: **gated 4.48 → 4.41; Adeptus Mechanicus −11.3 → −9.9 (+1.4, right direction);
IK/Daemons unchanged** — a rare NON-frozen-under win (a one-sided fidelity correction arming an under-shooter).
Live baseline now ~4.41. Full suite green (997). **The headline lever remains the user-gated (iii) un-interleaving
(both IK +27 and Daemons −14.7 depend on it — see wave 112).** Prior wave 112 detail follows.

**Wave 112** — DIAGNOSED the Chaos Daemons −14.7 under-shoot as the SAME primary
board-control residual as the Imperial Knights +27 (inverted), unifying the two biggest residuals → strengthens
the user-escalated (iii) un-interleaving fix (see the "Wave 112" section below). Prior wave 111 detail follows.

**Wave 111** — entering-round primary scoring (option ii, watchdog-approved, gated
`SWEG_ENTERSCORE` default-OFF): score Primary on control ENTERING each of rounds 2-5 (before that round's
combat) vs the baseline end-of-round-after-combat snapshot — a faithful approximation of 10e per-Command-phase
scoring, even-handed, cited `simulator.primary_vp_entering_round`. **Clean N=40 A/B REFUTES it as the IK lever:
OFF gated 4.48 == baseline (zero drift); ON 4.61 (+0.13, ~neutral) but Imperial Knights +26.6 → +27.5 (it
RAISED the Knight), Chaos Daemons −14.7 → −24.3 (COLLAPSED).** Pattern: entering-round scoring favours STATIC
HOLDERS (gunlines that hold entering the round — Astra Militarum −6.3 → −0.2, AdMech −11.3 → −5.6, Necrons
−13.9 → −11.4 all improved) and punishes MOBILE TAKERS (melee armies that charge onto markers DURING the round,
esp. their round-5 charges which entering-scoring drops). A single-snapshot timing fix in the
alternating-activation model is fundamentally biased — it collapses 10e's TWO per-player-Command-phase scorings
into one. **The clean fix REQUIRES (iii) un-interleaving to real per-player turns — FOUNDATIONAL + USER-ESCALATED
(do NOT build without the user's go); the (ii) experiment strengthens the case for it.** Kept `SWEG_ENTERSCORE`
gated default-OFF (live baseline 4.48 holds), not flipped. Full suite green (997), audit clean. LOOP_QA wave-111.

### Wave 112 — Chaos Daemons −14.7 under-shoot DIAGNOSED: it is the SAME residual as IK +27 (unified)

Per the watchdog steer, instrumented Daemons vs 8 opponents (200 games, `scripts/diag_daemons_wave112.py`;
writeup `docs/DAEMONS_UNDERSHOOT_DIAGNOSIS_2026-06-02.md`). Daemons are tabled 0x, keep 35-58% of units, all
games go 5 rounds → NOT a survival/arrival issue. The loss is PRIMARY VP (27-36 vs opponents' 30-41); secondary
a 40-cap wash. Only **22% of alive Daemon units are within 3" of a marker** (the deep-strike melee army fights
instead of holding; on-marker OC contest ~even). **The Daemons −14.7 and the IK +27 are the SAME primary
board-control / mission-fidelity gap, inverted — this unifies the two biggest residuals and strengthens the
user-escalated (iii) un-interleaving fix, which would address both at once.** No separable buildable-now
Daemon-only lever; did not touch Daemons stats. Live baseline holds at 4.48 (no code change). LOOP_QA wave-112.

### Earlier — wave 109-110: the VP-fidelity diagnostic that led here

VP-FIDELITY DIAGNOSTIC (user ruling: the re-fit path is KILLED; the
+27 is a SIM-FIDELITY gap in how the game is WON — tournaments use the SAME stats, so a win-rate gap cannot be
the stats). Instrumented IK vs 7 broad armies (`scripts/diag_ik_vp_wave109.py`; writeup
`docs/IK_VP_FIDELITY_DIAGNOSIS_2026-06-02.md`). FINDINGS: (1) **the Knight wins on VICTORY POINTS, NOT
combat/tabling** — it tables the opponent 0-2/25, never gets tabled, all games go 5 rounds, the broad army
keeps 25-37% of its units. (2) **The differential is PRIMARY VP (IK ~44 vs opp ~30, +14); secondary is a
40-cap WASH** (both blow past 40; Cleanse/Sabotage already live — not the lever). (3) **The Knight's primary
lead COMPOUNDS R2→R5 (+3.3 → +6.0); the broad army's board control COLLAPSES under attrition (8.4 → 5.9)** —
the one-Unit-per-model "elite combat over-rated / model-count board control under-rated" gap. Candidate fixes:
positional AI WASHED (`SWEG_MASS`); secondary is faithful; the **command-phase primary-scoring timing** fix is
BLOCKED by the alternating-activation round model (no per-player Command phases). Surfaced a build-direction
FORK to the watchdog (LOOP_QA wave-109): score primary on PEAK in-round control / start-of-round control /
authorise structural un-interleaving — the scoring surface, so plan-first + watchdog steer before building.
**This supersedes the "re-calibration is the next step" framing — the headline lever is now the PRIMARY
board-control fidelity fix, NOT a stat re-fit.** Live baseline holds at 4.48 (no code change this wave).
**Wave 110 follow-up CONFIRMED the premise:** of the markers the broad army controls ENTERING a round, 52%
(150/288 over 48 games) are STRIPPED by that round's combat before the end-of-round score — so the broad army
floods + controls markers but its bodies are killed in-round and it scores nothing, while the durable Knight
holds through combat. The end-of-round-after-all-combat single snapshot is the unfaithful mechanic; the lead
fix is option (ii) score primary on START-of-round control (plan-first, env-gated, awaiting watchdog steer).

### Earlier — wave 108: Go To Ground core stratagem (gated `SWEG_GTG`) — 8th FROZEN-UNDER lever

A targeted INFANTRY unit may spend 1 Command Point for a 6+ invuln + Benefit of Cover until end of phase
(even-handed `_maybe_go_to_ground`; reuses `transient_invuln_4`; verbatim-cited `simulator.go_to_ground`).
Clean N=40 A/B: OFF gated 4.48 == baseline (zero drift); ON 4.56 (+0.08, NOISE) — metric-neutral. REFUTED the
"helps the fragile under-shooters" hypothesis (Chaos Daemons WORSE, −14.7 → −16.2 — an even-handed defensive
save buff helps shooty gunlines, not a melee aggressor). Kept gated default-OFF. Committed `52539c6`.

### Earlier — wave 107: anti-tank picker fix (watchdog Q18) — REFUTED as an IK lever (7th frozen-under)

Built the watchdog's Q18 anti-tank fix; the wave-106 diagnosis was wrong on two counts. (1) OVERRIDE-pinned,
not a systemic mapper bias — a past de-over-arming (`data/overrides.json` DRK-DIAG-5) kept the anti-infantry
Disintegrator and discarded the anti-tank Dark Lance on the Ravager/Raider. (2) The systemic mapper mix-scoring
(b) was BUILT then REVERTED (net-unfaithful: re-labelled 71 ranged + 48 melee picks, promoted one-shot
Hunter-killer missiles, demoted specialists). (3) The cited override fix (c)'s N=40 A/B REFUTED the
"first non-frozen-under IK lever" hypothesis: Imperial Knights +27.3 → +26.6 (noise), Drukhari +4.6 → +9.0
(the bad loadout was COMPENSATING for Drukhari over-tuning), gated 4.13 → 4.30. KEPT the Ravager → Dark Lance
pin (faithful — the list's named anti-tank platform; Ravager-only gated 4.48), REVERTED the Raider pin
(a transport, not an anti-tank platform). Committed `e76956a`. Memory `project-antitank-picker-bias`;
LOOP_QA Q18-OUTCOME (fork: keep the Ravager now vs bundle the Drukhari loadout correction with the
re-calibration — open).

### Earlier — wave 105 (Fire Overwatch + the STRUCTURAL FLOOR)

**Fire Overwatch (gated `SWEG_OVERWATCH`), and the session's STRUCTURAL FLOOR.** Fire Overwatch (out-of-phase shooting at chargers/reserves, hits on 6s, 1
Command Point) is faithful but REGRESSES at N=80 (OFF 3.52 → ON 3.69) — driven by Imperial Knights +27.0 →
+30.4 (its big guns overwatch effectively); frozen-under, kept gated, not flipped. **SIX simulator-side
levers now (terrain, per-model structure, per-weapon dice, focus-fire, deployment, Fire Overwatch) are ALL
faithful but FROZEN-UNDER — none moves the IK +27, most are washes/small regressions.** The simulator-AI
track is at its FLOOR for this residual: the IK +27 (~half the gated error) is a STATS problem, needing the
FAITHFUL RE-CALIBRATION (re-fit per-faction stats/lists to the now-much-more-faithful sim) or the SCORING /
victory-point model — BOTH user-gated. Per the watchdog guardrail, the loop is REPORTING the floor and
HOLDING for the user's re-calibration go (the remaining queue levers #4-6 are expected to be the same
frozen-under washes; not worth grinding before the re-calibration). All fidelity work committed + gated
(default-OFF); live baseline holds. **The high-leverage next step is the re-calibration — the user's call.**

### Earlier — wave 103-104 (deployment lever: net-positive at N=40 but a wash at N=80; the IK-drop was an artifact)

**Deployment/screening (gated `SWEG_DEPLOY`).** Refined (gunlines at the zone midline, screen forward) →
N=40 4.13 → 3.75 (helped gunline under-shooters), but **N=80 confirmed a WASH** (3.52 → 3.44, inside noise) →
NOT flipped,
kept gated as a faithful metric-neutral fix (gunline under-shooters slightly better, IK slightly worse, net
wash); revisit at the re-calibration. The IK +27 remains a
re-calibration / scoring problem (the user's morning go). 17 tests pass, audit clean.

### Earlier — wave 102 (crude deployment: regressed; the IK-drop was a buried-own-Knights artifact, refined in w103)

**Intelligent deployment + screening (gated `SWEG_DEPLOY`), watchdog #2.** Crude version put gunlines at the
board edge → regressed (4.13 → 4.67) and showed an apparent IK-drop that wave 103 proved was an artifact
(buried IK's own Knights). Refined in wave 103 (above).

### Earlier — wave 101 (focus-fire: headline +better / IK +worse, frozen-under #4)

**Army-level FOCUS-FIRE (gated `SWEG_FOCUSFIRE`), watchdog #1 IK lever.** Opponents killed 0.00 big
Knights/game (won't-crack penalty); focus-fire concentrates when the army can collectively crack a brick. N=40
4.13 → 3.85 (headline better) but IK +27.3 → +29.0 (worse, frozen-under). FOUR simulator-side levers (terrain,
per-model structure, per-weapon dice, focus-fire) all leave/worsen IK +27 → it needs the RE-CALIBRATION or
SCORING model. Kept gated (bundle into the re-calibration; ~2× eval perf cost noted).

### Earlier — wave 100 (per-model Stage 4: per-weapon dice; both halves of the Knight hypothesis refuted)

**Per-model loadouts STAGE 4 (per-weapon Damage-dice rolling, gated `SWEG_ROLLDMG`).** BOTH halves of the
Knight hypothesis REFUTED — neither the weapon over-count (Stage 3) nor the mean-damage overkill (Stage 4)
reduces the Imperial Knights over-rate.
N=80 three-cell A/B: OFF 3.52 → per-model-mean 3.79 → per-model+dice **4.17**; Imperial Knights +27.0 →
+28.3 → +28.8 (flat/worse throughout), the strong elite armies (Votann +7→+13, Chaos Knights +2→+7) got
WORSE (frozen-under), and dice variance hurt the low-model elites (Custodes −3.8→−6.1). The IK over-rate is
durability/objective-holding, **triangulated THREE ways** (terrain + per-model structure + per-weapon dice)
— nothing about a Knight's guns moves its win rate. The re-architecture is a genuine FIDELITY win (each
model fires its real weapons with real dice, special weapons lost on death) but REGRESSES the headline
3.52 → 4.17 because per-faction stats are tuned to the OLD averaged sim — the fidelity-first debt the
deferred re-calibration (Q13) absorbs. Committed + GATED (default OFF). The real IK lever remains durability
/ objective scoring, NOT firepower. NEXT (pending user): Stage 5 + the re-calibration, vs pivoting to the
durability lever.

### Earlier — wave 99 (per-model Stages 2-3: firing reads each model's weapons; over-count refuted as the IK lever)

**Stages 2-3 (gated `SWEG_PERMODEL`):** plumbed `model_loadouts` onto `UnitProfile` and made `add_squad`
build one Unit per model from the loadout (each fires its own weapons, lost on death; pistols in melee;
single-model units stop over-collecting). The over-count fix went live but did NOT move Imperial Knights
(+27 flat) — it helped the strong elite armies over-shoot more (frozen-under). Faithful, kept, gated.

**Wave 99 / Stages 2-3:** Stage 2 plumbed `model_loadouts` onto `UnitProfile` (gate-inert, 4.13 unchanged).
Stage 3 made `add_squad` build one `Unit` per model from the loadout (`SWEG_PERMODEL`); single-model units
now fire only their actually-equipped guns (the Stage-1 over-count fix goes live); weapon-loss-on-death and
pistols-in-melee fall out of the existing per-Unit machinery; cited `simulator.per_model_loadouts`.
**THE A/B refuted the hypothesis:** same-N comparisons regress slightly (N=40 4.13→4.24, N=80 3.52→3.79) but
within the gated-MAE sampling noise (the OFF baseline alone swings 4.13→3.52 across N). The reliable
cross-N signal is per-faction: per-model HELPS the strong elite armies over-shoot MORE (Leagues of Votann
+6, Chaos Knights +5) and leaves Imperial Knights FLAT (+27→+28). So the weapon over-count was real (Stage 1
fixed it, a fidelity win) but removing it does NOT cut the Knight win rate — TRIANGULATED TWICE (terrain +
per-model): **the IK over-rate is durability / objective-holding, not firepower.** Per-model is a faithful
upgrade (kept, gated) but the frozen-under pattern, not the Knight lever. METHODOLOGY: per-model widens
variance → use N≥80 for its A/Bs. Stage 4 (per-weapon dice = the mean-overkill half of the hypothesis) is
the untested remaining piece. 949 tests pass, audit clean, run.py OK both gate states.

### Earlier — wave 98 (per-model Stage 1: mapper preserves loadouts + dice; over-collection diagnosed/fixed in data)

**Wave 98 / Stage 1 (data only):** the mapper now preserves `model_loadouts` (per-model weapons + raw dice)
and single-model units use proper option-picking instead of a flat weapon-walk. Diagnostic: 523 of 907
single-model units were over-collecting weapons (the Wraithknight fired both alternative arm cannons). Data-
only, metric 4.13 unchanged; the correction went live at Stage 3 (and, per above, did not move Imperial
Knights). The regen also synced a stale `deadly_demise` field (metric-neutral, kept per rule 7).

### Earlier — wave 97 (terrain rebuilt to competitive density, gated 3.59 → 4.13, refuted as the IK lever)

**Wave 97 rebuilt all stock maps to competitive Pariah Nexus terrain density** (`_competitive_terrain`: ~11
line-of-sight-blocking ruins + scatter, ~19% area, 180-degree even-handed, no clean cross-table sightline;
cited). N=40 gated 3.59 → 4.13 (regressed), and REFUTED the hypothesis: Imperial Knights got WORSE (+25.9 →
+27.3) — realistic terrain shields the durable Knight from return fire more than it limits its shooting, and
helps melee close. KEPT per the prime directive (the May-2026 target was played on realistic terrain;
reverting to sparse would be metric-tuning). Terrain is NOT the IK lever; the over-hold is durability
(LOOP_QA Q14).

### Earlier — wave 96 (core-rules quick-fix batch, gated 3.76 → 3.59)

**Wave 96 ran the core-rules-audit quick-fix batch** as three parallel worktree streams. LANDED Stream D+E
(rules-correctness): single Benefit of Cover (stale −1-to-hit removed), current-10e Ruins/Woods line of
sight (TOWERING no longer sees through ruins), Benefit-of-Cover AP0/Save-3+ exception for all models, Fall
Back FLY exemption removed. Gated 3.76 → 3.59, driven by Imperial Knights +27.0 → +25.9 and Drukhari +6.4 →
+4.7. Plus Stream B1 (Counter-Offensive citation). HELD Stream A (AI Objective-Control fidelity — faithful
but frozen-under regression) on `held/stream-a-ai-oc-fidelity` (`452ce81`), to land at the re-calibration
(Q13). DEFERRED Stream B2 (Insane Bravery registered but inert; P2 build) and unblocked P1.5 roll-damage.

### Earlier — wave 95 (positional re-model Candidate B landed, gated 4.15 → 3.76)

**Wave 95 LANDED the Q11 positional re-model** (Candidate B): the move AI masses a unit holding no
objective AND out of its own firing range onto the best holdable objective (arrive-in-cover) — the faithful
"idle units play the objectives" tactic, the dominant sub-cause. Gated 4.15 → 3.76, in band 8 → 9, Chaos
Daemons −22.7 → −14.7; Imperial Knights unchanged (+27, the over-shooter half can't be shot off).
Default-ON (`SWEG_MASS=0` re-gates).

### Earlier — wave 94 (geometry candidate regressed, reverted)

**Wave 94** built the geometry/clustering candidate (a unit on an objective credits Objective Control over
a coherency-extended footprint) → REGRESSED 4.15 → 4.30 (frozen-under: helped already-holding over-shooters,
not the under-shooters who don't reach markers). Reverted; pointed to Candidate B, which landed wave 95.

### Earlier — wave 93 (Q11 positional re-model scoped)

**Wave 93 scoped the Q11 positional re-model** (`docs/POSITIONAL_REMODEL_PLAN.md`). A within-3"-vs-6"
drill pinned the body-army on-marker OC gap to geometry/spread (secondary) + AI-not-massing (dominant).
Plan = `docs/POSITIONAL_REMODEL_PLAN.md` (Candidate A geometry first, then B AI-massing).

### Earlier — wave 92 (CA-2025-26 deck re-alignment complete)

**Wave 92 completed the CA-2025-26 secondary re-alignment** (Bring It Down 2+2(15+W)+2(20+W) max 6;
Assassination 4(4+W)/3(<4), no Warlord bonus; via destroyed-unit wound data in the snapshot). Across both
parts the deck re-alignment moved the headline 4.08 → **4.15** (cap-wash, flat), kept as fidelity. 7
cards re-valued, 5 board cards confirmed unchanged.

### Earlier — wave 91 (CA-2025-26 re-alignment part 1, 5 cards, metric-flat)

**Wave 91 did CA-2025-26 re-alignment part 1** (5 cards: No Prisoners 3→2, Cull 10/3→13/5, Engage
2/3/5→1/2/4, Behind Enemy Lines flat-4→3/4, Extend 5→4), ≥2-CA-source-verified; metric-flat (4.08→4.10,
cap-wash). The user ruled Q10 = Chapter Approved 2025-26 + Q11 = (c) the positional re-model.

### Earlier — wave 90 (Daemons re-diagnosed positional; secondary cap-wash; structural floor)

**Wave 90 re-diagnosed Chaos Daemons** as POSITIONAL (they survive 40-75% but lose the primary race),
not combat/attrition; found secondary is a CAP-WASH (both sides max 40, primary decides); consolidated
the dominant residual as ONE axis (primary/objective control: IK +27 over, Daemons −22 under). Gated 4.08
identified as a structural floor on the faithful track → escalated as Q11 (ruled this wave).

### Earlier — wave 89 (over-shooter detachments swept clean; over-rates are structural)

**Wave 89 audited the over-shooter detachments for fabricated buffs** — BSData-verified NEGATIVE finding:
they are already clean (fabrications swept in prior waves), so the over-shooter over-rates are structural,
not fabricated buffs. Two minor deferred flags (Custodes crit-on-5+ edition-conflict; a zero-metric Agents
fix). No code change. Memory `project-detachment-fabrication-pattern`.

### Earlier — wave 88 (Daemonic Manifestation built, real but metric-neutral)

**Wave 88 built Daemonic Manifestation** (the missing friendly half of the Chaos Daemons Shadow of Chaos
army rule) — real, cited, faction-gated, default-on — but the N=40 A/B was metric-neutral (Daemons
−22.2 → −22.5). The wave-87 diagnosis over-attributed; the Daemons residual needs re-diagnosis.

### Earlier — wave 87 (diagnosed Chaos Daemons −22; build planned)

**Wave 87 diagnosed the largest residual, Chaos Daemons (−22.2)** to the missing Daemonic Manifestation
rule and planned the build — which wave 88 then built and found metric-neutral (see above), so the
diagnosis over-attributed and the Daemons residual remains open.

### Earlier — wave 86 (mission-deck fork escalated; Tier B parked)

**Wave 86: verifying Tier B's secondary-card values surfaced that the sim targets the wrong mission
deck** — Pariah Nexus 2024 (what the sim approximates) vs Chapter Approved 2025-26 (the current standard
the May-2026 calibration target used). Escalated as a project-scope fork (`LOOP_QA.md` Q10, memory
`project-mission-deck-ca-2025`); Tier B parked for a unified deck-aligned re-alignment after the ruling.

### Earlier — wave 85 (Knights damaged-objective-control bracket re-added, real, gated 4.17 → 4.08)

**Wave 85 re-added the Knights' damaged-objective-control bracket** after the user reversed the wave-84
removal — it is a REAL 10e datasheet rule (BSData verbatim: Questoris −5 at ≤9 wounds, Armiger −3 at
≤5), cited, Knights-faction-gated, floored at 0. Gated 4.17 → 4.08; Imperial Knights +29.2 → +27.2.
Leftover IK +27.2 is the positioning finding. Lesson: `feedback-verify-stats-against-bsdata`.

### Earlier — wave 84 (OC contest verified faithful; damaged-OC removal later reversed)

**Wave 84 verified the summed-objective-control contest is FAITHFUL** (credited == raw per-model within
3"); the Knight over-controls because body armies have huge total objective control but get almost none
onto markers — a positioning / one-Unit-per-model representation gap. (Wave 84 also REMOVED the
damaged-OC bracket on a flawed read; that was wrong and wave 85 re-added it.) Reported
`project-oc-contest-faithful`.

### Earlier — wave 83 (Tier A board-control secondaries built + landed)

**Wave 83 built + landed Tier A** (the five real Pariah Nexus objective-holding / board-control
secondaries). N=40: gated **4.95 → 4.17 (−0.78)**, in band **6 → 9** — a clear faithful aggregate
win. Most over-shooters eased (Drukhari +18.6 → +9.7, Custodes/Sororitas/T'au down); board-control
under-shooters rose (Chaos Space Marines −19.2 → −11.3, Chaos Knights into band). It made Imperial
Knights WORSE (+19.1 → +29.2) because a durable Knight over-controls objectives and banks the new
board secondaries itself — which is what wave 84 then diagnosed. Full result + the sharpened
finding: `docs/SCORING_MODEL_OVERHAUL_PLAN.md`.

### Earlier — wave 82 (scoring overhaul scoped)

**Wave 82 scoped the user-authorised scoring-model overhaul** (`LOOP_QA.md` Q6: build the
scoring/victory-point overhaul, diagnose-don't-nerf, plan-first). Deliverable
`docs/SCORING_MODEL_OVERHAUL_PLAN.md`: primary scoring is faithful; the gap was the SECONDARY
economy (only 4 of ~12 tactical secondaries modelled). Wave 83 built Tier A from this plan.

### Earlier — wave 81 (contest/deny tested + reverted; the AI track concluded)

**Wave 81 built + tested redesign step #2 (contest/deny positioning) and it failed — the
diagnosis-predicted outcome.** Env-gated `SWEG_CONTEST`: a cheap chaff unit not on an
objective moves to CONTEST the nearest reachable enemy-controlled objective, to deny the
durable camper (Imperial Knights) its primary VP (naturally asymmetric — IK carries no chaff).
N=40 A/B vs 4.95: gated **4.95 → 5.14 (REGRESSED +0.19)**, **Imperial Knights +19.1 → +18.2
(only −0.9, still grossly over-rated)**, while the OTHER over-shooters got worse (Drukhari
+18.6 → +20.6, Votann +13.4 → +14.9). Reverted. The structural law (3rd confirmation): every
generic faithful AI improvement helps whoever has the better army, and the over-shooters HAVE
the better armies, so sharper play WIDENS the headline. Imperial Knights is a structural
VP-vs-durability SCORING residual, not AI-fixable → escalated as Q6 → user chose the scoring
overhaul (see above).

### Earlier — wave 80 (IK Armiger re-fit tested + reverted)

**Wave 80 ran the user's AI+re-fit hypothesis on the #1 residual (Imperial Knights)
and it failed.** The faithful re-fit toward the real Armiger-heavy tournament list made
IK WORSE — alone (gated 4.95 → 5.66, the efficient Armigers over-perform more in the sim)
and paired with focus fire (5.90, IK +39.5 / 88%). Reverted. **Firm diagnosis:** the IK
over-rate is the objective-HOLDING (the sim over-rates a durable camper because opponents
do not DENY its primary VP) — NOT the list (both shapes over-perform), the stats (current),
the rules (verified), or the shooting AI (a Knight can't be shot off — better targeting
only sharpens IK's own offence, confirmed 3×).

### Earlier — wave 79 (army focus fire built + tested, env-gated, regresses solo)

**Wave 79 built redesign step #1 (army-level focus fire) of the faithful AI track.**
Env-gated `SWEG_FOCUS`: the army nominates the most valuable durable enemy threat it
can hurt and its anti-armour weapons concentrate on it. It regresses solo (4.95 →
5.41): it HELPS the fragile over-shooter Drukhari (+18.6 → +14.2, its Ravagers get
focus-removed) but WORSENS the durable Imperial Knights (+19.1 → +25.9 — a Knight
can't be shot off, so the victims' fire is wasted while IK's own anti-armour sharpens
on the opponents' vehicles). Third confirmation that better SHOOTING AI sharpens the
durable over-shooters. **Next (the user's AI+re-fit path):** (1) rebuild the IK
archetype toward the real Armiger-heavy tournament list (the sim's big-Knight list is
over-gunned; Armigers are fragile so focus fire would remove them → IK down) — test the
re-fit PAIRED with focus fire; (2) build step #2 contest/deny (the real IK lever — deny
its primary VP, don't kill the Knight). Committed env-gated OFF; baseline unchanged.
Full detail: `docs/MATCHUP_FIDELITY_ANALYSIS.md`.

### Earlier — wave 78 (matchup-fidelity diagnosis + faithful-AI plan)

**Wave 78 opened the user-chosen phase (Q4 ruling): the faithful target/positioning
AI track + matchup-fidelity diagnosis.** A diagnosis+plan wave. Drilling per-matchup
(not aggregate) shows the residuals are driven by impossible-in-real-play lopsided
cells: Imperial Knights beat CSM/AdMech/Marines **100%**, Drukhari beat
Tyranids/CSM/AdMech **90%**; CSM loses **0%** to Emperor's Children, Daemons **0%** to
AdMech/Drukhari/TSON. Compared to real May-2026 play, the gap is almost entirely
**bucket (a), the opponent AI** — it does not focus-fire the durable/key threat, contest
and deny the camper's objectives, or allocate units to actions sensibly. Stats/rules
verified faithful (Knight T11/W26 already reflects the Dec-2025 update); one list note
(real winning Knights list is Armiger-heavy — flagged, not pulled). Full diagnosis + the
faithful-AI redesign plan: `docs/MATCHUP_FIDELITY_ANALYSIS.md`. The AI build executes in
the next waves (env-gated A/B; when it exposes an over-shoot, diagnose the faithful cause
— re-fit toward real lists now permitted — never a nerf).

### Earlier — wave 77 (per-unit Advance, metric-neutral; clean levers exhausting)

**Wave 77 was a consolidation wave.** Rotation-gating the tactical secondaries was
tested and REJECTED (Sabotage-off is gated 5.15 vs 4.91 on — the over-scoring is
net-positive, so reducing it regresses). Landed the per-unit Advance roll (real 10e:
one Advance roll per unit, not per model — the same bug class as the wave-76 charge
fix), a faithful correctness fix that is metric-neutral: gated 4.91 → **4.95** (within
N=40 noise) but in-band 5 → 6. **The clean impactful faithful levers are now exhausted**
— the two biggest residuals (Imperial Knights +19.1 durable camper, Drukhari +18.6
fragile) both need the opponent target/positioning AI, which regressed when tried
(wave 72). The strategic fork — take the AI-redesign + re-fit (goal-doc-restricted) vs
bank Stage 1 at ~4.9 — is **escalated to the user** (`LOOP_QA.md` Q4). The watchdog
ruled: do NOT start the AI-redesign + re-fit until the user rules; keep taking small
clean faithful fixes meanwhile (next: the missing Be'lakor datasheet for Chaos Daemons).

### Earlier — wave 76 (per-squad charge roll, gated 5.11 → 4.91)

**Wave 76 landed the per-model activation tax the watchdog mandated — as a
concrete core-rule fix.** Verify-first found the mechanism the prior washes
missed: the per-model over-rate is NOT spread/coherency (hordes cluster), it is the
CHARGE phase — SwegHammer rolled 2D6 *per model*, so an 11-model mob got 11 charge
attempts (~97% to make a 9" charge vs the real ~28%). Real 10e: a unit makes ONE
charge roll. A codex squad now shares one roll per round. Gated 5.11 → **4.91**,
bringing down the melee over-shooters (Orks +10.3→+8.1, Votann +14.7→+12.4) and
pulling Grey Knights back toward band. It works *because it cuts the horde's
effective melee output* — the exact thing the decision-overlay wash could not reach.
A clear core-rule correctness fix. Collateral (re-fit territory): Drukhari / T'au /
Sororitas up (their melee opponents now charge less reliably).

### Earlier — wave 75 (Sabotage + 40-VP secondary cap, gated 5.35 → 5.11)

**Wave 75 extended the proven action-secondary lever (watchdog confirmed).** Two
faithful changes: the real **40-VP total-secondary cap** (the sim never enforced it;
secondary-heavy shapes like Custodes ran past it) and **Sabotage** (a chaff unit
pushed forward performs an action — 3 VP in No Man's Land, 6 in the enemy DZ — with
the shoot/charge lockout). Gated 5.35 → **5.11**, and it dents the #1 residual:
Imperial Knights +23.3 → +18.0 (opponents score forward actions it can't reciprocate);
Custodes, Tyranids, Astra, AdMech, Necrons, Marines all better. **Honest collateral:**
the low-model armies that can't reciprocate over-corrected (CSM −16.6, Chaos Knights
−12.9, Grey Knights −6.6) — faithful in DIRECTION (low-model armies do struggle with
the secondary game) but amplified because cleanse/sabotage aren't rotation-gated yet
(they over-score vs the real draw-1-2/turn cadence). Tempering = a LATER secondary
wave, not wave 76.

**WAVE 76 IS FIRMLY THE PER-MODEL DURABILITY / ACTIVATION TAX** (watchdog-directed,
`LOOP_QA.md` Q3) — the genuine root cause of Imperial Knights +18.0 (still #1) that the
secondaries only chip at. It must be a FAITHFUL mechanic (real action-economy /
objective-count / coherency effects), NOT a metric-driven penalty on low-model armies.
"One more bounded secondary" instead = shying away (the watchdog will flag it).

### Earlier — wave 74 (Cleanse action secondary, gated 5.89 → 5.35)

**Wave 74 built the wave-73 structural lever and it worked.** The
action-economy secondary **Cleanse** (a real Pariah Nexus secondary that was
missing) now counterbalances the kill-secondary asymmetry: a unit performs the
Cleanse action on a controlled objective OUTSIDE its own deployment zone and
cannot shoot/charge that turn (the real action-vs-fight tradeoff), scoring 2 VP
for one / 4 for two. The asymmetry is even-handed — it falls out of unit cost
(`_is_chaff_unit`, <15 pts/model surplus bodies): Imperial Knights (no chaff)
score 0; hordes / MSU and elites with cheap aux score it. Gated MAE 5.89 → **5.35**
with exactly the predicted moves — durable over-shooters ease down (Imperial
Knights +27.9 → +23.3, World Eaters +16.5 → +12.5) and board-control under-shooters
rise (Astra −15.5 → −10.6; AdMech / Daemons / Tyranids / Necrons toward band). Also
fixed the dead Cull the Horde mechanic. In-band dipped 6 → 5 (small margins). This
is a faithful structural fix that moves the metric the right way by being more
correct — the first real win after three small/investigation waves.

### Earlier — wave 73 (investigation: the over/under split is the kill-secondary asymmetry)

**Wave 73 (investigation, no code change, headline unchanged at gated 5.89).** The
user steered the loop off narrow nerf-grinding toward structural levers. Verify-first
overturned the named lever ("secondaries never read") — they ARE counted (added to
`_a_vp`/`_b_vp` since 2026-05-20; `_a_secondary_vp` is a redundant unread tracker; the
literal fix would double-count). The real over/under driver is the **kill-secondary
asymmetry**: durable killers score Bring It Down / No Prisoners / Assassinate against
victims who score ~0 back (a horde scores 0 No Prisoners vs IK — they can't destroy a
durable Knight AS A UNIT under per-model representation). The missing counterbalance is
the **action-economy secondary family** (the sim models NO actions; only 2 of 9
tacticals) — the faithful, even-handed fix that rewards board-control under-shooters
and taxes low-model campers with an action-vs-fight tradeoff. Evidence in
`docs/SECONDARY_SCORING_ANALYSIS.md`; build plan in `docs/ACTION_SECONDARIES_PLAN.md`.
**Wave 74 = build the Cleanse vertical slice per that plan** (+ fix the dead Cull the
Horde mechanic: `_is_horde_unit` reads `starting_strength`/None, should read `max_models`).
Worker questions now route to the gitignored `LOOP_QA.md` watchdog channel, not the user.

### Earlier — wave 72 (Ion Shield ranged-only, gated 5.97 → 5.89)

**Status:** Headline gated MAE **5.89** (raw 9.28), **6/22 in band**. Wave 72
landed a faithful Imperial Knight durability fix (Ion Shield is "5+ invulnerable
**against ranged attacks only**" per BSData — big Knights have no melee invuln; the
sim applied it flat). Imperial Knights +29.0 → +27.9; melee under-shooters edge up.
Modest but the one metric-positive faithful lever found this wave.

**The headline is now firmly AI/structure-gated — TWO findings nail this down.**
(1) The under-shooters lose on VICTORY POINTS WHILE STILL ALIVE (Chaos Daemons lose
6-9/10 with survivors on the board, 0-1 tabled) — so per-faction COMBAT buffs do not
address their loss; it is the same objective/durability complex as the Knights
over-rate, from the under side. (2) Improving the target AI REGRESSES the headline:
a faithful value-based shooting-target picker (anti-armour concentrates on durable
threats, real weapon-target matching) was A/B'd and made it WORSE (5.97 → 6.11, IK
+29 → +32.9) because better targeting sharpens the killy over-shooters' own offence
more than it helps their victims remove un-killable Knights. This is the SECOND AI
lever to regress this session (objgreedy was the first, wave 71), both confirming
`project-ai-frozen-under-mae-first`: AI improvements expose over-tuned over-shooter
stats/lists. **A target-AI redesign will not reduce the headline until the
over-shooters are re-fitted.**

### Earlier — wave 71 (Code Chivalric fidelity fix, gated 5.98 → 5.97)

Wave 71 fixed the one genuine fidelity defect behind the Imperial Knights over-rate
(Code Chivalric was re-rolling all natural 1s; the real rule is one re-roll per
activation) and **proved the rest of that over-rate is a compensating error, not a
rule defect** — Bold Gallantry, Bondsman, all Knight stats and the maps verified
faithful end to end.

**Code Chivalric** (Imperial Knights army rule) was re-rolling EVERY natural 1
army-wide; the real rule is "re-roll ONE Hit and ONE Wound roll" per activation.
Reroll-all-1s over-scales with shot volume (a 20-shot Knight gun got ~3-4
effective re-rolls vs the rule's one). Now a single per-activation re-roll budget
(`code/units.py` `_chiv_hit_reroll`/`_chiv_wound_reroll`), faithful to the
one-Unit-per-model representation. Metric-neutral (the rule existing is the swing,
not the over-scaling) but correct.

**The Imperial Knights +29 over-rate is NOT a rule/stat defect — it is a
compensating error in the opponents' AI.** Everything was verified faithful:
Bold Gallantry (real Valourstrike Lance detachment, ~21pt, correctly gated on
Advance, charge-after-advance correctly blocked), Bondsman/Paladin's Duty (real,
~2.4pt), all Knight stats (OC 10/6, T 11/12, W 26/28 — match BSData), and the
maps (5-objective Leviathan quincunx). IK wins by **VP/objective-holding, not
tabling**. The root cause: the shooting-target AI is a min-HP "finish the weakest"
picker, so opponents shoot the W14 Armigers and chaff first and **never
concentrate fire on a big W26 Knight** — durable Knights sit on objectives
untouched all game. Under-shooters holding objectives better (tested via an
objective-greedy AI tweak — a wash, reverted) doesn't help, because they can't
take objectives FROM the un-killed Knights.

### Earlier — wave 69 (under-performer faction buffs, gated 8.74 → 8.29)

Headline gated MAE was **8.29** (raw 11.57), in-band 5/22. Wave 69 = the
win-win under-performer track: a 6-faction rules deep-dive (5 under-performers + an
over-performer over-buff audit) → implement each under-performer's missing rules
(verify-first against Wahapedia/BSData). Landed (gated 8.74→8.29): **Imperial Knights
−21.8→−16.0** (real Valourstrike Lance detachment + Bold Gallantry + Bondsman
abilities), **Chaos Daemons −19.0→−14.6** (per-god datasheet buffs — Tzeentch 4++
correction, Murderer's Cowl, Penumbral Puppetry/Gloam Rot), plus TOWERING
line-of-sight (cross-faction), Chaos Knights real Iconoclast Fiefdom detachment, and
GSC Patriarch/Primus leaders + Aberrant FNP. All verify-first (the over-performer
audit's "phantom Aeldari invuln" claim was DEBUNKED — Dark Reapers really have a
5++; the Daemons agent correctly corrected only the genuine Tzeentch 4++).

CAUGHT + REVERTED: CSM Dark Pacts per-unit auto-gamble crashed CSM 45.8→24.8% (the
self-inflicted D3 mortal wounds on every squad every round outweigh the buff — real
players are selective; task #36). Chaos Knights barely moved from the detachment
alone — its −38 is dominated by the AI-positional gap (the durable-objective
diagnostic moved CK −38→−8.8), so CK needs the objective AI (#12), not just rules.

### Earlier — wave 68 (core-rules-correctness batch, gated 7.80 → 8.74)

Headline gated MAE was **8.74** (raw 12.05), in-band 5/22. Wave 68 was a
deliberate **fidelity-first** wave from the full 10e core-rules audit
(`docs/CORE_RULES_AUDIT.md`): removed the **Heroic Intervention fabrication** (not a
10e rule — was a free defensive move for every Character) and fixed five real bugs —
Fall Back no longer always rolls Desperate Escape (only when battle-shocked or
crossing enemies); Indirect Fire now applies its unmodified-1-3-auto-fail + Benefit
of Cover; in-engagement (Pistol/Big Guns) and Blast target restrictions; unmodified-6
always hits; disembark can't place within Engagement Range; battle-shocked units
fight first in Remaining Combats. 919 tests green (deleted the HI test file), audit
280/280.

The headline rose +0.94 (7.80 → 8.74) — expected: the fixes move factions away from
a calibration fitted on the old wrong rules. Concentrated on **Chaos Daemons
−13.7 → −19.0** (HI removal correctly weakened a Character-heavy melee army that the
fabrication propped up) and the shooty over-shooters **Aeldari/Sororitas** (Fall Back
fix lets them disengage and keep firing). The **archetype-list re-fit (task #22)** is
now the gating next step and must lift Daemons + Knights while trimming
Aeldari/Sororitas/Thousand Sons.

### Earlier — wave 67 (per-unit-mechanics batch, gated 7.56 → 7.80, in-band 3 → 5)

Headline gated MAE was **7.80** (raw 11.11), **in-band 5/22** (was 3/22).
Wave 67 landed all six top findings from the per-unit-mechanics audit in parallel
(one worktree agent each, cherry-picked to `ba2a8b4`): unit coherency (cluster
squads at deployment + objective control credited per unit), per-unit secondary
scoring (No Prisoners / Cull count destroyed units), Reanimation/Undying Legions
grouped by `squad_id`, stratagem transient buffs applied to the whole squad (60
sites), per-squad battleshock + Mob Rule by squad_id, and the once-per-unit gate
re-keys (Oath, Acts of Faith, Strands, Miracle die, Markerlight, Blood Surge,
Beacons). All rules-correct; 922 tests green; citation 281/281 (new
`simulator.unit_coherency`).

The gated headline rose +0.24 (7.56 → 7.80) even though in-band improved 3→5 and
big structural fixes landed (Necrons +4.2→−1.3 from reanimation; Drukhari
+30.1→+27.8 from coherency). The regression is one faction: **Adepta Sororitas
+10.1→+17.2** (gated 6.3→13.4) — stratagem-buff propagation + the Acts-of-Faith
squad re-key correctly made Sororitas stronger, past a list tuned around the old
bugs. This is the fidelity-then-refit pattern: the sim is now more correct, so the
**archetype-list re-fit (task #22)** is the immediate next step, Sororitas first.

### Earlier — wave 66 (mortal-wound spillover + Deadly Demise + Blast, gated 7.78→7.56)

Wave 66
landed the mortal-wound half of the allocation rule (`Battle._apply_mortal_wounds`:
excess mortal wounds carry to the next model of the unit, unlike normal damage),
fixed **Deadly Demise** to hit each *unit* once (was per-model), and scoped **Blast**
to the targeted unit via `squad_id`. Eval 7.78 → 7.56 (small, rules-correct).

A user question about per-model vs per-unit framing then triggered a four-agent
**per-unit-mechanics audit** (`docs/PER_UNIT_MECHANICS_AUDIT.md`): the per-model
representation pervades the codebase and `squad_id` is the fix key. Top open items
(tasks #23-28): coherency wave (deployment clustering + OC-per-unit — the likely
remaining lever on horde over-shoot), per-unit secondary scoring (No Prisoners /
Cull count models not units), Reanimation profile.name→squad_id pooling, stratagem
transient-buff propagation to squad siblings, per-squad battleshock.

### Earlier this session — wave 65 (damage-allocation spillover, gated 9.27→7.78)

Wave 65 landed the biggest fidelity fix in many waves: **damage-allocation spillover**
(`simulator.damage_allocation_spillover`). The sim previously dumped a whole
volley into ONE model of a multi-model unit and wasted the overkill; now each
unsaved wound allocates to the next surviving same-`squad_id` model, with a
destroyed model's excess damage lost (kills bounded by unsaved-wound count, not
damage total — the actual 10e rule). This was the real "Lever 1" win: it moved
exactly the structural-residual factions (Tyranids −10.4, Imperial Knights +8.0,
Orks −7.2, Drukhari −7.2, Chaos Knights +4.8, AdMech −4.6). Built on the P1
`squad_id` infrastructure (behaviour-neutral) added the same session. See
`docs/RULE_ACCURATE_FIX_DESIGN.md` and memory `project-squad-activation-contained-wash`.

Second-order effect to chase next: elite/MEQ armies (Custodes +9.9, Marines
+10.3, Thousand Sons +21.7, Aeldari +13.5) now clear chaff more efficiently and
drifted further over — candidates for an archetype-list re-fit.

This file is the fast-pickup point for any session continuing the loop.

## Active goal directive

> Reduce gated MAE below per-faction noise floor while improving the
> rules correctness of the sim.

## Where the metric stands

| Eval | MAE_raw | MAE_gated | Inside band |
|---|---:|---:|---:|
| Wave 59 close (`f1c2825`) | 14.28 | 10.73 | 3/22 |
| Wave 60 close (`e1f3f53`+docs) | 14.27 | 10.71 | 2/22 |
| Wave 61 close (`c4d6da6`+docs) | 12.89 | 9.36 | 2/22 |
| Wave 62 close (`e1346a1`+docs) | 12.90 | 9.39 | 2/22 |
| Wave 63 close (`96fd68e`+docs) | 12.80 | 9.27 | 2/22 |
| Wave 64 close (`3203e35`+docs) | 12.80 | 9.27 | 2/22 |
| Wave 65 close (spillover+docs) | 11.15 | 7.78 | 2/22 |
| Wave 66 close (mortal+demise+blast) | 11.08 | 7.56 | 3/22 |
| Wave 67 close (per-unit batch ×6) | 11.11 | 7.80 | 5/22 |
| Wave 68 close (core-rules batch, fidelity) | 12.05 | 8.74 | 5/22 |
| Wave 69 close (under-performer faction buffs) | 11.57 | 8.29 | 5/22 |
| Wave 70 close (objective-aware AI #12) | 9.47 | 5.98 | 4/22 |
| Wave 71 close (Code Chivalric fidelity fix) | 9.38 | 5.97 | 6/22 |
| Wave 72 close (Ion Shield ranged-only) | 9.28 | 5.89 | 6/22 |
| Wave 73 (investigation only, no code change) | 9.28 | 5.89 | 6/22 |
| Wave 74 close (Cleanse action secondary + Cull-fix) | 8.74 | 5.35 | 6→5/22 |
| Wave 75 close (Sabotage + 40-VP secondary cap) | 8.50 | 5.11 | 5/22 |
| Wave 76 close (per-squad charge roll) | 8.16 | 4.91 | 5/22 |
| **Wave 77 close (per-unit Advance — metric-neutral)** | **8.29** | **4.95** | **6/22** |

Wave 65's lever was a **core-rule fidelity fix** (damage allocation), not AI or
stats — confirming the `project-faction-residual-rootcause` thesis that the big
residuals are structural representation bugs, not tuning. In-band count is flat
at 2/22 but the error *magnitude* dropped sharply (gated −1.49); the improved
factions are still outside their noise floors but much closer.

## Handoff context — wave 61 close

Three fixes landed (all on `claude/sim-calibration-6`, pushed through
`d141a69`; `c4d6da6` is the AI-gate commit, docs/close on top):

- **KNIGHTS-TITANIC-ESCAPE** (`31e477c`): TITANIC/FLY exempt from Desperate
  Escape + threshold 1→1-2 (Wahapedia verbatim).
- **KNIGHTS-DEMISE-D6PLUS2** (`d141a69`): mapper D6+2 parse + 11 chassis
  overrides (Deadly Demise was 1, should be 5).
- **KNIGHTS-AI-FALLBACK** (`c4d6da6`, the dominant lever): melee-primary
  units stay and fight instead of Falling Back. Corrected Knights UP
  (IK +10.1) AND over-shooters DOWN (Votann/AdMech/Orks/Marines/AstraMil).

New over-shoots introduced by the gate (melee units now staying engaged):
**World Eaters +7.1, CSM slightly over** — top carry-forward to re-tune.

## Next ranked levers for wave 77

Current biggest gated errors (wave 76 eval `data/wf_wave76_squadcharge_n40.json`):
Imperial Knights +19.6 (16.6), Drukhari +18.7 (15.3), Chaos Daemons −17.0 (13.8),
CSM −17.3 (14.9), Votann +12.4 (9.3), Chaos Knights −12.4 (9.1).

1. **MORE per-model activation-economy taxes in the charge-vein (the proven wave-76
   pattern).** Per-squad charge (5.11 → 4.91) confirms: find other per-model rolls/events
   that should be per-UNIT in real 10e and fix them. Candidates to verify-first: Desperate
   Escape tests (per model vs per unit), Battle-shock tests, overwatch, any "roll for the
   unit" event the sim does per model. Each is a core-rule correctness fix that cuts
   per-model over-rating.
2. **Rotation-gate the tactical secondaries (the deferred fidelity fix is now due).**
   cleanse/sabotage score every round; the real tactical deck draws ~1-2/turn. Gating them
   (like Engage/BEL via LC-2) would temper the wave-75 over-correction of the low-model
   armies (CSM −17.3, Chaos Knights −12.4) and the cheap-unit over-scoring (Votann,
   Sororitas) — a genuine fidelity fix, no longer pre-empting the per-model tax.
3. **Imperial Knights +19.6 (still #1) is NOT per-model** (1-model units, unaffected by
   per-squad charge) — it is the durable primary-camper over-rate. Its own diagnostic:
   likely the opponents not contesting it off objectives (the AI-targeting fix regressed,
   wave 72) or a durability/scoring angle. Drukhari +18.7 rose this wave (its melee
   opponents charge less reliably) — re-diagnose now that the melee layer changed.
4. **Re-fit candidates (archetype-list care rules):** re-measure after the above.

## Structural track (owns the remaining headline)

- **The over/under split is now understood and single-rooted.** Over-shooters are
  killy/durable elite armies (IK +29, WE +16.5, Drukhari +16.9, TSON +12.8,
  Custodes +10.0, Marines +8.6, Votann +9.0); under-shooters are board-control
  armies (Daemons −20, Astra −15.5, Necrons −9.5, AdMech −8.7, GSC −7.5,
  Tyranids −7.2). Wave 71 proved this is NOT rules/stats/lists (IK verified
  faithful end-to-end) — it is the min-HP target AI never removing durable
  objective-holders. Lever #1 above is the fix.
- The objective-greedy AI tweak (gunline troops claim reachable objectives) was
  tested and shelved as a wash — confirms holding-better is not the bottleneck;
  taking-from-durable-holders is.

NOTE: the IK/CK multi-profile weapon mapper is DONE (shipped pre-wave-60);
do not re-implement it. See memory `project-knights-multiprofile-weapons`.

## Standing operational rules

- Per CLAUDE.md §5: git identity via `-c user.email=jknight96@live.co.uk -c user.name=Allknight96` one-shot. Never edit config.
- Per CLAUDE.md §3: never push without explicit "go".
- Per CLAUDE.md §10: every rule fix needs a Wahapedia/BSData citation. The citation audit is ENFORCING on commit (`BLOCK_ON_MISSING_CITATIONS=True`).
- **Always** prefix the eval: `PYTHONHASHSEED=0 ... python -m scripts.evaluate_vs_meta --battles 40 --use-archetype` (segfault workaround; memory `project-eval-pythonhashseed-segfault`).
- Model tiering (global `~/.claude/CLAUDE.md`): set `model` per Agent dispatch; sonnet for T2 audits, never inherit Opus.
- Verify-first: agent and memory claims have been wrong repeatedly this branch — confirm file:line / rule text before acting.
- cwd-leak into agent worktrees is recurring — `cd` to main worktree and confirm `pwd` before git ops.

## Wave close checklist

1. Cherry-pick agent commits from the main worktree (check cwd).
2. pytest sweep + N=40 eval (`PYTHONHASHSEED=0`, `--use-archetype`).
3. Per-faction diff vs prior eval JSON.
4. Archive oldest wave-close block to `AUTO_LOOP_LOG_archive.md` (keep ~3).
5. Write new wave-close block at top of `AUTO_LOOP_LOG.md`.
6. Update this file with new headline + next levers.
7. `python scripts/loop_cleanup.py`.
8. Commit + push (push only on explicit user "go").

**WAVE 232 (2026-06-10) — five verified gates flipped DEFAULT-ON + weapon-keyword parity (ungated) + clean N=80 re-anchor. NEW STANDING FRAME: gated MAE 5.79.**
The wave's two code deliverables both landed: **weapon-keyword parity** (`dc4f63c`, ungated mapper fix — `indirect_fire` / `one_shot` / `hazardous` / `precision` now carried onto secondary + extra-melee profiles; 21/55/29/5 profiles across 523 multi-profile units) and the **five-gate default-ON flip** (`f35346c`): `SWEG_TANKSHOCK_DICE` (Toughness-many D6, 5+ = 1 mortal wound, cap 6; aggregate −0.13, Astra Militarum +0.61 decisive), `SWEG_ROLLOFF_ONCE` (once-per-battle first-turn roll-off; −0.36 aggregate), `SWEG_SITW_TEST` (Shadow in the Warp forced Battle-shock tests; Tyranids +2.11), `SWEG_HARBINGERS` (Chaos Knights Dread abilities; **Chaos Knights +7.42 decisive, 200 flips**), `SWEG_SOROR_ABILITIES` (per the wave-231 N=80 evidence, +0.81). All adjudicated KEEP off a fresh full-default N=40 OFF anchor (the ungated parity change invalidated prior anchors as pairing bases). Full suite 1304 passed / 1 skipped / 1 xfailed, audit clean, cli 0. Then a **clean full N=80 re-anchor: gated MAE 5.99 → 5.79** (raw 9.20, 4/22 in band). **NEW STANDING ANCHOR: `data/_anchor_wave232_n80_log.json`** (supersedes `_anchor_wave228_n80_log.json`). **Residual surface (sim vs real, gated points):**
- **UNDER-pole:** Astra Militarum −17.4 (g14.2, BANKED structural — displacement axis), Adepta Sororitas −13.5 (g9.7), Chaos Space Marines −13.3 (g10.9), Tyranids −13.0 (g9.2), Adeptus Mechanicus −8.2 (g4.1, **WORSENED from −4.8** — plausibly the keyword-parity redistribution, one_shot cuts 55 profiles' output → **scoped follow-up diagnostic queued**), Chaos Knights −5.1 (g1.8, much improved via Harbingers).
- **OVER-pole:** Imperial Knights +20.2 (g17.2, BANKED structural, worsened), Genestealer +14.4 (g9.8), Adeptus Custodes +13.3 (g10.7), Adeptus Astartes +13.0 (g10.8), Emperor's Children +11.6 (g5.9, improved), T'au +9.4 (g5.2), World Eaters +9.3 (g5.9), Death Guard +7.5 (g4.9), Grey Knights +6.6, Drukhari/Aeldari ~+5.3.
- **In band:** Orks, Thousand Sons, Leagues of Votann, Chaos Daemons.
**NEXT LEVERS:** (1) **Adeptus Mechanicus −8.2 scoped diagnostic** (did the one_shot parity over-cut its secondary profiles? `--factions` + paired, cheap); (2) backlog hygiene — sec_swap keyword-inheritance bug (~180 units), extra_melee_profiles serializer + swap drops `hazardous`, Leman Russ Punisher picker-bias override (#104); (3) T2 remainder (Astra Militarum First Rank Fire! Second Rank Fire!, Sororitas detachments/stratagems, Chaos Space Marines Pactbound). The **avenue-2 displacement build remains USER-GATED** (the strategic call awaiting the user; Astra Militarum and Imperial Knights both banked to it).
**POST-CLOSE ANCHOR CAVEAT (2026-06-10):** after the wave close, `origin/main` was merged in, bringing pull request #65 (**38 units with no canonical points data disabled in `data/overrides.json`** — they had been falling through to Lanchester-fallback pricing). Six of the 38 were archetype-list seeds and the disable **crashed `build_archetype_army` for five factions** (Necrons / Tyranids / Chaos Daemons / Astra Militarum / Adeptus Mechanicus); fixed by sourcing their canonical Wahapedia costs into `overrides.json` `points_listed` (Lokhust Heavy Destroyers 55, Carnifexes 90, Beasts of Nurgle 65, Scout Sentinels 55, Ironstrider Ballistarii 85, Sydonian Dragoons with taser lances 65) and re-enabling them; the other 32 stay disabled; `data/sweg_points_v1.json` re-baked against the final 1384-unit catalogue. **Consequence: `_anchor_wave232_n80_log.json` (measured pre-merge) is no longer byte-identical to the current tree** (draw pool − 32 units; the six seeds re-priced canonical-instead-of-Lanchester) — the NEXT wave must start with a fresh full N=80 re-anchor (or run both A/B arms fresh) before any paired comparison. The 5.79 headline itself may shift on the post-merge catalogue.

---

**WAVE 229 (2026-06-10) — AM −17.5 diagnostic: over-fragility REFUTED; root = DISPLACEMENT representation → AM BANKED (no faithful-fixable rule). Meta: remaining big residuals share the avenue-2 axis.**
Instrument-first (list-realism refuted: AM over-fields its core at 72.7% vehicle pts; positioning refuted: render shows AM well-spread) + a code-grounded vehicle-damage-path trace (Sonnet, spot-checked): **cover for vehicles / over-kill-spillover / damage-bracket / save-variance are ALL sim-correct.** The "+26% over-fragile" was a 3-opponent-slice artifact (refuted wave-177; vehicles get cover 63–69%). **The AM −17.5 is the DISPLACEMENT / board-control representation gap (avenue 2): the sim resolves objectives by raw model SURVIVAL; real 10e displaces out-fought armies off markers (pressure / maneuver / threat-of-charge) — UNMODELLED. AM wins 45% in tournaments by tanking with durable vehicles + holding through board pressure.** Per the watchdog's rule (pure representation → bank), **AM is BANKED as structural.** One real but MAE-neutral data-picker bug found (Leman Russ Punisher fires its 2-shot Multi-melta instead of its 20-shot Punisher gatling cannon — the EV-vs-Marine picker bias, missed by the wave-183 sweep); queued as faithful hygiene (single override, even-handed so ~0 MAE). **META-FINDING (strategy): the remaining big residuals — AM −17.5, Imperial Knights +17.2, Genestealer +14.8, Sororitas −15.3 — are dominated by the SAME displacement/board-control representation axis (avenue 2, partially built via wave-211 collision). The cheap faithful-RULE levers look largely harvested (CSM was the last); remaining MAE is structural.** IK +17.2 diagnostic DONE (instrument + render): **confirmed — IK banks to the SAME representation root.** Collision is on/maxed (production); the render (IK vs Tyranids) shows the Knight parking concentrated OC on central markers while the Tyranid horde scatters off them (the OC-delivery gap, [[project-oc-contest-faithful]]); no new faithful IK lever beyond collision. **META-FINDING CONFIRMED on BOTH poles (AM under + IK over = avenue-2 displacement).** The high-value direction — completing the avenue-2 displacement substrate (a big user-authorized build) — now awaits the **user's strategic call** (surfaced by the watchdog). Interim small levers available (Punisher hygiene #104, GSC +14.8, Sororitas −15.3) but low-yield; the watchdog steers interim-grind vs hold-for-user.
**AVENUE-2 PREP #1 (quantify displacement) DONE — directional-confirmed, NOT cleanly numeric.** Sororitas −15.3 has no cheap lever either (Miracle Dice / Acts of Faith is faithfully modelled — 3rd confirmation the cheap vein is harvested). A gated displacement upper-bound proxy (credit contested markers to the local combat-winner) moved **IK −7.27 toward real and Sororitas +4.10 toward real** (correct direction, confirming the axis) but cratered Chaos Knights — because the displacement gap is **bidirectional** (durable out-fighters should HOLD markers they lose on OC; cheap bodies should DISPLACE a concentrated holder), so **no single scoring proxy captures both, and the true MAE ceiling is only measurable by the actual build.** Qualitative case for avenue-2 is solid (both poles localize to it + directional proxy confirms + cheap rule-vein harvested); the exact gain is build-measured. Instrument reverted (clean tree). **REMAINING PREP #2: draft the displacement-substrate design (gated, multi-wave, instrument-first) so the build is greenlight-ready — pending watchdog steer (draft now vs hold for the user).**

---

**WAVE 228 (2026-06-10) — CSM abilities flipped DEFAULT-ON + clean full N=80 RE-ANCHOR. NEW STANDING FRAME: gated MAE 5.99.**
The wave-227 CSM datasheet abilities (faithful +1.9, even-handed) are flipped `SWEG_CSM_ABILITIES` **default-ON** (`a5c1239`; 3 gate sites `get(...,"1") != "0"`, `=0` reverts; 5 OFF tests set `=0`; full suite 1244 passed, audit 327/327, both-gate CLI 0). Then a **clean full N=80 re-anchor at all production defaults** (deploy-AI ON / scout-AI OFF / CSM-abilities ON) replaced the 4-waves-stale `_reservescap_on_n80` anchor (which had drifted ~0.6 / 83 flips). **NEW STANDING ANCHOR: `data/_anchor_wave228_n80_log.json`. NEW STANDING FRAME: gated MAE 5.99** (raw 9.42; 3/22 factions in noise band). **Residual surface (sim vs real, gated points):**
- **UNDER-pole:** Astra Militarum −17.5 (g14.3, **#1 lever**), Sororitas −15.3 (g11.5), Chaos Space Marines −13.7 (g11.3, the +1.9 helped modestly — deeper output/durability remains), Tyranids −13.1 (g9.3), Chaos Knights −9.0 (g5.7), Adeptus Mechanicus −4.8.
- **OVER-pole:** Imperial Knights +17.2 (g14.3, **#1 over**), Emperor's Children +15.2 (g9.5), Genestealer +14.8 (g10.2, the deploy-fix-exposed over-rating), Adeptus Custodes +13.4, Adeptus Astartes +12.0, T'au +10.6, Thousand Sons +9.4, Death Guard +8.7, Drukhari/World Eaters ~+7.
- **In band:** Necrons, Chaos Daemons, Leagues of Votann, Orks (~).
**Cadence note (watchdog-enforced):** re-anchor every ~3–4 waves OR run both-arms-fresh for the keep/reject gate (the reuse-anchor drift caveat). **NEXT LEVER: Astra Militarum −17.5** — instrument-first (list-realism ~60% vehicle points vs infantry-into-kill-zone positioning vs stats) + RENDER per the standing visual diagnostic. Then Genestealer +14.8 over (metric-tuning guard), Imperial Knights +17.2 positional.

**WAVE 233 (2026-06-10) — post-merge N=80 re-anchor: NEW STANDING FRAME gated MAE 5.74 (surface RESHUFFLE) + Adeptus Mechanicus diagnostic CLOSED + keyword-parity completion KEEP + DISPLACEMENT SUBSTRATE GREENLIT.**
The mandatory post-merge re-anchor (pull request #65's catalogue changes invalidated the wave-232 anchor) landed at **gated 5.74** (raw 8.93, 5/22 in band). **NEW STANDING ANCHOR: `data/_anchor_wave233_n80_log.json`.** The re-priced archetype seeds (Carnifexes 90 / Ironstrider Ballistarii 85 / Sydonian Dragoons 65 — canonical instead of over-priced Lanchester) reshuffled the surface: **Tyranids flipped −13.0 → +7.7 OVER, Adeptus Mechanicus −8.2 → +14.6 OVER**, Chaos Daemons into band. **Residual surface (sim vs real, gated points):**
- **UNDER-pole:** Chaos Space Marines −17.0 (g14.5), Astra Militarum −16.5 (g13.3, BANKED structural — displacement), Adepta Sororitas −16.5 (g12.8).
- **OVER-pole:** Imperial Knights +15.9 (g13.0, BANKED structural — displacement), Adeptus Mechanicus +14.6 (g10.4, NEW — post-re-price), Genestealer +13.1, Necrons +12.8 (NEW), Orks +11.3 (NEW), Aeldari +11.0.
- The wave-232 Adeptus Mechanicus worsening diagnostic CLOSED (zero evals: per-gate paired decomposition = faithful opponent buffs; one-shot-parity hypothesis falsified by audit). The **keyword-parity completion** (`8e8a060`: secondary/extra-melee profiles carry all four keywords end-to-end, sec_swap + per-model reset, 11 new tests, suite 1315 green) adjudicated **KEEP** — paired −0.08, decisive Genestealer −0.55 / Imperial Knights −0.33 both toward target.
**DISPLACEMENT SUBSTRATE GREENLIT (the strategic call landed).** Final-pass review done: strategy review confirmed all assumptions (+2 amendments: Stage 2 contests the FULL stacked Objective Control of the defending cluster; Battle-shock trivially passes Stage 1's no-control-consequence test, scoring at end of each Command phase); rules review found one contradiction (**FLY does NOT bypass the Fall Back shoot/charge lockout** — corrected) + Stage 3 cleared-position precision. Amendments folded (`601fc42`) + six ranked future candidates incl. the NEW visual finding (late-game markers sit EMPTY at 0/0 and nobody re-tasks to claim them). Reference values for game-shape comparison: `docs/REAL_META_SIGNATURES.md` (primary ≈29, going-first ≈49–52%, secondary ≈22.7; per-marker control data does not exist publicly — Stage 0 is its first measurement).
**NEXT LEVERS:** (1) **Stage 0 `SWEG_DISPLACE_INSTR`** (build in flight) — adjudicate, size the per-faction displacement-addressable victory points, then Stage 1 fall-back-only-when-wasted; (2) **harvest the under-pole/over-pole research agents** into a ranked diagnostic queue — priority questions: the three NEW over-pole entrants (Necrons +12.8, Orks +11.3, Aeldari +11.0) and the Tyranids/Adeptus Mechanicus flips (likely list-composition effects of the re-priced seeds — check archetype list draw shares before any rule work); (3) remaining hygiene: Leman Russ Punisher picker-bias override (#104), T2 remainder (Astra Militarum First Rank Fire! Second Rank Fire!, Sororitas detachments/stratagems, Chaos Space Marines Pactbound).

**WAVE 234 (2026-06-11) â€” N=80 re-anchor: NEW STANDING FRAME gated MAE 6.02 (7/22 in band â€” middle improved, POLES DEEPENED) + structural-debt review + queue-debt sweep + Ed's 23 issues triaged. Overnight fix cluster (wave 235) IN FLIGHT.**
The wave folded in `d66ca44` (ten stale `points_override` corrections â€” Ed-mistake-class pricing review) + `31ba197` (Adepta Sororitas The Blood of Martyrs detachment rule) â†’ mandatory fresh full N=80 re-anchor: **gated 6.02** (raw 8.96, **7/22 in band**, up from 5/22). **NEW STANDING ANCHOR: `data/_anchor_wave234_n80_log.json`.** The middle improved â€” Adeptus Mechanicus +14.6 â†’ +10.6 (g6.4), Genestealer Cults +13.1 â†’ +10.2 (g5.6), Orks +11.3 â†’ +6.6 (g3.7), Tyranids +7.7 â†’ +6.9 (g3.1) â€” but the poles deepened. **Residual surface (sim vs real, gated points):**
- **UNDER-pole:** Chaos Space Marines âˆ’19.3 (g16.8), Adepta Sororitas âˆ’18.8 (g15.0 â€” worse despite Blood of Martyrs landing), Astra Militarum âˆ’17.7 (g14.5, BANKED structural â€” displacement).
- **OVER-pole:** Aeldari +16.7 (g13.6, NEW top over), Necrons +16.4 (g13.1), Adeptus Custodes +15.8 (g13.2), Imperial Knights +15.7 (g12.7, BANKED structural â€” displacement).
- **In band (7):** Thousand Sons, Leagues of Votann, World Eaters, Emperor's Children, Chaos Daemons, Grey Knights, Drukhari.
**Wave deliverables:** `docs/STRUCTURAL_DEBT_REVIEW.md` (five-surface early-approximation audit: five command-point-sink stratagems, five leader fabrications, Battle Focus cadence wrong, Martial Grace magnitude wrong, a mobility-mechanic-erasure class tagged to the displacement substrate; Necron cluster orchestrator-verified against BSData verbatim; live Wahapedia resolved the two conflicts) + `docs/QUEUE_DEBT_SWEEP.md` (the queued-never-executed sweep, both halves â€” NE-1..NE-19 / SB-1..SB-6 ranked dispatch table) + **Ed's 23 GitHub issues triaged conventionally** (#40 closed; #43 #50 #54 #60 #62 close via pull request 66 keywords; #61 #44 #52 re-scoped open; #53 fulfilled â€” BASELINE.md catalogue count regenerated 1384, date-stamped). Stage 0 displacement instrument landed (`c33d8ab`); its run + verdict still pending (SB-1).
**NEXT LEVERS (wave 235 in flight):** (1) **the overnight fix cluster** â€” Necron leader fabrications (agent in flight) + Battle Focus per-round cadence (`10bda6a`, adjudicated KEEP) + Annihilation Legion fabrication removal (`a82c029`, adjudicated KEEP) + command-point-sink stratagem batch (Adaptive Strategy / Plaguesurge / Desecration of Worlds / Vigilance Eternal) + World Eaters Apoplectic Frenzy rewire to true Lethal Hits â†’ cherry-pick, full suite, fresh N=80 re-anchor; (2) **queue order after the re-anchor:** NE-2 First Rank Fire wrong-stat proxy + NE-9 Lord Solar 2â€“3 orders (both Astra Militarum âˆ’17.7), NE-6 Conquering Tyrant full-reroll scope (Necrons +16.4), torrent-over-cannon override batch, Farseer Branching Fates, hygiene batch (incl. issue #61 pooled-health remnants); (3) **Stage 0 instrument run + verdict** (SB-1), then displacement Stage 1 fall-back-only-when-wasted. Parked for a wave boundary: merge `origin/main` (pull request 67 archetype-unit replacements â€” frame-changing) + the Warp Friends target refresh decision.

---

**WAVE 235 (2026-06-11) — overnight fix cluster LANDED: NEW STANDING FRAME gated MAE 5.96 (5/22 in band) + Stage 0 displacement GO + three wave-236 fidelity commits cherry-picked post-anchor.**
Seven structural-debt fidelity fixes closed the wave (Battle Focus cadence `ecc925f`, Annihilation Legion removal `d89ab89`, command-point-sink stratagem batch `d8e0aed`, Necron leader fabrications `79546fb`/`aa8211c`, **Apoplectic Frenzy corrected to the verbatim advance-and-charge rule** `1321799`, NE-6 Conquering Tyrant two-branch scope `05c080f`) → fresh full N=80 re-anchor on `05c080f`: **gated 5.96** (raw 8.99, 5/22 in band). Fidelity trended the right factions toward target: Necrons +16.4 → +14.8 (g11.6), Aeldari +16.7 → +16.0 (g12.9), Imperial Knights +15.7 → +14.8 (g11.9). **Stage 0 displacement instrument: VERDICT GO** (addressable 10–25 primary victory points per game per side, over-pole dominant; `docs/DISPLACEMENT_SUBSTRATE_PLAN.md` §5). Post-anchor wave-236 commits: NE-2 First Rank, Fire! Second Rank, Fire! faithful +1 Attacks (`ea46aef`), Farseer Branching Fates fabrication removal (`d29fcee`), Chaos Lord Lord of Chaos fabrication removal + host-key correction (`2e7643b`). Full suite 1411 green, audit clean, demo exit 0.


---

**WAVE 236 (2026-06-11) — displacement Stage 1 ADOPTED AS DEFAULT + invulnerable-save repair (128 units) + nine-commit batch PUSHED to pull request 66 + N=80 re-anchor: NEW STANDING FRAME gated MAE 5.71 (best yet on the honest scale).**
**Displacement Stage 1 (`SWEG_DISPLACE_FALLBACK`) measured and adopted default-ON** (`5a80a4c`): N=80 paired vs the wave-236 anchor gated **6.03 → 5.96**, decisive movers Aeldari −1.74 / Chaos Knights +1.66 / Votann +1.42 toward target vs Imperial Knights +1.36 / Daemons −1.94 wrong-direction; legacy path byte-identical behind `=0`. **Mapper per-attack invulnerable-save repair** (`299aefc`, found by the Sororitas audit `docs/SORORITAS_UNDERPOLE_AUDIT.md`): the regex missed "invulnerable save of 4+" and bare-digit linked-profile forms, and the default-ON conditional-invuln path reads only the per-attack fields → **128 units (every Terminator-armour unit + 29/33 Sororitas) had NO invulnerable save**; gap 128 → 0, regen diff invuln-fields-only, orchestrator-verified. Rest of the batch: officer order counts (`33e1a67`), Forgefiend Daemonic Ordnance crit-election fix (`d16cfba`), Legionaries chainsword basket (`9c54ed2`), Chaos Space Marines leaders Master of Possession / Warpsmith / Dark Commune (`4f9cce3`, Faithful Flock real 5+ invulnerable; others structural no-flag). Full suite 1473 green, audit clean, demo exit 0, **pushed `1c7790c..4f9cce3`**, pull request 66 body refreshed. → **Fresh N=80 re-anchor on `4f9cce3`: gated 5.71** (raw 8.86, 5/22 in band). **Residual surface (sim vs real, gated points):**
- **UNDER-pole:** Chaos Space Marines −18.0 (g15.5, **improved 2.9 from −20.9** — the CSM batch landed), Astra Militarum −17.6 (g14.4, flat, BANKED structural — displacement), Adepta Sororitas −17.4 (g13.6, **improved 2.1** — the invuln repair; findings 2–7 re-rank next).
- **OVER-pole:** Adeptus Custodes +17.7 (g15.0, **NEW top residual, worsened** — board-control class per memory, Stage 2 displacement is the named lever), Imperial Knights +16.0 (g13.1, BANKED structural — Stage 2 in build), Necrons +15.2 (g12.0, worsened), Aeldari +14.3 (g11.2, **improved 2.2** — displacement decisive mover confirmed).
- **In band (5):** Thousand Sons, Leagues of Votann, Chaos Daemons, Grey Knights, Drukhari (World Eaters g0.53, Emperor's Children g0.38 just outside).
**Queue discovery:** torrent-over-cannon override batch ALREADY COMPLETE (ATK-BIAS-1 entries, prior wave) — retired.

