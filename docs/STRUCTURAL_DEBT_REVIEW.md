# Structural-debt review — early-era approximation and proxy sweep (wave 234, user-requested 2026-06-11)

Five parallel read-only audit agents swept the surfaces where the early calibration era
(sim-calibration-1 through 5) skipped or approximated rules. Shared rubric: FABRICATION
(rule does not exist or invented shape) / PROXY (real rule, wrong conditioning, magnitude,
or scope) / DEFENSIBLE (immaterial divergence with rationale), plus DEAD / STALE-COMMENT /
STRUCTURAL / LIVE-APPROXIMATION per-surface classes. Cross-check rule: at least two sources
before any fabrication claim; orchestrator re-verifies the highest-stakes claims before any
fix dispatch. Known debt (one-Unit-per-model, conditional invulnerable saves task 92,
feel-no-pain prose-walk, anti-tank picker, the fixed Necrons passives / Adeptus Mechanicus
Doctrina gate / pricing entries, Blood of Martyrs, queued game-shape findings) was excluded
from scope by briefing.

Residual frame for ranking (wave 233 anchor, now superseded by the wave 234 re-anchor):
UNDER Chaos Space Marines −17.0 / Astra Militarum −16.5 / Adepta Sororitas −16.5;
OVER Imperial Knights +15.9 / Adeptus Mechanicus +14.6 / Genestealer Cults +13.1 /
Necrons +12.8 / Orks +11.3 / Aeldari +11.0.

**Fixes are NOT dispatched from this document directly.** Items graduate to the harvest
queue (`RESEARCH_HARVEST_WAVE234.md`) or `CURRENT_STATE.md` levers after orchestrator
cross-verification, and land in subsequent waves batched with re-anchors where frame-changing.

---

## Surface 4 — simulator core (`code/simulator.py`, `code/units.py`, `code/strategy.py`) — COMPLETE

Agent verdict: 15 live approximations, 9 structural representation choices, ~7 stale
comments (none masking a re-introduced bug). Line anchors at production head `d66ca44`.

### Live approximations, agent-ranked

| # | Item | Anchor | Divergence | Residual relevance | Orchestrator note |
|---|------|--------|------------|--------------------|--------------------|
| 1 | Fight-phase one-sided resolution | `simulator.py:9738` | Default path gives only the active player a fight pass; real 10e alternates fights so a charged defender swings back in the same phase. `SWEG_FIGHTALT=1` implements alternation but is default-off. | OVER melee aggressors (Orks, World Eaters), UNDER high-damage defenders (Adeptus Custodes, Chaos Space Marines) | **Prior A/B exists** — waves 166/168 (`wf_wave166_fightalt_a_n40.txt`, `wf_wave168_fightalt_corrected_n40.txt`). Check the loop-log archive verdict before re-litigating. |
| 2 | Dark Pacts proxied as flat +1 to hit / +1 to wound | `simulator.py:9188`, `units.py:9191` | Real rule grants Lethal Hits or Sustained Hits 1 (natural-6 mechanics); the proxy fires on every attack. | UNDER/OVER Chaos Space Marines depending on weapon volume | Matches the ledger: wave-209 naive expansion was net-negative and reverted; only revisit with true Lethal/Sustained flags (the watchdog one-shot built these — verify what landed). |
| 3 | Waaagh! two legs unmodelled (army-wide 5+ invulnerable vs melee; Advance-then-Normal-Move) | `units.py:2384` | Only +1 to wound melee and +1 to charge modelled. | UNDER Orks on Waaagh turns — **suppressive vs the Orks +11.3 OVER residual** | Already recorded as counter-evidence in the harvest; building it is faithful and expected to RAISE Orks. Faithful-first policy applies. |
| 4 | Shadow of Chaos zone proxied as 18-inch radius from board centre | `simulator.py:8587`, `:8633` | Misses unconditional deployment-zone coverage and dynamic No-Man's-Land expansion. | UNDER Chaos Daemons | Daemons currently IN BAND (wave 233); wave-88 Daemonic Manifestation A/B was metric-neutral. Low priority until Daemons leave band. |
| 5 | Battle Focus: 5 of 6 Agile Manoeuvres unmodelled; flat token pool | `simulator.py:867` | Only the shoot-after-Advance spend exists; Lightning-Fast Reactions, Feigned Retreat, Celestial Shield, Battle Sight, Wraithwalk absent; pool not per-round. | UNDER Aeldari — **suppressive vs Aeldari +11.0 OVER** | Interacts with the Aeldari list-grounding lever (archetype designed on tainted prices). |
| 6 | Genestealer Cults resurgence: flat one-per-round revival, no marker/delay/cost-table | `simulator.py:9415`, `:7103` | Real rule places on a marker, arrives next turn, per-unit cost 2–8. | Mixed for Genestealer Cults (+13.1 OVER): no-delay revival over-rates durability; one-per-round cap under-rates chains | Candidate for the over-pole; needs an instrument readout (revival counts per game) before any build. |
| 7 | Contagions of Nurgle: index-era three-round escalation, codex replaced it with per-unit selectable auras | `units.py:134` | Round-3+ army-wide −1 to hit likely stronger than codex per-unit choice. | OVER Death Guard | Death Guard not on either pole — bank until it surfaces. |
| 8 | Born Soldiers REGIMENT/SQUADRON proxied by BATTLELINE/name-allowlist | `units.py:3249` | BSData carries no REGIMENT/SQUADRON keywords; ~5–10 REGIMENT datasheets miss Lethal Hits. | UNDER Astra Militarum (−16.5) | Under-pole relevant; bounded magnitude. Pairs with the Grizzled Company detachment-mismatch lever (real meta runs a different detachment entirely). |
| 9 | Leagues of Votann: retired Eye of the Ancestors token machinery still runs as a silent no-op; real Prioritised Efficiency wholly absent | `simulator.py:12319`, `units.py:2953` | Token bookkeeping with no consumer; objective-economy army rule unimplemented. | Leagues of Votann effectively have NO army rule | Dead-code cleanup + missing-rule build are separable; faction not on a pole. |
| 10 | Protocol of the Conquering Tyrant: re-roll 1s proxied as full re-roll, half-range gate dropped | `simulator.py:4644` | Full re-roll ≈ +0.5 expected uplift vs +0.17 for re-roll 1s (unled). | **OVER Necrons (+12.8)** — systematic per-activation inflation | Live over-pole contributor with a clear conservative fix. Strong candidate. |
| 11 | Code Chivalric: re-roll-one-of-choice mapped to re-roll natural 1s | `units.py:3028` | Under-values the choice re-roll (~+0.17 vs ~+0.5). | UNDER Imperial Knights — suppressive vs +15.9 OVER | Intentional conservative choice at wave 71; leave unless Imperial Knights drop below target after displacement lands. |
| 12 | Eye of the Gods table collapsed to permanent +1-to-wound-melee snowball | `simulator.py:11838` | Real table has six distinct results including Toughness and Move. | Modest, Chaos Space Marines | Fires at most once per character per battle; low priority. |
| 13 | Combat Drugs: Splintermind and Serpentin variants unmodelled | `units.py:1002` | Four of six drugs modelled. | UNDER Drukhari | Drukhari not on a pole; bank. |
| 14 | Pulse Onslaught: enemy movement debuff re-routed as +1 to hit for the firing unit | `simulator.py:4489` | **Proxy points the WRONG DIRECTION** — an offensive buff replacing mobility denial. | OVER T'au Empire | Wrong-direction proxies are the worst class; fix is cheap (drop the false buff even if the debuff stays unmodelled). |
| 15 | Transport first-pass: fixed capacity 12, no mid-game embark, Firing Deck uses passenger ballistic skill | `simulator.py:12458`, `:12733` | Capacity wrong for Land Raiders (10) / Wave Serpents (6) etc. | Mixed across transport-heavy factions | Structural-leaning; batch with displacement-era movement work. |

### Structural representation choices (recorded, not deep-dived)

Alternating-activation round structure; fight-phase active-only loop (distinct from item 1);
deterministic midline deployment without zones/infiltrate/scout pre-game; one-Unit-per-model
(known); single transport capacity constant; Doctrina picker heuristic vs free per-command-phase
declaration; no reserves variety beyond Deep Strike / Scout / Cult Ambush; no pre-game psychic
actions; objective control as a summed-points contest without geometric model spread.

### Stale comments

~7 comments keep an APPROXIMATION label where the fix already landed (re-roll consumers
removed, the infantry-wide Doctrina over-grant narrowed). None mask a re-introduced bug.
Cleanup is cosmetic — batch into a docs/comments pass, no eval needed.

---

## Surface 1 — approximation-tagged citations (`data/rule_citations.d/`, 113 entries) — COMPLETE

Agent verdict: 1 fabrication candidate, 3 dead entries, ~22 high-material proxies,
12 stratagem no-ops (overlaps surface 3), ~57 active lossy stratagem proxies, 5 defensible.

### Headline findings

| Item | Class | Evidence | Residual relevance |
|---|---|---|---|
| `ANNIHILATION_LEGION.reroll_wound_ones` | FABRICATION **CONFIRMED + FIXED** (2026-06-11, live Wahapedia; worktree commit `a82c029`) — fabricated inline quote removed, real "Annihilation Protocol" documented unmodelled | "Hardened Killers" does not exist on Wahapedia; the real rule is a charge re-roll + closest-target Armour Penetration buff, neither wireable with existing machinery. | OVER Necrons | 
| `simulator.penumbral_puppetry_approx` | DEAD — data never wired | `stealth=False` on all 12 named Tzeentch units in both parsed.json and overrides.json; the code gate exists but never fires. | UNDER Chaos Daemons (in band — bank) |
| `WARHOST.martial_grace` | **FIXED** (2026-06-11, worktree commit `10bda6a`) — whole Battle Focus cadence corrected: per-battle-round additive grant scaled by battle size (Incursion 2 / Strike Force 4 / Onslaught 6; evaluation runs 2000-point Strike Force), Martial Grace +1 per round | Real rule grants tokens **at the start of each battle round**; sim granted a flat 4 once at battle start, Martial Grace +1 once. Two Martial Grace legs (Swift as the Wind +1", Agile Manoeuvres die bonus) remain unmodelled, documented in the citation. | Aeldari capability increase — faithful-first, kept regardless of +11.0 OVER direction |
| `TELEPORT_STRIKE_FORCE.reroll_*` | PROXY always-on vs deep-strike-turn-only | BSData "Fury of Titan" verbatim confirms turn-of-arrival scope. Converges with surface 2. | OVER Grey Knights |
| `AWAKENED_DYNASTY.reanimate_per_round` + `simulator.reanimation_protocols` | PROXY under-firing | Real rule: D3 wounds per unit per command phase (median ≈2); sim: 1 model per round, end-of-round timing. | UNDER Necrons — suppressive vs +12.8 OVER |
| `simulator.voice_of_command_orders` | PROXY — all officers capped at 1 order | Lord Solar issues 2–3 orders per round in the codex. | UNDER Astra Militarum (−16.5) |
| `Order.First Rank, Fire! Second Rank, Fire!` | PROXY wrong mechanism | +1 attack on rapid-fire weapons proxied as +1 to hit; on big lasgun blocks the attack count is stronger. | UNDER Astra Militarum |
| `VALOURSTRIKE_LANCE.bondsman_enabled` | PROXY — strongest of six Bondsman variants applied uniformly | Paladin's Duty (Lethal Hits + Lance) given to all Armigers; Warden's/Crusader's variants weaker. | OVER Imperial Knights (+15.9) |
| `INQUISITION_TASK_FORCE` | Detachment name not in BSData; underlying rule real but scope army-wide and wound half dropped | — | Minor |
| `simulator.contagions_of_nurgle` | PROXY index-era shape | Converges with surface 4 item 7. | OVER Death Guard (off-pole) |

Defensible: `daemonic_manifestation`, `relentless_carnage`, `stratagem_per_command_phase_cap`
(documented AI heuristic, no rule claim), `warlord_designation`, `tactical_secondary_deck`.

## Surface 2 — detachment / leader / enhancement registries — COMPLETE

Agent verdict: **6 active FABRICATIONS** (all in leaders), 18 PROXY, ~30 DEFENSIBLE.
**All fabrication claims require orchestrator cross-verification against the BSData cache
before any fix dispatch** (standing rule: agents over-claim — the Greater Daemons pricing
claim this wave was refuted on direct check).

### Fabrication claims (agent-reported; verification status tracked here)

| Entry | Faction | Flag | Claim | Residual relevance | Verified? |
|---|---|---|---|---|---|
| Necron Overlord "My Will Be Done" | Necrons | `plus_one_to_hit=True` | Real 10e My Will Be Done is a once-per-round stratagem command-point discount, no hit buff — a 9th-edition holdover. Stacks on top of the faithful Awakened Dynasty led-unit +1 to hit, double-buffing led squads. | **OVER Necrons (+12.8)** — every Necron archetype seeds an Overlord | PENDING |
| Trazyn the Infinite | Necrons | `plus_one_to_hit=True` | No citation entry exists; no hit aura on the 10e datasheet (the command-point steal is separately and correctly modelled). | OVER Necrons | PENDING |
| Necron Chronomancer "Chronometron" | Necrons | `fnp=5` | Real Chronometron is a post-shoot 5-inch repositioning move; citation self-labels the feel-no-pain as a wrong-mechanic proxy. | OVER Necrons | PENDING |
| Necron Plasmancer "Harbinger of Destruction" | Necrons | `fnp=5` | Real rule is a 5+ critical-hit threshold on ranged attacks (offensive); proxied as a defensive save. Citation self-labels the mis-bucket. | OVER Necrons | PENDING |
| Chaos Lord "Lord of Hosts" | Chaos Space Marines | `plus_one_to_wound=True` | Real Lord of Chaos is a stratagem command-point discount; citation says "flavour proxy". Near-dormant — host mis-routed to a unit absent from most lists. | UNDER Chaos Space Marines (dormant) | PENDING |
| Grey Knights Grand Master "Tactical Acumen" | Grey Knights | `plus_one_to_wound=True` | Real Warrior Strategist is a stratagem command-point discount. | Minor | PENDING |

Note: four of six are self-labelled proxies in their own citation entries — knowing
wrong-mechanic substitutions from the early era, not undetected inventions. The class is
still removal/re-model: the 2026-06-02 ruling forbids effects the codex does not grant.

### Proxy highlights (direction or scope wrong, residual-relevant)

- **Dark Apostle default path** `reroll_hit_ones` — wrong direction; the faithful
  `plus_one_to_wound_melee_only` is already coded behind `SWEG_CSM_ABILITIES=1`, currently
  default-off. UNDER Chaos Space Marines. **Cheapest under-pole lever in the report: flip a
  gate that already exists** (needs the wave-history check on why it was gated off).
- **Farseer "Runes of Fate" + Yvraine** — always-on re-roll wound 1s vs once-per-phase /
  single-target-fight-phase real rules. Both contribute to Aeldari OVER (+11.0).
- **Teleport Strike Force** (Grey Knights) — deep-strike-turn-only re-rolls made always-on.
- **Lord of Contagion** — +1 to wound proxying melee-only Sustained Hits 1 + Lance.
- **Custodes Shield Host** — one of three Ka'tah stances wired with an odd-round gate the
  codex does not have; net direction ambiguous.
- **Veiled Blade enhancement** — bearer-only +2 attacks granted unit-wide. OVER Custodes.
- 12 further proxies recorded in the agent transcript (Inquisition, Annihilation Legion,
  Subterranean Assault, Chaos Sorcerer, Typhus, Brother-Captain, Kâhl, Warhost martial
  grace, Champion of Humanity, Puretide chip, Bondsman uniform-Paladin, Montka gate).

### Defensible (verified-faithful spot checks)

~30 entries confirmed faithful or immaterial, including Technomancer / Ethereal feel-no-pain
(verbatim), War Horde Sustained Hits (verbatim), All Is Dust, Cursed Legion, Bloodmaster,
Abaddon, Hyperphasic Fulcrum, Phasal Subjugator.

### Filing gap

`AWAKENED_DYNASTY.bonus_to_hit_when_led` is implemented and BSData-grounded but has no
formal entry in `data/rule_citations.d/` — file it (cheap, no behaviour change).

## Surface 3 — stratagems / secondaries / orders — COMPLETE

Agent verdict: **5 command-point-sink fabrications** (command points spent, zero game
effect), 10 documented no-ops (catalogued, no spend — defensible), ~25 live proxies,
~30 defensible. Secondaries: all 14 faithful to Chapter Approved 2025-26 (waves 91-92
re-alignment holds); three unmodelled tactical cards are documented exclusions, not
fabrications. Orders: Take Aim!/Take Cover! exact; Fix Bayonets!/First Rank Fire! wrong-stat
but direction-correct proxies.

### Command-point-sink fabrications (army pays, nothing happens)

| Entry | Faction | Cost | Status |
|---|---|---|---|
| Adaptive Strategy | Adeptus Astartes (Gladius) | 1 command point | Post-SC5-9 correction left the dispatcher firing with no effect — burns command points on an over-pole faction (masking effect: suppresses other stratagem fires). |
| Plaguesurge | Death Guard | 2 command points | Sets `Army.plaguesurge_active`; the contagion-range path ignores the flag (hard-coded 6 inches). |
| Desecration of Worlds | Thousand Sons | 1 command point | Sticky-objective grant never reaches the profile-keyed `_sticky_owner` table. |
| Vigilance Eternal | Adeptus Custodes | spent | Documented no-op but the spend path still fires. |
| Void Hardened | Leagues of Votann | spent | Dispatcher registers the spend, applies no effect (docstring admits it). |

Fix shape is uniform and cheap: either wire the effect or stop the spend (make it a true
catalogued no-op like the Tyranid tunnel cards). No re-anchor needed per entry — batch.

### Live proxy highlights (residual-relevant)

- **Apoplectic Frenzy (World Eaters)** — +1-to-wound proxy ~50% stronger than the real
  Lethal Hits; the `transient_lethal_hits` slot now exists (used elsewhere post-ST-1), so
  the rewire is mechanical.
- **Protocol of the Conquering Tyrant (Necrons)** — duplicate of surface 4 item 10
  (full re-roll vs re-roll-1s-within-half-range). Converging evidence, OVER Necrons.
- **Daemonic Invulnerability (Chaos Daemons)** — flat 4+ invulnerable proxy for
  re-roll-invulnerable-1s, roughly 3× over-model; Daemons in band, so it is masking a
  structural deficit, not a current metric lever.
- **Warp Surge** — Shadow-of-Chaos positional gate dropped (always-armed).
- **Lightning-Fast Reactions / Fire and Fade / Feigned Retreat / Skyborne Sanctuary /
  Webway Tunnel (Aeldari)** — five Warhost stratagems where mobility payoffs were replaced
  by save/shooting buffs; individually minor, jointly a slight Aeldari over-buff (+11.0 OVER).
- **Mobility-mechanic erasure pattern** (cross-faction): Da Biggest Boss, Tellyporta
  (Orks), Squad Tactics (Adeptus Astartes), Skyborne Sanctuary/Webway Tunnel (Aeldari) —
  movement/reserve effects systematically proxied as flat stat buffs because the early sim
  had no movement substrate. The displacement substrate now under construction is the
  prerequisite for un-proxying this whole class; tag them to it rather than fixing one-off.

## Surface 5 — mapper / data derivation — COMPLETE

Agent verdict: seven systematic derivation patterns, ranked by uncorrected residue × stat
importance. Per-unit corrections already in overrides.json are netted out.

| # | Pattern | Uncorrected residue | Direction | Pole exposure |
|---|---------|---------------------|-----------|---------------|
| 1 | **Feel-no-pain static baking** — BSData embeds conditional faction feel-no-pain as unconditional per-unit stats; `extract_fnp()` cannot discriminate | 85 active units with unvalidated feel-no-pain (~40 likely wrong: Chaos Spawn across five factions, Chaos Space Marines cultist variants, Thousand Sons Defiler 6+, Genestealer Cults) | Over-counts durability | **Chaos Space Marines (UNDER) / Genestealer Cults (OVER)** — biggest remaining data-fidelity lever; Haiku-tier Wahapedia cross-check sweep, same shape as the SC5-8 Drukhari patch |
| 2 | **Torrent-over-cannon weapon picker** — expected-value-vs-Marine baseline prefers 12-inch flamers over 19-inch-plus primaries | 18 units (Defilers, Heldrakes, Soul Grinder) modelled as short-range threats | Wrong engagement profile | Chaos Space Marines / Death Guard / Daemons (all UNDER) — overrides-only fix, no code |
| 3 | **Damage dice expected-value averaging** — `SWEG_ROLLDMG` gate exists but is OFF in standard evaluations | 381 units with fractional damage (142 at D6, 78 at D6+1, 26 at D6+2) | Over-values big dice vs one-wound targets | Imperial Knights / Adeptus Mechanicus (OVER benefit) — **NOTE: rolling damage was user-approved in the 2026-06 core-rules audit; the default flip appears never executed — queued-never-executed candidate** |
| 4 | Invulnerable-save extraction misses | ~5–10 units post-audit | — | Historically fixed; small |
| 5 | Basket integer-keyword rounding drops minority-model keywords (one melta in a ten-man squad rounds to zero) | Unquantified; partially closed by extra-profiles path | Under-counts special weapons | Space Marines / Chaos Space Marines (UNDER) |
| 6 | Basket range from highest-weight weapon | ~23 marginal units | Engagement decisions | Scattered |
| 7 | **Squad-size minimum=1 anomaly** — full-squad price divided by 1 | 3 confirmed: **Ratlings 60/model vs printed 6 (10×)**, Victrix Guard, Lokhust Destroyers | Mispricing (Ed class!) | Off-pole but trivially fixable |

---

## Orchestrator cross-verification log

**Necron leader fabrication cluster — VERIFIED 2026-06-11 against the BSData cache verbatim
(orchestrator, direct `Necrons.cat.gz` extraction):**

- My Will Be Done: "Once per battle round, one unit from your army with this ability can be
  targeted with a Stratagem for 0CP, even if you have already targeted a different unit with
  that Stratagem this phase." — stratagem discount, NO hit modifier. `plus_one_to_hit`
  fabrication CONFIRMED.
- Chronometron: "In your Shooting phase, after this model's unit has shot, if it is not
  within Engagement Range of any enemy units, that unit can make a Normal move of up to 5\"…"
  — movement ability, NOT feel-no-pain. CONFIRMED.
- Harbinger of Destruction: "Each time a model in this unit makes a ranged attack, an
  unmodified Hit roll of 5+ scores a Critical Hit." — offensive crit threshold, NOT
  feel-no-pain. CONFIRMED.
- Trazyn the Infinite: datasheet abilities are Leader / Ancient Collector (sticky objective)
  / Surrogate Hosts (character resurrection) — NO hit aura. CONFIRMED.

**RESOLVED (2026-06-11, live Wahapedia fetch):** `ANNIHILATION_LEGION.reroll_wound_ones` —
FABRICATION confirmed, including a fabricated inline verbatim quote ("Hardened Killers" does
not exist anywhere in the Necrons codex on Wahapedia). The real detachment rule is
"Annihilation Protocol" (charge re-roll for DESTROYER CULT / FLAYED ONES, +1 to the charge
roll versus Below Half-strength targets, and +1 Armour Penetration for DESTROYER CULT ranged
attacks at the closest eligible target —
https://wahapedia.ru/wh40k10ed/factions/necrons/#Annihilation-Legion). Neither leg has
existing machinery (no detachment charge re-roll field; no closest-eligible-target predicate
at the attack call site), so both are documented unmodelled rather than proxied. Fix landed
as worktree commit `a82c029` (flag removed, fabricated citation deleted, comment-record
citation added, regression tests added); the flag was LIVE in a minority of evaluation games
(weighted-random detachment pick, Cursed Legion dominant).

Chaos Lord / Grey Knights Grand Master fabrication claims: not yet orchestrator-verified
(lower stakes — dormant host routing / off-pole faction); verify before their fix dispatch.
