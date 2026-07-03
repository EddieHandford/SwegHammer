# Fidelity-first revisit worklist — parked/proxied faithful rules to fully implement

**Drafted 2026-06-06** (audit agent + watchdog review). USER-requested: revisit the changes parked during the
Knight-overshoot period and fully implement their rules. **Context:** during the over-pole, faithful 10e mechanics were
parked / gated-OFF / proxied — often *because* full implementation regressed the gated-MAE while the Knight over-rate
compensated (the "frozen-under" pattern, [[project-ai-frozen-under-mae-first]]). The 2026-06-03 fidelity-first rail
("never gate a faithful mechanic off to protect the metric; headline rising is authorised") came *after* most of those
calls, and we now know the over-rate is a one-Unit-per-model REPRESENTATION artifact. So the metric-protection reason for
parking them is invalid → land the faithful ones.

## Orchestrator rails for the sweep
- **Keep-if-faithful; the MAE will likely RISE — that's the POINT.** These mechanics were parked because they un-mask the
  over-rate (elites fire their real stronger guns; mobile armies score authentically). Landing them produces the HONEST
  frame; the un-masked over-rate is then owned by option-B (anti-walling) + the representation floor / Stage 2. Do NOT
  re-park a faithful mechanic because the MAE rises.
- **One flip + one N=80 A/B at a time** (clean attribution; these interact). A/B on the current production deck frame (~4.89).
- **The only legit reasons NOT to land an item:** (a) a verify-before-flip reveals a real BUG (not a faithful regression) —
  fix the bug first; (b) an unbuilt item needs a cited rule + faithfulness verification first (no fabrication); (c) a genuine
  infrastructure dependency (e.g. battleshock) isn't there yet.
- Cite every new/changed rule (rule-10). Determinism + `run.py --cli` clean before any commit.

## Ranked candidates (land highest-value first)

1. **Per-model weapon firing + rolled damage (`SWEG_PERMODEL` + `SWEG_ROLLDMG`)** — built Stages 1-4, gated-OFF, frozen-under.
   The core Weapons rule (each model fires only its own weapons; single-model units stop over-collecting mutex arm options —
   523/907 fixed; random Damage rolled not averaged). HIGH confidence, fully cited. **WATCHDOG CAVEAT (overrides the audit's
   "just flip"): the worker's last A/B was +0.64 DOMINATED by an un-attributed Daemons CRATER — possibly a per-model
   weapon-loss-on-death / target-allocation BUG, not a faithful regression. VERIFY-BEFORE-FLIP first (in-sim damage attribution:
   bug vs faithful). If BUG → fix it → then flip. If FAITHFUL → flip default-ON (accept the elite un-mask).** Then build Stage 5
   (target-aware firing-time weapon selection).
2. **Real 2-card Tactical secondary deck (`SWEG_TAC_DECK`)** — built, gated-OFF, washed N=80. The CA-2025-26 match draws a
   2-card hand; the sim's legacy "score every secondary simultaneously" is unfaithful (both armies cap at 40 = wash). HIGH,
   cited. Natural companion to the now-default primary deck. Flip + A/B; verify the 6 action cards are built or intentionally
   deferred; check interaction with `SWEG_PRIMARY_DECK`.
3. **Per-Command-phase primary scoring (`SWEG_CMDSCORE`)** — built, gated-OFF, held-for-recal. Real 10e scores primary in each
   player's Command phase; the sim's single end-of-round snapshot under-credits mobile holders. HIGH, cited. Qualification:
   verify it composes with `SWEG_PRIMARY_DECK` + Terraform/Ritual/Scorched, and that the per-player timing is faithfully
   approximated within the round model. Flip + A/B. (NOTE: `SWEG_ENTERSCORE` is the REFUTED approximation of this — do NOT use
   it; `SWEG_CMDSCORE` is the faithful version.)
4. **Squad split-fire (`SWEG_SQUADSHOOT`)** — built, gated-OFF, metric-neutral. 10e lets a unit's models target different
   enemy units in range. HIGH, cited. Metric-neutral is fine under fidelity-first. Flip + A/B (re-confirm neutral on 4.89).
5. **Collective-crack focus fire (`SWEG_FOCUSFIRE`)** — built, gated-OFF, frozen-under (IK worsened). Concentrate anti-armour
   on a brick the army can CRACK this turn; spread if uncrackable. MED-HIGH (tactical-AI, not a codex rule, but random-fire is
   un-tactical). Flip + A/B; note the ~2× eval cost (perf, not faithfulness).
6. **Intelligent deployment / screening (`SWEG_DEPLOY`)** — built, gated-OFF, washed. Role-split deployment (screens forward,
   durable mid-field). MEDIUM. Flip + A/B (may move more now that other fixes landed).
7. **Custodes Kaptaris Ka'tah (+1 invuln vs ranged)** — UNBUILT, deferred-because-Custodes-over-shoots. A real Shield Host
   stance bullet (cited in detachments.py). HIGH for Kaptaris (clean defensive rule). Build it; accept Custodes over-shoots
   more (fidelity-first). Dacatarai (Sustained Hits) = MEDIUM, needs BSData verification of which weapons carry the keyword —
   verify before building.
8. **BSData `extract_fnp` structural fix** — bypass-only (12 Tyranid overrides), deferred. The mapper's prose-walk false-
   positives Enhancement FNP into base stats. HIGH (data-correctness, not a metric lever). Audit the 4 suspected Enhancements
   (Custodes/Necrons/DG/Marines), fix `extract_fnp` to skip `type="upgrade"` entries, retire the bypass overrides.
9. **Chaos Knights Harbingers of Dread** — BLOCKED on battleshock infrastructure. HIGH but DEFER until the battleshock phase
   is faithfully modelled; verify the rule text vs BSData/Wahapedia then.

## Genuinely REFUTED — do NOT re-try
Fight-phase alternation (`SWEG_FIGHTALT` — faithful doubling moves the sim FURTHER from reality in the current round model),
kiting (`SWEG_KITE`), tarpit-charge (`SWEG_TARPIT`), OC-cluster (`SWEG_CLUSTER` — unfaithful), cohesive-hold (`SWEG_COHEREHOLD`
— over-floods), entering-round scoring (`SWEG_ENTERSCORE` — biased approximation, superseded by `SWEG_CMDSCORE`), CSM
Dark-Pacts +1/+1 proxy (3 attempts net-negative; the real path is the holistic mark/Dark-Apostle build, not the proxy),
board-wide collision (the avenue-2 physics, dead for this representation — option B is the anti-walling re-attempt).

## Needs verification before yes/no
Harbingers text; Custodes Dacatarai weapon-keyword scope; the BSData static-vs-runtime double-count remainder (DG Disgustingly
Resilient, Sororitas Acts/Shield of Faith, Marines Adept-of-the-Codex Enhancement FNP); the 5 remaining CA-2025-26 primaries
(Unexploded Ordnance / Supply Drop / Hidden Supplies / Linchpin / Burden of Trust — low-priority frame-completion hygiene).

## Added 2026-06-07 — recovered from the held/stream-a-ai-oc-fidelity branch (analysis: agent afe03927)
10. **Align the move-AI's Objective-Control view with the scorer (bracket-aware + battleshock-aware)** — GENUINELY MISSING, faithful,
    frozen-under (parked wave 95 because it regressed 3.76→3.89; the fidelity-first rail post-dates that). The planner's
    `_oc_on_objective` (`code/strategy.py:326-339`) and `own_oc` (`:2186`) use RAW `u.profile.oc`, so the AI plans as if a damaged
    Knight is OC 10 and battle-shocked units still hold — while the SCORER awards bracket/battleshock effective OC. Fix (3 hunks,
    recovered from held/ 5d83e5b + one hunk of 452ce81):
    (a) make `_oc_on_objective` use the CURRENT branch's `_effective_oc_value` (`strategy.py:342`, data-driven
        damaged_threshold/penalty + SWEG_DMGBRACKET) — NOT 5d83e5b's hardcoded faction variant;
    (b) add a `cur_round` param + battleshock guard so shocked units contribute 0 OC (own + enemy snapshot at `simulator.py:8779`);
    (c) use `_effective_oc_value(unit)` for `own_oc` in `pick_move_intent`.
    DROP the stale `SWEG_DMGOC` gate hunk (retired wave 191; scorer uses SWEG_DMGBRACKET). Cited simulator.damaged_objective_control_bracket
    + simulator.battleshock (verify the battleshock citation covers the AI-planning path, not just the scorer; run audit_rules).
    **TOUCHES `_oc_on_objective` — the SAME function as the #1 perf hot spot (incremental cache) + the collision base-edge OC fix.**
    Coordinate all three on that function; do the alignment as its own keep-if-faithful A/B (it moves the metric; the perf cache is
    byte-identical/neutral — keep them as separate commits for clean attribution). Sequence WITHIN the post-collision/efficiency
    window — do NOT pull ahead of the collision keep/reject. The rest of held/ (86c93c7, d614007) = already present → discard; the
    branch is deletable at consolidation once this is captured.
