import json
import os
from pathlib import Path

import pytest

from tb4.desktop.profile import (
    MAX_CONFIG_BYTES, Profile, ProfileBusy, ProfileError, ProfileLock,
    content_digest, default_config, drive_root_id, parse_config,
    profile_for, read_config, save_config,
)


def configured(profile):
    text = default_config(profile)
    text = text.replace('root_id = "replace-at-deploy-time"', 'root_id = "example-root"')
    text = text.replace('client_secrets_path = "replace-at-deploy-time"', 'client_secrets_path = ' + json.dumps(str(profile.directory / 'client.json')))
    return text


def no_provider(role, path):
    assert role in {'watchdog', 'fetcher'}
    assert path.is_file()


@pytest.mark.parametrize('role', ['watchdog', 'fetcher'])
def test_role_template_requires_configuration(tmp_path, role):
    p = profile_for(role, tmp_path)
    with pytest.raises(ProfileError, match='DRIVE_ROOT_ID_REQUIRED'):
        parse_config(role, default_config(p))
    parsed = parse_config(role, configured(p))
    assert parsed['desktop']['start_role'] is False
    assert parsed['drive']['token_path'] == str(p.directory / 'token.json')


def test_profiles_and_locks_are_independent(tmp_path):
    a = profile_for('watchdog', tmp_path)
    b = profile_for('fetcher', tmp_path)
    assert a.config != b.config and a.log != b.log
    with ProfileLock(a), ProfileLock(b):
        with pytest.raises(ProfileBusy):
            with ProfileLock(a):
                pass
    with ProfileLock(a):
        pass


def test_save_preserves_text_and_backups(tmp_path):
    p = profile_for('fetcher', tmp_path)
    text = configured(p) + '\n# Keep this comment.\n[extension]\nvalue = "custom"\n'
    digest = save_config(p, text, expected_digest=None, validator=no_provider)
    assert read_config(p.config) == text
    newer = text.replace('"custom"', '"changed"')
    save_config(p, newer, expected_digest=digest, validator=no_provider)
    assert read_config(p.backup) == text
    assert read_config(p.config) == newer
    if os.name != 'nt':
        assert p.config.stat().st_mode & 0o777 == 0o600
        assert p.directory.stat().st_mode & 0o777 == 0o700


@pytest.mark.parametrize('newline', ['\n', '\r\n'])
def test_conflict_does_not_overwrite_external_change(tmp_path, newline):
    p = profile_for('watchdog', tmp_path)
    text = configured(p)
    save_config(p, text, expected_digest=None, validator=no_provider)
    external = (text + '\n# external edit\n').replace('\n', newline)
    p.config.write_bytes(external.encode('utf-8'))
    with pytest.raises(ProfileError, match='CONFIG_CHANGED'):
        save_config(p, text, expected_digest=content_digest(text), validator=no_provider)
    assert read_config(p.config) == external


def test_live_worker_blocks_save(tmp_path):
    p = profile_for('watchdog', tmp_path)
    with ProfileLock(p):
        with pytest.raises(ProfileBusy):
            save_config(p, configured(p), expected_digest=None, validator=no_provider)
    assert not p.config.exists()


def test_failed_validation_preserves_existing_and_cleans_temporary(tmp_path):
    p = profile_for('fetcher', tmp_path)
    text = configured(p)
    digest = save_config(p, text, expected_digest=None, validator=no_provider)
    def fail(role, path):
        raise ProfileError('INVALID')
    with pytest.raises(ProfileError, match='INVALID'):
        save_config(p, text + '\n# changed', expected_digest=digest, validator=fail)
    assert read_config(p.config) == text
    assert not list(p.directory.glob('.validate-*'))
    assert not p.backup.exists()


@pytest.mark.parametrize('url,expected', [
    ('abc_DEF-123', 'abc_DEF-123'),
    ('https://drive.google.com/drive/folders/abc-123?usp=sharing', 'abc-123'),
    ('https://drive.google.com/drive/u/0/folders/abc_123/', 'abc_123'),
])
def test_folder_link_parser(url, expected):
    assert drive_root_id(url) == expected


@pytest.mark.parametrize('value', ['', 'replace-at-deploy-time', '../root', 'X:\\My Drive',
    'https://evil.example/drive/folders/abc', 'https://drive.google.com.evil/drive/folders/abc',
    'https://user@drive.google.com/drive/folders/abc', 'https://drive.google.com/file/d/abc/view'])
def test_folder_link_rejects_ambiguous_or_local_paths(value):
    with pytest.raises(ProfileError):
        drive_root_id(value)


def test_invalid_role_and_relative_profile(tmp_path):
    with pytest.raises(ProfileError):
        profile_for('../fetcher', tmp_path)
    with pytest.raises(ProfileError):
        Profile('fetcher', Path('relative'))


def test_oversize_and_broken_toml(tmp_path):
    with pytest.raises(ProfileError, match='TOO_LARGE'):
        parse_config('fetcher', 'x' * (MAX_CONFIG_BYTES + 1))
    with pytest.raises(ProfileError, match='STRUCTURE'):
        parse_config('fetcher', '[unclosed')


def test_rollback_is_another_verified_save(tmp_path):
    p = profile_for('fetcher', tmp_path)
    original = configured(p)
    digest = save_config(p, original, expected_digest=None, validator=no_provider)
    changed = original + '\n# new\n'
    digest = save_config(p, changed, expected_digest=digest, validator=no_provider)
    restore = read_config(p.backup)
    save_config(p, restore, expected_digest=digest, validator=no_provider)
    assert read_config(p.config) == original
    assert read_config(p.backup) == changed
