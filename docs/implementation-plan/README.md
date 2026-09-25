# TB4 Implementation Plan

This directory is the authoritative chronological engineering plan.

## Status authority

Only `manifest.yaml` contains authoritative step status.

Allowed states:

```text
PLANNED -> IN_PROGRESS -> VERIFIED
              |
              +-> BLOCKED
PLANNED/IN_PROGRESS -> SUPERSEDED
```

A step becomes `VERIFIED` only after objective evidence is stored under its own evidence directory and reviewed.

## Isolation

For step `IP-XX`:

```text
steps/IP-XX-*.md
amendments/IP-XX/
evidence/IP-XX/
```

Do not place evidence for one step under another step. Do not silently rewrite an accepted step; use an amendment when meaning or scope changes.

## Execution rule

Complete steps in numeric order unless the plan itself explicitly marks a step as parallel-safe. A later step may depend only on earlier VERIFIED steps and repository state explicitly listed in its preconditions.

## Step 1

IP-01 records the already-completed creation of the TB4 execution contract. Engineering implementation starts at IP-02.
