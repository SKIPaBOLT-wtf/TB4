# TB4 Canonical Source Map

Load only what the current operation needs.

## Always start here when context is cold

- Public repository: `docs/START_HERE.md`
- COACH workflow: `docs/COACH.md`
- Remote control tree: `START_HERE`, then `PARK_MAP`

## Read when choosing or validating protocol transitions

- `protocol/state-machines.yaml`
- `protocol/objects.yaml`
- relevant schema under `protocol/schemas/`

## Read when timing, timeout, freshness, or rate behavior matters

- `config/defaults.toml`
- `docs/CONFIGURATION.md`
- `docs/PERFORMANCE.md`

## Read for execution payload/result handling

- `docs/FETCH_BALL.md`
- `docs/TOY_BOX.md`
- `docs/STOP_BALL.md` for cancellation

## Read for wake/bootstrap

- `docs/WAKE_BONE.md`
- `docs/DEVICE_STATE.md`

## Read for fault/recovery

- `docs/FAILURE_RECOVERY.md`
- `docs/WATCHDOG_STATES.md`
- `docs/SECURITY.md` when trust/credentials/privilege are involved

## Read for Drive structure or repair

- `docs/DRIVE_TREE.md`
- `protocol/tree-blueprint.yaml`

## Source precedence

1. machine-readable canonical protocol/config files;
2. matching current repository documentation;
3. remote live state under the selected TB4 root;
4. conversational memory.

Live state determines what is happening now. Canonical protocol files determine what transitions are legal.
