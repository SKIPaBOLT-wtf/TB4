# IP-13 Evidence - DOG_TAG, DOG_PULSE, DOG_SNIFF, and Fault Schemas

Date: 2026-09-26

## Verified

- DOG_TAG contains stable identity and capabilities only; reachability fields are rejected.
- DOG_TAG secret-like fields are rejected.
- DOG_PULSE contains timestamp, sequence, instance identity, and paired claimed generation/operation fields.
- DOG_SNIFF separately carries bounded LAN observation evidence with ONLINE/OFFLINE/UNKNOWN semantics.
- DOG_SNIFF address lists are bounded.
- TARGET_LEASH fault bodies carry bounded target-local fault metadata without duplicating filename state.
- Canonical fixtures cover idle/busy pulse, ONLINE/OFFLINE/UNKNOWN sniff, and clear/tangled target-local fault examples.
- Negative tests cover invalid pulse sequence/time, unpaired claim fields, reachability leakage into DOG_TAG, secret-like identity fields, unbounded observations, and duplicated LEASH state.
- GitHub Actions CI run `36197612251` completed successfully for commit `38bda2be26f4fe01e9415bb5e4901548e49d080c`.

## Result

IP-13 completion criteria are satisfied.
