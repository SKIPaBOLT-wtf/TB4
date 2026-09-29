import json

import pytest

from tb4.desktop.profile import canonical_validate, default_config, profile_for, save_config
from tb4.desktop.worker import canonical_protocol_names


@pytest.mark.parametrize('role', ['watchdog', 'fetcher'])
def test_generated_desktop_profile_uses_production_validator(tmp_path, role):
    p = profile_for(role, tmp_path)
    text = default_config(p).replace('root_id = "replace-at-deploy-time"', 'root_id = "example-root"')
    text = text.replace('client_secrets_path = "replace-at-deploy-time"', 'client_secrets_path = ' + json.dumps(str(p.directory / 'client.json')))
    save_config(p, text, expected_digest=None)
    canonical_validate(role, p.config)


def test_protocol_display_names_come_from_canonical_registry():
    names = canonical_protocol_names()
    assert 'FETCH_BALL_READY' in names
    assert 'DOG_SNOOZE' in names
    assert 'DOG_PRIVATE_TOKEN' not in names
