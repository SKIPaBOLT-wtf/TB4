"""Closed metadata diagnosis of read-only loopback queries on an opted-in CI runner."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys
import time

REQUEST = "docs/implementation-plan/revisions/R2/evidence/RP-027/A001/native-discovery-diagnostic-request.json"


def main():
    if (sys.platform != "win32" or os.environ.get("GITHUB_ACTIONS") != "true"
            or os.environ.get("RUNNER_OS") != "Windows"
            or os.environ.get("TB4_REQUIRE_NATIVE_DISCOVERY") != "1"):
        print(json.dumps({"error": "ISOLATED_RUNNER_REQUIRED"}))
        return 2
    root = Path(__file__).resolve().parents[1]
    try:
        request = json.loads((root / REQUEST).read_text(encoding="utf-8"))
        if (type(request) is not dict
                or set(request) != {"schema_version", "item", "check", "attempt",
                    "intent_event", "source_commit", "request_revision", "scope"}
                or request["schema_version"] != 1 or request["item"] != "RP-027"
                or request["check"] != "RP-027.C2" or request["attempt"] != "A001"
                or request["scope"] != "SELECTED_LOOPBACK_ONLY"
                or type(request["request_revision"]) is not int
                or request["request_revision"] != 1
                or type(request["source_commit"]) is not str
                or len(request["source_commit"]) != 40
                or any(c not in "0123456789abcdef" for c in request["source_commit"])
                or type(request["intent_event"]) is not str
                or not request["intent_event"].startswith("RP-027-A001-")):
            raise ValueError
    except (OSError, ValueError, TypeError):
        print(json.dumps({"error": "DIAGNOSTIC_REQUEST_INVALID"}))
        return 2

    from tb4 import discovery_native as native
    from tb4.discovery_catalogue import DiscoveryError, Scope

    original_read = native.BoundedRead
    original_popen = native.subprocess.Popen
    observations = []
    stage = ["identity-first"]

    class MeasuredRead(original_read):
        def run(self, argv, *, timeout=5):
            metric = dict(stage=stage[0], budget_s=timeout, elapsed_s=None,
                outcome="UNAVAILABLE", output_bytes=None, output_complete=False,
                child_exit=None, stopped_live_child=False)
            observations.append(metric)
            started = time.monotonic()

            class Pipe:
                def __init__(self, pipe):
                    self.pipe = pipe

                def read(self, size):
                    raw = self.pipe.read(size)
                    metric["output_bytes"] = len(raw)
                    metric["output_complete"] = True
                    return raw

                def close(self):
                    self.pipe.close()

            class Child:
                def __init__(self, child):
                    self.child = child
                    self.stdout = Pipe(child.stdout)

                @property
                def returncode(self):
                    return self.child.returncode

                def poll(self):
                    result = self.child.poll()
                    if result is not None:
                        metric["child_exit"] = result
                    return result

                def wait(self, *, timeout):
                    result = self.child.wait(timeout=timeout)
                    metric["child_exit"] = result
                    return result

                def kill(self):
                    metric["stopped_live_child"] = self.child.poll() is None
                    self.child.kill()

            def start(*args, **kwargs):
                return Child(original_popen(*args, **kwargs))

            native.subprocess.Popen = start
            try:
                raw = super().run(argv, timeout=timeout)
                metric["outcome"] = "READY"
                return raw
            finally:
                native.subprocess.Popen = original_popen
                metric["elapsed_s"] = round(time.monotonic() - started, 3)

    spec = importlib.util.spec_from_file_location("tb4_isolated_loopback_diagnostic",
        root / "tests/discovery/test_native_loopback.py")
    qualification = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(qualification)
    qualification.BoundedRead = MeasuredRead
    identities = []
    selected = None
    for label in ("identity-first", "identity-second"):
        stage[0] = label
        try:
            selected = qualification.loopback()
            identities.append({"stage": label, "outcome": "READY"})
        except (DiscoveryError, AssertionError, ValueError, TypeError, KeyError):
            identities.append({"stage": label, "outcome": "UNAVAILABLE"})
    collection = {"status": "NOT_EXECUTED"}
    if selected is not None:
        stage[0] = "collection"
        result = native.collect_neighbors(Scope((selected,)),
            native.NativeNeighbors(runner=MeasuredRead()), clock=lambda: 100)
        collection = result.summary()
    print(json.dumps(dict(schema_version=1, item="RP-027", check="RP-027.C2",
        attempt="A001", source_commit=request["source_commit"],
        request_revision=request["request_revision"], intent_event=request["intent_event"],
        scope="SELECTED_LOOPBACK_ONLY", production_budgets_unchanged=True,
        queries=observations, identities=identities, collection=collection,
        diagnostic_only=True, acceptance=False), sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        exit_code = main()
    except Exception:
        print(json.dumps({"error": "DIAGNOSTIC_UNAVAILABLE"}))
        exit_code = 2
    raise SystemExit(exit_code)

