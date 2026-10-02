"""Actual staged/first-run adapters and a fresh synthetic commissioned domain."""
import hashlib
from pathlib import Path
from types import SimpleNamespace

from tb4.commissioning_checks import CommissionedStorage, Environment, Prerequisites
from tb4.commissioning_state import Reconciliation
from tb4.private_settings import PrivateSettings
from tb4.reconfiguration_candidate import Candidate, CandidateContext, SCHEMA
from reconfiguration_controller_support import resolution_archive
from reconfiguration_effects_support import guarded_system
from tests.security.test_private_settings import MemoryNative


def private(index):
    native = MemoryNative()
    native.binding = {"principal":"synthetic-owner", "directory":[41,index]}
    return PrivateSettings(native)


def system(*, profile=None, archive=None, transaction=None, environment=None, schemas=(), **kwargs):
    value = guarded_system(**kwargs)
    raw = (Path(__file__).parents[2]/SCHEMA).read_bytes()
    value.source.files[value.source.head][SCHEMA] = raw
    value.source.catalog["profiles"][0]["files"][SCHEMA] = hashlib.sha256(raw).hexdigest()
    for path in schemas:
        raw = (Path(__file__).parents[2]/path).read_bytes()
        value.source.files[value.source.head][path] = raw
        value.source.catalog["profiles"][0]["files"][path] = hashlib.sha256(raw).hexdigest()
    value.source.save()
    # Actual durable known-operation history in this fresh synthetic profile.
    # These fixture callbacks have no external effect and must never be replayed.
    history_calls = []
    for op,outcome in (("1"*64,Reconciliation.CONFIRMED),("2"*64,Reconciliation.REJECTED)):
        value.setup.perform_once(op,lambda:history_calls.append(op),owner_authorized=True)
        value.setup.reconcile(op,lambda _,outcome=outcome:outcome)
    assert value.controller.begin(owner_authorized=True) == "MAINTENANCE"
    decision,status = value.controller.proposal()
    assert not status["requires_resolution"]
    proof = resolution_archive(value)
    assert value.controller.resolve(decision,proof,owner_authorized=True) == "RESOLVED"
    context = CandidateContext(value.controller,proof,profile or private(1),
        archive or private(2),transaction or private(3))
    candidate = Candidate(context)
    checker = Prerequisites(environment=environment or (
        lambda:Environment("WINDOWS","X64","USER","DESKTOP_SESSION","INTERACTIVE")),
        storage=CommissionedStorage(value.flow.port),credentials=None,source=value.source,
        runtime=value.context.runtime,clock=lambda:220)
    return SimpleNamespace(value=value,candidate=candidate,checker=checker,context=context,
                           history_calls=history_calls)
