"""Reconstruct the sc52a field-weighted per-faction pole from the anchor log,
exactly as evaluate_vs_meta.run_matrix aggregates it (position-A-only per
ordered pair, weighted by each opponent's real Warp Friends game count).
Validate against the brief's stated poles, then emit the full 22-faction vector.
"""
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FACTIONS = [
    "Adeptus Astartes", "Necrons", "Aeldari", "Tyranids", "Orks",
    "T'au Empire", "Death Guard", "Adeptus Custodes", "Thousand Sons",
    "Leagues of Votann", "Chaos Space Marines", "World Eaters",
    "Emperor's Children", "Chaos Daemons", "Astra Militarum",
    "Adeptus Mechanicus", "Adepta Sororitas", "Grey Knights", "Drukhari",
    "Genestealer Cults", "Imperial Knights", "Chaos Knights",
]
BRIEF = {  # sim - real, from the task
    "Death Guard": 22.5, "Imperial Knights": 15.7, "Chaos Knights": 11.1,
    "Aeldari": 10.5, "Chaos Space Marines": 8.4, "Adeptus Custodes": 7.5,
    "Astra Militarum": -12.4, "Orks": -8.7, "Genestealer Cults": -7.0,
}

log = json.load(open(ROOT / "data" / "_anchor_sc52a_n80_log.json"))
real = json.load(open(ROOT / "data" / "warpfriends_rolling.json"))["factions"]
games_wt = {f: int(real[f]["total_games"]) for f in FACTIONS}
real_wr = {f: float(real[f]["win_rate"]) for f in FACTIONS}

n = log["n"]
# position-A wins per ordered pair
pairA = defaultdict(Counter)
for a, b, s, w in log["games"]:
    if w is not None:
        pairA[(a, b)][w] += 1

pair_wr = {}
for a in FACTIONS:
    for b in FACTIONS:
        if a == b:
            continue
        c = pairA.get((a, b), Counter())
        tot = c["A"] + c["B"]
        pair_wr[(a, b)] = 100.0 * c["A"] / tot if tot else float("nan")

sim_fw = {}
for f in FACTIONS:
    num = den = 0.0
    for o in FACTIONS:
        if o == f:
            continue
        wr = pair_wr[(f, o)]
        if wr != wr:
            continue
        num += wr * games_wt[o]
        den += games_wt[o]
    sim_fw[f] = num / den

poles = {f: sim_fw[f] - real_wr[f] for f in FACTIONS}

print("Field-weighted (position-A) reconstruction vs brief:")
print("%-22s %8s %8s %8s   %s" % ("faction", "simFW", "real", "pole", "brief"))
for f in FACTIONS:
    b = BRIEF.get(f)
    bs = "%+6.1f" % b if b is not None else "   -"
    flag = ""
    if b is not None and abs(poles[f] - b) > 1.5:
        flag = "  <-- MISMATCH"
    print("%-22s %8.1f %8.1f %+8.1f   %s%s" % (f, sim_fw[f], real_wr[f], poles[f], bs, flag))

json.dump({f: poles[f] for f in FACTIONS},
          open(ROOT / "scripts" / "_fill_audit_poles_out.json", "w"), indent=2)
print("\nn per pair =", n)
