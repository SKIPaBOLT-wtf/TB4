# RP-018/A001 reviewed validation

Final source: b04b4747ab4261b57d04840cbb8535cd020e8195.
Adapter source: 6d03401e16cd688687abc0bd6e92d4b37c519b8e.
Negative fixture correction: 0ca05f347f5a80019ae75aa6d97bf5aadba84aa6.
Final validation head: f12ef57e9b0a18cb883dda7a80586aa8dbd5f72b.
Base: bb7384669275e0294dc5d46c16d051a54632e054.
No live deployment, migration, existing profile, home host or credential mutation.

## Scope and invariant review

This is the optional control-authority adapter, matching the RP015 native Docs
control scope. It does not implement the old rename/move DriveBackend or claim
artifact payload provisioning/IO (RP019/040/048). Default Docs remains selected.
FolderStore opens existing pinned local files on Linux ext4/xfs, validates the
private root/files/schema/domain and canonical R2 document, uses exclusive
PERSIST/FULL SQLite transactions, increments revision under CAS and requires
client readback. No request can select another path/root, create/delete an
object, choose a command or fall back to local sync. The helper is per-call,
not a second coordination service or a second authority.

C1: real independent SQLite connections/processes and two SSH clients establish
strict revision ownership, readback and fixed filenames/object identities.
Hot-journal test observes dirty database pages before killing only its owned
writer, then reads the exact last committed revision/body without changing
object identities. Mode/size/schema/identity/permissions are checked. A busy
loser is not mistaken for a stale-revision rejection: the stale CAS is separately
rejected after release. Power loss and hostile same-account administration are
explicitly outside this proof.

C2: same RP015 terminal publication/reconcile and RP016 leadership code exercised
through folder protocol, subprocess helper and actual loopback OpenSSH. Stale
record permits immediate first-CAS takeover and preserves UNKNOWN target work;
forced request stops incumbent checks and transfers without peer/sink ACK.
Actual endpoint disconnect/restart, permission loss, journal rename, changed host
key and independent remote observers are covered. The lost-reply scenario drops
an actual successful helper response at the client port; INSPECT does not replay.
This is loopback SSH, not a claim about a home endpoint or a real WAN outage.

C3: missing/false/wrong-domain same-exchange LLM/role attestation fails before IO;
wrong transport binding or unsupported server filesystem cannot activate.
FolderAccess is a trusted setup attestation, not a forged-user-resistant token.
Later commissioning must actually test the authorized LLM adapter and install
protected host/key/root bindings. A Drive-only connector does not qualify.

C4: docs/FIXED_FOLDER_AUTHORITY.md lists eligible/unqualified modes, no automatic
switch/fallback, artifact/commissioning boundaries, hardware flush assumptions,
maintenance restrictions and unreleased status. Exact root binding plus private
configuration prevents normal discovery/recreation. Tests assert inventory and
refuse foreign/missing identity; malicious same-account replacement is not a
sandbox guarantee. Windows is a client, not this mode's server; Linux filesystem
allowlist was exercised but no separate xfs hardware qualification is claimed.

## Local Windows evidence

Python3.11.9. Full pytest with process-local venv PATH/PYTHONPATH and fresh
nonexistent task-owned --basetemp:1607 passed,30 skipped,4 known strict DEF002
xfails in36.14s, exit0. Collection:1639 nodes in0.67s, exit0 (two missing PySide6
modules contribute skips but no nodes). Declared skips:22 Linux server/SSH cases,
six other POSIX-only cases and two unavailable local GUI modules; native Desktop
CI supplies actual GUI/platform evidence. Ledger from ownership base, public
scanner and git diff --check all exit0; worktree clean. Exact nodes retained in
collected-tests.txt. Public fixtures/keys only; no private logs are attached.

Commands:
```text
python -X utf8 -m pytest --basetemp <fresh-task-owned-temp> -ra
python -X utf8 -m pytest --collect-only -q -o addopts='' --basetemp <another-fresh-task-owned-temp>
python -X utf8 -m tools.development.ledger --base bb7384669275e0294dc5d46c16d051a54632e054
python -X utf8 tools/scan_public_repo.py
git diff --check
```

## Preserved failures and repairs

DEF018: first feasibility CI lock loser was BUSY, not REJECTED. Original failed
run and corrected probe retained in feasibility-probe.md. No fake CAS success.
DEF019: initial local invocation omitted private basetemp and hit an inaccessible
shared pytest-current during cleanup. Shared temp was left untouched; unchanged
source targeted rerun39passed22skipped .69s exit0 on a fresh task root.
DEF020: original adapter CI36803498656/job110182766248:2failed1632passed2skipped
4xfail32.40s; Desktop Linux110182766106:2failed1643passed4xfail39.52s. Synthetic
schema tampering accidentally used SQLite DELETE journal mode; config extra
field hit an earlier closed-envelope guard. Only fixtures corrected. CI36803790514/
110183632940:1634passed2skipped4xfail40.38s. Failures are preserved, not waived.
DEF021: broader full Windows run first produced3failed1603passed30skipped4xfail
36.62s. Three unchanged legacy tests assumed POSIX path/platform behavior.
Explicit Windows/Linux ping simulation retains no-shell/fixed-flag assertions;
TOML fixture escaping retains privacy assertions; Linux service defaults use
POSIX semantics even on a Windows test host. Existing Desktop CI now runs full
regressions on both platforms. No production defaults changed.

## Privacy, compatibility and rollback

RPC accepts only bounded flat READ/CAS envelopes with fresh nonce/root/domain;
canonical body validated before writes. Provider stderr/error text is suppressed.
Synthetic canaries/keys never enter published runtime records. Trusted local
configuration, account and fixed helper are required: this is cooperative code,
not an OS authorization sandbox. No force/ACK barrier was reintroduced.

New adapter is not selected in installed v1. Rollback is to leave the existing
transport/profile selected; never reset/restore an active root or erase UNKNOWN
work. Physical power loss, deployment credential qualification, protected actual
LLM connector, real multi-host filesystem behavior, complete artifact allocation
and final integration/security/release remain later gates. DEF001/002 remain OPEN.

## Final CI regression

CI36804072502/job110184473775 on ubuntu24.04:1635 passed,2 skipped,4 known
strict xfails in40.97s. Required OpenSSH fixture installed and executed (not
skipped). Progress36804072485/job110184473622 PASS. Native merge26d989f
contains headf12ef57e9b0a18cb883dda7a80586aa8dbd5f72b into base
bb7384669275e0294dc5d46c16d051a54632e054. Final desktop receipts follow.

## Final native desktop and artifact evidence

Desktop run36804072536, merge26d989f2abbf1403383af6277998a1bf77add832:
- Linux job110184473977 (ubuntu22.04): GUI68 passed1.89s; full1646 passed,
  4 known strict xfails39.32s. Both builds, bundle self-tests, GUI smoke and
  install/uninstall profile-isolation PASS.
- Windows job110184474251 (windows2025-vs2026): GUI64 passed4 declared skips2.42s;
  full1618 passed28 declared skips4 known strict xfails41.03s. Both builds,
  bundle self-tests, GUI smoke and install/uninstall profile-isolation PASS.
- All jobs completed. Earlier corrected Desktop36803790462 also completed both
  packages; initial Desktop36803498649 completed Windows success/Linux recorded
  fixture failure. No old run remains active.

Provider-reported artifact metadata (not independently downloaded/hash verified):
Windows11136912440,120706476 bytes,
sha256:fe2a0affee52d4331603caa6505856af8f09128a645c366593a0748d4ce3e9a9.
Linux11136907351,314143662 bytes,
sha256:eef31f73e256528e907005420914498c5a220be4d5824847b22a295dc29b22c2.
These build regression receipts do not claim that an installed v1 profile is
wired to the unreleased adapter.

[CI run](https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36804072502),
[Desktop run](https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36804072536),
[Progress run](https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36804072485).
