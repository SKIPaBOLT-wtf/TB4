"""First-run handoff uses actual RP019 request adapters over a synthetic service."""
import copy
from dataclasses import asdict

import pytest

from tb4.commissioning_checks import CommissionedStorage
from tb4.drive.commissioning import Commissioner
from tb4.drive.commissioning_bootstrap import AuthorityHandle
from tb4.drive.leadership import Leadership
from tb4.private_settings import SettingsError
from test_native_commissioning import system, seed, Journal, ACTORS, ENROLLMENT, clock, finish


def prepared():
    spec, provider, port, journal, bootstrap = system()
    seed(bootstrap)
    handle = AuthorityHandle.parse(journal.read()["handle"])
    leader = Leadership(port.authority(handle), actor=ACTORS[0], enrollment=ENROLLMENT)
    grant = bootstrap.initial_grant(leader, clock())
    finish(Commissioner(spec, leader, grant, port, Journal(spec, ACTORS[0])))
    return spec, provider, port, dict(spec=asdict(spec), authority=handle.record())


def test_exact_commissioned_root_authority_and_artifacts_are_rechecked_read_only():
    spec, provider, port, record = prepared()
    before = copy.deepcopy(provider.created)
    provider.calls.clear()
    result = CommissionedStorage(port).verify(record)
    assert result["domain_id"] == spec.domain_id and provider.created == before
    assert all(name == "files.get" for name, _ in provider.calls)


@pytest.mark.parametrize("failure", ["root-permission", "trashed-authority", "changed-tab",
                                   "different-domain", "missing-artifact", "unready"])
def test_stale_or_mismatched_commissioning_marker_is_not_readiness(failure):
    spec, provider, port, record = prepared()
    if failure == "root-permission":
        provider.metadata[spec.root_id]["capabilities"]["canEdit"] = False
    elif failure == "trashed-authority":
        provider.metadata[record["authority"]["object_id"]]["trashed"] = True
    elif failure == "changed-tab":
        record["authority"]["tab_id"] = "different-tab"
    elif failure == "different-domain":
        record["spec"]["domain_id"] = ACTORS[1]
    elif failure == "missing-artifact":
        del provider.metadata[provider.created[-1]]
    else:
        provider.store.document["records"]["global.commissioning"]["body"]["state"] = "PREPARING"
    before = copy.deepcopy(provider.created)
    with pytest.raises(SettingsError, match="STORAGE_UNAVAILABLE"):
        CommissionedStorage(port).verify(record)
    assert provider.created == before
