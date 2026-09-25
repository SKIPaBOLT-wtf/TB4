# Contract Amendments

Do not edit an accepted contract point casually when the meaning changes.

Create amendments under a point-specific directory:

```text
amendments/
└── EC-09/
    └── A-001-short-description.md
```

Each amendment records:

- point ID;
- problem;
- old interpretation;
- new interpretation;
- reason;
- compatibility impact;
- affected implementation-plan steps;
- date;
- approval/review state.

After an amendment is accepted, update the canonical point if appropriate and add the amendment path to that point's entry in `../manifest.yaml`.

Do not store implementation completion evidence here.
