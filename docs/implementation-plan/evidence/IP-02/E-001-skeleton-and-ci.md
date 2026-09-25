# IP-02 Evidence - Canonical Repository Skeleton

Date: 2026-09-25

## Verified

- Python packaging metadata exists in `pyproject.toml`.
- Canonical package roots exist under `src/tb4/`.
- Public `protocol/`, `config/`, `tools/`, and `docs/decisions/` paths exist.
- `tests/test_import.py` verifies the package can be imported.
- GitHub Actions CI run 36193874666 completed its `Install` step successfully.
- The same CI run completed its `Test` step successfully.
- The test ran against commit `0409d2c9adc9302c4f3f45163364b36f3441ae03`.

## Directory checks

- `src/tb4`: present
- `protocol`: present
- `config`: present
- `tools`: present
- `docs/decisions`: present

## Result

IP-02 completion criteria are satisfied. The repository has a testable Python skeleton and stable public locations for protocol, configuration, tools, tests, and decision records.
