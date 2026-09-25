# Contract Verification Evidence

Verification evidence is isolated by contract point:

```text
evidence/
└── EC-16/
    └── E-001-stale-generation-tests.md
```

Evidence must state:

- point ID;
- what was verified;
- exact commands/tests/checks used;
- observed result;
- relevant commit SHA or artifact;
- verifier/date.

Only after evidence exists and has been reviewed may the point status in `../manifest.yaml` become `VERIFIED`.

Do not put amendments or implementation-plan completion notes here.
