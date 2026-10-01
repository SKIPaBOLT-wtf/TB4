"""Credential-free acceptance of the ACTUAL binaries and both role installers."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "desktop-dist"
ROLES = ("watchdog", "fetcher")


def run(argv, *, env, timeout=180):
    result = subprocess.run([str(item) for item in argv], env=env, capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f"distribution command failed: {Path(argv[0]).name}: {result.returncode}; "
                           f"{result.stdout[-3000:].decode(errors='replace')} "
                           f"{result.stderr[-3000:].decode(errors='replace')}")
    return result


def main():
    results = []
    with tempfile.TemporaryDirectory(prefix="tb4-desktop-acceptance-") as temp:
        home = Path(temp)
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen", PYTHONUTF8="1")
        if os.name == "nt":
            env["LOCALAPPDATA"] = str(home / "local")
            profiles = home / "local/TB4"
        else:
            env.update(HOME=str(home), XDG_DATA_HOME=str(home / "data"), XDG_CONFIG_HOME=str(home / "config"))
            profiles = home / "data/tb4"
        suffix = ".exe" if os.name == "nt" else ""
        for role in ROLES:
            bundle = DIST / "bundles" / f"tb4-{role}"
            worker = bundle / f"tb4-{role}-worker{suffix}"
            gui = bundle / f"tb4-{role}{suffix}"
            report = home / f"{role}-self-test.json"
            run([worker, "--action", "self-test", "--report", report], env=env)
            assert json.loads(report.read_text())["self_test"] == "PASS"
            gui_report = home / f"{role}-gui.json"
            run([gui, "--action", "gui-smoke", "--report", gui_report], env=env)
            observed = json.loads(gui_report.read_text())
            assert observed["gui_smoke"] == "PASS" and observed["worker_started"] is False
            setup_report = home / f"{role}-setup-gui.json"
            run([gui, "--action", "setup-smoke", "--report", setup_report], env=env)
            setup_observed = json.loads(setup_report.read_text())
            assert setup_observed["setup_gui_smoke"] == "PASS"
            assert setup_observed["settings_created"] is False and setup_observed["runtime_started"] is False
            profile = profiles / role
            profile.mkdir(parents=True, exist_ok=True)
            (profile / "preserve-marker.txt").write_text("private-profile-preservation-test")
            results.append({"role": role, "bundle_self_test": "PASS", "gui_smoke": "PASS",
                            "setup_gui_smoke": "PASS"})

        installed = {}
        for role in ROLES:
            if os.name == "nt":
                setup, = (DIST / "installers").glob(f"TB4-{role}-*-setup.exe")
                destination = home / "applications" / role
                run([setup, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-",
                     f"/DIR={destination}", "/TASKS="], env=env)
            else:
                run(["sh", DIST / "linux" / role / "install.sh"], env=env)
                destination = home / "data/tb4-apps" / role
            installed[role] = destination
            executable = destination / f"tb4-{role}-worker{suffix}"
            assert executable.is_file()
            run([executable, "--action", "self-test"], env=env)

        for index, role in enumerate(ROLES):
            if os.name == "nt":
                run([installed[role] / "unins000.exe", "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"], env=env)
            else:
                run(["sh", installed[role] / "uninstall.sh"], env=env)
            deadline = time.monotonic() + 30
            binary = installed[role] / f"tb4-{role}{suffix}"
            while binary.exists() and time.monotonic() < deadline:
                time.sleep(.25)
            assert not binary.exists(), "role binary survived completed uninstall"
            assert all((profiles / item / "preserve-marker.txt").is_file() for item in ROLES)
            if index == 0:
                peer = installed[ROLES[1]] / f"tb4-{ROLES[1]}-worker{suffix}"
                assert peer.is_file(), "uninstaller removed the other role"
                run([peer, "--action", "self-test"], env=env)
            results[index]["install_uninstall_profile_isolation"] = "PASS"
    (DIST / "acceptance.json").write_text(json.dumps({"results": results, "scope": "credential-free-platform-CI"}, indent=2), encoding="utf-8")
    print(json.dumps(results))


if __name__ == "__main__":
    main()
