"""Real protected checkpoint/journal codecs, synthetic commissioned transport."""
from dataclasses import replace
import hashlib
from pathlib import Path

from tb4.private_settings import PrivateSettings
from tb4.reconfiguration_effects import Effects, SCHEMA
from tb4.reconfiguration_maintenance import Maintenance
from tb4.watchdog.checkpoint_store import NativeCheckpoint, SCHEMA as CHECKPOINT_SCHEMA
from tb4.watchdog.leadership_runtime import Checkpoint, NativeWatchdogContext, NativeWatchdogRuntime
from tests.security.test_private_settings import MemoryNative
from reconfiguration_controller_support import system
from test_native_leadership import clock


def guarded_system(*, checkpoint_store=None, effect_store=None, **kwargs):
    value = system(**kwargs)
    for path in (SCHEMA,CHECKPOINT_SCHEMA):
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
