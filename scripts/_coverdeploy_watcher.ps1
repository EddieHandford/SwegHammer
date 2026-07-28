# Detached watcher: wait for the cover-deploy ON-arm eval, then paired_delta vs
# sc66a + symmetrized diag_frame -> data/_coverdeploy_verdict.txt with VERDICT_DONE.
param([int]$epid)
while (Get-Process -Id $epid -ErrorAction SilentlyContinue) { Start-Sleep -Seconds 25 }
Start-Sleep -Seconds 5
$env:PYTHONHASHSEED = "0"; $env:PYTHONIOENCODING = "utf-8"
$out = "data/_coverdeploy_verdict.txt"
if (Test-Path "data/_coverdeploy_on_n40_log.json") {
    "===== paired_delta: sc66a (OFF) vs SWEG_COVER_DEPLOY=1 (ON), N=40 =====" | Out-File $out -Encoding utf8
    (python -m scripts.paired_delta "data/_anchor_sc66a_n40_log.json" "data/_coverdeploy_on_n40_log.json" 2>&1) | Out-File $out -Append -Encoding utf8
    "`n===== diag_frame: cover-deploy ON, symmetrized =====" | Out-File $out -Append -Encoding utf8
    (python -m scripts.diag_frame "data/_coverdeploy_on_n40_log.json" 2>&1) | Out-File $out -Append -Encoding utf8
} else {
    "COVERDEPLOY LOG MISSING - eval died." | Out-File $out -Encoding utf8
    Get-Content "data/_coverdeploy_on_n40.err" -Tail 12 -ErrorAction SilentlyContinue | Out-File $out -Append -Encoding utf8
}
"VERDICT_DONE" | Out-File $out -Append -Encoding utf8
