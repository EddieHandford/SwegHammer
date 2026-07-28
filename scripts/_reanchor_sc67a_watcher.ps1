# Detached watcher: wait for the sc67a re-anchor eval (new dense-terrain default),
# then capture summary + symmetrized diag_frame -> data/_anchor_sc67a_record.txt.
param([int]$epid)
while (Get-Process -Id $epid -ErrorAction SilentlyContinue) { Start-Sleep -Seconds 25 }
Start-Sleep -Seconds 5
$env:PYTHONHASHSEED = "0"; $env:PYTHONIOENCODING = "utf-8"
$out = "data/_anchor_sc67a_record.txt"
if (Test-Path "data/_anchor_sc67a_n80_log.json") {
    "===== sc67a RE-ANCHOR (dense-terrain default) summary =====" | Out-File $out -Encoding utf8
    Get-Content "data/_anchor_sc67a_n80.out" -Tail 32 | Out-File $out -Append -Encoding utf8
    "`n===== diag_frame: sc67a, symmetrized =====" | Out-File $out -Append -Encoding utf8
    (python -m scripts.diag_frame "data/_anchor_sc67a_n80_log.json" 2>&1) | Out-File $out -Append -Encoding utf8
} else {
    "SC67A LOG MISSING - re-anchor eval died." | Out-File $out -Encoding utf8
    Get-Content "data/_anchor_sc67a_n80.err" -Tail 12 -ErrorAction SilentlyContinue | Out-File $out -Append -Encoding utf8
}
"VERDICT_DONE" | Out-File $out -Append -Encoding utf8
