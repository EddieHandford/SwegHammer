"""Replace the CURRENT_STATE head entry with the corrected end-of-session picture.

Written as a script because Bash heredocs and PowerShell here-strings are both
intercepted in this environment.

Idempotent: refuses to run twice.
"""
from __future__ import annotations

PATH = "docs/CURRENT_STATE.md"
SENTINEL = "THE FAITHFUL-ADOPTION WAVE (2026-07-25)"

ENTRY = """
> **⭐⭐ THE FAITHFUL-ADOPTION WAVE (2026-07-25) — the Astra Militarum under-pole is SOLVED and DIAGNOSED (error 11.5 -> 7.5, its best ever), Death Guard moved for the first time in the campaign (14.2 -> 12.2), and adopting every faithful mechanic costs the frame — a REDISTRIBUTION, not a regression.**
>
> **THE ASTRA MILITARUM ANSWER.** The registered-but-never-run order-coverage question was measured: the army issues **2.93 Orders per round against a legal ceiling of 8.77 (33 percent)**, and the dispatcher was never the bottleneck. Four defects, each found by asking a question of the WHOLE codebase rather than of the faction:
> (1) the 6-inch Voice of Command aura was measured **centre-to-centre** while the 10e core measuring rule — cited in this repository and already applied to Engagement Range and objective control — is base-edge; a foot Officer reaching a Leman Russ got 6.00 inches instead of the legal 9.00, **44 percent of the legal area**;
> (2) the **entire battleline is piloted as sacrificial chaff** — every Astra Militarum infantry datasheet is under the 15-points-per-model bar, and AI-9's only safety gate declines once a friendly has ALREADY ARRIVED in the enemy deployment zone, so while the first unit walks (four-plus rounds) the whole army marches, Advances, forfeits its Shooting phase and dies. Cadian Shock Troops dealt **0.4 wounds a game**; Death Korps of Krieg dealt damage on **zero of 254 activations**;
> (3) the advance-suppression guard's 0.5 expected-damage floor was applied **per model** though the simulator stores one `Unit` per model, so **no multi-model squad in the catalogue could ever pass it**;
> (4) four rules the army OWNS and could not use were switched off — Cadia Stands!, Duty and Honour!, Lord Castellan, and the Reinforcements! stratagem.
> **`SWEG_ORDER_AURA_BASEEDGE` alone is +3.33 — 87 percent of the whole result from one comparison operator.** Four piloting heuristics built the same night were worth nothing; see `docs/AM_ORDER_COVERAGE_FINDINGS.md` and `docs/AM_INFANTRY_NEVER_FIRES.md`.
>
> **THE GENERALISED METHOD (`docs/MEASUREMENT_DEFECT_AUDIT.md`).** Ask the codebase a question and let the answer name a CLASS. *What rule does it state but not apply everywhere?* -> the measurement class, four verdicts, and the rule that **impact tracks FREQUENCY OF CONSEQUENCE, not distortion size** (Contagion and the Order aura are identically distorted — both keep 44 percent of legal area — and are worth 0.00 and +3.33). *What does it implement but leave switched off?* -> eleven mechanics enabled; of eighteen default-off rules gates across all twenty-two factions, **seven were Astra Militarum**, the most of any faction.
>
> **THE NUMBERS.** Raw mean absolute error (both-sides, `scripts/_config_compare2.py`): four-gate **5.46**, sc67a 5.48, weapon-range-off 5.93, sc68a (all gates) 6.31. Gated: four-gate **2.51**, sc67a 2.76, 3.13, 3.21. **The two metrics disagree — gated subtracts noise bands, so weapon range costs 0.08 gated but 0.38 raw. Always quote both.** sc68a is the best configuration yet for BOTH biggest poles (Death Guard 12.2, Astra Militarum 7.5) while six mid-table factions absorb the cost: Votann +4.1, Astartes +3.2, Chaos Knights +2.9, Necrons +2.8, Sororitas +2.7, Tyranids +2.3.
>
> **THE STRUCTURAL FINDING, with numbers on both sides: individually faithful mechanics can make calibration WORSE by inflating factions already over-performing.** Weapon range measured base-edge (+5.5 on Adeptus Astartes alone) and Kindred Hero's [LETHAL HITS] grant (Votann, already +8.4 over). Neither is a defect in the fix — both say those factions over-perform for a reason the faithful mechanic amplifies, the sharpened diagnosis fidelity-first predicts (`SWEG_TERRAIN_DENSE` precedent, adopted at +0.46).
>
> **CAVEATS THAT COST REAL TIME — read before trusting any sweep.** FOUR instruments produced confident wrong answers this session, each caught only by checking the CODE: a gate sweep that inferred defaults from the comparison direction reported Fire Overwatch as disabled (it is on; the line is a guard clause); the chaff cap counted `Unit` instances (one per MODEL) where Behind Enemy Lines scores per UNIT; a confession sweep reported the Aeldari Fate-dice and Battle-Focus over-counts as live when both were adopted on 2026-07-08 (**citations keep their pre-fix narrative — the "ADOPTED" note is in the code comment**); and a fabrication sweep scanning effect prose returned 126 hits with the top six all false. **Also: three of the seventeen "adopted" gates are INERT** (identical digest on and off) — `SWEG_CHALLENGER_GAP_CAPPED` is only a sub-option of `SWEG_CHALLENGER_CARDS`, which is default-off by a deliberate 2026-07-04 reversion. **Check a gate's PARENT and path reachability before adopting it.**
>
> STATE: fourteen gates effective; all kill-switches together restore digest `db13417fb7e3b2d47cef9867` exactly; production digest `4aab205fbb99635db7c607db`. New anchor `data/_anchor_sc68a_n80_log.json`. NOTHING COMMITTED (rule 3). OPEN: the candidate configuration (Astra Militarum gates + aura, global redistributors off) is screening; if it recovers the frame it is the recommendation, leaving weapon range as a separate doctrine call with its measured price.
"""


def main() -> None:
    src = open(PATH, encoding="utf-8").read()
    if SENTINEL in src:
        print("entry already present — no change")
        return
    lines = src.split("\n")
    lines.insert(1, ENTRY)
    open(PATH, "w", encoding="utf-8").write("\n".join(lines))
    print("CURRENT_STATE head updated")


if __name__ == "__main__":
    main()
