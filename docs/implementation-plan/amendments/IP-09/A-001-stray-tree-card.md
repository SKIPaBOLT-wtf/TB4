# A-001 — Define STRAY_TREE contents

## Affected step

IP-09 — Canonical Drive Tree Blueprint

## Problem

The verified blueprint defined each STRAY_YARD dynamic child as a folder but did not define where bounded discovery evidence lives inside that folder.

## Decision

Each deterministic `stray-<stable-id-fragment>` folder contains exactly one required fixed object:

`STRAY_CARD`

STRAY_CARD stores bounded discovery evidence. The stray folder remains outside the active control path.

## Reason

Mutable discovery timestamps and address evidence must not be encoded into deterministic folder names. A fixed child object preserves stable naming and permits write-on-change updates.

## Compatibility impact

Additive protocol-major-1 tree extension. Existing registered device trees are unchanged.

## Repair rule

If a known stray folder is unambiguous and its STRAY_CARD is missing, the card may be recreated from the current discovery observation. The STRAY_YARD root and stray identity folder are not execution authorization.
