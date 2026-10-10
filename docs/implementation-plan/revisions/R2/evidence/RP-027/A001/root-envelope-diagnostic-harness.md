# Root envelope diagnostic: task harness import failure

Exact source `5b9c339e06d91822c594dca6f276f6634dd2dc48`, checkout `192f29230fe06e79e321ccb57707babe599ab265`. Child exit1 before fixture construction. Actual `ModuleNotFoundError: No module named 'tests'` arises because the task-only diagnostic included src/tests/test-adapter directories but omitted the repository root needed by existing tests.security imports. No Root.begin, synthetic SDK/native fixture operation, or origin proof occurred. Outer shell exit0 is not diagnostic success.

Correct only the task-only import search path, preserving source/branch/clean guard and exact one-probe preservation predicates, and execute after a new verified INTENT.
