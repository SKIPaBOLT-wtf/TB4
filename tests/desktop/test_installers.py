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


@pytest.mark.skipif(os.name == 'nt', reason='POSIX installer contract')
@pytest.mark.parametrize('script', ['install-linux.sh', 'uninstall-linux.sh'])
@pytest.mark.parametrize('table_type', ['directory', 'dangling-symlink'])
@pytest.mark.parametrize('table_location', ['network-table', 'custom-table', 'data/nested-custom'])
def test_linux_installer_preserves_installation_local_table_before_any_replacement(tmp_path, script, table_type, table_location):
    env = dict(os.environ, HOME=str(tmp_path), XDG_DATA_HOME=str(tmp_path / 'data'),
               XDG_CONFIG_HOME=str(tmp_path / 'config'))
    destination = tmp_path / 'data/tb4-apps/watchdog'
    destination.mkdir(parents=True)
    worker = destination / 'tb4-watchdog-worker'
    worker.write_text('#!/bin/sh\nexit 0\n'); worker.chmod(0o755)
    table = destination / table_location
    table.parent.mkdir(parents=True, exist_ok=True)
    if table_type == 'directory':
        table.mkdir(); (table / 'settings.json').write_text('synthetic-retained-table')
    else:
        if table_location != 'network-table':
            pytest.skip('a dangling custom link contains no table data and native storage never adopts it')
        table.symlink_to(destination / 'absent-target', target_is_directory=True)
    source = tmp_path / 'operation.sh'
    source.write_text((ROOT / 'packaging/desktop' / script).read_text().replace('@ROLE@', 'watchdog'))
    result = subprocess.run(['sh', str(source)], env=env, capture_output=True, timeout=15)
    assert result.returncode != 0 and worker.exists()
    assert not destination.with_name('watchdog.previous').exists()
    if table_type == 'directory':
        assert (table / 'settings.json').read_text() == 'synthetic-retained-table'
    else:
        assert table.is_symlink()


@pytest.mark.skipif(os.name == 'nt', reason='POSIX installer contract')
@pytest.mark.parametrize('operation', ['install', 'uninstall'])
@pytest.mark.parametrize('failure', ['failed-search', 'denied-directory'])
def test_linux_installer_refuses_when_local_data_inspection_is_unavailable(tmp_path, operation, failure):
    if failure == 'denied-directory' and os.geteuid() == 0:
        pytest.skip('permission denial requires an actual non-root Linux principal')
    home = tmp_path / 'isolated-home'
    home.mkdir()
    env = dict(os.environ, HOME=str(home), XDG_DATA_HOME=str(home / 'data'),
               XDG_CONFIG_HOME=str(home / 'config'))
    destination = home / 'data/tb4-apps/watchdog'
    destination.mkdir(parents=True)
    worker = destination / 'tb4-watchdog-worker'
    original = '#!/bin/sh\n# original-synthetic\nexit 0\n'
    worker.write_text(original)
    worker.chmod(0o755)
    table = destination / 'custom-table/settings.json'
    table.parent.mkdir()
    table.write_text('synthetic-preserved-table')
    stage = tmp_path / 'candidate'
    stage.mkdir()
    bundle = stage / 'tb4-watchdog'
    bundle.mkdir()
    for name in ('tb4-watchdog', 'tb4-watchdog-worker'):
        candidate = bundle / name
        candidate.write_text('#!/bin/sh\n# candidate-synthetic\nexit 0\n')
        candidate.chmod(0o755)
    (stage / 'uninstall.sh').write_text('#!/bin/sh\nexit 0\n')
    script = stage / (operation + '.sh')
    script.write_text((ROOT / ('packaging/desktop/' + operation + '-linux.sh')).read_text().replace('@ROLE@', 'watchdog'))
    if failure == 'failed-search':
        shims = tmp_path / 'shims'
        shims.mkdir()
        find = shims / 'find'
        find.write_text('#!/bin/sh\nexit 42\n')
        find.chmod(0o755)
        env['PATH'] = str(shims) + os.pathsep + env['PATH']
    else:
        table.parent.chmod(0)
    try:
        result = subprocess.run(['sh', str(script)], env=env, capture_output=True, timeout=20)
    finally:
        if failure == 'denied-directory':
            table.parent.chmod(0o700)  # Restore this isolated fixture only.
    assert result.returncode != 0
    assert worker.read_text() == original
    assert table.read_text() == 'synthetic-preserved-table'
    assert not destination.with_name('watchdog.previous').exists()
    assert not (home / 'data/applications/tb4-watchdog.desktop').exists()
    assert str(table.parent).encode() not in result.stdout + result.stderr
