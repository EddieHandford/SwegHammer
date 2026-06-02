# The per-faction residual structure converges on ONE axis (waves 109–114)

Per the watchdog steer (diagnose the out-of-band factions to find any separable
missing mechanic), this is the synthesis. Across six factions spanning every army
archetype, instrumented the win mechanism (tabling vs primary VP vs secondary VP)
the way wave 109 instrumented the Imperial Knights. The result is a clean
convergence: **the whole per-faction residual is a single axis — primary
board-control / mission fidelity.**

## The data (instrumented, 25 games per matchup unless noted)

| faction | residual | tabled? | decided on | primary (self vs opp) | reading |
|---|---|---|---|---|---|
| Imperial Knights | **+27** over | never | primary | ~44 vs ~30 | durable camper OVER-holds |
| Thousand Sons | +9 over | never | primary | 39.7 vs 31.8 | durable elite OVER-holds |
| Chaos Space Marines | −9 under | never | primary | 36.1 vs 36.5 | ≈even, mild under |
| Necrons | −13.9 under | never | primary | out-held (1.67 vs 2.09 markers) | out-massed, UNDER-holds |
| Chaos Daemons | −14.7 under | never | primary | 27–36 vs 30–41 | mobile melee UNDER-holds |
| World Eaters | over (vs weak) | never | primary | 33.1 vs 36.3 | mobile melee loses primary vs strong |

Invariants across ALL six (and every opponent):
- **Never tabled** (0 tablings in hundreds of games); every game runs the full
  five rounds; armies keep 28–60% of their units. The win is NOT decided by combat.
- **Secondary VP is always a wash** — every army's raw secondary (54–77) exceeds
  the 40/game cap, so both sides contribute exactly 40 to the decision. Secondary
  never differentiates.
- **Primary VP is the entire differential.** Durable / elite armies (Imperial
  Knights, Thousand Sons) OVER-hold the markers and over-shoot; mobile-melee
  (Daemons, World Eaters) and out-massed holders (Necrons, Chaos Space Marines)
  UNDER-hold and under-shoot. Same axis, opposite ends.

## Conclusion — (iii) un-interleaving is the dominant remaining lever; no separable fix

There is **no separable, faction-specific missing mechanic** behind the big
residuals. Necrons' reanimation works (they are never tabled, survive 28–60%);
the Daemon / Shadow-of-Chaos combat half is modelled; secondary scoring (selection
+ caps + live Cleanse / Sabotage) is faithful. Every residual is the same primary
board-control gap, which the wave 109–111 chain proved is rooted in the
alternating-activation round model scoring primary ONCE per round (after combat),
crediting only the durable post-combat survivor — where real 10e scores at each
player's Command phase (a unit holds an objective from when it takes it until an
enemy takes it). The faithful fix is **(iii) un-interleaving to real per-player
turns + per-Command-phase scoring** — FOUNDATIONAL and **user-escalated**.

A secondary contributing factor (noted, not pursued — delicate): because every
army maxes the 40 secondary cap, the secondary game — where a board-control army
out-scores a Knight via actions/board it can't do — is erased as a differentiator,
leaving primary (which over-rewards durable holders) to decide everything. This is
the same scoring-economy fidelity family and is best addressed alongside (iii), not
as a separate metric-tuning of the cap.

**Net: the loop has localised the ENTIRE headline residual to one faithful,
user-gated structural fix (iii). It is genuinely blocked on the user's decision.**
The remaining buildable-now work is faithful hygiene (one-sided data corrections
like the wave-113 Skorpius restore, which helped Adeptus Mechanicus the right
direction). Reported to the watchdog (LOOP_QA wave-114).
