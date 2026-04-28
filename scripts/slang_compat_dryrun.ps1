# Step-A2 dry-run: compile Falcor's entry-point shaders against the upgraded
# Slang compiler (2026.5.2) to estimate the breaking surface from the 2024.1.34 → 2026.5.2 jump.
# Skips header-only .slang modules; only targets files with shader stage suffixes.

param(
    [string]$Repo = "E:\GitSource\Falcor",
    [int]$MaxFiles = 0,
    [string]$LogDir = "$env:TEMP\falcor_slang_dryrun"
)

$slangc = Join-Path $Repo "external\packman\slang\bin\slangc.exe"
if (-not (Test-Path $slangc)) { throw "slangc not found at $slangc" }

$includes = @(
    (Join-Path $Repo "Source"),
    (Join-Path $Repo "Source\Falcor"),
    (Join-Path $Repo "Source\Falcor\Shaders")
)
$incArgs = @()
foreach ($i in $includes) { $incArgs += "-I"; $incArgs += $i }

$patterns = @("*.cs.slang","*.rt.slang","*.3d.slang","*.ps.slang","*.vs.slang","*.gs.slang")
$files = @()
foreach ($p in $patterns) {
    $files += Get-ChildItem -Path (Join-Path $Repo "Source") -Recurse -Filter $p -File
}
$files = $files | Where-Object { $_.FullName -notmatch "_coopvec_precheck" }
if ($MaxFiles -gt 0) { $files = $files | Select-Object -First $MaxFiles }

if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }

$results = @()
$pass = 0; $fail = 0
$start = Get-Date
foreach ($f in $files) {
    $rel = $f.FullName.Substring($Repo.Length + 1)
    $outFile = Join-Path $LogDir "_tmp_out.spv"
    $args = @($incArgs) + @("-target","spirv","-profile","glsl_460","-o",$outFile,$f.FullName)
    $output = & $slangc @args 2>&1 | Out-String
    $ok = ($LASTEXITCODE -eq 0)
    if ($ok) { $pass++ } else { $fail++ }
    $results += [pscustomobject]@{ File=$rel; OK=$ok; Output=$output }
}
$elapsed = ((Get-Date) - $start).TotalSeconds

Write-Output ""
Write-Output "===== Slang dry-run summary ====="
Write-Output "Slang version: 2026.5.2"
Write-Output ("Files: {0} | Pass: {1} | Fail: {2} | Elapsed: {3:F1}s" -f $files.Count, $pass, $fail, $elapsed)
Write-Output ""

# Group failures by first-error fingerprint
$failGroups = @{}
foreach ($r in ($results | Where-Object { -not $_.OK })) {
    $first = ($r.Output -split "`n" | Where-Object { $_ -match "error" } | Select-Object -First 1) -replace '\\u001b\[[0-9;]*m',''
    $first = ($first -replace '^\s*','').Substring(0, [Math]::Min(180, $first.Length))
    if (-not $failGroups.ContainsKey($first)) { $failGroups[$first] = @() }
    $failGroups[$first] += $r.File
}

Write-Output "===== Failures by first-error fingerprint ====="
foreach ($k in ($failGroups.Keys | Sort-Object { -$failGroups[$_].Count })) {
    Write-Output ("[{0,3}x] {1}" -f $failGroups[$k].Count, $k)
    foreach ($f in ($failGroups[$k] | Select-Object -First 3)) { Write-Output "        $f" }
    if ($failGroups[$k].Count -gt 3) { Write-Output "        ... and $($failGroups[$k].Count - 3) more" }
}

# Save full logs for failed files
foreach ($r in ($results | Where-Object { -not $_.OK })) {
    $logName = ($r.File -replace '[\\/:]','_') + ".log"
    Set-Content -Path (Join-Path $LogDir $logName) -Value $r.Output
}
Write-Output ""
Write-Output "Full logs for failed files: $LogDir"
