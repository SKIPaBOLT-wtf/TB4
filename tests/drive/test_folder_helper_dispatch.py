"""Portable closed dispatch/order tests; mocked IO never qualifies real SSH."""
from io import BytesIO
from types import SimpleNamespace
import sys

import pytest

from tb4.drive import folder_helper as helper
from tb4.drive import folder_probe
from tb4.drive.docs_authority import AuthorityError

BAD_COMMANDS = [
    None, "", " tb4-folder-v1", "tb4-folder-v1 ", "tb4-folder-v1\n",
    "tb4-folder-v1 extra", "tb4-folder-probe-v1 extra", "TB4-FOLDER-V1",
    "tb4-folder-v2", "tb4-folder-v1;synthetic-command", "synthetic-command",
    "$(synthetic-command)", "\x00tb4-folder-v1", "x" * 4097,
]


@pytest.mark.parametrize("command,probe", [
    ("tb4-folder-v1", False), ("tb4-folder-probe-v1", True)])
def test_exact_two_fixed_tokens_select_only_the_existing_mode(command, probe):
    assert helper.dispatch_mode(command) is probe


@pytest.mark.parametrize("command", [*BAD_COMMANDS, 1, b"tb4-folder-v1", ["tb4-folder-v1"]])
def test_other_values_never_select_a_helper_mode(command):
    with pytest.raises(AuthorityError, match="^HELPER_COMMAND$"):
        helper.dispatch_mode(command)


@pytest.fixture
def main_io(monkeypatch):
    events = []
    class Input:
        def read(self, limit):
            events.append(("stdin", limit))
            return b"synthetic-closed-request"
    output = BytesIO()
    # Pytest resumes global sys.stdout between fixture setup and test call.
    # Keep only this helper's simulated IO private to the tested program.
    monkeypatch.setattr(helper, "sys", SimpleNamespace(platform="linux",
        stdin=SimpleNamespace(buffer=Input()), stdout=SimpleNamespace(buffer=output)))
    monkeypatch.setattr(helper.signal, "SIGALRM", 999, raising=False)
    monkeypatch.setattr(helper.signal, "signal", lambda *_: events.append(("signal",)))
    monkeypatch.setattr(helper.signal, "alarm", lambda value: events.append(("alarm", value)), raising=False)
    config = object()
    def load(path, *, mapping_store):
        assert path == "synthetic-server-config" and mapping_store is None
        events.append(("config",))
        return config
    def store(value):
        assert value is config
        events.append(("store",))
        return value
    def authority(value, raw):
        assert value is config and raw == b"synthetic-closed-request"
        events.append(("authority",))
        return b'{"result":"SYNTHETIC_NORMAL"}'
    def probe(value, raw):
        assert value is config and raw == b"synthetic-closed-request"
        events.append(("probe",))
        return b'{"result":"SYNTHETIC_PROBE"}'
    monkeypatch.setattr(helper, "load_config", load)
    monkeypatch.setattr(helper, "FolderStore", store)
    monkeypatch.setattr(helper, "handle", authority)
    monkeypatch.setattr(folder_probe, "handle_probe", probe)
    return events, output


def arguments(monkeypatch, *modes):
    monkeypatch.setattr(sys, "argv",
        ["synthetic-helper", "--config", "synthetic-server-config", *modes])


@pytest.mark.parametrize("command", [c for c in BAD_COMMANDS if c is None or "\x00" not in c])
def test_opt_in_rejects_before_config_stdin_store_or_handler(main_io, monkeypatch, command):
    events, output = main_io
    arguments(monkeypatch, "--credential-dispatch")
    if command is None:
        monkeypatch.delenv("SSH_ORIGINAL_COMMAND", raising=False)
    else:
        monkeypatch.setenv("SSH_ORIGINAL_COMMAND", command)
    assert helper.main() == 2
    assert events == [("signal",), ("alarm", 8)]
    assert output.getvalue() == b'{"result":"UNKNOWN"}'


@pytest.mark.parametrize("command,probe", [
    ("tb4-folder-v1", False), ("tb4-folder-probe-v1", True)])
def test_opt_in_routes_one_bounded_request_to_only_one_handler(main_io, monkeypatch, command, probe):
    events, output = main_io
    arguments(monkeypatch, "--credential-dispatch")
    monkeypatch.setenv("SSH_ORIGINAL_COMMAND", command)
    assert helper.main() == 0
    assert events == [("signal",), ("alarm", 8), ("config",),
                      ("stdin", helper.MAX_WIRE + 1)] + (
                          [("probe",)] if probe else [("store",), ("authority",)])
    assert output.getvalue() == (b'{"result":"SYNTHETIC_PROBE"}'
                                if probe else b'{"result":"SYNTHETIC_NORMAL"}')


@pytest.mark.parametrize("probe", [False, True])
def test_original_modes_ignore_untrusted_original_command(main_io, monkeypatch, probe):
    events, output = main_io
    arguments(monkeypatch, *(["--commissioning-probe"] if probe else []))
    monkeypatch.setenv("SSH_ORIGINAL_COMMAND", "unrecognized legacy original command")
    assert helper.main() == 0
    assert events[-1] == (("probe",) if probe else ("authority",))
    assert output.getvalue() == (b'{"result":"SYNTHETIC_PROBE"}'
                                if probe else b'{"result":"SYNTHETIC_NORMAL"}')


def test_both_modes_are_refused_before_any_helper_io(main_io, monkeypatch):
    events, output = main_io
    arguments(monkeypatch, "--commissioning-probe", "--credential-dispatch")
    with pytest.raises(SystemExit) as stopped:
        helper.main()
    assert stopped.value.code == 2 and events == [] and output.getvalue() == b""


def test_non_linux_does_not_enter_dispatch_or_config(main_io, monkeypatch):
    events, output = main_io
    arguments(monkeypatch, "--credential-dispatch")
    monkeypatch.setattr(helper.sys, "platform", "win32")
    monkeypatch.setenv("SSH_ORIGINAL_COMMAND", "tb4-folder-v1")
    assert helper.main() == 2 and events == [] and output.getvalue() == b""

