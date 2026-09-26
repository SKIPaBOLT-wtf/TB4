# A-003 — Add STRAY_CARD observation object

## Affected step

IP-03 — Canonical Vocabulary Registry

## Problem

The canonical vocabulary defined STRAY_YARD and deterministic `stray-*` folders but did not name the bounded observation object stored inside a stray folder. IP-41 requires first-seen/last-seen evidence without promoting an unknown device into BALL_PARK.

## Decision

Add the fixed logical object name:

`STRAY_CARD`

It is an observation-only JSON object inside one deterministic `stray-*` folder.

## Reason

A named fixed object keeps the stray subtree deterministic and avoids encoding mutable timestamps into folder names.

## Compatibility impact

Additive protocol-major-1 vocabulary extension. Existing active control objects and state machines are unchanged.

## Affected future work

IP-41 STRAY_HUNTER uses STRAY_CARD. Discovery remains non-authorizing and cannot create BALL_PARK execution capabilities.
