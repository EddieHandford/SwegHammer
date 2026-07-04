#!/usr/bin/env bash
# READ-ONLY driver: replay the Orks / Genestealer Cults cells from sc52a twice
# (committed defaults == sc52a ON, and the five kill-switches off == sc51a), plus
# a Sororitas sample for the elite action-conversion comparison. Writes scratch
# JSON to data/_horde_*.json (never committed).
set -e
cd "$(dirname "$0")/.."
export PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 SWEG_WORKERS=14
LOG="/c/Users/Jake/AppData/Local/Temp/claude/C--Users-Jake-Claude/b459ab07-c175-4820-8f10-ac17a5b125b1/scratchpad/runall.log"
echo "== START $(date) ==" > "$LOG"

run() { echo "-- $1 $(date) --" >> "$LOG"; python -m scripts._horde_conv_replay "$2" "$3" "$4" >> "$LOG" 2>&1; }

# ON (sc52a, all six fixes default-on)
unset SWEG_TAC_SHEDDING SWEG_ACTIONS_HAND_GATED SWEG_TACDECK_FULL SWEG_FIXED_POOL_FULL SWEG_CP_PER_COMMAND_PHASE
run "ORKS_ON"  "Orks"               "data/_horde_orks_on.json"   0
run "GSC_ON"   "Genestealer Cults"  "data/_horde_gsc_on.json"    0
run "SORO_ON"  "Adepta Sororitas"   "data/_horde_soro_on.json"   800

# OFF (== sc51a substrate: the five secondary-economy kill-switches off)
export SWEG_TAC_SHEDDING=0 SWEG_ACTIONS_HAND_GATED=0 SWEG_TACDECK_FULL=0 SWEG_FIXED_POOL_FULL=0 SWEG_CP_PER_COMMAND_PHASE=0
run "ORKS_OFF" "Orks"               "data/_horde_orks_off.json"  0
run "GSC_OFF"  "Genestealer Cults"  "data/_horde_gsc_off.json"   0
echo "== DONE $(date) ==" >> "$LOG"
