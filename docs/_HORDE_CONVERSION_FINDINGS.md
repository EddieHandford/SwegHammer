# The horde secondary-conversion investigation — is the sc52a crater faithful or fixable?

**Read-only.** The secondary-economy re-anchor (sc51a → sc52a, six printed-rule
fixes) re-priced the field and the headline metric rose to gated 4.23. The
intended beneficiaries — the body/horde armies — **cratered away from real**:
Orks −3.78 decisive (now 36.2 vs real 44.9, −8.7 under), Genestealer Cults −3.94
decisive (now 40.4 vs real 47.4, −7.0 under). The ranked hypothesis was horde
action-**conversion**: that the artificial intelligence holds the scoreable
cards but never performs the Cleanse / Sabotage / Establish-Locus actions to
score them, while the completed deck arms elite opponents with Cull the Horde.
This investigation decides, with evidence, whether the crater is FAITHFUL (real
Cull-the-Horde vulnerability, honest residual) or a FIXABLE conversion / heuristic
gap.

**Verdict up front: the crater is FAITHFUL. Adopt sc52a as-is.** The hordes
convert their own secondaries at near-elite rates and score *more* action victory
points per game than the over-converting elite; the card-shedding heuristic never
throws away a horde's scoreable cards; and the extra secondary the completed deck
hands their opponents is the printed game correctly scoring Cull the Horde / Bring
It Down / Assassination / No Prisoners / Overwhelming Force off genuinely
target-rich horde rosters. The "artificial intelligence never performs the
actions" hypothesis is **refuted**. The horde under-pole is honest, and its cause
is NOT secondary conversion — it is the horde's kill-vulnerability and a primary /
board-control side-effect of the wave, which belong to the primary / durability
economy, not the secondary deck.

---

## 1. Method and the reproduction gate (mandatory)

Every Orks game (3,360) and every Genestealer Cults game (3,360) recorded in the
standing anchor `data/_anchor_sc52a_n80_log.json` was reconstructed from its seed
exactly as `scripts/_ec_crater_replay.py` / `scripts/_sec_audit_replay.py` build
them (the canonical `build_faction_random_army` + `Battle` construction under
`PYTHONHASHSEED=0`), instrumented per card / action / discard, and its replayed
winner compared to the anchor's recorded winner. An 800-game Adepta Sororitas
sample (the elite that over-converted to +6.5) was replayed the same way for the
action-conversion comparison. Scratch scripts: `scripts/_horde_conv_replay.py`
(instrumented replay), `scripts/_horde_conv_analyze.py` (the channel split),
`scripts/_horde_conv_games.py` (narratives), `scripts/_horde_conv_compo.py`
(roster composition).

**Reproduction gate — PASSED exactly:**

| Cell | winners matched | official win-rate (as-side-A, field-weighted) | task-cited sc52a |
|---|---|---|---|
| Orks (sc52a defaults) | **3,360 / 3,360** | **36.17 %** | 36.2 |
| Genestealer Cults (sc52a defaults) | **3,360 / 3,360** | **40.44 %** | 40.4 |
| Adepta Sororitas (sc52a defaults) | 800 / 800 | — | — |

The official metric is `scripts/evaluate_vs_meta.py`'s convention: the faction as
**side A only**, per-opponent win-rate **field-weighted by each opponent's real
tournament prevalence** (`data/warpfriends_rolling.json`). Both numbers reproduce
the task's sc52a figures to the rounding, so the replay is trustworthy.

The **before** substrate (sc51a) is reproduced by the five secondary-economy
kill-switches off (`SWEG_TAC_SHEDDING=0 SWEG_ACTIONS_HAND_GATED=0
SWEG_TACDECK_FULL=0 SWEG_FIXED_POOL_FULL=0 SWEG_CP_PER_COMMAND_PHASE=0`), which the
decision ledger certifies byte-identical to sc51a (0 / 36,960 flips). That arm
reproduces sc51a's win-rates exactly:

| Cell | sc51a (kill-switches off) official | task-implied sc51a | crater ON−OFF |
|---|---|---|---|
| Orks | **39.95 %** | ~39.98 | **−3.78** (matches the task exactly) |
| Genestealer Cults | **44.38 %** | ~44.34 | **−3.94** (matches the task exactly) |

Pairing sc52a against sc51a on the same seeds gives a clean per-game before/after.

---

## 2. The real split — it is NOT a secondary-conversion collapse

Decomposing the paired per-game raw victory-point swing (sc52a − sc51a, focus
faction versus its opponent, averaged over all 3,360 games in each cell):

| | Δ own primary | Δ opp primary | **PRIMARY swing** | Δ own secondary | Δ opp secondary | **SECONDARY swing** | **TOTAL raw swing** |
|---|---|---|---|---|---|---|---|
| **Orks** | −0.16 | +0.41 | **−0.57** | **+2.75** | +2.79 | **−0.04** | **−0.61 / game** |
| **Genestealer Cults** | −1.10 | +1.20 | **−2.30** | **+1.82** | +2.62 | **−0.80** | **−3.10 / game** |

Two decisive readings:

1. **The hordes' OWN secondary ROSE with the fix** (+2.75 Orks, +1.82 Genestealer
   Cults per game). They convert the completed deck. The "I hold the cards but the
   artificial intelligence never performs the actions to score them" channel is
   therefore **near-zero for Orks and small for Genestealer Cults** — it is not
   the crater.
2. The secondary swing against the horde is a near-wash for Orks (−0.04) and a
   modest tilt for Genestealer Cults (−0.80). The **Orks crater is not a secondary
   swing at all** — its total raw swing is only −0.61/game, dominated by a
   marginal primary loss; the −3.78 official number is the field-weighting / as-A
   convention amplifying a near-neutral raw change across the (Marine-heavy) real
   field. The **Genestealer Cults crater is −3.10 raw/game and is dominated by a
   PRIMARY loss (−2.30)**, not a secondary one — a board-control side-effect of the
   wave (the doubled command points and the action-vs-aggression trade), which is
   a faithful direction and outside the secondary deck.

So the "two channels" the brief asked to split are:

- **Channel A — "the deck armed my opponent against me":** the opponent's
  secondary rose +2.79/game (Orks) and +2.62/game (Genestealer Cults). This is
  the dominant secondary channel.
- **Channel B — "I can't convert my own cards":** the horde's own secondary rose
  **+2.75/game (Orks)** and **+1.82/game (Genestealer Cults)** — i.e. the horde
  converts almost exactly as much new secondary as its opponent (Orks) or a bit
  less (Genestealer Cults). Channel B is **not a defect**; the hordes do convert.

## 2a. What the completed deck actually handed each side (per-card, sc52a − sc51a)

The opponent's extra secondary is the printed cards scoring off horde targets, not
a single Cull-the-Horde spike:

**Orks — opponent secondary gained per game (sc52a − sc51a):** overwhelming_force
+1.07, a_tempting_target +1.16, cull_the_horde +0.73 (its Tactical-track access is
new; opponent Cull is now 2,365 Tactical vs 1,295 Fixed), marked_for_death +0.66,
recover_assets +0.49, display_of_might +0.28. Note the *pre-existing* horde
killers actually **fell**: opponent bring_it_down −0.36 (still 4.29/game off Orks'
~18 vehicle/walker model-instances), no_prisoners −0.15, assassination −0.22 — so
the fix did not increase the biggest anti-Orks card (Bring It Down); that
vulnerability was already present in sc51a.

**Genestealer Cults — opponent secondary gained per game:** overwhelming_force
+1.23, a_tempting_target +1.07, marked_for_death +0.86, cull_the_horde +0.67,
recover_assets +0.49, display_of_might +0.48. The dominant anti-Genestealer card,
**assassination, is 7.76/game off their ~12 character model-instances — and it
FELL −0.36 with the fix** (it was already crushing them in sc51a). No prisoners
1.48 (−0.15) likewise pre-existing.

The horde's own side gained through the *same* new cards (Orks own: a_tempting
+1.43, overwhelming_force +1.18, recover_assets +0.90, display_of_might +0.73,
marked +0.70, cull +0.29; Genestealer Cults own: a_tempting +1.50 and the same
family). The completed deck armed **both** sides; the horde is the one whose
roster presents more targets.

## 2b. The horde presents a target-rich roster — this is the faithful crux

Per-game secondary balance under sc52a (own vs the opponent's total secondary):

| Focus (sc52a) | own secondary | opp secondary | gap | opponent's top secondary source /game |
|---|---|---|---|---|
| **Adepta Sororitas (elite, +6.5 over)** | 13.39 | 13.31 | **−0.07** | assassination 3.22, bring_it_down 2.40 |
| **Orks** | 11.64 | 14.67 | **+3.03** | **bring_it_down 4.29** (vehicles), a_tempting 1.16, cull 1.09, overwhelming 1.07 |
| **Genestealer Cults** | 13.26 | 18.24 | **+4.98** | **assassination 7.76** (characters), no_prisoners 1.48, overwhelming 1.23 |

The elite is **not** out-scored on secondary (−0.07); the hordes are (+3.03,
+4.98). The reason is roster shape, confirmed by `scripts/_horde_conv_compo.py`:
Orks field ~18 monster/vehicle model-instances (Trukks, Battlewagons, Deff Dreads,
Killa Kans, Gorkanauts) → Bring It Down food; Genestealer Cults field ~12
character model-instances → Assassination food; both field 28–40 horde bodies →
Cull the Horde / No Prisoners / Overwhelming Force food. This is exactly the
real-game vulnerability, now correctly modelled.

---

## 3. Action conversion — the hypothesis is REFUTED

Instrumented Cleanse / Sabotage / Establish-Locus / Recover-Assets funnels under
sc52a (assignments flagged in the Movement phase → units alive to complete →
victory points realised):

| Card | Orks VP/assign | Orks complete-rate | Genestealer Cults VP/assign | Sororitas (elite) VP/assign | Sororitas complete-rate |
|---|---|---|---|---|---|
| cleanse | **1.58** | 685/919 = 75 % | 1.49 | 1.66 | 204/255 = 80 % |
| sabotage | **1.22** | 1491/2199 = 68 % | 1.24 | 1.40 | 395/520 = 76 % |

- The hordes assign actions **and complete them** at 68–75 % (elite 76–80 %) — a
  small survival gap, not a collapse.
- Per-game **action victory points scored: Orks 2.85, Genestealer Cults 2.38,
  elite Sororitas 2.35.** The hordes score *more* action victory points per game
  than the over-converting elite.
- Establish Locus and Recover Assets (drawable by default under the completed
  deck, `_action_cards_active` = true) score for the hordes too (Orks
  recover_assets 3,035 victory points across the cell; establish_locus 422) — they
  are not dead cards.

The picture of a horde that "holds the scoreable cards but the artificial
intelligence never performs the actions" does not exist in the data. Actions are
performed, completed, and scored at near-elite efficiency. Hand-gating (D2) made
actions rarer but efficient (the pre-fix 0.18 victory-points-per-action waste the
audit measured is gone), so the horde now performs an action only for a card it
actually holds — and converts it.

---

## 4. The card-shedding heuristic — NOT throwing away scoreable cards

`SWEG_TAC_SHEDDING`'s two live mechanisms:

- **New Orders** fires only on a *structurally dead* card with a command point to
  spend. Across 3,360 games it discarded **4 cards (Orks) / 12 (Genestealer
  Cults)** — negligible, all provably dead (assassination against a
  character-less enemy). Not a factor.
- **End-of-turn voluntary discard** sheds at most one "cannot-pay" card per turn.
  The cards it flags most are the ones genuinely dead or persistently unscoreable
  for the holder: establish_locus (no objective-control body in a scoring
  position), extend_battle_lines, bring_it_down / assassination / cull_the_horde
  (no qualifying enemy target), marked_for_death, overwhelming_force. **The
  horde's bread-and-butter board cards are almost never flagged:**
  secure_no_mans_land (Orks 55/290 = 19 %, Genestealer Cults 66/252 = 26 % of
  probes) and engage_on_all_fronts (Orks **2/622 = 0.3 %**, Genestealer Cults
  12/699 = 1.7 %).

The clinching test: the horde's own board-card scoring **rose or held** from sc51a
to sc52a — Orks secure_no_mans_land +0.08, engage_on_all_fronts +0.10;
Genestealer Cults secure ±0.00, engage −0.01. If shedding were discarding cards
the horde would have scored, this would have fallen. It did not.

**Shedding verdict: the heuristic does NOT throw away scoreable horde cards.** It
sheds structurally-dead and persistently-zero cards; the horde's scoreable board
cards (Secure No Man's Land, Engage on All Fronts) pass through untouched. This
was the most likely fixable defect and it is absent.

---

## 5. Which matchups drive the crater (per-opponent, field-weighted)

The −3.78 / −3.94 reconcile exactly to per-opponent contributions, and both point
at the **shooting / elite / fast** armies that kill the horde efficiently:

**Orks** (contribution to −3.78): Adeptus Astartes −8.8 (**−1.88, half the
crater**), Thousand Sons −17.5 (−0.62), T'au Empire −8.8 (−0.61), Aeldari −16.2
(−0.51), Leagues of Votann −13.8 (−0.47), Custodes / World Eaters −6.2 each.
Orks **GAINED** versus the armies they out-body: Tyranids +15.0 (+0.67), Imperial
Knights +8.8, Chaos Knights +8.8, Adepta Sororitas +10.0.

**Genestealer Cults** (contribution to −3.94): T'au Empire −30.0 (**−2.05**),
Chaos Daemons −36.2 (−1.11), Necrons −13.8 (−1.06), Aeldari −31.2 (−0.97), Chaos
Space Marines −11.2 (−0.71). Genestealer Cults **GAINED** versus Adeptus Astartes
+6.2 (+1.31), Astra Militarum +12.5 (+0.69), Emperor's Children +16.2 (+0.64).

The crater is not spread evenly — it is the horde losing more close games to the
armies that shoot it off the board (which now bank secondary for doing so), and
winning more against the armies it out-grinds. That is the faithful shape of a
body army in a shooting-heavy meta.

---

## 6. Representative games

**Genestealer Cults vs Chaos Space Marines, s=18 (crater loss, 44 vs 50).**
Genestealer Cults converted its own hand well — Cleanse 4, Overwhelming Force 3,
Marked for Death 5, Engage 2 = 14 secondary. It lost because in the final round
the Marines' kill-spree scored Assassination 5 + Marked for Death 5 + No Prisoners
5 = 15 off dead Genestealer Cults characters and bodies. Pure "opponent armed
against me," in a dead-even game the kill-cards tipped.

**Genestealer Cults vs Adeptus Astartes, s=11 (crater loss, 42 vs 45).** Won
primary 40–30, lost secondary 2–13: the Marines scored Assassination 7 + 4 off the
Cult's characters. The Cult held Establish Locus / Behind Enemy Lines /
Overwhelming Force / Marked for Death but could not score them — not because the
heuristic hid them, but because it had not killed / positioned enough. Faithful
under-conversion driven by the board, not a bug.

**Orks vs Drukhari, s=15 (crater loss, 42 vs 50).** Orks WON primary 28–20 but
lost secondary 12–30: the elite Drukhari, cycling the completed deck, scored
Secure 5, Cull the Horde 5, Overwhelming Force 3, Engage 4, Recover Assets 3,
Storm 4, Bring It Down 4 off the Orks. The clearest "the deck armed my opponent"
game — the horde converted (12) but the opponent converted more off the horde's
own bodies.

**Orks vs Astra Militarum, s=43 / vs Chaos Daemons, s=24 (crater losses).** Both
primary blow-outs (Orks primary 8 and 25). Orks still converted 15 and 9 secondary
respectively — the loss is being out-fought, with marginal secondary tipping an
already-losing game. Not a conversion failure.

The recurring signature: the horde's own secondary is non-zero and often healthy
(12–15); it loses because the opponent *also* scores heavily on secondary (off the
horde's bodies) and/or out-fights it on primary.

---

## 7. Crisp verdict — FAITHFUL, adopt sc52a as-is

**The crater is faithful.** The evidence is one-directional:

1. The hordes' **own secondary rose** with the fix (+2.75 / +1.82 per game) — they
   convert the completed deck.
2. They **perform and complete Cleanse / Sabotage / Establish-Locus / Recover-
   Assets actions at near-elite rates and score more action victory points per
   game than the over-converting elite** — the "artificial intelligence never
   performs the actions" hypothesis is refuted.
3. The **card-shedding heuristic never discards the horde's scoreable board
   cards** — its most-shed cards are genuinely dead, and horde board-card scoring
   rose under it.
4. The extra secondary the opponent gains is the **printed deck correctly scoring
   Cull the Horde / Bring It Down / Assassination / No Prisoners / Overwhelming
   Force off genuinely target-rich horde rosters** (Orks ~18 vehicles, Genestealer
   Cults ~12 characters, both 28–40 bodies) — real, faithful vulnerability. The
   biggest anti-horde cards (Bring It Down vs Orks, Assassination vs Genestealer
   Cults) were *already present in sc51a* and the fix did not increase them.
5. The net secondary swing is a wash for Orks (−0.04) and a small tilt for
   Genestealer Cults (−0.80); the Orks official −3.78 is the field-weighting /
   as-side-A convention amplifying a near-neutral raw shift (−0.61/game) across the
   Marine-heavy field, and the Genestealer Cults crater is majority a **primary /
   board-control** side-effect (−2.30 of the −3.10 raw), not a secondary one.

**There is no conversion bug and no heuristic defect to fix in the secondary
deck.** The horde under-pole (Orks −8.7, Genestealer Cults −7.0 under real) is
honest, but its cause is NOT the secondary economy — which now works. The residual
belongs to two surfaces outside this investigation:

- **The kill / primary economy:** the hordes get shot off the board by the
  gunline / elite meta and bank less primary, which the completed deck then lets
  those opponents convert into secondary too. This is the same surface the
  durability-wave audits flagged (the simulator over-pays a survivor's uptime and
  under-models the body army's grind). The horde residual is a MATCHUP / list-
  strength / durability-economy question, not a secondary-conversion one.
- **The Genestealer Cults primary side-effect of the wave (−2.30/game):** worth a
  follow-up isolation (most likely the doubled command-point generation letting
  opponents fight harder, or the action-vs-aggression board trade), but it is a
  faithful direction and not a reason to withhold sc52a.

**Build direction:** do not touch the secondary deck, the shedding heuristic, or
the action assignment — they are faithful. Hand the horde under-pole to the
primary / durability / kill economy. If the loop wants the hordes closer to real,
the lever is the sim's over-payment of durable uptime and the body army's primary
grind, not the secondary economy the broken deck was masking. sc52a is adopted
correctly under the no-knobs, fidelity-first ruling.
