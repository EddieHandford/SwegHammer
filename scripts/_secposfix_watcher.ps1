# Detached watcher: wait for the secondary-posfix ON eval, then paired_delta vs sc67a
# + diag_frame + a secondary-VP re-measure (diag_signatures with the flag on).
param([int]$epid)
while (Get-Process -Id $epid -ErrorAction SilentlyContinue) { Start-Sleep -Seconds 25 }
Start-Sleep -Seconds 5
$env:PYTHONHASHSEED = "0"; $env:PYTHONIOENCODING = "utf-8"
$out = "data/_secposfix_verdict.txt"
if (Test-Path "data/_secposfix_on_n40_log.json") {
    "===== paired_delta: sc67a (OFF) vs SWEG_SECONDARY_POSFIX=1 (ON), N=40 =====" | Out-File $out -Encoding utf8
    (python -m scripts.paired_delta "data/_anchor_sc67a_n80_log.json" "data/_secposfix_on_n40_log.json" 2>&1) | Out-File $out -Append -Encoding utf8
    "`n===== diag_frame: secondary-posfix ON, symmetrized =====" | Out-File $out -Append -Encoding utf8
    (python -m scripts.diag_frame "data/_secposfix_on_n40_log.json" 2>&1) | Out-File $out -Append -Encoding utf8
    "`n===== secondary-VP signature ON (target ~22.7) =====" | Out-File $out -Append -Encoding utf8
    $env:SWEG_SECONDARY_POSFIX = "1"
    (python -m scripts.diag_signatures --pairs 12 --seeds 3 2>&1 | Select-String -Pattern "secondary victory|Sim:|Real:") | Out-File $out -Append -Encoding utf8
} else {
    "SECPOSFIX LOG MISSING - eval died." | Out-File $out -Encoding utf8
    Get-Content "data/_secposfix_on_n40.err" -Tail 12 -ErrorAction SilentlyContinue | Out-File $out -Append -Encoding utf8
}
"VERDICT_DONE" | Out-File $out -Append -Encoding utf8
