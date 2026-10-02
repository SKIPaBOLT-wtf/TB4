"""Synthetic local table fixture support, no provider/network/native claims."""
from dataclasses import asdict
from pathlib import Path

from tb4.commissioning_state import Setup
from tb4.drive.commissioning import SetupSpec
from tb4.drive.commissioning_bootstrap import AuthorityHandle
from tb4.discovery_catalogue import Catalogue, Interface, Observation, Scope
from tb4.exchange_layout import Capacity
from tb4.network_table import draft
from tb4.network_table_store import LocalNetworkTable
from tb4.private_settings import PrivateSettings
from tests.security.test_private_settings import MemoryNative

DOMAIN = "00000000-0000-4000-8000-000000000026"
CANARY = "SYNTHETIC_PRIVATE_NETWORK_CANARY"


def make_setup(store=None):
    native = MemoryNative()
    setup = Setup(store or PrivateSettings(native), create=True)
    spec = SetupSpec("synthetic-network-root", DOMAIN, "a"*64, setup.installation_id,
                     "NATIVE_DOCS", Capacity(devices=2, quarantine=2))
    record = dict(spec=asdict(spec), authority=AuthorityHandle("synthetic-doc", "b"*64, "synthetic-tab").record())
    setup.choose(dict(role="watchdog", storage=record, network_scope=["192.0.2.0/24"]))
    return setup


class MemoryFactory:
    def __init__(self):
        self.natives = {}

    def __call__(self, root, *, create=False, owner_authorized=False):
        root = Path(root)
        if create:
            assert owner_authorized and not root.exists()
            root.mkdir(mode=0o700)
            native = MemoryNative()
            native.binding = dict(principal="synthetic-owner", directory=[len(self.natives)+10, 26])
            self.natives[str(root)] = native
        return PrivateSettings(self.natives[str(root)])


def system(tmp_path):
    installation = tmp_path / "installation"
    installation.mkdir(mode=0o700)
    setup, factory = make_setup(), MemoryFactory()
    table = LocalNetworkTable(setup, installation_root=installation, factory=factory)
    assert table.configure(owner_authorized=True) == "CONFIRMED"
    seed(table)
    return table, factory


def seed(table, *, at=100, address="192.0.2.8", name=CANARY):
    value = table.read()
    catalogue = Catalogue(value["catalogue"])
    scope = Scope((Interface("synthetic-interface", 7, ("192.0.2.0/24",), "LAN"),))
    catalogue.observe((Observation(7, address, "NEIGHBOR_CACHE", at, 60,
                                   hardware_hint="synthetic-hint", name_hint=name),), scope, now=at)
    table.sync_observations(catalogue.private_image(), current_owner=lambda:True)
    return table.read()


def good_proposal(table, *, kind="COMPUTER", stable_ip="UNKNOWN"):
    value = table.read()
    device_id = next(e["device_id"] for e in value["catalogue"]["entries"] if e is not None)
    proposed = draft(value, device_id)
    proposed["description"].update(device_kind=kind, stable_ip=stable_ip)
    return proposed

