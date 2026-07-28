"""Insert the sc68a seventeen-gate adoption entry at the DECISION_LEDGER head.

Written as a script rather than a shell one-liner because both Bash heredocs and
PowerShell here-strings get intercepted in this environment.

Read-write, idempotent: refuses to insert twice.
"""
from __future__ import annotations

LEDGER = "docs/DECISION_LEDGER.md"
MARKER = "## ⭐⭐ THE ASTRA MILITARUM MEASURING DEFECT (2026-07-25)"

ENTRY = """## ⭐⭐ THE FAITHFUL-ADOPTION WAVE (2026-07-25) — seventeen gates on, and the fidelity-versus-metric fork gets real numbers

Owner ruling: "implement it all". SEVENTEEN default-off gates were flipped
default-on after triage, in three groups, each with its kill-switch retained and
the whole set verified: **all seventeen kill-switches together reproduce the
prior event-log digest `db13417fb7e3b2d47cef9867` exactly**, so nothing changed
except defaults. New production digest `4aab205fbb99635db7c607db`.

GROUP 1, the measurement family (see `docs/MEASUREMENT_DEFECT_AUDIT.md`):
`SWEG_ORDER_AURA_BASEEDGE`, `SWEG_AM_INFANTRY_FIRE`, `SWEG_SQUAD_DAMAGE_FLOOR`,
`SWEG_CHAFF_COMMIT_CAP`, `SWEG_AURA_BASEEDGE`, `SWEG_RANGE_BASEEDGE`.

GROUP 2, Astra Militarum rules the army OWNED and could not use — found by
asking "what rule does this codebase implement but leave switched off?"
(`scripts/_gate_sweep.py`): `SWEG_AM_CADIA_STANDS` (Cadia Stands!),
`SWEG_AM_DUTY_AND_HONOUR` (the Order), `SWEG_CREED_TWO_ORDERS` (Lord Castellan),
`SWEG_REINFORCEMENTS` (the Combined Arms stratagem). Of eighteen default-off
gates with rules-claim citations across all twenty-two factions, SEVEN were
Astra Militarum — by far the most of any faction, and a completely different
angle on the under-pole from anything previously tried.

GROUP 3, other missing mechanics: `SWEG_VOTANN_KAHL_LETHAL`,
`SWEG_EC_DAEMONETTE_FF`, `SWEG_WARP_RIFTS`, `SWEG_OVERWATCH_MOVE`,
`SWEG_ACTION_ECONOMY` (the full Chapter Approved deck), `SWEG_SECONDARY_HANDCAP`
(the real two-active-card limit, which the citations confirm bounds a documented
secondary victory-point over-count), `SWEG_CHALLENGER_GAP_CAPPED` (Challenger
Cards catch-up).

DELIBERATELY NOT FLIPPED, and the distinction is load-bearing: `SWEG_AM_RECON`,
`SWEG_AM_GRIZZLED` and `SWEG_VOTANN_HEARTHBAND` are DETACHMENT CHOICES — turning
them on changes which army is fielded, a list decision, not a fidelity fix.
`SWEG_M4`, `SWEG_MELEE_HOLD_OBJECTIVE` and `SWEG_AM_CHASE_VP` are piloting
heuristics that quote a real rule to justify themselves.
`SWEG_OVERRIDE_MELEE_PRECEDENCE` has a recorded unresolved defect interaction.
"Implement it all" means every faithful MECHANIC, not every switch.

**THE RESULT — `data/_anchor_sc68a_n80_log.json`, N=80: gated mean absolute
error 2.76 -> 3.21 (+0.45 WORSE). But it is a REDISTRIBUTION, not a regression,
and the composition matters far more than the total** (both-sides frame,
`scripts/_config_compare.py`):

* **Death Guard error 14.2 -> 12.2** (61.8 -> 59.8). The number one residual,
  which the counterplay campaign, the durability audits and nine canary
  iterations all failed to move, finally moved — 4.5 points toward reality.
* **Astra Militarum error 11.5 -> 7.5** (33.8 -> 37.8), its best ever.
* Against that, five mid-table factions break: Leagues of Votann 8.4 -> 13.0,
  Adeptus Astartes 4.8 -> 8.9, Necrons 4.1 -> 7.6, Tyranids 12.5 -> 15.9, Chaos
  Knights 1.1 -> 4.4.

**THE STRUCTURAL FINDING, now with numbers on both sides: individually faithful
mechanics can make the calibration WORSE by inflating factions that were already
over-performing.** Two clean cases. (1) `SWEG_RANGE_BASEEDGE` — weapon range
measured base-edge per the core rule the repository already cites and already
applies to Engagement Range — screened +5.5 on Adeptus Astartes alone, an
existing over-pole. (2) `SWEG_VOTANN_KAHL_LETHAL` — Kindred Hero's [LETHAL HITS]
grant, an unambiguous datasheet ability — inflated Leagues of Votann, already
+8.4 over. Neither is a defect in the fix. Both say the faction was
over-performing for a reason the faithful mechanic then amplifies, which is
exactly the sharpened diagnosis the fidelity-first doctrine predicts (the
`SWEG_TERRAIN_DENSE` precedent, adopted at +0.46 on the same argument).

METHOD NOTE for future waves — three instruments lied this session and each was
caught only by checking the CODE rather than the derived signal: a gate sweep
that inferred defaults from the comparison direction reported Fire Overwatch as
disabled (it is on, the line is a guard clause); the chaff cap counted `Unit`
instances (one per MODEL) where Behind Enemy Lines scores per UNIT; and a
confession sweep reported the Aeldari Fate-dice and Battle-Focus over-counts as
live when both were adopted default-on on 2026-07-08 — **citations keep their
pre-fix narrative, the "ADOPTED" note lives in the code comment**.

DECOMPOSITION IN FLIGHT: sixteen-gate arm with `SWEG_RANGE_BASEEDGE=0` to price
the weapon-range share, then kill-switch arms for `SWEG_VOTANN_KAHL_LETHAL` and
the scoring trio. Nothing committed (rule 3).

"""


def main() -> None:
    src = open(LEDGER, encoding="utf-8").read()
    if "THE FAITHFUL-ADOPTION WAVE (2026-07-25)" in src:
        print("entry already present — no change")
        return
    if MARKER not in src:
        print("MARKER NOT FOUND — refusing to guess an insertion point")
        return
    open(LEDGER, "w", encoding="utf-8").write(src.replace(MARKER, ENTRY + MARKER, 1))
    print("ledger entry inserted at head")


if __name__ == "__main__":
    main()
