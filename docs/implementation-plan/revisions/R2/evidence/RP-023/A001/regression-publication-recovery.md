# Regression source publication consistency failure

The test-only source commit `5f085bfd39384f2ed115d52cffd3a0a7dba6e7df` was published and read back with eight new cases. The task helper subsequently loaded a serialized file map, mutated that temporary copy without storing it, and the next documentation checkpoint `dd8cfb5ed1e83a09fe4d303012ba6bb07bd6c39b` republished the earlier test body. Ref/readback inspection at `200516e1a95ddafcedd0fac3c5f8968cb3a62d62` and the stored map confirmed those new tests were absent. Runtime source was unaffected. No diagnostic test was launched under INTENT0027; its source precondition failed.

Recovery: explicitly persist the refreshed file map, publish exactly the test bytes from the already verified5f085 source, compare remote readback, and only then issue a fresh test INTENT. Preserve every intermediate commit and event. Future source publication must store the map before any whole-checkpoint publication.
