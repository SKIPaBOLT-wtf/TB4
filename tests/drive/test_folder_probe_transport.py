"""Pure protected-endpoint/argument rejection; no native/SSH proof is inferred."""
from dataclasses import replace
import os
from pathlib import Path
import sys

import pytest

from tb4.drive.docs_authority import AuthorityError
from tb4.drive.folder_probe_transport import ProbeEndpoint, _argv, _file_option

TARGET = "00000000-0000-4000-8000-000000000229"
TRUST = "e" * 64


def endpoint(tmp_path):
    return ProbeEndpoint(TARGET, TRUST, str(Path(sys.executable).resolve()), "storage.invalid",
                         22222, "synthetic-user", str(tmp_path / "synthetic-known"), 1)


@pytest.mark.parametrize("field,value", [
    ("target_id", "not-an-id"), ("trust", "g" * 64), ("executable", "ssh"),
    ("host", "-oProxyCommand=BAD"), ("host", "storage.invalid;BAD"), ("host", "bad..invalid"),
    ("host", "a" * 64 + ".invalid"), ("host", "bad\ninvalid"),
    ("port", True), ("port", 0), ("port", 65536), ("user", "bad\nuser"),
    ("known_hosts", "relative-known"), ("known_version", True), ("known_version", 0),
    ("timeout", True), ("timeout", 0), ("timeout", 16), ("timeout", float("nan")),
], ids=["target", "trust", "relative-client", "host-option", "host-shell", "host-empty-label",
        "host-label-length", "host-control", "bool-port", "zero-port", "large-port",
        "user-control", "relative-known", "bool-version", "zero-version", "bool-timeout",
        "zero-timeout", "large-timeout", "nan-timeout"])
def test_bad_private_endpoint_is_closed_before_native_io(tmp_path, field, value):
    with pytest.raises(AuthorityError, match="^PROBE_ENDPOINT$"):
        replace(endpoint(tmp_path), **{field: value})


@pytest.mark.parametrize("host", ["storage.invalid", "127.0.0.1", "::1", "fe80::1%synthetic0"])
def test_exact_private_dns_ipv4_ipv6_and_scoped_address_inputs(tmp_path, host):
    value = replace(endpoint(tmp_path), host=host)
    assert value.host == host


def test_fixed_args_disable_other_identity_and_command_sources_and_preserve_spaces_percent(tmp_path):
    value = endpoint(tmp_path)
    key = str(tmp_path / "synthetic key % value")
    known = str(tmp_path / "synthetic known % value")
    argv = _argv(value, key, known)
    assert argv[:4] == (value.executable, "-F", "none", "-T")
    assert argv[-6:] == ("-p", "22222", "-l", "synthetic-user", "storage.invalid", "tb4-folder-probe-v1")
    assert len(argv) <= 64 and len([v for v in argv if v.startswith("-oIdentityFile=")]) == 1
    assert "-oIdentityAgent=none" in argv and "-oBatchMode=yes" in argv
    assert "-oControlPath=none" in argv and "-oControlPersist=no" in argv
    assert "-oProxyCommand=none" in argv and "-oProxyJump=none" in argv
    assert "-oPasswordAuthentication=no" in argv and "-oKbdInteractiveAuthentication=no" in argv
    assert "-oPermitLocalCommand=no" in argv and "-oClearAllForwardings=yes" in argv
    assert "-oStrictHostKeyChecking=yes" in argv and "-oUpdateHostKeys=no" in argv
    assert "-oConnectionAttempts=1" in argv and "-oConnectTimeout=2" in argv
    assert "-oIdentityFile=" + _file_option(key) in argv
    assert "-oUserKnownHostsFile=" + _file_option(known) in argv
    assert "%%" in _file_option(key) and _file_option(key).startswith('"')
    null = '"NUL"' if os.name == "nt" else '"/dev/null"'
    assert "-oCertificateFile=" + null in argv and "-oGlobalKnownHostsFile=" + null in argv
    assert all(token not in repr(value) for token in (TRUST, TARGET, value.known_hosts, value.host))


@pytest.mark.parametrize("suffix", ["bad\nfile", "bad\rfile", "bad\tfile", "$" + "{UNSELECTED}"],
                         ids=["newline", "return", "tab", "environment"])
def test_file_directive_cannot_select_an_interpolated_or_control_path(tmp_path, suffix):
    with pytest.raises(AuthorityError, match="^PROBE_ENDPOINT$"):
        _argv(endpoint(tmp_path), str(tmp_path / suffix), str(tmp_path / "synthetic-known"))
