"""Synthetic RP-027 images and local setup; no provider/network fixture claims."""
from dataclasses import asdict

from tb4.commissioning_state import Setup
from tb4.drive.commissioning import SetupSpec
from tb4.drive.commissioning_bootstrap import AuthorityHandle
from tb4.drive.docs_authority import NativeDocsAuthority
from tb4.exchange_layout import Capacity, empty_document
from tb4.private_settings import PrivateSettings
from tb4.timing_contract import TimingProfile
from tests.security.test_private_settings import MemoryNative
from tests.drive.test_native_docs_transport import BINDING, DOMAIN, WireStore

CANARY = "SYNTHETIC_PRIVATE_RECONFIGURATION_CANARY"
TRANSITION = "c" * 64


def configure(document, phase="MAINTENANCE", revision=1):
    document["records"]["global.settings"] = dict(generation=1, operation_id=TRANSITION,
        retention="RETAINED", body=dict(descriptor_state="VALIDATED", revision=1,
        timing=asdict(TimingProfile()), configuration=dict(schema_version=1, revision=revision,
        phase=phase, transition_id=TRANSITION)))
    return document


def image(document=None):
    wire = WireStore(document or empty_document(DOMAIN, Capacity(2, 2, 2, 2)))
    return NativeDocsAuthority(wire.client(), BINDING).read()


def setup(capacity=Capacity(2, 2, 2, 2)):
    value = Setup(PrivateSettings(MemoryNative()), create=True)
    spec = SetupSpec("synthetic-root", DOMAIN, "a" * 64, value.installation_id,
                     "NATIVE_DOCS", capacity)
    value.choose(dict(role="watchdog", storage=dict(spec=asdict(spec),
        authority=AuthorityHandle(BINDING.document_id, "b" * 64, BINDING.tab_id).record())))
    return value
