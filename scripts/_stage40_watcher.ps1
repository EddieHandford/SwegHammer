# Detached watcher: wait for the seeds-8..39 ON-arm eval to finish, merge with the
# N=8 log into a full N=40 log, then paired_delta vs sc65a + symmetrized diag_frame.
param([int]$epid)
while (Get-Process -Id $epid -ErrorAction SilentlyContinue) { Start-Sleep -Seconds 25 }
Start-Sleep -Seconds 5
$env:PYTHONHASHSEED = "0"; $env:PYTHONIOENCODING = "utf-8"
$out = "data/_stage40_verdict.txt"
if (Test-Path "data/_stage_on_seeds8_39_log.json") {
    (python -m scripts._merge_stage_logs "data/_stage_on_n8_log.json" "data/_stage_on_seeds8_39_log.json" "data/_stage_on_n40_log.json" 2>&1) | Out-File $out -Encoding utf8
    "`n===== paired_delta: sc65a (OFF) vs SWEG_AM_STAGE_FORWARD=1 (ON), N=40 =====" | Out-File $out -Append -Encoding utf8
    (python -m scripts.paired_delta "data/_anchor_sc65a_n40_log.json" "data/_stage_on_n40_log.json" 2>&1) | Out-File $out -Append -Encoding utf8
    "`n===== diag_frame: stage-forward ON, symmetrized =====" | Out-File $out -Append -Encoding utf8
    (python -m scripts.diag_frame "data/_stage_on_n40_log.json" 2>&1) | Out-File $out -Append -Encoding utf8
} else {
    "SEEDS-8..39 LOG MISSING - eval died." | Out-File $out -Encoding utf8
    Get-Content "data/_stage_on_seeds8_39.err" -Tail 12 -ErrorAction SilentlyContinue | Out-File $out -Append -Encoding utf8
}
"VERDICT_DONE" | Out-File $out -Append -Encoding utf8
