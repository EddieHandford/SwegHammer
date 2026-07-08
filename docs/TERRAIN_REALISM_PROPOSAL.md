# Make terrain real — line of sight + wall collision (owner-ordered, 2026-07-09)

The last big unfaithful subsystem. Everything else in the simulator is now
audited faithful (rules, damage math, scoring economy, lists, movement rates,
the measurement frame); terrain alone remains a statistical modifier standing
on unused geometry. This proposal upgrades it to physics, as one package,
because its two halves are incoherent apart.

## What is wrong today (measured / verified)

1. **No line of sight exists.** Shooting resolution never traces a ray.
   "Cover" is `cover_at(target.position)` — an angle-independent lookup of
   whether the TARGET stands in a cover zone, granting one save pip. The
   shooter's position is irrelevant; walls never block a shot. The 2026-06-15
   audit measured this as a symmetric ~46 percent output tax on every faction.
2. **Movement tunnels through walls** (open issue 52). Units path
   point-to-point with no segment-versus-terrain intersection test. The map
   data already carries wall geometry per terrain piece; nothing consults it.

## The real rules being restored (citable, Wahapedia core rules)

- Visibility: a model can only be targeted if visible to the attacker; ruins
  block visibility to models wholly behind them (true occlusion, not a save
  modifier).
- Benefit of Cover: models IN or partially obscured by terrain get the save
  benefit — the positional half the simulator already approximates.
- Movement: models cannot move through terrain features' walls; they go
  around, over (if permitted), or through openings.

## Why this may be the Astra Militarum / Death Guard lever (the hypothesis)

True line of sight is how FRAGILE armies survive shooting in real play: real
Astra Militarum hides its squishy objective-holders behind ruins and denies
entire shooting phases; durable armies do not need to. Today's symmetric
cover tax gives fragile armies none of that asymmetric protection — and the
two remaining poles (Astra Militarum −20 under, Death Guard +16 over) are
precisely the most-fragile-bodies and least-needs-cover factions. The
five-facet audit found AM dies exactly as its datasheets imply UNDER FULL
EXPOSURE — which is faithful arithmetic on unfaithful geometry. HYPOTHESIS,
stated falsifiably in advance: with real occlusion, fragile-body factions
gain survivable board presence (AM presence-to-control conversion rises,
its per-opponent primary-denial deficit narrows) and always-exposed durable
armies lose relative advantage — both remaining poles move toward real. The
sign is NOT guaranteed (the durability wall has banked play improvements
before); the falsifier is the facet instruments, not the headline alone.

## Build plan (one package, three gated stages)

Stage T1 — **geometry substrate**: segment-versus-terrain-piece intersection
helpers (walls as rectangles/segments from the existing map data), cached per
map; a `has_los(a, b)` and a `path_blocked(a, b)` primitive. Pure library
code, no behaviour change, unit-tested against hand-drawn cases.

Stage T2 — **movement collision** (`SWEG_TERRAIN_COLLISION`, default-off):
`_move_toward` clamps movement at wall intersections and routes around via
the existing candidate-destination machinery (no pathfinding rewrite — reject
blocked candidates, prefer unblocked ones; a unit with every candidate
blocked stops at the wall). Byte-identical off. Screen full-frame.

Stage T3 — **line-of-sight shooting** (`SWEG_TERRAIN_LOS`, default-off):
targeting requires `has_los(shooter, target)`; Benefit of Cover keeps its
current positional grant (already faithful for the in-cover case); indirect
fire weapons (already flagged in profiles) exempt, per their real rule.
Screen full-frame; expect large movement in both directions — this is a
FRAME-CHANGE-CLASS adoption requiring a fresh N=80 anchor and re-validation
of held/adopted levers whose screens predate it.

Stage T4 (after adoption) — **planner integration**: the threat-projection
layer (docs/THREAT_LAYER_PROPOSAL.md) reads the same `has_los` geometry, so
planning and resolution agree and cover play becomes emergent. Until T3
adopts, the threat layer ships its v1 cover-attenuation form (consistent
with today's resolution) — do NOT ship occlusion-aware planning against
non-occluding resolution; the planner would hide units behind walls that do
not stop bullets.

## Discipline

Each stage: gated default-off, byte-identical-off proven, rules cited
(Wahapedia core visibility/terrain verbatim per CLAUDE.md rule 10),
`run.py --cli` and audit green, full-frame screens with the facet
instruments (presence-to-control, primary-denial, walked-into-it rate)
reported alongside the headline. Tier-3 build (Opus-grade dispatch).
Performance note: `has_los` sits in the shooting hot loop across ~37,000
games per anchor — cache per (shooter-cell, target-cell) pair per map, and
budget a wall-clock regression test before adoption.

## Status

APPROVED-in-principle by the owner ("we need to fix this") 2026-07-09;
queued behind the sc61a re-anchor relaunch. Closes issue 52 at stage T2.
