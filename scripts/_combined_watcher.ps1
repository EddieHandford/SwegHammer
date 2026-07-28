# Detached watcher: wait for the combined-counterplay ON eval, then paired_delta vs sc67a + diag_frame.
param([int]$epid)
while (Get-Process -Id $epid -ErrorAction SilentlyContinue) { Start-Sleep -Seconds 25 }
Start-Sleep -Seconds 5
$env:PYTHONHASHSEED = "0"; $env:PYTHONIOENCODING = "utf-8"
$out = "data/_combined_verdict.txt"
if (Test-Path "data/_combined_on_n40_log.json") {
    "===== paired_delta: sc67a (OFF) vs [DEVWOUND+SECPOSFIX+MOBDENY]=1 (ON), N=40 =====" | Out-File $out -Encoding utf8
    (python -m scripts.paired_delta "data/_anchor_sc67a_n80_log.json" "data/_combined_on_n40_log.json" 2>&1) | Out-File $out -Append -Encoding utf8
    "`n===== diag_frame: combined ON, symmetrized =====" | Out-File $out -Append -Encoding utf8
    (python -m scripts.diag_frame "data/_combined_on_n40_log.json" 2>&1) | Out-File $out -Append -Encoding utf8
} else {
    "COMBINED LOG MISSING - eval died." | Out-File $out -Encoding utf8
    Get-Content "data/_combined_on_n40.err" -Tail 12 -ErrorAction SilentlyContinue | Out-File $out -Append -Encoding utf8
}
"VERDICT_DONE" | Out-File $out -Append -Encoding utf8
