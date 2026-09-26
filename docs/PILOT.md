# TB4 Private Pilot Preparation

IP-59 prepares one coordinator role and one independent target for the first real TB4 pilot without committing deployment secrets.

## Goal

Before IP-60 begins, a private deployment must be able to answer all of these questions without editing public source code:

- Which machine runs WATCHDOG?
- Which machine runs FETCHER?
- Which existing Google Drive folder is the TB4 root?
- Where are local Google OAuth files stored?
- Can the target be awakened with WOL, or is WOL intentionally disabled?
- Can WATCHDOG bootstrap FETCHER through an already-configured SSH host alias, or is SSH bootstrap intentionally disabled?
- Are the public protocol/configuration rules valid?
- Are local prerequisite files and commands present?
- Is there a documented rollback path?

No private answer belongs in this repository.

## Private configuration workflow

Use one private pilot file as the source of deployment truth.

1. Copy `config/examples/pilot.example.toml` to a location outside the repository.
2. Replace every required `replace-at-deploy-time` placeholder.
3. Disable optional WOL/SSH capabilities explicitly when they do not apply.
4. Protect the private file with local operating-system permissions.
5. Install the Google provider dependency:

```sh
python -m pip install -e ".[google]"
```

6. Perform the one explicit local OAuth authorization:

```sh
python tools/authorize_drive.py --config /private/path/pilot.toml
```

7. Run the sanitized pilot preflight:

```sh
python tools/preflight.py --config /private/path/pilot.toml
```

8. Generate role-specific service configs in a private directory:

```sh
python tools/prepare_pilot.py \
  --config /private/path/pilot.toml \
  --output-dir /private/tb4-generated
```

This writes `watchdog.toml` and `fetcher.toml` from the same target/root identity and applies private POSIX permissions where supported.

9. Bootstrap the canonical TB4 tree inside the explicitly selected existing Drive folder:

```sh
python tools/bootstrap_drive.py --config /private/path/pilot.toml
```

The bootstrap operation is idempotent and never creates a second TB4 root.

10. Copy each generated role config to the appropriate host private configuration location, then use the platform installation/check procedure.

The preflight and setup tools deliberately avoid echoing configured root IDs, addresses, MAC addresses, SSH aliases, credential paths, or credential contents into public evidence.

## Required readiness areas

### Public specification

The repository protocol validator must pass before private checks are considered meaningful.

### Drive

Required:

- an explicitly selected existing TB4 root ID;
- local OAuth client-secrets file;
- local authorized-user token file for non-interactive service startup.

The root is never created implicitly by repair/bootstrap code.

### WATCHDOG identity

A private deployment assigns a stable TB4 device ID to the coordinator. Public docs use `watchdog-host`; deployments should use their own private stable identity.

### Target identity

A private deployment assigns a stable TB4 device ID to the target independently of DHCP address or current hostname.

### Wake-on-LAN

If enabled, a MAC address is required.

If disabled, preflight records the capability as intentionally unavailable rather than as an error.

### SSH bootstrap

If enabled, use an existing SSH host alias from local SSH configuration. The private pilot config stores the alias, not passwords or private keys.

SSH remains a FETCHER bootstrap mechanism. It is not the normal TB4 command transport.

## Timing profile

The default configuration is suitable for the first small-LAN pilot:

- known-device local probe: 20 s;
- unchanged remote publish: 300 s;
- stray scan: 600 s;
- active heartbeat: 10 s;
- active stale threshold: 35 s;
- WOL initial wait: 10 s;
- wake probe: 5 s;
- wake deadline: 90 s;
- FETCHER idle exit: 600 s.

Do not tune these merely to make a failing pilot pass. First determine whether the failure is transport latency, boot time, network reachability, OAuth, service startup, or protocol behavior.

## Preflight status meanings

`PASS`
: Required check is satisfied.

`OPTIONAL`
: Capability is intentionally disabled and the pilot can continue without testing that scenario.

`MISSING`
: Required private value/file/capability is absent.

`INVALID`
: Value exists but violates the expected structure.

`BLOCKED`
: A prerequisite check failed, making a dependent check meaningless.

Preflight exits 0 only when all required checks pass.

## Rollback

### WATCHDOG Linux service

```sh
sudo systemctl disable --now tb4-watchdog.service
sudo rm -f /etc/systemd/system/tb4-watchdog.service
sudo systemctl daemon-reload
```

Private configuration and OAuth files should be removed separately only when intentionally decommissioning the deployment.

### FETCHER Linux service

```sh
sudo systemctl disable --now tb4-fetcher.service
sudo rm -f /etc/systemd/system/tb4-fetcher.service
sudo systemctl daemon-reload
```

### FETCHER Windows service

Use the repository removal helper:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\packaging\windows\remove-fetcher.ps1
```

### Drive rollback

Do **not** recursively delete the TB4 root as an automatic rollback action.

Stop TB4 services first. Preserve the root for inspection until the pilot state is understood. If cleanup is later desired, perform it as an explicit maintenance action after verifying no active operation or evidence is required.

## Public pilot evidence

IP-60 public evidence may record:

- tested TB4 commit;
- scenario name;
- PASS/FAIL;
- sanitized failure class;
- timing observations that do not identify private infrastructure.

It must not contain private IPs, MAC addresses, SSH aliases, root IDs, credential paths, token material, or user/account identifiers.
