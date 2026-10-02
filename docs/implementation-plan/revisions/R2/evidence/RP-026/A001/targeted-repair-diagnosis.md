# Network-table qualification diagnosis and repair WIP

Original failure: targeted-windows-initial-failure.md, source f638b9ec28091554f879dd59cd4b8db3105f1251.
Repair source: f719927c8eed0df2d98842f9782ff4b3068f22f4 on feat/rp026-local-network-table.
Repair INTENT: RP-026-A001-0019. No repaired tests have run yet.

Source/observed-result diagnosis:

- The old drift stimulus supplied only an unverified neighbor hardware hint at a different address. The accepted discovery policy quarantines HINT_COLLISION, preserving the known endpoint and its addressing fact. The repaired test asserts that negative first, then supplies an explicit fresh trusted FIXED_HELPER identity binding and retains the original STABLE_ADDRESS_REQUIRED assertion after actual endpoint drift. No discovery/enrollment policy is weakened.
- The router test reused an existing draft containing a FETCHER role and UNKNOWN platform. Changing only device_kind retained that role, correctly requiring platform details. The repaired stimulus explicitly clears roles/launch_mode for the non-computer scenario and retains the original adequacy, stale and clock assertions.
- The lock test prepared its proposal while the native table lock was already held. Preparation moves before the lock, so the intended approve operation is exercised. The new table binding accessor now normalizes native store exceptions to NETWORK_STORE_UNAVAILABLE without echoing native values. Native Windows/Linux lock/protection code is unchanged.
- Status inspection preserves discovered devices when its clock cannot be read; untrusted zero time does not make approval/addressing facts fresh. Added explicit clock negatives, with no role/coordination barrier.
- Source review extended Linux installer preservation to custom installation-local table frames, using a read-only installation-time presence check. Default/custom/nested data fixtures remain private; no path output, router operation or runtime scan occurs.

Initial patch preparation was rejected because its final documentation context omitted the preceding sentence. Inspection confirmed zero source diff; the corrected exact patch was then applied. No partial source mutation or test was replayed. The rejected patch/failure remains in task/tool history. All repaired files were remotely read back; the task-owned local draft commit remains preserved separately. No Git CLI push retry was used.

DEF-049/050 stay OPEN and C1-C4 remain held. These findings support the hypotheses, but passing runtime/fixture rechecks are still required. Source scope, former failed assertions and all accepted predecessor evidence are retained. Generated machine schema and the UNRELEASED instruction catalog were unchanged. No real device/network/configuration/secret or installed skill was touched.

Next: new exact-source target/native Windows qualification INTENT, then separately recorded Linux/hosted packaged qualification once local gates pass.

Checkpoint preparation rejected a prospective replacement of an existing hypothesis (DEFECT_HISTORY_REWRITTEN). No ref/file was published. The original hypothesis is preserved verbatim and the supported source/trace conclusion is appended as a separate hypothesis. Full unchanged history guards apply.
