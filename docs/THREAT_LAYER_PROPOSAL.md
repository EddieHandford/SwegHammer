# Threat-projection layer — design proposal (owner-originated, 2026-07-09)

Owner's framing, verbatim in spirit: give every enemy unit a projected damage
bubble — guns at range plus move-and-charge melee reach with a probability
gradient — sum them into a positional field, give every friendly unit a threat
*tolerance*, and make movement and charge decisions price their destination
against it, including the case where killing the charge target removes its
contribution from the field.

## Why this is the right shape (the mechanism-difference argument)

Every rejected positional lever (staging, kiting, gunline-hold, screens,
probe-reserve) was a SINGLE-SIDED defensive nudge: it made one behaviour more
cautious, everyone banked the caution symmetrically, and the durable side
profited (the family-table wash). A threat field is a SUBSTRATE, not a nudge:
it works both directions at once — fragile units decline exposure they cannot
pay for, durable and killy units *commit correctly* because the same
arithmetic tells them the destination is affordable or that the charge target
dies and stops projecting. No prior lever operated on both sides. That is the
stated escape from the settled family verdicts, and it is honestly uncertain —
the durability-over-reward could still bank it — but it is a genuinely new
mechanism, and it is faithful play modelling: "threat range" is the standard
real-play concept the researched playbooks in the pilot findings already cite.

Board-read failures this layer addresses as one class: the Astra Militarum
turn-one whole-line advance into an 18-to-48-inch gunline envelope (decided
its worst crater); the Orks open-ground march into Thousand Sons/T'au fire;
the Emperor's Children Daemon Prince arriving from reserve beside parked
Broadsides; charging one of two adjacent Khorne Berzerker squads with no
awareness of the second (charge scoring reads ONLY the target's own melee
threat — verified, strategy.py score = value / (1 + threat_against_target));
futile charges; uncoordinated pile-ons.

## Design

**The field.** Per enemy unit E and battlefield position p:
`threat_E(p) = ranged_expected_wounds(E → me at p) · in_range(E, p)
             + melee_expected_wounds(E → me) · P_reach(E, p)`
where `P_reach` uses E's Move plus the real two-dice charge distribution
(`charge_success_probability`, already in strategy.py) — the owner's melee
gradient. Sum over enemies = incoming field `T(p)`. All the per-pair
expected-wounds math already exists and is audited (`_ranged_expected_wounds`,
`_kill_potential_wounds`).

**Cost control.** Do not rasterise the board: evaluate `T` only at the
handful of candidate destinations each activation already considers, and
cache the per-enemy projection parameters once per battle round (the staging
envelope precompute pattern, simulator.py `_precompute_staging_envelope`).
Complexity is then O(candidates × enemies) per activation — comparable to the
existing bias chains.

**Tolerance (knob-free).** A unit's tolerance is DERIVED, never tuned:
`tolerance = expected value of the job at p` — claiming or holding a marker
(victory points per round), a charge that removes a threat or holder, a
shooting position that brings weapons to bear — priced against
`T(p) / effective_wounds` (the fraction of the unit's value forfeited by
standing there). The mission-override lesson from staging is preserved: a
mission-critical move (claim, contest, charge-home) is never frozen, only
re-routed or re-targeted when a cheaper-exposure destination does the same job.

**The charge case (owner's key clause).** When scoring a charge destination,
subtract the target's own contribution weighted by the probability the fight
kills it this turn: `T_post(p) = T(p) − threat_target(p) · P(kill)`, and add
the counter-charge term for every OTHER enemy whose `P_reach` of p is
material — the two-Berzerker case priced exactly. Survivability post-charge
becomes part of the same number the target's value already lives in.

**Consumers, in adoption order.** (1) charge target scoring (the supported-
target blindness), (2) move-intent destination choice (the exposure walks),
(3) reserve/deep-strike arrival placement (the parked-gun arrivals), then —
only if adopted — the staging/kite/advance-discipline heuristics become
redundant special cases and can retire into it (one lever, five deletions).

## Build discipline

Tier-3 structural work (novel mechanic; Opus-tier agent per the dispatch
tiering rules). Gate `SWEG_THREAT_LAYER` default-off, byte-identical off,
consumers gated individually so each screens separately (charge-consumer
first — smallest surface, clearest instrument). Instrument-before-build is
already satisfied by the pilot boards, but add one cheap counter first: per
faction, how often a unit ends its activation in a cell whose realized
next-turn incoming damage exceeds its remaining wounds (the "walked into it"
rate) — the number the layer must reduce, and the number that makes the
screen's mechanism check falsifiable. Expectations stated honestly in
advance: the metric consequence is uncertain in sign (the durability wall has
banked every play-quality improvement so far); the justification is fidelity
of play, and the falsifier is the walked-into-it rate, not the headline.

## Owner refinements (2026-07-09, second pass)

**1. Kills edit the field mid-turn — and sequencing falls out.** The field is
computed live at each activation from currently-alive enemies, so a unit shot
dead earlier in the turn projects nothing by the time later units move — the
"dangerous move becomes fine because we killed the projector first" case is
automatic, not special-cased. Two deliberate couplings on top: (a) a
planned-kill discount — a mover may price a destination against
`T(p) − threat_E(p) · P(E dies to fire already allocated this turn)`, so
moves can be planned into cells our own shooting is about to clear; (b) an
"unlocks space" term for the SHOOT picker — a target's value gains the
threat it projects over destinations our army wants this turn, which makes
"kill the screen so the charge lane opens" an arithmetic consequence rather
than a heuristic. The army-level activation plan already biases activation
ORDER, giving the shoot-before-move sequencing a place to live.

**2. Ranged threat does not cross line of sight — cover becomes emergent.**
Gun projections are occluded by blocking terrain along the segment from the
enemy to the evaluated cell (the map's terrain pieces carry wall geometry),
so cells behind ruins carry only the melee gradient — and tolerance-driven
movers HUG COVER as a consequence of the arithmetic, with no cover heuristic
at all: the Orks open-ground march fixes itself by pathing through the
occluded cells. HONEST CAVEAT, flagged deliberately: the sim's actual
shooting RESOLUTION uses angle-independent positional cover
(`cover_at(target.position)`, the audited symmetric ~46 percent tax) and has
no true line-of-sight blocking — so the layer would plan with sharper
geometry than the resolution enforces. That is acceptable for an AI
evaluation layer (real players also plan with better geometry than they
sometimes get), but it creates a documented asymmetry, and the real fix —
line-of-sight-blocked shooting resolution — is a separate, large Stage-1
rules-fidelity question in its own right (a major re-anchor event, sign
uncertain, adjacent to open issue 52 on wall collision). Sequence: layer
first with occlusion-aware planning; resolution line of sight as its own
gated proposal afterwards if the owner wants it.

## Status

**Consumer 1 (charge scoring) BUILT 2026-07-09** — owner go given. The FIELD
substrate plus consumer 1 (charge-target scoring) are implemented in
`code/strategy.py` (`_charge_field_post_denominator` and the field helpers,
`pick_charge_target`), gate `SWEG_THREAT_CHARGE` (default-off, byte-identical
off), with a one-line map-pass hook in `code/simulator.py._do_charge` and the
citation `simulator.threat_projection_charge` in
`data/rule_citations.d/threat_layer.json` (audit green). v1 uses the
cover-attenuation ranged form (no line-of-sight occlusion, per the caveat
above). The walked-into-it falsifier ships as `scripts/diag_walked_into_it.py`.
Validated (no evals): field math checked against hand computation; the
two-Berzerker mechanism confirmed (gate off cannot tell the supported target
from the isolated one, gate on penalises the supported target and re-picks the
isolated one); across six charge-heavy battles the gate changed the chosen
charge target 28 times in 248 decisions (11.3%); walked-into-it baselines
recorded (World Eaters 0.224, T'au 0.214, Chaos Daemons 0.164 lethal-cell rate).
NOT YET SCREENED — awaits the sc61a re-anchor before any `SWEG_THREAT_CHARGE=1`
vs anchor evaluation.

Consumers 2 (move-intent destinations) and 3 (reserve / deep-strike arrival
placement) remain PARKED and OUT of scope: a parallel worktree owns the
movement-resolution region. The owner's planned-kill discount (refinement 1a) is
also deferred — fire-allocation state is not cleanly readable at charge time, so
it is documented as consumer-2 work rather than forced here.
