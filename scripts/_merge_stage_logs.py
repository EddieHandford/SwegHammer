"""Merge two disjoint-seed-window game logs into one n=40 log for paired_delta.
Usage: python -m scripts._merge_stage_logs <log_a> <log_b> <out>"""
import json, sys
a = json.load(open(sys.argv[1], encoding="utf-8"))
b = json.load(open(sys.argv[2], encoding="utf-8"))
out = {"n": 40, "games": a["games"] + b["games"]}
json.dump(out, open(sys.argv[3], "w", encoding="utf-8"))
print(f"merged {len(a['games'])}+{len(b['games'])}={len(out['games'])} games -> {sys.argv[3]} (n=40)")
