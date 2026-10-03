"""Actual native request/runtime boundary, synthetic provider and clocks."""
from dataclasses import replace

import pytest

from tb4.configuration_contract import ConfigurationError
from tb4.watchdog.leadership_runtime import Action, NativeWatchdogRuntime, Work
from tests.reconfiguration_support import configure
from test_native_watchdog_startup import setup  # noqa: F401 - actual fixture
from test_native_leadership import clock, tid


def test_stale_first_reader_acquires_during_maintenance_without_peer_acks(setup):
    configure(setup.store.document)
    client = setup.make(utc=220)
    client.runtime.cycle()
    assert client.local.state.grant.epoch == 2
    assert client.runtime.state == "RUNNING" and client.runtime.reason == "CONFIGURATION_MAINTENANCE"
    assert not client.scheduled
    commits = setup.store.commits
    client.sample[0] = clock(240, 20)
    client.runtime.cycle()
    assert setup.store.commits == commits + 1 and not client.scheduled


def test_eager_effect_refuses_maintenance_and_same_runtime_resumes_after_revision_check(setup):
    client = setup.make(utc=220)
    assert client.runtime.tick()
    configure(setup.store.document)
    seen = []
    with pytest.raises(ConfigurationError, match="MAINTENANCE"):
        client.runtime.perform(Work(Action.SSH, tid("forbidden"), lambda *a:seen.append(a)))
    assert not seen and not client.local.state.receipts
    configure(setup.store.document, "ACTIVE")
    with pytest.raises(ConfigurationError, match="REVISION_REQUIRED"):
        client.runtime.perform(Work(Action.SSH, tid("still-forbidden"), lambda *a:seen.append(a)))
    runtime = NativeWatchdogRuntime(replace(client.context, configuration_revision=lambda:1))
    assert runtime.tick()
    assert runtime.perform(Work(Action.SSH, tid("current"), lambda *a:seen.append(a) or "COMPLETE")) == "COMPLETE"
    assert len(seen) == 1


def test_maintenance_arriving_during_local_wal_blocks_external_call(setup):
    client = setup.make(utc=220)
    assert client.runtime.tick()
    def pause(state):
        if state.receipts and state.receipts[-1].outcome == "UNKNOWN":
            configure(setup.store.document)
            setup.store.bump()
    client.local.after_replace = pause
    called = []
    with pytest.raises(ConfigurationError, match="MAINTENANCE"):
        client.runtime.perform(Work(Action.LAUNCH, tid("race"), lambda *a:called.append(a)))
    assert not called and client.local.state.receipts[-1].outcome == "NOT_DISPATCHED"
