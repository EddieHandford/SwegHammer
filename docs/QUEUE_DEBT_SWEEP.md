# Queue-debt sweep — previously queued, never executed (wave 234, user-requested 2026-06-11)

Companion to `STRUCTURAL_DEBT_REVIEW.md`. Two read-only agents swept every place work gets
queued — the loop question log and memory layer (this half, COMPLETE) and the documentation
layer (second half, pending). Classification: NEVER-EXECUTED / STILL-BLOCKED (precondition
named, with whether it has since been met) / EXECUTED (commit cited, appendix in the agent
transcript). Residual figures quoted from the frames in which items were queued; the live
frame is `CURRENT_STATE.md`.

## Half 1 — question log + memory layer — COMPLETE

### Unblocked or open debt, ranked

| # | Item | Queued at | Status | Effort | Notes |
|---|------|----------|--------|--------|-------|
| 1 | Displacement substrate Stage 1 (fall-back-only-when-wasted) | wave 233 greenlight | NEVER-EXECUTED (Stage 0 instrument landed `c33d8ab`) | multi-wave | Already the active build plan — confirms, not new. |
| 2 | **Farseer "Branching Fates" proxy replacement** — always-on re-roll-wound-1s aura vs real once-per-phase set-one-roll-to-6 | wave 214, re-queued 215/216 as "unblocked by task 92" | **STILL-BLOCKED → PRECONDITION MET** (task 92's phase-conditional schema hook landed `febc8ae`) — never executed | single-fix | Converges with structural review surface 2 (Aeldari over-pole). Top overnight candidate. |
| 3 | **Fight-alternation re-test on the current frame** (`SWEG_FIGHTALT=1`) | wave 231 fresh-eyes T3.3 | **EXECUTED wave 245 — REJECTED decisively** (variant (b) round-scoped: gated 6.77 → 7.96 paired N=40, melee cluster all wrong-direction). Both variants now measured rejections; gate + code path DELETED at wave-245 close. Do not re-litigate without a frame change touching melee frequency itself. | done | See `docs/DECISION_LEDGER.md`. |
| 4 | Character-ability sweep continuation: Adeptus Mechanicus → Tyranids → Chaos Knights → Daemons | wave 231 (Sororitas leg landed `cde26de`) | NEVER-EXECUTED | 4 × single-fix | |
| 5 | Sororitas Bringers of Flame detachment rule | wave 231 T2.7 | NEVER-EXECUTED (Hallowed Martyrs half landed wave 234 `31ba197`) | single-fix | Under-pole −16.5. Natural sequel to Blood of Martyrs. |
| 6 | Chaos Space Marines Pactbound Zealots detachment rule (no-op shell) | wave 231 T2.8 | NEVER-EXECUTED | single-fix | Under-pole −17.0. |
| 7 | First Rank Fire! Second Rank Fire! upgrade from +1-to-hit proxy to real rapid-fire extra attacks | wave 231 T2.6 | NEVER-EXECUTED | single-fix | Converges with structural review surfaces 1+3. Astra Militarum under-pole. |
| 8 | Emperor's Children: runs with no army rule / detachment / stratagems — verify then build | wave 231 T4.11 | NEVER-EXECUTED | single-fix | Was +15.2 over on the wave-228 frame. |
| 9 | **Chaos Lord fabricated +1-to-wound removal + host-routing completion** | waves 213-216, "provably metric-neutral, cheap" | NEVER-EXECUTED | data-edit | Wave-214 question-log verification + structural review surface 2 = two sources; cleared to fix. |
| 10 | Voluntary tactical-card discard (real Chapter Approved play cycles dead cards) | wave 231 T3.10 | NEVER-EXECUTED | single-fix (verify + cite first) | |
| 11 | Core universal stratagems absent: Grenade, Rapid Ingress, Smokescreen | wave 231 T4.13 + core-rules audit P2 | NEVER-EXECUTED | 3 × single-fix | |
| 12 | Enhancements expansion (19/22 factions get zero) | wave 231 T4.14 | NEVER-EXECUTED | multi-wave cumulative | |
| 13 | Warp Friends target-data refresh (`scripts/scrape_warpfriends`) | "re-run periodically"; last scrape ≈ wave 145 (~6 weeks stale) | NEVER-EXECUTED | one command — **BUT frame-changing**: refreshing the target re-bases every anchor and the headline scale. Decide deliberately at a clean wave boundary; logged to the question log, not auto-run. | |
| 14 | Mapper `extract_fnp` prose-walk structural fix (root cause; overrides only bypassed it) | "iter 31-45 mapper phase" — that window has passed | STILL-BLOCKED → arguably unblocked | single-fix + parsed.json regen | Converges with structural review surface 5 pattern 1 (85 unvalidated feel-no-pain units). |
| 15 | Reserves cleanup batch: embarked-passenger reserve-cap accounting (wave 223); reserves round off-by-one `strategy.py:2902` (rule says destroyed end of round 3); stale `cult_ambush_pending` on cap-promoted units (wave 224); Punisher gatling override (wave 229); stale default-OFF comment `simulator.py:7237` (wave 225) | various | NEVER-EXECUTED ×5 | one Haiku-tier hygiene batch | Mostly metric-neutral fidelity/hygiene; batch into one commit. |
| 16 | Multi-metric fidelity review (all-faction turn-by-turn victory points / kills vs real data) | user directive, post-secondary-rebuild (precondition met wave 92) | PARTIALLY EXECUTED (per-faction instruments only) | multi-wave | The signatures harness (wave 234) is the seed of exactly this — fold together. |
| 17 | Wyvern/Griffon `ex_swap` keyword path in `units.py` ~1649-1686 | wave 231 T1.1 | POSSIBLY EXECUTED (mapper layer fixed `dc4f63c`+`8e8a060`; units.py path unconfirmed) | verification only | Verify before marking done. |

### Still blocked (precondition genuinely not met)

- **Stream A held branch** (`held/stream-a-ai-oc-fidelity`, 2 unmerged commits) — waiting on
  worklist #10 which never landed; the branch is a zombie. Audit and explicitly retire or
  integrate at a wave boundary.
- **Per-model loadouts Stage 5** + `SWEG_PERMODEL`/`SWEG_ROLLDMG` default flip — waiting on
  the post-Stage-1 re-calibration pass. (Note: structural review surface 5 pattern 3 says
  rolling damage was user-approved in the core-rules audit; the approval was for the
  mechanism, the default flip remains gated on re-calibration. Both readings recorded.)
- **Detachment variety expansion** (Hypercrypt, Stormlance/Ironstorm/Anvil, Crusher, Devout
  Pursuit, Solar Spearhead, Wych Cult, Renegade/Soulforged) — backlog, no gate, never
  dispatched.

## Half 2 — documentation layer — COMPLETE

Second read-only agent swept `CURRENT_STATE.md`, `AUTO_LOOP_LOG*.md`, `DECISION_LEDGER.md`,
`STRUCTURAL_DEBT_REVIEW.md`, `FIDELITY_REVISIT_WORKLIST.md`, `DISPLACEMENT_SUBSTRATE_PLAN.md`,
`RESEARCH_HARVEST_WAVE234.md` and cross-checked every queued sentence against `git log`.
Full per-item execution checks (grep patterns, commit refutations) are in the agent transcript;
this is the ranked actionable table. Items that duplicate Half 1 rows are marked (=H1#n).

| ID | Item | Class | Effort | Residual touched |
|----|------|--------|--------|------------------|
| NE-1 | Leman Russ Punisher picker-bias override (=H1#15) | NEVER-EXECUTED | data-edit | Astra Militarum −16.5 |
| NE-2 | First Rank Fire! attack-count proxy (wrong stat: +1-to-hit vs +1 attack on rapid fire) (=H1#7) | NEVER-EXECUTED | single-fix | Astra Militarum −16.5 |
| NE-3 | Hallowed Martyrs stratagems — Spirit of the Martyr + Righteous Vengeance (substrate-independent two) | NEVER-EXECUTED | 2 × single-fix | Sororitas −16.5 |
| NE-4 | Genestealer resurgence revival-count instrument (precondition for any build) | NEVER-EXECUTED | diagnostic script | Genestealer +13.1 |
| NE-5 | Five leader fabrications: Overlord/Trazyn `plus_one_to_hit`, Chronomancer/Plasmancer `fnp=5`, Chaos Lord `plus_one_to_wound` (=H1#9 for the Lord) | NEVER-EXECUTED | single-fix each | Necrons +12.8 / Chaos Space Marines −17.0 |
| NE-6 | Protocol of the Conquering Tyrant: full re-roll → re-roll-1s within half range | NEVER-EXECUTED | single-fix | Necrons +12.8 |
| NE-7 | Reanimation Protocols: 1 model/round → D3 wounds/unit/Command phase | NEVER-EXECUTED | single-fix | Necrons +12.8 (SUPPRESSIVE — raises) |
| NE-8 | Warhost Martial Grace: +1 token total → +1 per battle round | NEVER-EXECUTED | single-fix | Aeldari +11.0 (SUPPRESSIVE — raises) |
| NE-9 | Voice of Command: Lord Solar should issue 2–3 orders, capped at 1 | NEVER-EXECUTED | single-fix | Astra Militarum −16.5 |
| NE-10 | Leagues of Votann: dead Eye-of-Ancestors token machinery + Prioritised Efficiency wholly absent | NEVER-EXECUTED | multi-fix | off-pole |
| NE-11 | Teleport Strike Force re-rolls always-on vs deep-strike-turn-only ("Fury of Titan") | NEVER-EXECUTED | single-fix | Grey Knights (over) |
| NE-12 | Pulse Onslaught wrong-direction proxy → drop the false buff | NEVER-EXECUTED | single-fix | T'au (wrong-direction) |
| NE-13 | Adaptive Strategy: dispatcher still burns 1 command point with zero effect post-SC5-9 | NEVER-EXECUTED | single-fix | Astartes masking |
| NE-14 | Desecration of Worlds: command points spent, sticky-objective write never lands | NEVER-EXECUTED | single-fix | Thousand Sons |
| NE-15 | Plaguesurge: flag set, contagion range stays hard-coded 6" | NEVER-EXECUTED | single-fix | Death Guard (off-pole) |
| NE-16 | `AWAKENED_DYNASTY.bonus_to_hit_when_led` citation filing gap | NEVER-EXECUTED | data-edit (5 min) | audit hygiene |
| NE-18 | `cult_ambush_pending` stale-flag clear (=H1#15 batch) | NEVER-EXECUTED | 1-line | none (inert) |
| NE-19 | Move-AI Objective-Control view: `strategy.py:326-339`/`:2186` use raw `profile.oc`, scorer uses bracket+battleshock effective — planner blind to its own scoring rules | NEVER-EXECUTED | single-fix (3 hunks) | cross-faction AI quality |
| SB-1 | Displacement Stages 1–4 | STILL-BLOCKED (Stage 0 adjudication pending — instrument built `c33d8ab`, run+verdict missing) | multi-wave | both poles |
| SB-2 | Re-task to claim empty markers | STILL-BLOCKED (Stage 1+) | single-fix | cross-faction |
| SB-3 | Mobility-mechanic erasure class (Tellyporta, Webway Tunnel, Squad Tactics, Da Biggest Boss, Skyborne Sanctuary) | STILL-BLOCKED (displacement substrate) | multi-wave | Orks/Aeldari |
| SB-4 | Aeldari archetype → Aspect Host / Corsair Coterie (+ honest-price template re-derive after `d66ca44`) | STILL-BLOCKED (list grounding) | data-edit | Aeldari +11.0 |
| SB-5 | Astra Militarum archetype → Grizzled Company | STILL-BLOCKED (list grounding) | data-edit | Astra Militarum −16.5 |
| SB-6 | Waaagh! 5+ invulnerable vs melee leg | NEVER-EXECUTED (counter-evidence, faithful-first applies) | single-fix | Orks +11.3 (SUPPRESSIVE) |
| NE-17 | `SWEG_OBJ_HOME` home-marker re-flip | STILL-BLOCKED (home-contesting AI = displacement Stages 1–2) | re-test only | under-pole |

## Ed's issue triage (2026-06-11, user-directed downtime work)

All 23 open issues reviewed individually, code-state verified by two read-only audit agents,
and commented on GitHub the conventional way. Dispositions:

- **Closed**: #40 renderer crash — fixed on main by Ed's own `693751a`; verified ancestor of origin/main.
- **Close via pull request 66 closing keywords** (fixed on this branch; ADD `Fixes #43, #50, #54, #60, #62`
  to the pull request body at the pending rewrite): #43 Oath of Moment + Combat Doctrines (live, faithful,
  hits-only `d1a7c1f`), #50 deepstrike artificial-intelligence overhaul (all three asks, `b18c80c`),
  #54 base sizes (keyword-family granularity end-to-end), #60 melee fallback (mapper has it; zero
  melee-only disabled units), #62 Wraithguard/Wraithblades (min_models=5 in parsed.json; points fixed
  `c084ba0`+`d66ca44`).
- **Re-scoped, kept open**: #61 → pooled-health remnants in ancillary paths (`simulator.py:9033,
  11209-11223, 12638-12640` — model-count math wrong for per-model Unit instances; hygiene backlog);
  #44 → Battle Focus implemented, remaining = Martial Grace per-round grant (=NE-8) + non-vehicle
  spend-scope re-verify; #52 → body collision + path-cap + pathfinding live by default, terrain-wall
  tunnelling remains (tagged to displacement substrate; do not close until walls block movement).
- **Framing updates posted** (retry-after-rebalance premises superseded by the 2026-06-02
  printed-points ruling): #43, #44, #45 (Drukhari mapper re-assess as straight data fidelity — re-queued),
  #47 (bisection loop is a Stage 2 instrument now, not a Stage 1 absorber).
- **Holds confirmed**: #46 (Bearer token, Eddie), #48 (Stage 1 convergence), #49 (Stage 2 anchor set),
  #51 (transports after displacement + calibration pass).
- **Feature requests parked** with notes: #55 diagnostics tab (flagged first pick for a quiet window),
  #56 Pygame renderer, #57 per-unit cover user interface, #58 army builder, #59 calibration browser.
- **Documentation**: #63 standing task acknowledged; #53 BASELINE.md catalogue table regeneration
  QUEUED for the wave-close documentation sweep (date-stamp it).

New queue entries from triage: #61 remnant (hygiene batch), #53 regeneration (wave close),
#44 scope re-verify, Drukhari mapper re-assessment (#45). Also noted: origin/main moved — pull
request 67 merged (5 archetype units replaced after the no-canonical-points purge); a merge from
main is a FRAME-CHANGING event, decide at a wave boundary alongside the Warp Friends refresh.

## Wahapedia resolutions (2026-06-11, live fetch, two confirmations each)

- **`ANNIHILATION_LEGION.reroll_wound_ones` = FABRICATION confirmed** (resolves the surface 1 vs 2
  conflict in STRUCTURAL_DEBT_REVIEW.md — surface 1 was right). No rule named "Hardened Killers"
  exists; the inline notes at `code/detachments.py:1529-1543` carry a FABRICATED verbatim quote.
  Real detachment rule is **"Annihilation Protocol"**: (1) DESTROYER CULT or FLAYED ONES units
  re-roll Charge rolls, +1 to the Charge roll as well if a target is Below Half-strength;
  (2) DESTROYER CULT ranged attacks against the closest eligible target get +1 Armour Penetration.
  Source: https://wahapedia.ru/wh40k10ed/factions/necrons/ (#Annihilation-Legion). Fix dispatched.
- **Battle Focus token cadence WRONG in sim**: real rule grants tokens **at the start of each
  battle round** by battle size (Incursion 2 / Strike Force 4 / Onslaught 6); sim grants 4 once at
  battle start, so the pool goes dark rounds 3–5. **Martial Grace = +1 token per battle round**
  (confirms NE-8), plus two unmodelled legs (+1" on Swift as the Wind; +1 to D6-rolling manoeuvres).
  Five non-vehicle manoeuvres entirely unimplemented: Swift as the Wind (+2" Move), Flitting
  Shadows (Fire Overwatch denial), Sudden Strike (6" pile-in/consolidate), Opportunity Seized and
  Fade Back (reactive D6+1" Normal moves — tag the reactive pair to the displacement substrate).
  All SUPPRESSIVE direction vs Aeldari +11.0 (faithful-first applies). Source:
  https://wahapedia.ru/wh40k10ed/factions/aeldari/ (#Warhost for Martial Grace). Cadence fix dispatched;
  manoeuvre builds queued.

Notable EXECUTED confirmations (audit trail): all six FIDELITY_REVISIT items 1–6 default-ON
(wave 210); `SWEG_CSM_ABILITIES` ON (`a5c1239`); paired/CRN tooling (wave 218); `--factions`
scoping (`a51a6de`); deployment-AI + reserves cap (`2b5977a`); Blood of Martyrs (`31ba197`);
Awakened Dynasty passive removal + Doctrina gate (`e4b51d3`); pricing audit (`d66ca44`).
Void Hardened's no-op-with-spend is DELIBERATE (docstring labels it) — distinct from
Adaptive Strategy's inadvertent spend; do not batch them identically.
