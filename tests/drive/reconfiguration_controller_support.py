"""Actual setup/commissioning/Docs/instruction adapters; synthetic provider facts."""
from dataclasses import replace
import hashlib
from pathlib import Path
from types import SimpleNamespace

from tb4.private_settings import PrivateSettings
from tb4.reconfiguration_evidence import ProtectedEvidence
from tb4.reconfiguration_maintenance import Maintenance, MaintenanceContext, WAL_SCHEMA
from tb4.watchdog.leadership_runtime import Action, Capabilities, Checkpoint
from tests.security.test_private_settings import MemoryNative
from test_ballpark_publication import ready
from test_ballpark_setup import FACTS
from test_native_watchdog_startup import LocalCheckpoint

TRANSITION = "d" * 64


def system(*, profile_store=None, state_store=None, baseline_store=None):
    pub, guide, flow, setup, provider, native, kwargs, source = ready(profile_store)
    assert pub.publish() == "CONFIRMED"
    # Synthetic compatible release only. Production's catalog remains UNRELEASED.
    raw = (Path(__file__).parents[2] / WAL_SCHEMA).read_bytes()
    source.files[source.head][WAL_SCHEMA] = raw
    source.catalog["profiles"][0]["files"][WAL_SCHEMA] = hashlib.sha256(raw).hexdigest()
    source.save()
    state_native, baseline_native = MemoryNative(), MemoryNative()
    state_store = state_store or PrivateSettings(state_native)
    baseline_store = baseline_store or PrivateSettings(baseline_native)
    baseline = ProtectedEvidence(baseline_store, installation_id=setup.installation_id, transition_id=TRANSITION)
    checkpoint = LocalCheckpoint(setup.installation_id, Checkpoint(grant=flow.grant))
    caps = [Capabilities(setup.installation_id, True, True, frozenset(Action))]
    context = MaintenanceContext(setup, flow.leader, checkpoint, state_store, baseline, flow.port,
                                 kwargs["clock"], lambda:caps[0], source, FACTS)
    return SimpleNamespace(controller=Maintenance(context), context=context, setup=setup, provider=provider,
        flow=flow, profile_native=native, state_native=state_native, baseline_native=baseline_native,
        checkpoint=checkpoint, caps=caps, source=source)


def resolution_archive(value, store=None):
    return ProtectedEvidence(store or PrivateSettings(MemoryNative()),
        installation_id=value.setup.installation_id, transition_id=TRANSITION)


def restart(value):
    return Maintenance(value.context)
