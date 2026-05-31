# Auto-loop log (recent)

Older iter blocks live in `AUTO_LOOP_LOG_archive.md`. Per
`AUTO_LOOP_PROCEDURE.md` §E this file keeps the most recent close + the
in-flight wave only.

## Wave 80 close (2026-05-31) — IK Armiger re-fit tested + REVERTED; the AI+re-fit shooting/list routes fail for Imperial Knights (no net code change)

Branch `claude/sim-calibration-6`. Ran the user's AI+re-fit hypothesis on the #1 residual
(Imperial Knights): the faithful list-realism re-fit toward the real Armiger-heavy
tournament-winning list, alone and paired with the wave-79 focus fire. BOTH regress; IK
climbs. Reverted. Headline unchanged at gated 4.95. The finding is the deliverable.

THE TEST. Re-fit the IK archetype from big-Knight-heavy to the real Armiger-heavy list (6
Helverin / 6 Warglaive / Moirax / Canis Rex anchor — the proven competitive shape per the
Goonhammer / Sprues & Brews 2025 reviews). The builder produced a correct ~13-Armiger,
~1970pt list.
- Re-fit ALONE (focus fire off): gated 4.95 → **5.66** — IK UP. The efficient Armigers
  over-perform MORE in the sim (their real-world fragility tax is not modelled).
- Re-fit PAIRED with focus fire: gated **5.90**, **Imperial Knights +39.5 / 88%** — the
  fragile Armigers get focus-removed but they are cheap and many, and both lists' offence
  sharpens. Worst IK result yet.

DIAGNOSIS (firm now): the Imperial Knights over-rate is NOT the list — both the big-Knight
and the Armiger shapes over-perform in the sim (the Armiger one more). It is not the stats
(T11/W26 already current), not the rules (verified 71-72), and not the shooting AI (a Knight
cannot be shot off, so better targeting only sharpens IK's OWN offence — confirmed a 3rd
time). The over-rate is the **objective-HOLDING**: the sim over-rates a durable camper
because opponents do not **deny its primary VP**. Reverted the re-fit (both shapes are
realistic, so the regressing swap is not a clear fidelity win). The remaining faithful lever
is **contest/deny positioning (step #2)** — opponents sacrifice cheap bodies onto the
objectives IK is NOT on / contested ones to deny its primary VP, the real way Knights are
beaten. Logged `LOOP_QA.md` Q5; building step #2 next, env-gated, drilling IK's objective
holding before/after. If it too fails, IK is a structural scoring residual (VP-vs-durability),
not AI-fixable — and that is the finding to report.

## Wave 79 close (2026-05-31) — army focus fire built + tested (env-gated, regresses solo); diagnosis → Armiger re-fit + contest/deny next

Branch `claude/sim-calibration-6`. Built redesign step #1 of the faithful AI track (army-level
focus fire) per `docs/MATCHUP_FIDELITY_ANALYSIS.md`. It regresses solo, exactly the
accept-regression-then-re-fit scenario the user described. Committed env-gated OFF — baseline
gated 4.95 unchanged.

BUILT (env-gated `SWEG_FOCUS`): `Battle._nominate_focus_target` + a `_do_shoot` override. The
army nominates the most valuable durable enemy threat it can hurt (Knight/Monster/Vehicle or
8+ wound model, preferring one on an objective), and its ANTI-ARMOUR weapons only
(`_is_antiarmour_weapon`: damage≥3 / AP≤-2 / Anti-MONSTER-VEHICLE-TITANIC) concentrate on it —
weapon-target matched, so bolters keep clearing chaff. Smoke-confirmed: Chaos Space Marines
focus-fire the Knight Castellan and win a matchup they normally lose 0%.

| Eval | MAE_gated | note |
|---|---:|---|
| Wave 78 baseline | 4.95 | focus fire OFF |
| Focus fire ON (A/B) | **5.41** | regressed +0.46 |

Per-faction: Drukhari +18.6 → +14.2 (HELPED, −4.4 — its fragile Ravagers/Talos get
focus-removed) but Imperial Knights +19.1 → +25.9 (WORSE, +6.8), GSC −5.4 → −15.9, T'au up.

DIAGNOSIS (the user's diagnose-the-over-shoot step): focus fire is the right tool for FRAGILE
high-value threats (Drukhari) but WRONG for the durable Imperial Knights — a Knight cannot be
shot off (T11/W26/5++), so the victims' fire is wasted while IK's own anti-armour sharpens on
the opponents' vehicles/dreadnoughts. Third confirmation (after wave-72 value-targeting) that
better SHOOTING AI sharpens the durable over-shooters. The faithful next steps the regression
exposes: (1) **IK list-realism re-fit** — the sim's big-Knight archetype is OVER-GUNNED vs the
real Armiger-heavy tournament list; rebuild it toward the real list (Armigers are T9/W14, so
focus fire would REMOVE them → IK down). Test: Armiger re-fit PAIRED with focus fire. (2)
**Contest/deny (#2)** — the real IK lever is denying its primary VP (contest the objectives it
is not on; body it off), not killing the Knight. 926 tests pass; audit 294/294. Focus fire
committed env-gated OFF, pending those.

## Wave 78 close (2026-05-31) — matchup-fidelity diagnosis + faithful-AI plan (no code change)

Branch `claude/sim-calibration-6`. First wave of the user-chosen phase (Q4 ruling): the
faithful target/positioning AI track + matchup-fidelity diagnosis. A diagnosis+plan wave
(like wave 73 → 74), because the AI redesign is big/risky and warrants clean context.
Headline unchanged at gated 4.95.

MATCHUP DIAGNOSIS (drilled per-cell, not aggregate). The over-shooters crush specific
victims: Imperial Knights beat CSM / AdMech / Marines **100%**, Drukhari beat Tyranids /
CSM / AdMech **90%**. The under-shooters get crushed: CSM loses **0%** to Emperor's
Children (10% to Sororitas/Votann); Chaos Daemons lose **0%** to AdMech / Drukhari / TSON.
These are impossible in real competitive play (~even). Compared to real May-2026 play, the
gap sorts almost entirely into **bucket (a) — the opponent AI**: it does not (1) focus-fire
the durable/key threat with concentrated anti-armour (the way a real list deletes a Knight
or a Ravager), (2) contest/deny the durable camper's objectives, or (3) allocate units to
actions sensibly (CSM/Daemons suicide spare units on Sabotage). Verified NOT a stat gap —
the sim's Knight stats (Questoris T11/W26) already reflect the December-2025 toughness
update, and the rules were verified faithful in waves 71-72. One list note (bucket b): the
real winning Knights list is Armiger-heavy vs the sim's big-Knight build — flagged, not
pulled (uncertain direction).

DELIVERABLE: `docs/MATCHUP_FIDELITY_ANALYSIS.md` — the per-cell findings, the real-play
comparison, the 3-bucket sort, and the faithful-AI redesign plan: (1) ARMY-LEVEL focus fire
on the highest-value reachable threat (weapon-target-matched — the per-UNIT value-picker
regressed in wave 72 because it sharpened the over-shooters' own offence symmetrically); (2)
contest/deny objectives (#13 positioning — body the camper off the VP); (3) action
allocation = spare-and-survivable only. Each env-gated A/B, and when the better AI exposes
an over-shoot, DIAGNOSE the faithful cause (re-calibration toward real lists now permitted)
— never a nerf. Build in the next waves, drilling the driving matchup cells before/after.

