# Detached watcher: wait for the stage-forward ON-arm eval to finish, then run
# paired_delta vs sc65a + symmetrized diag_frame, writing the verdict with a
# VERDICT_DONE sentinel. $epid passed as arg 0.
param([int]$epid)
while (Get-Process -Id $epid -ErrorAction SilentlyContinue) { Start-Sleep -Seconds 20 }
Start-Sleep -Seconds 5
$env:PYTHONHASHSEED = "0"; $env:PYTHONIOENCODING = "utf-8"
$out = "data/_stage_verdict.txt"
if (Test-Path "data/_stage_on_n8_log.json") {
    "===== ON-arm summary tail =====" | Out-File $out -Encoding utf8
    Get-Content "data/_stage_on_n8.out" -Tail 8 | Out-File $out -Append -Encoding utf8
    "`n===== paired_delta: sc65a (OFF) vs SWEG_AM_STAGE_FORWARD=1 (ON), N=8 =====" | Out-File $out -Append -Encoding utf8
    (python -m scripts.paired_delta "data/_anchor_sc65a_n40_log.json" "data/_stage_on_n8_log.json" 2>&1) | Out-File $out -Append -Encoding utf8
} else {
    "ON-ARM LOG MISSING - eval died." | Out-File $out -Encoding utf8
    Get-Content "data/_stage_on_n8.err" -Tail 12 -ErrorAction SilentlyContinue | Out-File $out -Append -Encoding utf8
}
"VERDICT_DONE" | Out-File $out -Append -Encoding utf8
