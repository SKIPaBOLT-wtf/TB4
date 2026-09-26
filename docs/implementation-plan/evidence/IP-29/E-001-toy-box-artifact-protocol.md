# IP-29 Evidence - TOY_BOX Artifact Protocol

Date: 2026-09-26

## Verified

- FETCH_BALL artifact references are defined as exact stable Drive IDs of immutable TOY_BOX descriptor objects.
- Descriptor creation is explicitly last: content must first be remotely read back and verified by exact byte size and SHA-256.
- Descriptor schema requires complete=true and bounded identity, size, digest, timestamp, kind, interpreter hint, and safe suffix fields.
- Artifact content uses a separate exact content_object_id, avoiding folder scans.
- Remote path, filename, command, argument, and arbitrary interpreter metadata are forbidden.
- Script suffixes and interpreter hints use strict whitelists; remote metadata cannot become a local path or shell fragment.
- Request script, request data, large text result, binary result, and structured result artifact kinds are defined.
- Expired request artifacts must not start new execution.
- Large results are referenced from FETCH_BALL rather than expanding live control objects.
- Schema tests cover valid request/result fixtures, hash format, hard size ceiling, incomplete descriptor rejection, path traversal fields, unsafe suffixes, unsafe interpreter hints, script suffix constraints, and binary/data interpreter rejection.
- GitHub Actions CI run `36240737346` completed successfully for commit `138d5864174f71b24ff1f2816852b17d46f1d5db`.

## Result

IP-29 completion criteria are satisfied.
