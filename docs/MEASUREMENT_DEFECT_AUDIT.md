# Defect-class audit — measurement, gating, approximation, and admitted defects

> **THE METHOD, which generalised four times.** Ask a question of the whole
> codebase rather than of one faction, and let the answer name a CLASS:
>
> 1. *What rule does the codebase STATE but not apply everywhere?* → the
>    measurement-defect class below. Yield: **+3.33 on the deepest under-pole**.
> 2. *What rule does it IMPLEMENT but leave switched off?*
>    (`scripts/_gate_sweep.py`) → eleven mechanics enabled, seven correctly
>    excluded as list choices or heuristics. Class now exhausted.
> 3. *What does it implement as a KNOWN APPROXIMATION?*
>    (`scripts/_approximation_sweep.py`) → **269 of 515 citations** self-declare
>    as approximations, proxies or partial mappings.
> 4. *Which citations ADMIT a live defect left in place?*
>    (`scripts/_admitted_defect_sweep.py`) → 32 confessions, but **18 of them
>    were already fixed** — see the retraction below. Cross-check gate defaults
>    against the CODE or this sweep lies.
> **CORRECTION — three of the seventeen "adopted" gates are INERT.** Verified by
> digest: `SWEG_SECONDARY_HANDCAP`, `SWEG_ACTION_ECONOMY` and
> `SWEG_CHALLENGER_GAP_CAPPED` all off gives `4aab205fbb99635db7c607db`, exactly
> the same as all on. **Fourteen gates took effect, not seventeen**, and the
> sc68a mid-table cost comes entirely from those fourteen.
>
> The reason is a NAMING TRAP worth remembering. `SWEG_CHALLENGER_GAP_CAPPED` is
> not the switch for Challenger Cards — the parent is `SWEG_CHALLENGER_CARDS`,
> which is default-off and was **"REVERTED TO DEFAULT-OFF 2026-07-04"**, a
> deliberate earlier decision. `..._GAP_CAPPED` only chooses HOW the victory-point
> gap is measured once the feature is already running. So one of the three
> "missing mechanics" was not missing at all; it was switched off on purpose three
> weeks earlier. Likewise `SWEG_SECONDARY_HANDCAP` only applies to the FIXED
> secondary branch, and with `SWEG_TAC_DECK` default-on every army scores through
> the TACTICAL branch, which never reaches it.
>
> **Rule: before adopting a gate, find its PARENT and check the code path is
> reachable.** Matching a gate name to a citation is not evidence that flipping it
> does anything — and a default-off gate may encode a deliberate prior ruling
> rather than an oversight.
>
> 6. *Which CORE rules enumerate several trigger legs, with only some wired?*
>    (`scripts/_trigger_leg_sweep.py`) — the generalisation of this session's
>    largest structural find. **One real defect: Fire Overwatch**, whose trigger
>    names four move types and two timings and which the simulator fired only on
>    charge and Reserves arrival. Wiring the movement leg moved Death Guard 2.1
>    toward reality — the first movement of that residual in the project's
>    history. The detector's credibility is that it ranks that known case FIRST
>    (10 legs enumerated, 4 omitted). Its other 16 hits were adjudicated and are
>    **correctly implemented**: the Advance-blocks-charge lockout is wired with
>    its proper exemptions (Gladius Assault doctrine, Murderer's Cowl, Apoplectic
>    Frenzy), and performing an Action blocks charging as well as shooting. In
>    both cases the citation's EFFECT text describes a narrower gate than its
>    QUOTE, which is what tripped the detector. **Verdict: the class is thin, not
>    rich — but the one member was worth more than any piloting lever this
>    project has built.**
> 5. *What does the simulator GRANT that no rule text authorises?* — the
>    fabrication class. `scripts/_fabrication_sweep.py` **FAILED as designed**:
>    126 shortlist hits with the top six all false positives, because scanning
>    effect PROSE for mechanic names cannot separate "grants Lethal Hits" from
>    "the sim already models Rendax Lethal Hits" or "the prior fabricated proxy
>    was removed". The class is real — the ledger records removed `LeaderAbility`
>    fabrications and the Khorne Berzerkers mislabelling — but the detector must
>    compare the STRUCTURED flags the code sets (`lethal_hits`,
>    `plus_one_to_hit`, `fnp`, …) against the quoted text, not the narrative.
>    Registered as unbuilt; do not trust the current script's output.

## RETRACTED — "the Aeldari resource over-supply" was a false lead

Sweep 4 first reported that both Aeldari army-rule resources were over-supplied
with the fixes switched off, and that this explained the number two over-pole.
**That was wrong, and the error is instructive enough to keep on the record.**

`simulator.strands_of_fate` really does confess a "KNOWN OVER-COUNT … up to
~36-40 spends/round" against a codex six-dice-per-battle, and
`simulator.battle_focus` really does record that unspent Battle Focus tokens
should be discarded and a prior comment wrongly said otherwise. Both readings of
the citations were correct. But **both fixes were adopted default-on back on
2026-07-08** (`SWEG_AELDARI_FATE_FAITHFUL`, `SWEG_AELDARI_BF_DISCARD`), as was
World Eaters' Blood Tithe scoping.

**The trap: a citation keeps its pre-fix narrative after adoption.** The
"ADOPTED default-on" note lives in a CODE COMMENT beside the gate, not in the
citation text. So a sweep that reads only citations sees a live confession where
the defect has in fact been closed for weeks.

`scripts/_admitted_defect_sweep.py` now cross-references every named gate against
its ACTUAL default read from the code, and splits the output into ACTIONABLE
(fix gate still off, or no gate named at all) versus ALREADY FIXED. On that
corrected basis: **14 actionable, 18 already fixed** — and most of the 14 are
either gates deliberately excluded elsewhere in this document (Hearthband is a
list choice; re-embark is dead code behind a default-off gate) or substring
artefacts of the gate-name matching.

**Standing rule for any future sweep of this codebase: never treat citation prose
as evidence of current behaviour. Read the gate default from the code.** The same
mistake in the opposite direction produced the earlier "Fire Overwatch is
disabled" false alarm.

---

# Measurement-defect audit — where the simulator measures centre-to-centre

**Date:** 2026-07-25
**Why this document exists.** The Astra Militarum session found that ONE range
test measured centre-to-centre instead of base-edge was worth **+3.33 win-rate
points** on the deepest under-pole — 87 percent of everything that session
achieved — while four separate piloting heuristics built the same night came back
marginal or inert. Measurement defects are, on this evidence, the highest-yield
class of fidelity bug in the codebase, and they are cheap to find. This is the
inventory.

## The rule

`data/rule_citations.d/keywords_and_mechanics.json`, already in this repository:

> When measuring the distance between models, measure between the closest points
> of the bases of the models you're measuring to and from.

Centre-to-centre is therefore **stricter than the rules by the sum of the two
models' base radii**. The error is largest where bases are largest: an infantry
model is 0.63 inches of radius, a Leman Russ or Rhino hull 2.37, an Imperial
Knight considerably more. On a 6-inch aura between a foot character and a tank,
centre-only delivers 67 percent of the legal radius — **44 percent of the legal
area**.

## Where the codebase already gets it right

* **Engagement Range** — `code.sim.geometry._er_gap`, cited
  `simulator.engagement_range_base_edge`, default-on since wave 240.
* **Objective control** — `Battle._assign_army_oc`, control radius = centre
  distance − base radius, cited in `keywords_and_mechanics.json`.

Both prove the project understands the rule. Everything below is a place it was
not applied.

## FIXED this session (gated default-off, byte-identical off, cited)

| site | gate | status |
|---|---|---|
| Voice of Command 6-inch Order aura (`code/orders.py`, 3 call sites) | `SWEG_ORDER_AURA_BASEEDGE` | **screened +3.33 Astra Militarum, gated 2.76 → 2.59** |
| Weapon range eligibility + the Rapid Fire X / Melta X half-range trigger (`Battle._do_shoot`) | `SWEG_RANGE_BASEEDGE` | built, screening |

## The weapon-range result — faithful, and metric-HARMFUL. An owner call.

Resolution-only arm, N=80 paired against `sc67a` (`_scr_rangebe_log.json`):

```
gated mean absolute error:  2.76 -> 3.26   (+0.50, WORSE)
Adeptus Astartes  48.7 -> 54.2   +5.49 UP*    (real 47.0 — further away)
Tyranids          40.1 -> 36.7   -3.42 DOWN*  (deepest under-pole, deeper)
Astra Militarum   33.8 -> 33.8   -0.01        nothing
```

The static probe predicted this exactly: the correction recovers in-range target
pairs in proportion to base size, so large-based durable shooters bank it and
Adeptus Astartes gains most. **Astra Militarum gets nothing from it** — this was
never an under-pole lever.

**This is the fidelity-versus-metric tension in its purest form, and it is an
owner decision, not an agent one.** The rule is unambiguous, it is already cited
in this repository, and the simulator already applies it to Engagement Range and
objective control — so leaving weapon range centre-only is a known-wrong
measurement retained because it flatters the metric. The project has faced this
before and chosen fidelity: `SWEG_TERRAIN_DENSE` was adopted fidelity-first at
**+0.46** gated on exactly the reasoning that the faithful frame sharpens the
diagnosis rather than hiding it. The same argument applies here, and the +0.50
would land as a larger, more honest Adeptus Astartes over-pole to be attacked
structurally.

Recommendation: adopt on fidelity grounds, re-anchor, and treat the inflated
Astartes residual as the next target — but that is the owner's ruling to make.

### Both arms are now in, and the verdict is stable

| arm | gated | Adeptus Astartes | Tyranids |
|---|---|---|---|
| resolution only (`_scr_rangebe_log.json`) | 2.76 → **3.26** | +5.49 | −3.42 |
| complete, + reach estimates (`_scr_rangebe2_log.json`) | 2.76 → **3.28** | +5.38 | −3.57 |
| **reach-estimate contribution alone** | 3.26 → **3.28** | — | — |

**The reach-estimate inconsistency is worth +0.02 — nothing.** The concern that
prompted the fold-in was sound in principle (an estimate and its resolution must
share one measurement) but is empirically immaterial here. The fold-in stays,
because consistency is correct and costs nothing; it simply does not change the
answer. The practical value is that the owner's decision now rests on a number
measured twice, independently, landing in the same place: **+0.50 gated, driven
almost entirely by Adeptus Astartes.**

## OPEN — high confidence these are the same defect

Each is a datasheet or army rule whose text reads "within N inches of this
model", i.e. a rules-measured model-to-model distance, currently measured centre
to centre. Line numbers are `code/simulator.py` at the time of writing.

| line | mechanic | range |
|---|---|---|
| 11019 | Tyranids Synapse | 6" |
| 11029 | Shadow in the Warp | 6" |
| 11038 | Death Guard Contagion Range | 3"/6"/9" by round |
| 11050 | Chaos Daemons Shadow of Chaos | 18" |
| 11058, 11708 | Chaos Knights Harbingers of Dread | 9" |
| 18252, 18308 | T'au markerlight — see note below | 36" weapon range |
| 6387 | Aeldari Blitzing Firepower | 12" |
| 18913 | transport embark proximity | 3" |
| 18906 | disembark enemy-proximity legality | 1" (Engagement Range — should use `_er_gap`) |

**These are NOT metric-neutral, and that must be stated plainly.** Contagion
belongs to Death Guard and Harbingers to Chaos Knights — the number one and
another over-pole; Synapse and Shadow in the Warp belong to Tyranids, the deepest
under-pole. Widening them all is faithful but pushes the frame in both
directions at once. Fidelity-first says adopt regardless of the metric, but each
needs its own screen and none should ride an unrelated result.

## CLOSED — the reach-estimate inconsistency, now folded into the gate

`SWEG_RANGE_BASEEDGE` initially corrected only RESOLUTION, leaving the
**artificial intelligence's own estimates of its reach** centre-to-centre — so
with the gate on, a mover under-estimated its reach by both base radii and closed
further than it needed to, worst for exactly the large-based platforms the
correction most affects. All four sites now route through the shared
`_weapon_range_gap(attacker, target)` helper (the weapon-range companion to
`_er_gap_units`), so estimate and resolution share one measurement:

| line | what it estimates |
|---|---|
| 3943, 4104 | "is an enemy inside my weapon range" for move intent |
| 6111 | candidate reach in the stratagem scorer |
| 14436 | the advance-suppression family's can-I-damage guard |

**This gives a free two-arm decomposition rather than a wasted run.** The screen
launched before the fold-in (`data/_scr_rangebe_log.json`) measures the
**resolution-only** correction; a second arm on the completed gate measures the
whole mechanic, and the difference is exactly what the artificial intelligence's
own reach estimate is worth. Report both.

## NOT defects (checked, deliberately centre-only)

* 19177 — "transport within 6 inches of an objective". An objective marker is not
  a model; the marker-radius handling lives in `_assign_army_oc`.
* 17402, 17477 — squad-counting heuristics for counter-charge and wave sizing.
  Internal artificial-intelligence bookkeeping, no rule text behind them.
* 18737 — 6-inch proximity to a destroyed model's position, an internal
  bookkeeping radius.
* 6591 — a CHARACTER-within-6-inches test; classify against its rule before
  touching it, it may be a Lone Operative or leader-proximity proxy.

### Note — T'au markerlight belongs to the WEAPON-range gate, and is deliberately deferred

`_run_markerlight_phase` sets `markerlight_range = 36.0`: that is the
Markerlight **weapon's** range, not an aura, so it belongs under
`SWEG_RANGE_BASEEDGE` with the other weapon ranges rather than under
`SWEG_AURA_BASEEDGE` — routing it through `_weapon_range_gap` is the one-line
change.

It is NOT being made yet, on purpose. An arm using `SWEG_RANGE_BASEEDGE` is in
flight (`data/_scr_rangebe2_log.json`), and widening a gate's scope while a
screen using it is running would leave that result mapping to no code state that
ever existed. Three arms with three different meanings of the same gate name is
how a calibration record becomes untrustworthy. **Add markerlight to
`SWEG_RANGE_BASEEDGE` only after the in-flight arm lands, then re-screen the
gate.** T'au is an under-pole (−6.9), so unlike Contagion and Harbingers this
site may well be metric-positive.

## FOUR verdicts, and the rule they establish

| fix | faithful | metric effect | recommendation |
|---|---|---|---|
| `SWEG_ORDER_AURA_BASEEDGE` | yes | **gated −0.17, Astra Militarum +3.33 DECISIVE** | **adopted** |
| `SWEG_AURA_BASEEDGE` (Battle-shock auras) | yes | +0.03, zero decisive movers | **adopted** — free |
| T'au markerlight (inside `SWEG_RANGE_BASEEDGE`) | yes | +0.03, one marginal mover | **adopted** — free |
| `SWEG_RANGE_BASEEDGE` (weapon + half range) | yes | **+0.50**, Adeptus Astartes +5.4 | **adopted on owner ruling** |

**The rule these four establish: a measurement defect matters in proportion to
how often the corrected band changes an OUTCOME — not to how distorted the band
is.**

* The Order aura gates the Voice of Command economy every single Command phase →
  **+3.33**, the largest single lever of the campaign.
* Weapon range gates every shot → moved the frame hard (+0.50, wrong way).
* Battle-shock auras gate a test that rarely swings on the margin → **nothing**,
  despite Contagion being distorted *exactly as badly* as the Order aura (both
  keep 44 percent of legal area).
* Markerlight is a 36-inch band where two base radii are a small fraction, and
  the mark usually lands either way → **nothing**.

Contagion and the Order aura are the clean natural experiment: identical
distortion, opposite impact. Distortion size predicts nothing on its own. Use
frequency-of-consequence to triage any future site.

## Superseded: the three-verdict table

| fix | faithful | metric effect | recommendation |
|---|---|---|---|
| `SWEG_ORDER_AURA_BASEEDGE` | yes | **gated −0.17, Astra Militarum +3.33 DECISIVE** | **adopt** — a clear win |
| `SWEG_AURA_BASEEDGE` (Battle-shock auras) | yes | **+0.03, inside noise, zero decisive movers** | **adopt** — free removal of a known-wrong measurement |
| `SWEG_RANGE_BASEEDGE` (weapon + half range) | yes | **+0.50**, via Adeptus Astartes +5.4 | **owner ruling** — the fidelity-versus-metric fork |

The aura arm (`_scr_aurabe_log.json`) is the cleanest possible negative: gated
2.76 → 2.79, no faction moving decisively, every paired interval spanning zero,
and flip counts mostly under twenty. Battle-shock outcomes do not hinge on those
marginal band widths often enough to matter. It is still worth adopting — it
costs nothing and deletes a measurement the rules contradict — but it is not a
lever and should not be sold as one.

**The lesson the three verdicts teach together:** a measurement defect matters in
proportion to how often the corrected band changes an OUTCOME. The Order aura
gates the Voice of Command economy on every Command phase, so it was worth +3.33.
Weapon range gates every shot, so it moved the frame hard (in the wrong
direction). Battle-shock auras gate a test that rarely swings on the margin, so
they moved nothing. Distortion size alone does not predict impact — frequency of
consequence does.

## Distortion scales INVERSELY with the stated range — and the audit is now closed

The error is the sum of the two base radii, so a short range is proportionally
far more broken than a long one:

| site | stated | legal | radius kept | **area kept** |
|---|---|---|---|---|
| disembark Engagement Range | 1.0" | 2.26" | 44% | **20%** |
| transport embark | 3.0" | 6.00" | 50% | **25%** |
| Voice of Command aura → tank | 6.0" | 9.00" | 67% | **44%** |
| Death Guard Contagion → Crawler | 6.0" | 9.00" | 67% | 44% |
| Chaos Knights Harbingers | 9.0" | 12.00" | 75% | 56% |
| Aeldari Blitzing Firepower | 12.0" | 15.00" | 80% | 64% |

The 6-inch Order aura, at 44 percent of its legal area, was worth **+3.33**. That
sets the scale: the two short-range sites above it are worse still.

**But they are both DEAD CODE.** The transport embark 3-inch test and the
disembark 1-inch Engagement Range test both live inside
`Battle._maybe_reembark_after_move`, which returns on its first line unless
`SWEG_REEMBARK=1` — and that gate is **default-off**. Correcting their
measurement would be entirely inert in the production configuration. They are
recorded here so that if `SWEG_REEMBARK` is ever adopted, the measurement is
fixed in the same change; the 1-inch test should simply route through the
existing `_er_gap_units`, since it is an Engagement Range check that does not use
the Engagement Range helper.

**That leaves Aeldari Blitzing Firepower (`simulator.py` 6387, gate
`SWEG_AELDARI_BLITZ_RANGE`, default-on) as the only live unfixed site in the
class — and at 64 percent of legal area it is the LEAST distorted of all of
them.** Everything live and materially wrong is now either fixed and screened, or
built and screening.

## How to work this list

1. Confirm the rule text for the mechanic (Wahapedia / BSData) — do not assume
   "within N inches" from the variable name.
2. Route the comparison through a base-edge helper, gate it default-off, prove
   byte-identical off with `python -m scripts._detcheck` (digest
   `db13417fb7e3b2d47cef9867`).
3. Cite it per CLAUDE.md rule 10.
4. Screen it ALONE. These cut across factions and several favour the over-poles;
   a bundled screen cannot be attributed.
