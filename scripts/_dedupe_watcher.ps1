# Detached watcher: wait for the ON-arm eval (PID 80740) to finish, then run the
# paired_delta join vs sc64a + the symmetrized diag_frame, writing the verdict to
# data/_dedupe_verdict.txt with a VERDICT_DONE sentinel. Survives bash-poll reaping.
while (Get-Process -Id 80740 -ErrorAction SilentlyContinue) { Start-Sleep -Seconds 30 }
Start-Sleep -Seconds 5
$env:PYTHONHASHSEED = "0"
$env:PYTHONIOENCODING = "utf-8"
$out = "data/_dedupe_verdict.txt"
if (Test-Path "data/_dedupe_on_n40_log.json") {
    "===== ON-arm summary table =====" | Out-File $out -Encoding utf8
    Get-Content "data/_dedupe_on_n40.out" -Tail 20 | Out-File $out -Append -Encoding utf8
    "`n===== paired_delta: sc64a (OFF) vs SWEG_LEADER_SQUAD_DEDUPE=1 (ON) =====" | Out-File $out -Append -Encoding utf8
    (python -m scripts.paired_delta "data/_anchor_sc64a_n40_log.json" "data/_dedupe_on_n40_log.json" 2>&1) | Out-File $out -Append -Encoding utf8
    "`n===== diag_frame: dedupe ON, symmetrized per-faction =====" | Out-File $out -Append -Encoding utf8
    (python -m scripts.diag_frame "data/_dedupe_on_n40_log.json" 2>&1) | Out-File $out -Append -Encoding utf8
} else {
    "ON-ARM LOG MISSING - eval died before writing the log." | Out-File $out -Encoding utf8
    "--- stderr tail ---" | Out-File $out -Append -Encoding utf8
    Get-Content "data/_dedupe_on_n40.err" -Tail 12 -ErrorAction SilentlyContinue | Out-File $out -Append -Encoding utf8
}
"VERDICT_DONE" | Out-File $out -Append -Encoding utf8
