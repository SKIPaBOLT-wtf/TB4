# Windows service packaging

IP-52 defines the Windows service/process-lifecycle boundary for FETCHER. Complete runtime composition is verified by later integration and pilot steps.

## Requirements

- Python 3.11 or newer;
- TB4 installed with the Windows extra: pip install "tb4[windows]";
- service installation from an elevated terminal;
- deployment configuration stored outside the repository.

Default configuration path:

    C:\ProgramData\TB4\fetcher.toml

A private deployment may override it with the service environment variable TB4_FETCHER_CONFIG.

## Service implementation

TB4 uses pywin32 ServiceFramework rather than shipping an additional service-wrapper executable.

Service name:

    TB4Fetcher

The committed install helper uses the built-in NT AUTHORITY\LocalService account by default. No password is committed for that built-in identity.

## Install

From an elevated PowerShell:

    powershell -NoProfile -ExecutionPolicy Bypass -File .\packaging\windows\install-fetcher.ps1

Direct pywin32 command path:

    python -m tb4.platform.windows_service --startup auto --username "NT AUTHORITY\LocalService" install
    python -m tb4.platform.windows_service start
    python -m tb4.platform.windows_service status

## Remove

    powershell -NoProfile -ExecutionPolicy Bypass -File .\packaging\windows\remove-fetcher.ps1

## No interactive profile dependency

TB4 script artifacts are materialized as local files. PowerShell execution uses:

    powershell.exe -NoLogo -NoProfile -NonInteractive -File <script>

or the equivalent pwsh command. Large scripts are not embedded in the Windows service command line.

## Process-tree shutdown

FETCHER child processes are started in a new process group. Cancellation and timeout use taskkill with an argument vector and /T so descendants are addressed as a tree. If the first tree termination does not finish within the grace period, TB4 retries with /F.

No shell string is constructed for process-tree cleanup.

## Clean-host verification checklist

1. Install Python and TB4 with the windows extra.
2. Create C:\ProgramData\TB4\fetcher.toml with private deployment settings.
3. Install the service from an elevated PowerShell.
4. Confirm TB4Fetcher appears in Service Control Manager.
5. Confirm the service can start before an interactive user login.
6. Confirm a script artifact runs with -NoProfile -NonInteractive -File.
7. Confirm stopping or cancelling a test process also removes its child tree.
8. Confirm no private credential is present in repository/service definitions.

Items 5–7 are integration/pilot assertions and are not claimed by static packaging tests alone.
