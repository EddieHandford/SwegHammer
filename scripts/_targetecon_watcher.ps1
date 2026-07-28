# Detached watcher: wait for the target-economics ON-arm eval, then paired_delta vs
# sc67a (N=80 anchor, pairs on the overlapping 40 seeds) + diag_frame.
param([int]$epid)
while (Get-Process -Id $epid -ErrorAction SilentlyContinue) { Start-Sleep -Seconds 25 }
Start-Sleep -Seconds 5
$env:PYTHONHASHSEED = "0"; $env:PYTHONIOENCODING = "utf-8"
$out = "data/_targetecon_verdict.txt"
if (Test-Path "data/_targetecon_on_n40_log.json") {
    "===== paired_delta: sc67a (OFF) vs SWEG_TARGET_ECONOMICS=1 (ON), N=40 =====" | Out-File $out -Encoding utf8
    (python -m scripts.paired_delta "data/_anchor_sc67a_n80_log.json" "data/_targetecon_on_n40_log.json" 2>&1) | Out-File $out -Append -Encoding utf8
    "`n===== diag_frame: target-economics ON, symmetrized =====" | Out-File $out -Append -Encoding utf8
    (python -m scripts.diag_frame "data/_targetecon_on_n40_log.json" 2>&1) | Out-File $out -Append -Encoding utf8
} else {
    "TARGETECON LOG MISSING - eval died." | Out-File $out -Encoding utf8
    Get-Content "data/_targetecon_on_n40.err" -Tail 12 -ErrorAction SilentlyContinue | Out-File $out -Append -Encoding utf8
}
"VERDICT_DONE" | Out-File $out -Append -Encoding utf8
