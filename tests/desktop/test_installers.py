import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_windows_installers_are_non_admin_role_scoped_and_preserve_profiles():
    text = (ROOT / 'packaging/desktop/windows.iss').read_text()
    for required in ('PrivilegesRequired=lowest', 'AppId=TB4.{#ROLE}.desktop',
                     'CloseApplications=no', 'InitializeUninstall', '--action probe-lock'):
        assert required in text
    assert '[UninstallDelete]' not in text
    assert 'LocalSystem' not in text
    assert 'taskkill' not in text


@pytest.mark.skipif(os.name == 'nt', reason='POSIX installer contract')
def test_linux_install_uninstall_isolated_and_preserves_profiles(tmp_path):
    home = tmp_path / 'home with spaces'
    home.mkdir()
    env = dict(os.environ, HOME=str(home), XDG_DATA_HOME=str(home / 'data'), XDG_CONFIG_HOME=str(home / 'config'))
    installed = home / 'data/tb4-apps'
    profiles = home / 'data/tb4'
    for role in ('watchdog', 'fetcher'):
        stage = tmp_path / role
        bundle = stage / f'tb4-{role}'
        bundle.mkdir(parents=True)
        for name in (f'tb4-{role}', f'tb4-{role}-worker'):
            executable = bundle / name
            executable.write_text('#!/bin/sh\nexit 0\n')
            executable.chmod(0o755)
        for source, target in (('install-linux.sh', 'install.sh'), ('uninstall-linux.sh', 'uninstall.sh')):
            (stage / target).write_text((ROOT / 'packaging/desktop' / source).read_text().replace('@ROLE@', role))
        profile = profiles / role
        profile.mkdir(parents=True)
        (profile / 'preserved').write_text('retained')
        subprocess.run(['sh', str(stage / 'install.sh'), '--autostart'], env=env, check=True, capture_output=True, timeout=15)
        assert (installed / role / f'tb4-{role}').is_file()
        assert (home / f'config/autostart/tb4-{role}.desktop').is_file()
    subprocess.run(['sh', str(installed / 'watchdog/uninstall.sh')], env=env, check=True, capture_output=True, timeout=15)
    assert not (installed / 'watchdog').exists()
    assert (installed / 'fetcher/tb4-fetcher').is_file()
    assert all((profiles / role / 'preserved').is_file() for role in ('watchdog', 'fetcher'))


@pytest.mark.skipif(os.name == 'nt', reason='POSIX installer contract')
def test_linux_uninstaller_refuses_live_role(tmp_path):
    env = dict(os.environ, HOME=str(tmp_path), XDG_DATA_HOME=str(tmp_path / 'data'), XDG_CONFIG_HOME=str(tmp_path / 'config'))
    destination = tmp_path / 'data/tb4-apps/fetcher'
    destination.mkdir(parents=True)
    worker = destination / 'tb4-fetcher-worker'
    worker.write_text('#!/bin/sh\nexit 1\n')
    worker.chmod(0o755)
    uninstall = tmp_path / 'uninstall.sh'
    uninstall.write_text((ROOT / 'packaging/desktop/uninstall-linux.sh').read_text().replace('@ROLE@', 'fetcher'))
    result = subprocess.run(['sh', str(uninstall)], env=env, capture_output=True, timeout=15)
    assert result.returncode != 0
    assert worker.exists()
