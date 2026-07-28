"""Record the Tyranid sourced-list verdict, the adoption, and the digest-coverage
correction across the three documentation files."""
from __future__ import annotations

VERDICT = """
## VERDICT — screened, proven, adopted (2026-07-26)

Scoped screen, `data/_scr_nidlist_log.json`, N=80 paired against `sc68a`:

| frame | before | after | real | error |
|---|---|---|---|---|
| A-frame (paired_delta --scoped) | 35.9 | **45.4** (+9.49, decisive) | 47.4 | 11.5 → **2.0** |
| both-sides (`scripts/_residual_table.py`) | 31.0 | **44.6** | 47.0 | 15.9 → **2.4** |

Overall gated mean absolute error **3.21 → 2.85**. Eleven other factions drift
down between 0.3 and 1.4 points; that is the correct collateral, because their
Tyranid matchup became genuinely harder once Tyranids fielded the army the real
47 percent was earned with.

Nothing else attempted in this campaign moved Tyranids at all. `SWEG_MELEE_CHARGE_HOLD`
doubled charge eligibility and connection and tripled Hormagaunt melee damage for
+0.34. The list was the whole problem.

**Adopted.** `SWEG_TYRANID_LIST_SOURCED` is default-ON; `=0` is the kill-switch.
Re-anchor `sc69a` running.

## The verification claim in the section above was vacuous — corrected

This document previously said the gate was "byte-identical when off, digest
`4aab205fbb99635db7c607db`". That verified nothing.

`scripts/_detcheck.py` runs three pairings — Death Guard against Astra Militarum,
Aeldari against Adeptus Astartes, Orks against T'au Empire. Six factions of
twenty-two. **Tyranids never appear in it.** The canonical digest is therefore
structurally blind to a Tyranid-only change and reads identical whether this gate
is on or off. A measurement covering six factions was quoted to certify all
twenty-two — the same error class as the other retractions in this session.

`scripts/_detcheck_wide.py` now provides a second digest over all twenty-two
factions (ring pairing, each faction once per side, forty-four battles). The
canonical narrow digest is deliberately left untouched, because it is referenced
across the documentation and every prior wave's verification.

| configuration | wide digest |
|---|---|
| sourced list ON (new production default) | `f243047dbb6a7f45d64aae66` |
| `SWEG_TYRANID_LIST_SOURCED=0` (kill-switch) | `91a2c9d431b0f8e85d1712e1` |

They differ, which is the coverage proof the narrow digest could not give.

**General consequence:** any gate whose effect is confined to the sixteen factions
outside those three pairings has never been byte-identity-verified by anything.
Faction-scoped gates should be verified against the wide digest from now on.
"""

LEDGER = """## THE TYRANID LIST WAS THE WHOLE PROBLEM (2026-07-26)

**Screened and adopted.** Replacing the Tyranid archetype with the army it cites
moves Tyranids **+9.49** in the A-frame (35.9 to 45.4 against a real 47.4, error
11.5 to about 2.0) and from 31.0 to 44.6 both-sides (error 15.9 to 2.4). Overall
gated mean absolute error **3.21 to 2.85**. Eleven other factions drift down 0.3
to 1.4 points — correct collateral, their Tyranid matchup got harder.

Nothing else in this campaign moved Tyranids. `SWEG_MELEE_CHARGE_HOLD` doubled
charge eligibility and connection and tripled Hormagaunt melee damage, for +0.34.
The number-one under-pole was never a mechanics problem.

`SWEG_TYRANID_LIST_SOURCED` adopted default-ON, `=0` the kill-switch. Re-anchor
`sc69a` running. Full account in `docs/TYRANID_LIST_FIDELITY.md`.

**A sixth retraction, and the most consequential.** Every "byte-identical
verified, digest `4aab205fbb99635db7c607db`" claim made for this gate was vacuous.
`scripts/_detcheck.py` runs three pairings covering six factions of twenty-two and
**Tyranids appear in none of them**, so the digest cannot see a Tyranid-only
change and reads identical either way. `scripts/_detcheck_wide.py` now gives a
second digest across all twenty-two factions: `f243047dbb6a7f45d64aae66` with the
list on, `91a2c9d431b0f8e85d1712e1` with the kill-switch. The canonical digest is
left untouched, being referenced by every prior wave. **Any gate confined to the
other sixteen factions has never been byte-identity-verified by anything.**

**A bug of mine, caught by its own screen.** `SWEG_FALLBACK_CAPABILITY` screened
+0.92 gated and +0.81 both-sides worse — but the screen measured a defect in the
gate. Legacy eligibility is `role in ("SHOOTY","HEAVY") and not
_is_melee_class(...)`; I wrote `role == "HEAVY" or (has a gun and not
melee-primary)`, making HEAVY unconditional and stripping the task #7 protection
that a melee Knight, Carnifex or Hive Tyrant never Falls Back. The evidence landed
exactly where that predicts: Imperial Knights −9.03 and Chaos Knights −6.33, the
two almost-entirely-HEAVY-melee factions, were the largest movers. Guard now
universal; re-screen outstanding. The mechanism still looks right where it should
— even under the bug, Astra Militarum +4.30 and Death Guard −4.97 both moved
decisively toward real.

**The session's standing lesson, six instances.** Every error was a quantity
defined for one case applied to another: one gate's blast radius quoted for a
different gate; an exclusion counted before the short-circuit that caused it; a
menu's absence read as a list's absence; a parser letting the last block swallow
the module tail; a condition written for gunlines applied to melee heavies; and a
digest covering six factions used to certify twenty-two.

"""

STATE = """### 2026-07-26 (later) — the Tyranid under-pole is closed, and it was the input

**New anchor `sc69a` running.** Production now has `SWEG_TYRANID_LIST_SOURCED`
default-ON. Canonical narrow digest unchanged at `4aab205fbb99635db7c607db` (it
cannot see Tyranid changes — see below); wide digest `f243047dbb6a7f45d64aae66`,
kill-switch `91a2c9d431b0f8e85d1712e1`. Nothing committed.

**Result.** Tyranids +9.49 A-frame (35.9 to 45.4 against a real 47.4) and 31.0 to
44.6 both-sides (against 47.0). Faction error 15.9 to 2.4. Overall gated mean
absolute error 3.21 to 2.85. The number-one residual was an input defect: the
archetype did not field the list it cites. No rule changed.

**Byte-identity coverage was much narrower than assumed.** `_detcheck` covers six
factions of twenty-two and never plays Tyranids, so it could not see this gate at
all and every byte-identical claim about it was vacuous. `_detcheck_wide.py` now
covers all twenty-two. Any faction-scoped gate outside Death Guard, Astra
Militarum, Aeldari, Adeptus Astartes, Orks and T'au Empire has never actually been
verified.

**`SWEG_FALLBACK_CAPABILITY` screened +0.92 worse, but on a bug of mine** — HEAVY
was made unconditionally eligible, stripping the melee-heavy protection, and
Imperial Knights (−9.03) and Chaos Knights (−6.33) duly collapsed. Guard is now
universal; needs a fair re-screen against `sc69a`. Astra Militarum +4.30 and Death
Guard −4.97 moved toward real even under the bug.

**Next.** Re-screen the fixed fall-back gate and `SWEG_CULL_PICK_AWARE` against
`sc69a`. Re-screen `SWEG_MELEE_CHARGE_HOLD` too — it was judged against the wrong
Tyranid army. Then the same source audit for Death Guard (+12.2, no source cited),
Adeptus Astartes (+8.9, declares only 700 of 2000 points) and Leagues of Votann
(+13.0), per task #32.

"""


def prepend(path, mark, text):
    s = open(path, encoding="utf-8").read()
    if mark in s:
        print(f"{path}: already recorded")
        return
    open(path, "w", encoding="utf-8").write(text + s)
    print(f"{path}: updated")


def append(path, mark, text):
    s = open(path, encoding="utf-8").read()
    if mark in s:
        print(f"{path}: already recorded")
        return
    open(path, "a", encoding="utf-8").write(text)
    print(f"{path}: updated")


def main() -> None:
    append("docs/TYRANID_LIST_FIDELITY.md", "## VERDICT", VERDICT)
    prepend("docs/DECISION_LEDGER.md", "## THE TYRANID LIST WAS THE WHOLE PROBLEM",
            LEDGER)
    prepend("docs/CURRENT_STATE.md",
            "### 2026-07-26 (later) — the Tyranid under-pole is closed", STATE)


if __name__ == "__main__":
    main()
