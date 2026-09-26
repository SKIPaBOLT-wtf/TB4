param(
    [string]$Python = "python",
    [string]$ServiceAccount = "NT AUTHORITY\LocalService"
)

$ErrorActionPreference = "Stop"

& $Python -m tb4.platform.windows_service --startup auto --username $ServiceAccount install

if ($LASTEXITCODE -ne 0) {
    throw "TB4 FETCHER service installation failed with exit code $LASTEXITCODE"
}

Write-Host "Installed TB4Fetcher. Configure C:\ProgramData\TB4\fetcher.toml before starting the service."
