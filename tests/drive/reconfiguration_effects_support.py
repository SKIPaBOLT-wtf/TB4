"""Real protected checkpoint/journal codecs, synthetic commissioned transport."""
from dataclasses import asdict, replace
import hashlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID

from tb4.ballpark_publication import Publisher
from tb4.ballpark_setup import GuidedBallpark
from tb4.commissioning_state import Setup
from tb4.discovery_workflow import Discovery
from tb4.drive.commissioning import Commissioner
from tb4.drive.commissioning_bootstrap import AuthorityHandle
from tb4.drive.leadership import Leadership
from tb4.private_settings import PrivateSettings
from tb4.reconfiguration_effects import Effects, SCHEMA
from tb4.reconfiguration_evidence import ProtectedEvidence
from tb4.reconfiguration_maintenance import Maintenance, MaintenanceContext, WAL_SCHEMA
from tb4.watchdog.checkpoint_store import NativeCheckpoint, SCHEMA as CHECKPOINT_SCHEMA
from tb4.watchdog.leadership_runtime import Action, Capabilities, Checkpoint, NativeWatchdogContext, NativeWatchdogRuntime
from tests.security.test_private_settings import MemoryNative
from reconfiguration_controller_support import TRANSITION
from test_ballpark_setup import FACTS, confirm, source
from test_discovery_workflow import SCOPE, observation
from test_native_commissioning import system as commissioning_system, seed, Journal, finish
from test_native_leadership import ACTORS, ENROLLMENT, clock


def guarded_system(*, checkpoint_store=None, effect_store=None, **kwargs):
    # A genuinely fresh initial synthetic installation, never an epoch rewind.
    # The accepted ready/build fixture deliberately models later-owner takeover.
    profile_native = MemoryNative()
    profile_store = kwargs.pop("profile_store",None) or PrivateSettings(profile_native)
    assert profile_store.read() is None
    with patch("tb4.commissioning_state.uuid4",return_value=UUID(ACTORS[0])):
        setup = Setup(profile_store,create=True)
    spec,provider,port,journal,bootstrap = commissioning_system()
    seed(bootstrap)
    handle = AuthorityHandle.parse(journal.read()["handle"])
    leader = Leadership(port.authority(handle),actor=setup.installation_id,enrollment=ENROLLMENT)
    grant = bootstrap.initial_grant(leader,clock())
    assert grant.epoch == 1 and grant.owner == spec.bootstrap_actor == setup.installation_id
    finish(Commissioner(spec,leader,grant,port,Journal(spec,setup.installation_id)))
    setup.choose(dict(role="watchdog",storage=dict(spec=asdict(spec),authority=handle.record()),
                      network_scope=["192.0.2.0/24"]))
    caps = [Capabilities(setup.installation_id,True,True,frozenset(Action))]
    flow = Discovery(setup,storage_port=port,leadership=leader,grant=grant,
        clock=lambda:clock(220),capabilities=lambda:caps[0])
    flow.configure(SCOPE,owner_authorized=True)
    flow.observe((observation(),)); assert flow.publish() == "CONFIRMED"
    origin = source(); guide = GuidedBallpark(setup,source=origin,runtime=FACTS)
    guide.begin(); confirm(guide); assert Publisher(guide,flow).publish() == "CONFIRMED"
    state_native,baseline_native = MemoryNative(),MemoryNative()
    state_store = kwargs.pop("state_store",None) or PrivateSettings(state_native)
    baseline_store = kwargs.pop("baseline_store",None) or PrivateSettings(baseline_native)
    assert not kwargs
    baseline = ProtectedEvidence(baseline_store,installation_id=setup.installation_id,transition_id=TRANSITION)
    context = MaintenanceContext(setup,leader,None,state_store,baseline,port,lambda:clock(220),
                                  lambda:caps[0],origin,FACTS)
    value = SimpleNamespace(setup=setup,provider=provider,flow=flow,source=origin,caps=caps,
        context=context,profile_native=profile_native,state_native=state_native,baseline_native=baseline_native)
    for path in (WAL_SCHEMA,SCHEMA,CHECKPOINT_SCHEMA):
        raw = (Path(__file__).parents[2]/path).read_bytes()
        value.source.files[value.source.head][path] = raw
        value.source.catalog["profiles"][0]["files"][path] = hashlib.sha256(raw).hexdigest()
    value.source.save()
    value.checkpoint = NativeCheckpoint(checkpoint_store or PrivateSettings(MemoryNative()),
        installation_id=value.setup.installation_id,binding=value.flow.leader.backend.binding,
        create=True,owner_authorized=True,initial=Checkpoint(grant=value.flow.grant))
    value.effects = Effects(value.flow.leader,value.checkpoint,effect_store or PrivateSettings(MemoryNative()))
    value.context = replace(value.context,checkpoint=value.checkpoint,effects=value.effects)
    value.controller = Maintenance(value.context)
    return value


def runtime(value, work=None):
    sample = [clock(240)]
    called = []
    def next_work():
        called.append(True)
        return work
    context = NativeWatchdogContext(value.flow.leader,value.checkpoint,lambda:value.caps[0],lambda:sample[0],
        next_work,effects=value.effects)
    return NativeWatchdogRuntime(context),sample,called
