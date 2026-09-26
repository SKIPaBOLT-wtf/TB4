# Linux service packaging

IP-51 defines the stable Linux service wrapper. Full runtime composition is verified later by integration and pilot steps.

## Paths

Public code and unit files contain no credentials.

- WATCHDOG config: `/etc/tb4/watchdog.toml`
- FETCHER config: `/etc/tb4/fetcher.toml`
- optional environment file: `/etc/tb4/tb4.env`
- systemd units: `/etc/systemd/system/tb4-*.service`

Secrets and deployment-specific values stay outside the public repository.

## Dedicated service account

Create a non-login account appropriate for the distribution, for example:

```sh
sudo useradd --system --home-dir /var/lib/tb4 --create-home --shell /usr/sbin/nologin tb4
sudo install -d -o tb4 -g tb4 -m 0700 /etc/tb4 /var/lib/tb4
```

Do not grant sudo merely to make TB4 convenient. Add only the local permissions a deployment actually requires.

## Install package

Install TB4 into a system-managed Python environment or virtual environment and ensure the `tb4` console script is available to systemd.

The committed units use `/usr/bin/env tb4` so they do not embed a machine-specific Python path.

## Configuration/runtime check

Before enabling a service:

```sh
tb4 watchdog --check --config /etc/tb4/watchdog.toml
tb4 fetcher --check --config /etc/tb4/fetcher.toml
```

These commands parse the role configuration, validate bounded deployment settings, and resolve the production runtime factory. They deliberately do not authenticate to Google Drive, send network probes, wake a host, or execute a job. End-to-end readiness is proven by the private pilot, not by a local config check.

## Install units

```sh
sudo install -m 0644 packaging/systemd/tb4-watchdog.service /etc/systemd/system/
sudo install -m 0644 packaging/systemd/tb4-fetcher.service /etc/systemd/system/
sudo systemctl daemon-reload
```

Then enable only roles intended for that host:

```sh
sudo systemctl enable --now tb4-watchdog.service
# or
sudo systemctl enable --now tb4-fetcher.service
```

Inspect with:

```sh
systemctl status tb4-watchdog.service
journalctl -u tb4-watchdog.service
```

## Shutdown contract

systemd sends SIGTERM. `ServiceHost` converts SIGTERM/SIGINT into a shared stop event and runs registered cleanup callbacks exactly once in reverse registration order.

FETCHER combines the service stop event with STOP_BALL cancellation while a child process is active, so SIGTERM participates in the same bounded process-tree shutdown path. `KillMode=mixed` remains a final systemd safety net for processes remaining in the service cgroup after the graceful stop interval.

## Security boundary

The units intentionally avoid embedding credentials or private paths. More aggressive systemd sandboxing is deferred to the security-hardening step because FETCHER may legitimately need deployment-specific filesystem access.
