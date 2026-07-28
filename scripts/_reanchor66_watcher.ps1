# Detached watcher: wait for the sc66a re-anchor eval, then append the symmetrized
# diag_frame (new pole picture) to the summary with a REANCHOR_DONE sentinel.
param([int]$epid)
while (Get-Process -Id $epid -ErrorAction SilentlyContinue) { Start-Sleep -Seconds 25 }
Start-Sleep -Seconds 5
$env:PYTHONHASHSEED = "0"; $env:PYTHONIOENCODING = "utf-8"
$sum = "data/_anchor_sc66a_n40_summary.txt"
if (Test-Path "data/_anchor_sc66a_n40_log.json") {
    "`n===== diag_frame: sc66a (production: leader-attach + dedupe + orders), symmetrized =====" | Out-File $sum -Append -Encoding utf8
    (python -m scripts.diag_frame "data/_anchor_sc66a_n40_log.json" 2>&1) | Out-File $sum -Append -Encoding utf8
    "`n===== paired_delta: sc65a (pre-orders) vs sc66a (orders adopted) =====" | Out-File $sum -Append -Encoding utf8
    (python -m scripts.paired_delta "data/_anchor_sc65a_n40_log.json" "data/_anchor_sc66a_n40_log.json" 2>&1) | Out-File $sum -Append -Encoding utf8
} else {
    "REANCHOR LOG MISSING - eval died." | Out-File $sum -Append -Encoding utf8
    Get-Content "data/_anchor_sc66a_n40.err" -Tail 12 -ErrorAction SilentlyContinue | Out-File $sum -Append -Encoding utf8
}
"REANCHOR_DONE" | Out-File $sum -Append -Encoding utf8
