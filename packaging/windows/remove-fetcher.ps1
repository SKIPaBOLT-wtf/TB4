param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"

& $Python -m tb4.platform.windows_service stop
$stopCode = $LASTEXITCODE

& $Python -m tb4.platform.windows_service remove
if ($LASTEXITCODE -ne 0) {
    throw "TB4 FETCHER service removal failed with exit code $LASTEXITCODE"
}

if ($stopCode -ne 0) {
    Write-Warning "Service stop returned exit code $stopCode; remove still completed."
}
