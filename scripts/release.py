"""Bump the app version, add a CHANGELOG stub, commit and tag.

Usage:  python scripts/release.py patch|minor|major [--dry-run] [--push]
Rules: docs/VERSIONING.md.  The single source of truth is the VERSION file (shown in the app via /api/version).
"""
import argparse, pathlib, re, subprocess, sys, time

ROOT = pathlib.Path(__file__).resolve().parent.parent


def git(*a, check=True):
    return subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True, check=check).stdout.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("part", choices=["patch", "minor", "major"])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--push", action="store_true")
    a = ap.parse_args()
    cur = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    mj, mn, pt = map(int, re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", cur).groups())
    new = {"patch": f"{mj}.{mn}.{pt + 1}", "minor": f"{mj}.{mn + 1}.0", "major": f"{mj + 1}.0.0"}[a.part]
    print(f"{cur} -> {new}")
    if a.dry_run:
        return
    if git("status", "--porcelain"):
        sys.exit("Working tree is not clean; commit or stash your changes first.")
    (ROOT / "VERSION").write_text(new + "\n", encoding="utf-8")
    cl = ROOT / "CHANGELOG.md"
    text = cl.read_text(encoding="utf-8")
    stub = f"## [{new}] — {time.strftime('%Y-%m-%d')}\n\n- (تغییرات این نسخه را اینجا بنویسید)\n\n"
    cl.write_text(text.replace("## [", stub + "## [", 1) if "## [" in text else text + "\n" + stub, encoding="utf-8")
    git("add", "VERSION", "CHANGELOG.md")
    git("commit", "-m", f"release v{new}")
    git("tag", "-a", f"v{new}", "-m", f"ProcureMind {new}")
    print(f"Committed and tagged v{new}. Edit CHANGELOG.md, then: git commit --amend && git tag -f v{new}")
    if a.push:
        git("push", "origin", "HEAD", "--follow-tags")


if __name__ == "__main__":
    main()
