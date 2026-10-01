"""Model restart on actual protected files; never a live deployment."""
import sys

from tb4.commissioning_state import Setup
from tb4.commissioning_checks import detect_environment
from tb4.private_settings import native_settings
from test_private_settings_native import fixture


def test_actual_native_model_restart_preserves_identity_and_cancellation(fixture):
    root, store = fixture
    first = Setup(store, create=True)
    first.choose({"role":"fetcher", "network_scope":[]})
    identity = first.installation_id
    first.cancel()
    restarted = Setup(native_settings(root))
    assert restarted.installation_id == identity and restarted.status()["state"] == "CANCELLED"
    restarted.resume()
    assert restarted.missing_choices() == ("storage",)
    assert not restarted.status()["settings_validated"]


def test_actual_environment_probe_reports_only_closed_nonidentifying_facts():
    environment = detect_environment(launch_mode="DESKTOP_SESSION")
    assert environment.os == ("WINDOWS" if sys.platform == "win32" else "LINUX")
    assert environment.architecture in {"X64","ARM64"}
    assert environment.privilege in {"ROOT","ELEVATED","USER"}
    assert environment.launch_mode == "DESKTOP_SESSION"
    assert environment.session in {"INTERACTIVE","NONINTERACTIVE_OR_LOCKED","UNQUALIFIED"}
