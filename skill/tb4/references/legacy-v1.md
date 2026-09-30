# Historical v1 COACH manual — not an active R2 instruction profile

Preserved for old protocol review. This text does not authorize new workflows or live migration. See the repository entry and compatibility catalog.

---
name: tb4
description: Operate and troubleshoot the user's TB4 Drive-native terminal bridge as the AI-side COACH. Use when the user asks to run, inspect, wake, cancel, recover, or continue work on a TB4-managed target; inspect TB4 device/control state; coordinate WATCHDOG/FETCHER work; or diagnose TB4 protocol failures. Treat the public TB4 repository and the selected Google Drive TB4 control tree as canonical sources. Use exact object identities, deterministic protocol states, bounded waiting, and result-aware replay rules. Never use SSH as a general payload transport or invent undocumented state transitions.
---

# TB4 COACH

## Start from canonical state

1. Read the public TB4 repository `docs/START_HERE.md` when repository context is not already loaded.
2. Read `docs/COACH.md` for the current COACH workflow.
3. Read only the protocol/config files needed for the operation. Use `references/source-map.md` as the loading map.
4. Open the selected Google Drive TB4 root, then read `PARK_MAP`. Cache exact object IDs for the current operation.
5. Never embed a private Drive root ID, credential, host address, or private deployment topology in this Skill or public project files.

If repository guidance and conversational memory differ, use the canonical repository unless the user explicitly changes the design.

## Act as COACH, not WATCHDOG or FETCHER

Own:
- target selection;
- work intent and payload construction;
- run-limit selection within canonical configuration;
- interpretation of terminal evidence;
- next-step planning.

Do not own:
- LAN discovery;
- Drive retry loops implemented by deterministic helpers;
- target process execution;
- WATCHDOG health decisions;
- undocumented protocol recovery.

## Preflight every control operation

1. Resolve the target through `PARK_MAP`; prefer exact stable Drive object IDs over folder listing.
2. Inspect the canonical WATCHDOG fault object. If `DOG_SHIT_BLOCKING`, allow diagnostic/repair work only until the invariant is revalidated.
3. Inspect the target's canonical observation/heartbeat objects as needed.
4. Inspect the exact requested channel object and require the canonical state expected by the operation.
5. On an unexpected or ambiguous state, read `protocol/state-machines.yaml`; do not guess a transition.

Normal live work must not scan folders when `PARK_MAP` already provides the object ID.

## Make a target ready

If a fresh FETCHER is already available, do not wake/bootstrap it again.

If the target requires wake/bootstrap:
1. Use its canonical `WAKE_BONE` object.
2. Follow only transitions allowed by `protocol/state-machines.yaml`.
3. Write a wake request only while COACH owns the body-writing state.
4. Require remote verification before publishing the request state.
5. Treat wake failure as target-local unless canonical health rules say otherwise.
6. Treat a fresh target `DOG_PULSE` as readiness evidence; SSH command success alone is not readiness.

SSH is a fixed service-bootstrap mechanism only. Never send arbitrary job scripts through SSH.

## Dispatch work

Require `FETCH_BALL_READY` before creating a new job on that target.

1. Reserve the channel through the canonical COACH transition.
2. Build a new explicit operation ID and generation according to canonical schemas/helpers.
3. Choose `run_limit_s` from task complexity, bounded by canonical configuration.
4. For a small simple command, use the supported inline payload form.
5. For a multiline/large script, use a verified `TOY_BOX` artifact. Do not build giant one-line remote shell commands.
6. Write and remotely verify the request body before publishing it for FETCHER.
7. Never reuse an old generation for a retry.

For mutating work, make the command as inspectable and idempotent as practical, but never assume idempotency when the prior result is unknown.

## Wait without burning reasoning or remote calls

Load timing values from canonical configuration rather than hardcoding them here.

After dispatch:
- determine the earliest useful recheck time and the relevant terminal/deadline conditions;
- prepare likely next actions for each terminal branch while waiting;
- work on independent targets or analysis instead of repeatedly polling unchanged state;
- if the host supports a watcher/sub-agent, delegate only the exact object ID, expected state change(s), earliest check time, and deadline;
- otherwise recheck only when useful during the active operation. Never claim background monitoring when the host cannot provide it.

Do not use folder scans as a substitute for waiting on one known object.

## Interpret terminal results

Use canonical terminal evidence, not exit code alone.

- `FETCH_BALL_DONE`: consume the trustworthy successful result.
- `FETCH_BALL_PARTIAL`: inspect completed effects before deciding what remains.
- `FETCH_BALL_FAILED`: retry only as a new explicit generation when justified.
- `FETCH_BALL_CANCELLED`: consume returned evidence; a later retry is a new generation.
- `FETCH_BALL_GONE`: result/effects may be unknown. For mutating work, inspect current target state before any retry.

Large result artifacts belong outside the live control body. Follow verified artifact references rather than expecting unlimited inline output.

After terminal evidence has been consumed/reconciled, recycle the channel through canonical COACH transitions until it is `FETCH_BALL_READY` again.

## Cancel safely

Use the target's canonical `STOP_BALL` object. Bind cancellation to the exact FETCH_BALL object ID, operation/job ID, and generation required by the schema. A stale or mismatched cancellation must not stop a newer job.

## Fail closed

Never:
- invent a state name or transition;
- treat absence as a healthy explicit state;
- blindly replay `GONE` or otherwise unknown mutating work;
- overwrite a newer generation with stale evidence;
- clear `DOG_SHIT_BLOCKING` merely because it was read;
- place credentials or private deployment values in Drive protocol objects or public repository files;
- bypass helper verification just to reduce Drive operations.

When canonical state cannot be reconciled, preserve evidence and use the documented repair/blocking path.

## Preserve the project's vocabulary

Use canonical dog/ball names such as `BALL_PARK`, `FETCH_BALL`, `WAKE_BONE`, `DOG_SNOOZE`, `DOG_SHIT`, `BONEYARD`, and `DOG_POUND`. Do not replace them with a parallel “professionalized” vocabulary.
