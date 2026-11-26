"""One-click update from GitHub (no git needed): downloads the latest code and copies it over this folder.

Never touched: models/, bin/, data/, logs/, .venv/, .git/, .env. Restart the app afterwards.
Usage:  python scripts/update.py            (or run scripts/update.bat on Windows)
"""
import argparse
import pathlib
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
URL = "https://github.com/RezaFarahanipy/ProcureMind/archive/refs/heads/main.zip"
KEEP = {"models", "bin", "data", "logs", ".venv", ".git", ".env"}


def version(folder: pathlib.Path) -> str:
    f = folder / "VERSION"
    return f.read_text(encoding="utf-8").strip() if f.exists() else "unknown"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default=str(ROOT), help="folder to update (default: this project)")
    ap.add_argument("--url", default=URL)
    ap.add_argument("--no-pip", action="store_true", help="do not reinstall Python requirements")
    a = ap.parse_args()
    target = pathlib.Path(a.target).resolve()
    old = version(target)
    print(f"Current version: {old}\nDownloading {a.url} ...")
    with tempfile.TemporaryDirectory() as tmp:
        zpath = pathlib.Path(tmp) / "src.zip"
        with urllib.request.urlopen(a.url, timeout=120) as r, open(zpath, "wb") as f:
            shutil.copyfileobj(r, f)
        with zipfile.ZipFile(zpath) as z:
            z.extractall(tmp)
        src = next(p for p in pathlib.Path(tmp).iterdir() if p.is_dir())
        for item in src.iterdir():
            if item.name in KEEP:
                if item.is_dir():
                    (target / item.name).mkdir(exist_ok=True)
                continue
            dest = target / item.name
            if item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest)
    new = version(target)
    if not a.no_pip and (target / "backend" / "requirements.txt").exists():
        print("Installing Python requirements ...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", str(target / "backend" / "requirements.txt")], check=False)
    print(f"Updated: {old} -> {new}. Restart start_app.bat to use the new version.")
    if old == new:
        print("(same version number: code may still have changed; see CHANGELOG.md)")


if __name__ == "__main__":
    main()
