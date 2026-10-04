# RP-027 A001 inherited effect/runtime source checkpoint

Exact source: ac587b6b6856e3c7785030720ee9c120c2fad0e5. Verified INTENT RP-027-A001-0021:833b670828312f34199acf20b36e059466070ecd. Seventeen scoped files saved and read back; local commit 200adc52425cfec839378439e510ea28b3324b88 retained on its own preservation branch.

A-002 records the exact unreleased extension and limits. One existing global.summary slot reserves tb4_effects_v1; prior non-effect data is retained. Normal publication cannot mutate its row, concurrent old plans cannot erase it, and bootstrap refuses prior unresolved summary or absent later-epoch coverage. Only the initial current owner can seed its exact protected checkpoint; this is not a live migration grant.

NativeCheckpoint persists typed owner/binding/grant/election/mutation/receipt state through actual PrivateSettings CAS and explicit same-frame pending recovery. A durable maintenance reservation fences local work without stopping role tick/renewal/acquisition. Effects persists exact native intent before strict CAS, journals UNKNOWN before invoking bounded work, retains exact terminal outcomes and restarts in inspect-only mode. A late actual reply preserves the reservation. Original local unresolved status is published atomically with maintenance. A covered zero-blocker fallback may resolve explicitly without contacting the former owner; UNKNOWN/missing evidence remains a refusal.

Pins (LF Git blob bytes, UNRELEASED with no builds): effects1abc0034e685aa7ba0a6b8b3c94410997624ef4bac03af2fa131ac1442110005; native checkpoint4f898bd51242cd61cca59dd7a016d467898671f266d2d1f1a9e38fd79eeeb6d4; maintenance WALf8cba98bb15e544d84a2e73cc58a2e359e974f96e323f708a46107275de13d31. Covered adoption changes only the draft schema; actual shared fresh coverage is a code prerequisite, never a JSON grant.

Focused synthetic/fresh-native tests were added for race/lost reply/unknown fallback/covered unavailable owner/no replay/malformed/copy/protection/promotion/maximum action capacity. They have not run. Diff whitespace/source/privacy/compatibility/rollback review found no live/deployment/private host/credential changes or existing accepted history removal. No C1-C4 acceptance is claimed. C2 candidate, C3 same-object root changes, C4 monotonic activation and full platform/common review remain required.

Next: separately verified exact-source24-target regression run, preserving every actual failure before source repair.
