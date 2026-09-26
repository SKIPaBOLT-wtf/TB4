# IP-52 Evidence E-001 — Windows service packaging

## Verified capability

The Windows FETCHER packaging/process-lifecycle boundary is implemented.

## Evidence

- Native pywin32 ServiceFramework wrapper is defined for TB4Fetcher.
- Default private config path is C:\ProgramData\TB4\fetcher.toml.
- Installation helper defaults to the built-in NT AUTHORITY\LocalService identity without embedding a password.
- PowerShell script artifacts execute through local files with -NoProfile -NonInteractive -File.
- Windows child-process cleanup uses taskkill /T with argv arguments and escalates to /F only after the grace period.
- No giant shell command is constructed for process-tree termination.
- GitHub Actions run 36268997860 passed on the repository head.
- Full suite result: **491 passed in 8.22s**.

Workflow: https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36268997860

Per amendment A-001, full runtime composition and pre-login pilot proof remain owned by later integration/pilot steps.
