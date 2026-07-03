# The build-mechanism durability audit — is the archetype fill the single structural lever? (2026-07-03)

## The question

The residual sc52a over/under-poles all trace (per the closed secondary-economy
arc) to the primary/kill economy over-paying survivor uptime, on rules now
audited faithful. The owner chose army-list fidelity as the next surface. This
is the **horizontal, structural cut**: across all 22 evaluation factions, does
`build_archetype_army`'s seed plus random fill produce a **durability-per-point**
that **correlates** with the over/under-pole? If the over-pole factions
systematically get filled with more durability-per-point than their real lists
carry, and the under-pole factions get less, then the fill mechanism is a single
structural lever — one fix, not 22 per-faction list edits. If there is no such
correlation, the poles are per-faction list divergences to hand to the vertical
audits.

## Verdict (the crisp call)

**There is no single structural fill-mechanism durability divergence. Durability-
per-point does not track the pole. The poles are per-faction list divergences
layered on an economy that rewards low-model-count survivor uptime — hand them
to the vertical audits.**

The specific durable-brick provisioning the hypothesis names (fraction of points
in Toughness-10-or-more / 15-wound-or-more platforms) has a correlation with the
pole of only **r = +0.23 (not significant, p = 0.30)**, and it is non-monotone
(the under-pole bucket carries *more* brick share than the mid bucket). Two clean
counterexamples falsify the hypothesis outright:

* **Astra Militarum** is the largest under-pole (−11.9) yet carries the highest
  durable-brick share of any non-Knight faction (0.50) and an above-average
  wounds-weighted Toughness (7.3). Its fill is 36% armour by points — Rogal Dorn
  (Toughness 12), Manticore (Toughness 10), Leman Russ (Toughness 11), Basilisk
  (Toughness 9). If durable fill drove the pole, Astra Militarum would over-perform.
  It is the biggest under-performer.
* **Aeldari** is the fourth-largest over-pole (+14.7) yet carries **zero** durable
  bricks in seed *or* fill and the lowest durability in the game (0.054 wounds per
  point, wounds-weighted Toughness 3.8). Its fill is entirely Toughness-3
  one-wound Aspect Warriors. Its over-pole cannot be a durability-provisioning
  artifact.

The **only** durability metric that correlates with the pole is invulnerable-save
coverage (r = +0.52), but that is a roster property (elite factions intrinsically
carry invulnerable saves), it is present **equally in the seed and the fill**
(seed r = 0.52, fill r = 0.49 — so it is not a fill artifact), and it is confounded:
Thousand Sons, Chaos Daemons and Drukhari all carry ~100% invulnerable coverage
without over-poling. The cleaner correlate is **wounds-per-point at r = −0.49
(negative)**: over-poles are low-model elite armies, under-poles are high-wounds-
per-point hordes. That is the model-count / survivor-uptime axis the brief's
preamble already identifies — not a durability-provisioning axis.

## How the mechanism composes

`build_archetype_army` builds each 2000-point army in two phases:

1. **Seed** — `_instantiate_template` walks the curated template in
   (−count, −cost, character-first) order and seeds one squad per entry until a
   per-faction fraction of the budget is spent (`SEED_FRACTION` 0.30 default, with
   per-faction overrides up to 0.78 under the default-on leader-stack gate), plus a
   flagship epic-hero anchor (up to 0.6× budget) and a cheapest-character guarantee.
   Seed squads are fielded at minimum models.
2. **Fill** — `_random_fill` tops up the remaining budget. Under the default-on
   `SWEG_FILL_TEMPLATE_POOL` gate the fill draws **uniformly among the affordable
   curated-template units first**, falling back to the whole faction catalogue only
   when no template unit is affordable. Fill squads are fielded at maximum models.
   Caps: battleline at max(1, template count), monster/titanic/epic-hero at the
   template count (0 for unseeded wreckers), per-name spend at half the remaining
   budget, epic heroes one per army.

The realized **seed point-share varies enormously by faction** — from 0.28
(Tyranids) to 0.78 (Grey Knights) — so the fill is anywhere from 22% to 72% of the
army. That variance alone argues against a uniform fill lever: the fill's influence
is not constant across the poles.

## The 22-faction durability-per-point table (seed/fill split)

Sampled 45 archetype builds per faction at 2000 points, all environment gates at
production defaults (the sc52a anchor build path). `wpp` = wounds per point;
`wtT` = wounds-weighted Toughness; `brick` = point share in Toughness-10+/15-wound-+
platforms; `inv`/`fnp` = wound coverage with an invulnerable save / feel-no-pain;
`sdfrac` = realized seed point-share; `f.*` = the fill slice alone.

| Faction | pole | wpp | wtT | brick | inv | fnp | seedfrac | fill.wpp | fill.wtT | fill.brick |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Death Guard | +22.2 | 0.076 | 7.9 | 0.37 | 0.68 | 0.28 | 0.56 | 0.089 | 7.3 | 0.19 |
| Imperial Knights | +17.6 | 0.078 | 10.2 | 0.65 | 1.00 | 0.00 | 0.44 | 0.076 | 10.5 | 0.77 |
| Chaos Knights | +15.2 | 0.082 | 10.2 | 0.56 | 1.00 | 0.00 | 0.43 | 0.082 | 10.2 | 0.62 |
| Aeldari | +14.7 | 0.054 | 3.8 | 0.00 | 0.95 | 0.00 | 0.30 | 0.060 | 4.0 | 0.00 |
| Adeptus Custodes | +10.8 | 0.064 | 6.7 | 0.15 | 0.89 | 0.00 | 0.58 | 0.068 | 6.4 | 0.11 |
| Leagues of Votann | +8.0 | 0.091 | 6.8 | 0.25 | 0.10 | 0.16 | 0.48 | 0.091 | 6.9 | 0.24 |
| Adepta Sororitas | +6.9 | 0.065 | 6.1 | 0.27 | 1.00 | 0.07 | 0.65 | 0.075 | 5.9 | 0.25 |
| Chaos Space Marines | +6.7 | 0.095 | 6.2 | 0.40 | 0.52 | 0.03 | 0.66 | 0.124 | 5.7 | 0.29 |
| World Eaters | +5.8 | 0.084 | 6.7 | 0.34 | 0.61 | 0.03 | 0.30 | 0.082 | 6.9 | 0.30 |
| Adeptus Mechanicus | +5.6 | 0.089 | 5.8 | 0.20 | 0.83 | 0.00 | 0.73 | 0.102 | 5.1 | 0.16 |
| Drukhari | +4.1 | 0.086 | 4.9 | 0.00 | 1.00 | 0.00 | 0.33 | 0.088 | 4.7 | 0.00 |
| T'au Empire | +3.7 | 0.100 | 6.7 | 0.17 | 0.38 | 0.00 | 0.59 | 0.097 | 6.9 | 0.24 |
| Necrons | +3.7 | 0.097 | 6.2 | 0.17 | 0.48 | 0.08 | 0.34 | 0.110 | 5.3 | 0.00 |
| Grey Knights | +2.8 | 0.069 | 7.1 | 0.13 | 0.57 | 0.02 | 0.78 | 0.074 | 7.6 | 0.10 |
| Tyranids | −0.3 | 0.110 | 5.3 | 0.43 | 0.23 | 0.00 | 0.28 | 0.116 | 4.8 | 0.32 |
| Thousand Sons | −0.6 | 0.082 | 5.1 | 0.16 | 1.00 | 0.15 | 0.37 | 0.087 | 4.9 | 0.11 |
| Chaos Daemons | −2.8 | 0.086 | 7.1 | 0.46 | 1.00 | 0.07 | 0.38 | 0.091 | 6.6 | 0.36 |
| Adeptus Astartes | −4.2 | 0.090 | 6.4 | 0.21 | 0.09 | 0.00 | 0.31 | 0.092 | 6.1 | 0.17 |
| Genestealer Cults | −5.5 | 0.090 | 5.1 | 0.10 | 0.25 | 0.18 | 0.49 | 0.094 | 5.1 | 0.08 |
| Emperor's Children | −6.6 | 0.082 | 6.4 | 0.26 | 0.49 | 0.09 | 0.36 | 0.088 | 6.3 | 0.21 |
| Orks | −8.2 | 0.108 | 5.5 | 0.00 | 0.44 | 0.00 | 0.30 | 0.110 | 5.6 | 0.00 |
| Astra Militarum | −11.9 | 0.088 | 7.3 | 0.50 | 0.11 | 0.00 | 0.72 | 0.103 | 6.2 | 0.35 |

Poles are the sc52a field-weighted (position-A, opponent-game-count-weighted)
reconstruction from `data/_anchor_sc52a_n80_log.json` plus the live Warp Friends
real win rates — the exact aggregation `evaluate_vs_meta.run_matrix` uses. The
reconstruction reproduces the brief's stated poles closely (Death Guard +22.2 vs
+22.5, Orks −8.2 vs −8.7, Astra Militarum −11.9 vs −12.4 essentially exact; six
minor same-sign residuals consistent with a slightly higher-N headline anchor).

## The correlation (the number)

Pearson r / Spearman rho between each metric and the pole, N = 22, for the full
army and separately for the seed and fill slices:

| metric | FULL r | FULL rho | SEED r | FILL r |
|---|---:|---:|---:|---:|
| wounds per point | **−0.49** | −0.47 | −0.41 | −0.45 |
| wounds-weighted Toughness | +0.39 | +0.29 | +0.25 | +0.43 |
| **durable-brick point share** | **+0.23** | +0.21 | +0.06 | +0.30 |
| invulnerable coverage | **+0.52** | +0.49 | +0.52 | +0.49 |
| feel-no-pain coverage | +0.16 | −0.16 | +0.12 | +0.12 |

Bucket means (over-pole ≥ +6, under-pole ≤ −6, mid otherwise):

| bucket | n | wpp | wtT | brick | inv | fnp |
|---|---:|---:|---:|---:|---:|---:|
| OVER | 8 | 0.076 | 7.2 | 0.33 | 0.77 | 0.07 |
| MID | 11 | 0.089 | 6.0 | 0.22 | 0.58 | 0.05 |
| UNDER | 3 | 0.093 | 6.4 | 0.25 | 0.35 | 0.03 |

Read the brick-share column: OVER 0.33, MID 0.22, **UNDER 0.25** — non-monotone.
Durable-brick provisioning does not separate the poles. The over-poles do carry
somewhat more brick share on average, but the effect is weak, statistically
insignificant, and dominated by the two Knight factions (whose brick share is
faithful to reality — see below); strip the two Knights and the over-pole brick
mean collapses to ~0.24, indistinguishable from mid and under.

The decisive comparison is **seed versus fill**. If the fill were the structural
lever, the fill's durability would correlate with the pole *more strongly* than the
seed's. It does not: the strongest correlate (invulnerable coverage) is identical
in seed and fill (0.52 vs 0.49); the others are within noise. The fill does not
introduce a durability skew beyond what the curated seed already carries — because
under the default template-first fill it draws from the same curated template pool
the seed does.

## The fill's realism

Fill composition (mean point-share of the fill slice) for factions spanning the poles:

* **Death Guard (durable over-pole).** Fill is ~flat across the whole template:
  Myphitic Blight-hauler 15.8%, Deathshroud 15.5%, Plagueburst Crawler 14.5%,
  Bloat-drone 12.5%, Daemon Prince 10.0%, Plague Marines 9.7%, Poxwalkers 9.6%,
  Lord of Contagion 9.2%. The fill's brick share (0.24) is **less than the seed's**
  (0.52) — the seed carries the bricks (Mortarion, Plagueburst Crawlers), the fill
  dilutes toward chaff. The fill does not over-provision durability here.
* **Imperial Knights (brick over-pole).** Fill is 85% bricks — but the *entire*
  template pool is big Knights (Toughness 11-12, 26-28 wounds) plus three Armiger
  types. Uniform-within-pool necessarily returns big Knights. This is **faithful**:
  real Imperial Knight lists genuinely are three-to-five big Knights plus Armigers.
  The over-pole is not a fill-durability artifact; it is the kill economy over-valuing
  Knight survivability (the primary-economy story), not the fill selecting unrealistic
  units.
* **Aeldari (fragile over-pole).** Fill is entirely Toughness-3 one-wound Aspect
  Warriors (Howling Banshees 18.6%, Fire Dragons 13.8%, Dark Reapers 13.8%, ...).
  Zero bricks. A +15 over-pole on the most fragile fill in the game.
* **Astra Militarum (under-pole).** Fill is 36% armour by points (Rogal Dorn,
  Manticore, Leman Russ, Basilisk). The most tank-heavy fill of any non-Knight
  faction — on the biggest under-pole.
* **Orks (horde under-pole).** Fill is Toughness-5/6 multi-wound-but-cheap infantry
  and light walkers (Nobz, Meganobz, Deffkoptas, Killa Kans); zero bricks.

The fill's one genuine unrealism is its **shape**: the uniform-within-template-pool
draw produces a roughly *flat* point-distribution across template entries (every
Death Guard entry lands ~10-16% of the fill), whereas a real list is curated to a
role curve — two battleline squads, one-or-two objective holders, two-or-three
threats, points concentrated on the threats. But this flattening is **symmetric**:
it applies identically to durable and fragile factions, and where it deviates from
the seed it skews toward *cheaper, higher-wounds-per-point chaff* (Chaos Space
Marines fill wpp 0.124 vs seed's lower value; Necrons 0.110; Astra Militarum 0.103;
Tyranids 0.116) because affordability plus a uniform draw over the many cheap
template entries favours chaff. That is the **opposite** of the hypothesized
"over-selects the most durable / expensive units." The `SWEG_FILL_TEMPLATE_POOL`
gate has already closed the older whole-catalogue leak (Chaos Predators / Land
Raiders / Heldrakes reaching production armies); the residual non-template tail is
now under ~2% per unit and appears only when no template unit is affordable.

## Why the hypothesis fails structurally

The hypothesis requires: durable factions' rosters are mostly durable, so a
template-pool-filtered random fill over-selects bricks. Under the current default
mechanism this does not operate, for two reasons:

1. The fill is **template-gated**, not roster-gated. It draws from the curated
   template, and the templates already include each faction's chaff (Death Guard's
   Poxwalkers and Plague Marines, Astra Militarum's Cadian infantry). So a durable
   faction whose template is mixed gets a mixed fill that is *less* durable than the
   seed. Only a faction whose template is intrinsically all-brick (the two Knight
   armies) gets an all-brick fill — and that is faithful to reality.
2. Durability-per-point is **not the reward axis**. The kill/scoring economy rewards
   low model count and survivor uptime (wounds-per-point r = −0.49: fewer, pricier
   models score better), which is orthogonal to raw armour provisioning. Aeldari
   proves a fragile low-model army over-poles; Astra Militarum proves an armour-heavy
   army under-poles. Toughness-10 tanks do not help a faction whose problem is that
   the economy over-pays elite single-model uptime.

This confirms and quantifies the qualitative verdict already recorded in
`docs/ARCHETYPE_FIDELITY_AUDIT.md` (2026-07-01): "there is no distinct structural
durability over-reward mechanism … the durable-share axis itself does not
discriminate" (its Death Guard and Astra Militarum counter-cases). This audit
extends that from three hand-picked counter-cases to a full-22 correlation.

## Handoff

The poles are **per-faction list divergences on a primary/kill economy that
over-pays low-model survivor uptime**, not a single fill-mechanism durability lever.
There is no one durability-dial fix. Hand the residuals to the vertical audits:

* The over-poles that are genuinely list-shaped go to per-faction template work
  (the Death Guard vertical audit companion; the World Eaters / Emperor's Children /
  Knight-chassis curation already staged in `docs/ARCHETYPE_FIDELITY_AUDIT.md`).
* The over-poles that are economy-shaped (Aeldari, Imperial Knights, Custodes — low
  model count, faithful lists) are **not** list-fixable downward without breaking
  fidelity; they belong to the primary/kill-economy survivor-uptime surface the
  brief's preamble names, not to list fidelity.
* The under-poles (Astra Militarum, Orks) are likewise economy-shaped: armour and
  wounds are present in the sim lists; the economy does not pay for horde bodies.

The one build-mechanism refinement that is real but **not a durability lever** is the
fill's flat point-distribution versus a real role curve. Correcting it toward a
role-shaped draw would change *which* units fill (fewer threats, more battleline /
objective-holders), which is a faithful, citable direction — but the audit shows it
would move durable and fragile factions symmetrically and so would not, on its own,
deflate the durable over-poles or lift the horde under-poles together. It is a
fidelity improvement, not the pole lever.

## Reproduction

Scratch scripts (this branch only, prefix `_fill_audit_`):

* `scripts/_fill_audit_poles.py` — reconstructs the sc52a field-weighted pole vector
  from the anchor log and validates against the brief.
* `scripts/_fill_audit_census.py` — samples 45 archetype builds per faction at 2000
  points via the real `build_archetype_army`, splits seed versus fill with a wrapper
  on `_random_fill`, and writes the durability-per-point vectors.
* `scripts/_fill_audit_correlate.py` — the correlation table and bucket means.
* `scripts/_fill_audit_composition.py` — the fill-composition realism tally.

Run with `PYTHONIOENCODING=utf-8 PYTHONHASHSEED=0 python -m scripts._fill_audit_census`
then `... _fill_audit_correlate`. No tracked source files are modified.
