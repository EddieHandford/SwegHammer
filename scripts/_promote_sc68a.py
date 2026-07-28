"""Promote sc68a to STANDING ANCHOR and record the Tyranids correction.

Owner ruled "implement it" — the full faithful adoption stands, so the frame it
produces becomes the standing anchor and the Tyranids residual becomes the new
number one target.

Idempotent.
"""
from __future__ import annotations

PATH = "docs/CURRENT_STATE.md"
SENTINEL = "STANDING ANCHOR IS NOW data/_anchor_sc68a_n80_log.json"

ENTRY = """
> **⭐⭐ STANDING ANCHOR IS NOW `data/_anchor_sc68a_n80_log.json` (2026-07-26, owner ruling "implement it") — full faithful adoption stands; gated mean absolute error 3.21, raw 6.31; production digest `4aab205fbb99635db7c607db`; all seventeen kill-switches together restore `db13417fb7e3b2d47cef9867`.**
>
> **THE TRADE, ACCEPTED KNOWINGLY.** Adoption is NOT the best-metric configuration — the Astra Militarum package alone reads gated 2.51 / raw 5.46, and `cand1` (that package plus the four Astra Militarum rules and the Battle-shock aura fix) reads 2.58 / 5.56. Full adoption costs +0.70 gated against the best. It is adopted because every gate in it is faithful, on the `SWEG_TERRAIN_DENSE` precedent (adopted at +0.46 on the same argument), and because it is the ONLY configuration that improves BOTH historic poles at once: **Astra Militarum error 11.5 → 7.5** and **Death Guard 14.2 → 12.2**.
>
> **THE NEW NUMBER ONE RESIDUAL IS TYRANIDS: 31.0 against a real 47.0, error 15.9** — it has overtaken Death Guard (12.2) and Aeldari (13.0). It was 34.5 at `sc67a`, so this session's adoption cost it 3.4 points.
>
> **ITS CAUSE IS NOT YET IDENTIFIED — an earlier claim that Fire Overwatch explains it is RETRACTED.** The direct test (Tyranids-scoped arm, `SWEG_OVERWATCH_MOVE=0` against `sc68a`, `data/_scr_tyranids_ow_log.json`) gives **35.9 → 34.7, paired delta −1.19 with a 3.09 interval: NOT decisive, and the wrong sign.** The earlier inference came from comparing `cand1` to `cand2`, which also differed in whether `SWEG_RANGE_BASEEDGE` was on, so it could not attribute cleanly. Death Guard's gain from Fire Overwatch IS confirmed (`cand1` 14.5 → `cand2` 12.4); the Tyranids collapse is a separate, open question.
>
> **STARTING POINTS FOR THE TYRANIDS INVESTIGATION.** Tyranids was ALREADY the deepest under-pole before this session (34.5 vs real 47.0, error 12.5) — the adoption deepened an existing hole rather than digging a new one. It is the largest-model-count army measured (113 models), it is melee-and-advance shaped, and the same one-`Unit`-per-model representation that produced two defects for Astra Militarum applies to it with more force. The Astra Militarum method transfers directly: instrument what the units actually DO (`scripts/_am_unit_audit.py`, `_am_lockout_probe.py`, `_am_intent_probe.py` are all faction-parameterisable), find the mechanism, then look for the misapplied or unwired rule behind it.
"""


def main() -> None:
    src = open(PATH, encoding="utf-8").read()
    if SENTINEL in src:
        print("already promoted — no change")
        return
    lines = src.split("\n")
    lines.insert(1, ENTRY)
    open(PATH, "w", encoding="utf-8").write("\n".join(lines))
    print("sc68a promoted to standing anchor; Tyranids correction recorded")


if __name__ == "__main__":
    main()
