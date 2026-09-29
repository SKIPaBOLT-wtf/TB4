"""Build actual independent desktop bundles; never access private deployment data."""
from __future__ import annotations

import argparse
import ast
import hashlib
import os
import shutil
import subprocess
import sys
import tarfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build(role: str, output: Path) -> None:
    if role not in {"watchdog", "fetcher"}:
        raise ValueError("invalid role")
    work = output / "build" / role
    work.mkdir(parents=True, exist_ok=True)
    bootstrap = work / "launch.py"
    bootstrap.write_text(
        'import importlib, sys\nfrom pathlib import Path\n'
        'sys.path.insert(0, str(Path(sys._MEIPASS) / "src"))\n'
        f'raise SystemExit(importlib.import_module("tb4.desktop.entry").main({role!r}))\n', encoding="utf-8")
    spec = work / "desktop.spec"
    tracked = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z", "src/tb4", "protocol", "config", "LICENSE"],
                             check=True, capture_output=True, timeout=20).stdout.decode().split("\0")
    data_files = []
    imports = set()
    for relative in filter(None, tracked):
        path = ROOT / relative
        if path.is_symlink() or not path.is_file():
            raise ValueError("source resource must be a regular tracked file")
        data_files.append((str(path), Path(relative).parent.as_posix()))
        if relative.startswith("src/") and path.suffix == ".py":
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Import):
                    imports.update(item.name for item in node.names)
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    imports.add(node.module)
    imports = sorted(name for name in imports if name != "tb4" and not name.startswith("tb4."))
    # Preserve the production resource layout; include only tracked source/data.
    spec.write_text(f'''
from PyInstaller.utils.hooks import collect_all
root = {str(ROOT)!r}
entry = {str(bootstrap)!r}
datas = {data_files!r}
binaries = []
hidden = {imports!r} + ['PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets']
for package in ('yaml', 'jsonschema', 'jsonschema_specifications', 'referencing', 'rpds',
                'attrs', 'attr', 'tomlkit', 'google.auth', 'google.oauth2', 'googleapiclient',
                'google_auth_oauthlib', 'google_auth_httplib2', 'httplib2', 'requests',
                'requests_oauthlib', 'oauthlib', 'certifi'):
    d, b, h = collect_all(package)
    datas += d
    binaries += b
    hidden += h

def analysis():
    return Analysis([entry], pathex=[], binaries=binaries, datas=datas,
                    hiddenimports=hidden, excludes=['tb4'], noarchive=False)
a = analysis()
p = PYZ(a.pure)
gui = EXE(p, a.scripts, [], exclude_binaries=True, name='tb4-{role}',
          debug=False, strip=False, upx=False, console=False)
b = analysis()
q = PYZ(b.pure)
worker = EXE(q, b.scripts, [], exclude_binaries=True, name='tb4-{role}-worker',
             debug=False, strip=False, upx=False, console=True)
coll = COLLECT(gui, worker, a.binaries, a.datas, b.binaries, b.datas,
               strip=False, upx=False, name='tb4-{role}')
''', encoding="utf-8")
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
                    "--distpath", str(output / "bundles"), "--workpath", str(work / "pyinstaller"), str(spec)],
                   check=True, timeout=1200)
    bundle = output / "bundles" / f"tb4-{role}"
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    installers = output / "installers"
    installers.mkdir(exist_ok=True)
    if os.name == "nt":
        compiler = shutil.which("iscc") or str(Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / "Inno Setup 6/ISCC.exe")
        subprocess.run([compiler, f"/DROLE={role}", f"/DSourceDir={bundle}",
                        f"/DOutputDir={installers}", f"/DVersion={version}",
                        str(ROOT / "packaging/desktop/windows.iss")], check=True, timeout=600)
    else:
        stage = output / "linux" / role
        stage.mkdir(parents=True, exist_ok=True)
        shutil.copytree(bundle, stage / bundle.name, dirs_exist_ok=True)
        for source, name in (("install-linux.sh", "install.sh"), ("uninstall-linux.sh", "uninstall.sh")):
            target = stage / name
            target.write_text((ROOT / "packaging/desktop" / source).read_text().replace("@ROLE@", role), encoding="utf-8")
            target.chmod(0o755)
        archive = installers / f"TB4-{role}-{version}-linux-x64.tar.gz"
        with tarfile.open(archive, "w:gz") as stream:
            stream.add(stage, arcname=f"TB4-{role}")
    records = []
    for path in sorted(installers.iterdir()):
        if path.suffix in {".exe", ".gz"}:
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            records.append(f"{digest}  {path.name}\n")
    (installers / "SHA256SUMS.txt").write_text("".join(records), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", choices=("watchdog", "fetcher"), required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "desktop-dist")
    args = parser.parse_args()
    build(args.role, args.output.resolve())
