# Session handover — fidelity-first program (updated 2026-07-02, evening)

**READ FIRST:** `docs/CURRENT_STATE.md` head + `docs/DECISION_LEDGER.md` (2026-07-02 entries) + `docs/ARCHETYPE_FIDELITY_AUDIT.md`.

**Standing anchor: `data/_anchor_sc42a_n80_log.json`, gated 4.39-era scale → current 4.52** (honest frame; nothing compares across the 2026-07-02 scoring-truth re-base). Branch `claude/sim-calibration-17`, all work committed AND pushed (owner gave standing push authorization 2026-07-02 "push it then keep going").

**Landed today:** scoring-truth batch (secondary consumer fix + round-5 timing + per-marker objective control; going-first 69%→50.0%); template-first fill; sourced templates DG/EC/IK/WE + Be'lakor Scintillating Legion archetype (Daemons in-band); Canis Rex phantom-model fix; mapper choice-group fix (69 units); Despoiler sourced gun build; Custodes offense batch (previous day).

**HELD gates (reasons in the ledger — do not re-propose blind):** SWEG_CK_REALISM (the 85.8%-vs-44.7 finding — attributed ~93% to the ranged-hold-on-unkillable-platforms interaction; fix fork awaits owner steer: terrain density is the favourite), SWEG_AM_GRIZZLED (AM cannot convert Orders yet), SWEG_TAC_VOLUNTARY_DISCARD (real rule; the unconditional command-point grant leaks — needs your-turn-only grant + card-pursuit artificial intelligence), SWEG_ACTION_ECONOMY (establish_locus needs a positional filter).

**NEXT QUEUE:** (1) owner fork on the static-gunline fix — terrain density to competitive standards is the recommended big wave; (2) card-pursuit artificial intelligence (route spare units toward held tactical cards — the Astra Militarum unlock, secondary track 9.5 vs real 22.7); (3) establish_locus positional filter then action-economy re-screen; (4) Votann Hearthband detachment; (5) Myphitic Blight-hauler re-enable; (6) override-precedence bug (extra_melee_profiles discarded by per-model rebuilds); (7) New Orders stratagem; (8) Grizzled + voluntary-discard re-screens after (2).

---



## The standing directive that governs this run

The user said, verbatim:

> "Please continue to build and screen. Untill i say stop. Driving for next 4 hours"

That is an explicit authorisation for an **autonomous continuous build-and-screen
loop with no questions asked while they are away**. Make adopt/reject calls
yourself using the fidelity-first pattern below, and commit + push each adopted
lever periodically. This supersedes CLAUDE.md rule 3 (no push without "go") **for
this run only** — it was set up by the earlier "Push, then pick up the tail"
instruction and the user has watched ~13 commits land under it without objection.
Do **not** stop and wait for input; do **not** ask clarifying questions. If the
safe vein is exhausted (it nearly is — see below), keep doing genuinely useful,
non-list, non-structural work rather than padding with near-inert levers.

Still hard rules, not superseded: cite every rule; no acronyms in prose/commits;
never touch archetype **list/composition** (user-reserved); test `python run.py
--cli` before every push; git identity via `-c` one-shot.

---

## Where the metric is

- **Branch:** `claude/sim-calibration-16`. Latest work: the Adeptus Custodes
  offense batch (Master of the Stances / Advanced Firepower / Slayers of
  Tyrants), committed locally, **NOT pushed** (the prior run's push
  authorization was scoped to that run; awaiting the user's go).
- **Headline:** noise-gated, **field-weighted** per-faction mean absolute error =
  **2.23** (anchor `data/_anchor_sc35a_n80_log.json`, local artifact). The rise
  from 2.02 is the ADOPTED Canis Rex phantom-model data fix (a faithful
  correction never gated off to protect the metric); the regression is expected
  to be recouped by the owner-reserved Imperial Knights template corrections.
- **THE OWNER-PROMPTED ARCHETYPE AUDIT (read first): `docs/ARCHETYPE_FIDELITY_AUDIT.md`**
  — the "structural durability over-reward" is REFUTED as a distinct mechanism;
  it decomposes into archetype-layer infidelities (owner decision menu in the
  doc), three concrete scoring deltas, and the (now fixed) Canis Rex bug. Next
  autonomous levers: the one-marker-per-squad Objective Control clamp faithful
  fix (NEW, unmeasured); re-screens of round-5 scoring timing + the secondary
  2-card cap on the CURRENT frame (both already built + gated; old rejections
  are frame-stale). Rejected this session (do not re-attempt): the Astra
  Militarum charge-discipline scope-down (−2.41 decisive).
- **Rule 14 checkpoint: REACHED (~15 wave commits).** STOP stacking waves on
  this branch — mark the pull request merge-ready for review and start
  `claude/sim-calibration-17` for the next wave. THREE commits are local-only
  awaiting the owner's push go: the Custodes offense batch, the audit +
  charge-discipline record, and the Canis Rex fix.

### Current residuals (field-weighted, gated), from sc33a

| Faction | Sim | Real | Diff | gated | note |
|---|---|---|---|---|---|
| Astra Militarum | 33.0 | 45.3 | −12.3 | 9.08 | UNDER — structural (fragile end of durability wall) |
| World Eaters | 55.1 | 44.9 | +10.1 | 6.73 | OVER — structural durability over-reward (+ list-zone composition) |
| Death Guard | 55.5 | 47.6 | +7.8 | 5.27 | OVER — structural |
| Emperor's Children | 63.9 | 53.3 | +10.6 | 4.92 | OVER — structural |
| Chaos Daemons | 60.4 | 52.6 | +7.8 | 4.69 | OVER — structural |
| Imperial Knights | 55.2 | 47.7 | +7.5 | 4.51 | OVER — structural |
| Leagues of Votann | 54.0 | 48.0 | +6.0 | 2.93 | OVER — newly overshot by the ranged-hold just adopted |
| Adeptus Custodes | 44.6 | 49.5 | −5.0 | 2.30 | **UNDER despite being durable — anomaly = under-modelled offense. The one clean safe lever left.** |
| Drukhari | 47.7 | 52.4 | −4.6 | 1.25 | small |
| T'au Empire | 48.8 | 54.3 | −5.5 | 1.24 | small; do NOT ranged-hold (see below) |
| Grey Knights | 41.5 | 46.7 | −5.2 | 0.98 | small |

Recompute this table any time with the field-weighted residual script pattern in
`docs/EVAL_PROTOCOL.md` (weights are opponent `TOURNAMENT_GAMES` from
`data/warpfriends_rolling.json`; noise floors from the same file). **Do not** read
per-faction numbers off `paired_delta` output for the headline — that display is
UNIFORM-weighted and misleads.

---

## The one thing in flight

**RESOLVED (2026-07-01, evening session).** The Custodes offense audit was
re-dispatched and returned nine ranked candidates; the top three were built,
screened, and ADOPTED fidelity-first as a combined wash (gated 2.01 → 2.02,
Custodes +0.31 — see `docs/CURRENT_STATE.md` head and the decision ledger).
**The Custodes durable-but-under anomaly is NOT a datasheet-offense gap** —
the remaining audit candidates (Quicksilver Execution, Moment Shackle, Stand
Vigil, Sentinel Storm) are lower-ranked trinkets of the same shape; do not
chase them expecting the −5 to close. The safe autonomous vein is now
CONFIRMED DRY — the next moves are the two user-decisions in the section
below (World Eaters list-zone composition; the structural durability
remodel). The original re-dispatch brief is kept below for reference only.

Re-dispatch brief (Tier 2 / Sonnet, find-then-report, no edits): audit
`C:\Users\Jake\Claude\code\SwegHammer` for MISSING Custodes OFFENSIVE mechanics.
Custodes is 44.6 sim vs 49.5 real (under by ~5, gated 2.30) — anomalous because
durable armies over-score here, so the sim is under-modelling Custodes damage.
Already modelled (exclude): Martial Ka'tah **lethal-hits** stance (`code/units.py`
~line 3850, search `Adeptus Custodes` + `effective_lethal_hits`) and Assemblage of
Might (AURIC_CHAMPIONS detachment; `assemblage_of_might` in `code/detachments.py`).
It must: (1) report the Custodes archetype's units and **detachment** from
`code/archetypes.py` — a detachment-specific rule that isn't the archetype's
detachment is useless (a "Shield Host Martial Mastery" idea was rejected for
exactly this — the archetype runs Auric Champions); (2) read each unit's offensive
abilities from `data/bsdata/cache/` (Adeptus Custodes .cat.gz) and/or Wahapedia,
including the OTHER Martial Ka'tah stances beyond lethal hits; (3) check each vs
`code/units.py`/`code/simulator.py` (modelled or missing); (4) return a ranked
list with verbatim cited text, detachment-gating, modelled-yes/no with file:line,
expected damage mechanism, and wiring cost. No file edits; no list/detachment
changes. **There is real headroom (5 pts), so a moderate offense lever should LAND
near 49.5 rather than overshoot** — unlike CK/Votann. Watch for overshoot anyway
(Custodes is durable); if it overshoots, adopt-as-is per the CK/Votann precedent.

When you build the winner, follow the flag-plumbing pattern (see below), screen it
Custodes-scoped, and adopt on the fidelity-first rule.

---

## The pattern to run every lever through

1. **Build** the gate default-**on** with a `SWEG_*=0` kill-switch, army-scoped to
   the built-for faction only (per-faction AI: a lever helps only its own faction;
   never nerf other armies' AI; only *universal bugs* get fixed globally).
2. **Off-path must be byte-identical** — with the kill-switch set, the run must
   reproduce the anchor with **0/36960 flips**. Verify this first; if it flips off,
   the gate leaks.
3. **Cite it** — add an entry to the right `data/rule_citations.d/<faction>.json`
   (verbatim rule text, real source URL, trigger/effect/scope) and register the key
   in `scripts/audit_rules.py` `SIMULATOR_RULE_KEYS`. Run the audit; it must say
   "All active rules cited and well-formed". **Never invent a citation** — if you
   can't source it, stop that lever.
4. **Screen scoped:** anchors are built **VANILLA + `--use-archetype`, NEVER
   `--sweghammer`** (this exact mistake cost a screen earlier — see memory
   `sweg_anchor_eval_flags`). Module form is required:
   `PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m scripts.evaluate_vs_meta
   --use-archetype --battles 80 --factions "<X>" --log-games <out>` (the bare
   `scripts/evaluate_vs_meta.py` path is shadowed by stdlib `code`). Then use the
   scoped paired-delta + merge flow from `docs/EVAL_PROTOCOL.md` to fill unchanged
   cells from the prior anchor and produce the new anchor.
5. **Judge on mean delta + gated field-weighted MAE**, not flip count — levers that
   consume extra RNG (forced tests, mortal-wound rolls) break the paired
   common-random-number pairing and make flip counts noisy.
6. **Decide, fidelity-first:**
   - Faithful rule that helps or is metric-neutral → **adopt**.
   - Faithful rule that **overshoots** a durable faction → **adopt-as-is** (the
     overshoot is the sim's structural over-reward, not the lever's fault — this is
     the CK ranged-hold / Votann ranged-hold precedent, an explicit user choice).
   - Anything that **empirically hurts** the metric (drags MAE, dips many cells) →
     **revert**, even if the rule is real.
7. **Adopt** = flip default-on, update `docs/CURRENT_STATE.md` (prepend a block) and
   `docs/DECISION_LEDGER.md` (a LANDED line), promote the scoped anchor to the new
   standing anchor, `run.py --cli` smoke, commit, push.

Flag-plumbing for an override-set profile flag (the tau_nova_charge template):
UnitProfile field in `code/units.py` + `CatalogEntry` field + constructor
`bool(d.get(...))` + `_apply_override` mapping + units.py entry→UnitProfile
conversion + `data/overrides.json` entry + citation. **Name-scoping alternative**
(`p.name == "..."`) skips plumbing for a single datasheet — but VERIFY it actually
fires (Grey Knights Force Edge was name-scoped and inert, 0 flips even on).

Commit identity + trailer (mandatory):
```
git -c user.email=jknight96@live.co.uk -c user.name=Allknight96 commit -F <msgfile>
```
Message ends with:
```
Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01TDDo39E5t9d8VuKdWwmZ4C
```

---

## What has been established (don't re-litigate)

- **Advance-discipline piloting is the highest-value lever family** and it is now
  COMPLETE: heavy shooting platforms hold and shoot instead of Advancing and
  forfeiting their Shooting phase. Shared `_suppress_advance` block in
  `code/simulator.py` `_do_move` (~line 11580), entry points `_ad_generic`
  (`SWEG_ADVANCE_DISCIPLINE`, default-off generic), `_ad_am`
  (`SWEG_AM_ADVANCE_DISCIPLINE`, +5.75), `_ad_ck` (`SWEG_CK_RANGED_HOLD`, +11.27),
  `_ad_votann` (`SWEG_VOTANN_RANGED_HOLD`, +10.37). Shared filter: ranged
  damage-per-activation ≥ 2.0 & range ≥ 18", and it never suppresses ASSAULT /
  transient-assault units. **Do NOT add a T'au entry point** — T'au is a
  mobile-shooting army (assault/jump) and cratered under the generic version; the
  code comment at ~line 11619 records this.
- **The big remaining error mass is structural**, both ends of one durability wall:
  durable factions (WE/DG/EC/Daemons/IK, now also CK/Votann) over-score because
  they survive to hold objectives in the survivor-snapshot model; fragile Astra
  Militarum under-scores because its cheap bodies die before scoring. Ability audits
  on the over-poles returned ~zero candidates (they are ability-exhausted). This is
  **off-limits for autonomous work** — it needs either a structural scoring remodel
  (hard, previously retired) or user direction.
- **Astra Militarum Orders are fully modelled** (`code/orders.py` — four wired
  Orders, per-officer profiles, squad grouping, Creed two-orders, Fix Bayonets and
  Duty-and-Honour guards). AM's gap is the durability wall, not a missing mechanic.
- **Class-bias helps, single-target-bias drags.** Biasing routing fire toward a
  *class* of target (Votann on-objective, CK below-half) helped; concentrating fire
  on single high-value targets (T'au markerlit bias) over-concentrated and dragged
  the metric — rejected.
- **Datasheet-ability levers on small units are near-inert** (Drukhari Tormentors,
  T'au Nova Charge small). The lifts come from *piloting*, not datasheets.
- **Adopted this session:** T'au Nova Charge, T'au ignore-cover arm, Custodes Ka'tah
  lethal-hits (+3.66, biggest datasheet lift), Assemblage of Might, Drukhari
  Incubi Tormentors (fidelity), deepstrike triage, AM advance-discipline (+5.75),
  CK ranged-hold (+11.27, overshoot adopt-as-is), Votann ranged-hold (+10.37,
  overshoot adopt-as-is). **Reverted:** Grey Knights Force Edge (inert), T'au
  target-bias (dragged), AM officer front-line (hurt −2.19), AM advance-discipline
  refinement (killed the lift).

---

## Suggested order of work for the successor

1. **Land the Custodes offense lever** (the in-flight audit's best candidate) — the
   last clean safe under-pole. Real headroom, should land not overshoot.
2. If more safe levers surface from the audit, run them through the pattern.
3. When the safe vein is confirmed dry, **do not pad**. Instead, when the user
   returns, surface the two high-value moves that need their sign-off:
   - **List-zone:** the World Eaters archetype composition looks mis-built
     (Khârn-anchored, not Angron) — flagged as the highest-value remaining lever but
     it is a LIST change and user-reserved.
   - **Structural:** a faithful remodel of the durability/objective-scoring
     over-reward would deflate every over-pole and lift Astra Militarum at once —
     the single biggest opportunity, but risky and previously retired; propose a
     concrete plan before touching it.
4. Watch the rule-14 checkpoint: at ~15 commits, mark this pull request merge-ready
   and open `claude/sim-calibration-17`.

Full lever-hunt state is in task #18 and `docs/DECISION_LEDGER.md`.
