"""Correlate each durability-per-point metric against the sc52a field-weighted
pole, for the FULL army, the SEED slice, and the FILL slice separately.
Reads the census + pole reconstruction outputs. Hand-rolled Pearson/Spearman
(no scipy dependency). READ-ONLY.
"""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
census = json.load(open(ROOT / "scripts" / "_fill_audit_census_out.json"))
poles = json.load(open(ROOT / "scripts" / "_fill_audit_poles_out.json"))

FACS = [f for f in census]  # keep census order


def pearson(xs, ys):
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return 0.0
    return sxy / math.sqrt(sxx * syy)


def ranks(vs):
    order = sorted(range(len(vs)), key=lambda i: vs[i])
    r = [0.0] * len(vs)
    i = 0
    while i < len(vs):
        j = i
        while j + 1 < len(vs) and vs[order[j + 1]] == vs[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


def spearman(xs, ys):
    return pearson(ranks(xs), ranks(ys))


def pval(r, n):
    if abs(r) >= 1.0:
        return 0.0
    t = r * math.sqrt((n - 2) / (1 - r * r))
    # two-sided p via a crude normal approx of the t (n=22 -> df=20, ok-ish)
    z = abs(t)
    p = math.erfc(z / math.sqrt(2))
    return p


poles_v = [poles[f] for f in FACS]
n = len(FACS)

print("=" * 78)
print("Correlation of durability-per-point metrics vs sc52a field-weighted pole")
print("N = %d factions" % n)
print("=" * 78)
metrics = [
    ("wpp", "wounds / point"),
    ("wt_T", "wounds-weighted Toughness"),
    ("brick_share", "durable-brick point share (T>=10 or W>=15)"),
    ("inv_cov", "invuln wound coverage"),
    ("fnp_cov", "feel-no-pain wound coverage"),
]
for part in ("full", "seed", "fill"):
    print("\n--- %s slice ---" % part.upper())
    print("%-42s %7s %7s %8s" % ("metric", "Pear r", "Spear", "p(Pear)"))
    for key, label in metrics:
        xs = [census[f][part][key] for f in FACS]
        r = pearson(xs, poles_v)
        rho = spearman(xs, poles_v)
        p = pval(r, n)
        print("%-42s %+7.3f %+7.3f %8.4f" % (label, r, rho, p))

# Also: seed durability vs fill durability -- is fill MORE durable than seed?
print("\n" + "=" * 78)
print("Per-faction table (sorted by pole desc)")
print("=" * 78)
hdr = ("faction", "pole", "wpp", "wtT", "brick", "inv", "fnp", "sdfrac",
       "f.wpp", "f.wtT", "f.brk")
print("%-20s %6s %6s %5s %5s %5s %5s %5s | %6s %5s %5s" % hdr)
for f in sorted(FACS, key=lambda f: -poles[f]):
    c = census[f]
    print("%-20s %+6.1f %6.4f %5.1f %5.2f %5.2f %5.2f %5.2f | %6.4f %5.1f %5.2f" % (
        f, poles[f], c["full"]["wpp"], c["full"]["wt_T"], c["full"]["brick_share"],
        c["full"]["inv_cov"], c["full"]["fnp_cov"], c["seed_pts_frac"],
        c["fill"]["wpp"], c["fill"]["wt_T"], c["fill"]["brick_share"]))

# Split factions into over/under buckets and print mean durability
print("\n" + "=" * 78)
over = [f for f in FACS if poles[f] >= 6.0]
under = [f for f in FACS if poles[f] <= -6.0]
mid = [f for f in FACS if -6.0 < poles[f] < 6.0]
def bmean(bucket, part, key):
    return sum(census[f][part][key] for f in bucket) / len(bucket) if bucket else 0.0
print("Bucket means (over pole>=+6, under<=-6, mid otherwise):")
print("%-8s %3s %7s %7s %8s %7s %7s" % ("bucket", "n", "wpp", "wtT", "brick", "inv", "fnp"))
for name, bk in (("OVER", over), ("MID", mid), ("UNDER", under)):
    print("%-8s %3d %7.4f %7.1f %8.2f %7.2f %7.2f" % (
        name, len(bk), bmean(bk, "full", "wpp"), bmean(bk, "full", "wt_T"),
        bmean(bk, "full", "brick_share"), bmean(bk, "full", "inv_cov"),
        bmean(bk, "full", "fnp_cov")))
print("\nOVER:", over)
print("UNDER:", under)
