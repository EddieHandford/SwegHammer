# Detached watcher: wait for the orders-issuer ON-arm eval, then paired_delta vs
# sc65a + symmetrized diag_frame -> data/_orders_verdict.txt with VERDICT_DONE.
param([int]$epid)
while (Get-Process -Id $epid -ErrorAction SilentlyContinue) { Start-Sleep -Seconds 25 }
Start-Sleep -Seconds 5
$env:PYTHONHASHSEED = "0"; $env:PYTHONIOENCODING = "utf-8"
$out = "data/_orders_verdict.txt"
if (Test-Path "data/_orders_on_n40_log.json") {
    "===== ON-arm summary tail =====" | Out-File $out -Encoding utf8
    Get-Content "data/_orders_on_n40.out" -Tail 6 | Out-File $out -Append -Encoding utf8
    "`n===== paired_delta: sc65a (OFF) vs SWEG_ORDER_ISSUER_BY_SQUAD=1 (ON), N=40 =====" | Out-File $out -Append -Encoding utf8
    (python -m scripts.paired_delta "data/_anchor_sc65a_n40_log.json" "data/_orders_on_n40_log.json" 2>&1) | Out-File $out -Append -Encoding utf8
    "`n===== diag_frame: orders-issuer ON, symmetrized =====" | Out-File $out -Append -Encoding utf8
    (python -m scripts.diag_frame "data/_orders_on_n40_log.json" 2>&1) | Out-File $out -Append -Encoding utf8
} else {
    "ON-ARM LOG MISSING - eval died." | Out-File $out -Encoding utf8
    Get-Content "data/_orders_on_n40.err" -Tail 12 -ErrorAction SilentlyContinue | Out-File $out -Append -Encoding utf8
}
"VERDICT_DONE" | Out-File $out -Append -Encoding utf8
