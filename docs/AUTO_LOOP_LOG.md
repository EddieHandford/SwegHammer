# Auto-loop log (recent)

Older iter blocks live in `AUTO_LOOP_LOG_archive.md`. Per
`AUTO_LOOP_PROCEDURE.md` §E this file keeps the most recent close + the
in-flight wave only.

## Wave 81 close (2026-06-01) — contest/deny built + tested + REVERTED; the LAST faithful AI lever for Imperial Knights fails → escalated the structural scoring-residual finding (no net code change)

Branch `claude/sim-calibration-6`. Built redesign step #2 (contest/deny positioning) of the
faithful AI track per `docs/MATCHUP_FIDELITY_ANALYSIS.md` and the watchdog's Q5 confirmation.
It barely moved the #1 residual and regressed the headline — the diagnosis-predicted failure.
Reverted. Headline unchanged at gated 4.95. The finding is the deliverable and is escalated.

THE TEST (env-gated `SWEG_CONTEST`). A cheap chaff unit not on an objective moves to CONTEST
the nearest reachable enemy-CONTROLLED objective (deny the durable camper its primary VP),
prioritised over the AI-9 sacrificial enemy-DZ run. Naturally asymmetric: Imperial Knights
carry no chaff, so only their victims gain the contest. N=40 A/B vs baseline 4.95:
- gated **4.95 → 5.14 (REGRESSED +0.19)**; in-band 6/22 → 5/22.
- **Imperial Knights +19.1 → +18.2 (only −0.9; still grossly over-rated at +18.2).**
- The other over-shooters got WORSE: Drukhari +18.6 → +20.6, Votann +13.4 → +14.9, Orks +1.3.

THE FINDING (escalation-grade, `LOOP_QA.md` Q6). Contest/deny was the last faithful AI lever
the diagnosis pointed at for Imperial Knights, and it FAILED. This is the THIRD confirmation
(after wave-72 value-targeting, wave-79 focus fire) of one structural law: **every generic,
faithful AI improvement helps whoever has the better army; the over-shooters HAVE the better
armies; so sharper play WIDENS the headline** (memory `project-ai-frozen-under-mae-first`).
Mechanism for IK: opponents do contest, but a Knight is durable enough to hold/retake, so its
durability converts to held primary VP — the sim's kill-centric scoring under-models how real
tournaments deny primary through the full secondary economy + board tempo. **Imperial Knights
(and the durable over-shooters generally) is a structural VP-vs-durability SCORING residual,
not AI-fixable.** Per the watchdog's Q5 ruling: reported, not nerfed; escalated to the user as
a mission call (Q6: (a) build the scoring/VP-model lever — the real root cause; (b) bank ~4.95
and declare substantial convergence; (c) keep small clean UNDER-shooter fixes meanwhile). My
non-blocking default: (c) now + recommend (a). 926 tests / audit 294/294 expected green
(no net code change — revert restored `code/strategy.py` to baseline).

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

