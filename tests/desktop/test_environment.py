import os
import sys

import pytest
from tb4.desktop.environment import prepare_external_programs


def test_source_runtime_environment_is_unchanged(monkeypatch):
    monkeypatch.setattr(sys, 'frozen', False, raising=False)
    before = dict(os.environ)
    prepare_external_programs()
    assert dict(os.environ) == before


@pytest.mark.skipif(os.name == 'nt', reason='POSIX library environment')
@pytest.mark.parametrize('original', [None, '/system-extra'])
def test_frozen_child_paths_restore_host_libraries_only(tmp_path, monkeypatch, original):
    bundle = tmp_path / 'bundle'
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, '_MEIPASS', str(bundle), raising=False)
    monkeypatch.setenv('LD_LIBRARY_PATH', str(bundle))
    if original is None:
        monkeypatch.delenv('LD_LIBRARY_PATH_ORIG', raising=False)
    else:
        monkeypatch.setenv('LD_LIBRARY_PATH_ORIG', original)
    monkeypatch.setenv('PATH', os.pathsep.join([str(bundle / 'Qt/bin'), '/usr/bin', '/bin']))
    prepare_external_programs()
    assert os.environ.get('LD_LIBRARY_PATH') == original
    assert os.environ['PATH'] == '/usr/bin:/bin'
