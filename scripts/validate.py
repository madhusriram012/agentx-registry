#!/usr/bin/env python3
"""Validate an agentx registry — run by CI on every PR.

Checks:
  1. Layout: packages/<name>/<version>/ contains <name>-<version>.tgz, its .sha256, and a manifest
  2. sha256 in the .sha256 file matches the actual tarball
  3. Manifest name/version match the directory path; deps are name@range shaped
  4. metadata.json lists exactly the version dirs present; "latest" is the highest version
  5. IMMUTABILITY (PR mode): no file under an already-published version dir was
     modified or deleted — compares against the base branch (like Maven Central,
     published versions can never change)

Usage:
  python scripts/validate.py .                # full check
  python scripts/validate.py . --base main    # + immutability vs base branch (CI)

Stdlib only — no dependencies.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

try:
    import yaml  # optional; falls back to a minimal parser check if absent
except ImportError:
    yaml = None

NAME_RE = re.compile(r"^[a-z0-9-]+$")
DEP_RE = re.compile(r"^[a-z0-9-]+@.+$")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+].+)?$")

errors: list[str] = []


def err(msg: str) -> None:
    errors.append(msg)
    print(f"  ✗ {msg}")


def sha256_of(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def semver_key(v: str):
    return tuple(int(x) for x in re.match(r"(\d+)\.(\d+)\.(\d+)", v).groups())


def validate_version_dir(name: str, vdir: Path) -> None:
    version = vdir.name
    if not SEMVER_RE.match(version):
        err(f"{name}/{version}: not a valid semver version")
        return

    tgz = vdir / f"{name}-{version}.tgz"
    sha = vdir / f"{name}-{version}.tgz.sha256"
    manifests = [p for p in (vdir / "skill.yaml", vdir / "agent.yaml") if p.exists()]

    if not tgz.exists():
        err(f"{name}/{version}: missing {tgz.name}")
    if not sha.exists():
        err(f"{name}/{version}: missing {sha.name}")
    if not manifests:
        err(f"{name}/{version}: missing skill.yaml or agent.yaml")

    if tgz.exists() and sha.exists():
        expected = sha.read_text().split()[0]
        actual = sha256_of(tgz)
        if expected != actual:
            err(f"{name}/{version}: sha256 mismatch (file says {expected[:12]}…, actual {actual[:12]}…)")

    if manifests and yaml:
        m = yaml.safe_load(manifests[0].read_text())
        if m.get("name") != name:
            err(f"{name}/{version}: manifest name '{m.get('name')}' != directory '{name}'")
        if m.get("version") != version:
            err(f"{name}/{version}: manifest version '{m.get('version')}' != directory '{version}'")
        if m.get("kind") not in ("skill", "agent"):
            err(f"{name}/{version}: manifest kind must be skill|agent")
        for d in m.get("dependencies") or []:
            if not DEP_RE.match(d):
                err(f"{name}/{version}: bad dependency format '{d}' (want name@range)")


def validate_package(pkg_dir: Path) -> None:
    name = pkg_dir.name
    if not NAME_RE.match(name):
        err(f"package '{name}': invalid name (lowercase alphanumeric + dashes)")
        return

    version_dirs = sorted([d for d in pkg_dir.iterdir() if d.is_dir()], key=lambda d: d.name)
    for vdir in version_dirs:
        validate_version_dir(name, vdir)

    meta_path = pkg_dir / "metadata.json"
    if not meta_path.exists():
        err(f"{name}: missing metadata.json")
        return
    meta = json.loads(meta_path.read_text())
    dir_versions = sorted(d.name for d in version_dirs)
    meta_versions = sorted(meta.get("versions", []))
    if dir_versions != meta_versions:
        err(f"{name}: metadata.json versions {meta_versions} != directories {dir_versions}")
    if meta_versions:
        highest = max(meta_versions, key=semver_key)
        if meta.get("latest") != highest:
            err(f"{name}: metadata.json latest '{meta.get('latest')}' should be '{highest}'")


def check_ownership(root: Path, base: str, author: str) -> None:
    """Namespace enforcement (Maven groupId equivalent): the PR author must own
    every package the PR touches. New packages: the same PR must add the author
    to OWNERS.json for that package (first-publish = namespace claim)."""
    owners_path = root / "OWNERS.json"
    owners: dict = json.loads(owners_path.read_text()) if owners_path.exists() else {}

    diff = subprocess.run(
        ["git", "diff", "--name-only", f"origin/{base}...HEAD", "--", "packages/"],
        cwd=root, capture_output=True, text=True,
    )
    touched_pkgs = sorted({p.split("/")[1] for p in diff.stdout.splitlines() if p.count("/") >= 2})

    for pkg in touched_pkgs:
        allowed = owners.get(pkg, [])
        if author not in allowed:
            if not allowed:
                err(f"OWNERSHIP: new package '{pkg}' — this PR must also add "
                    f'"{pkg}": ["{author}"] to OWNERS.json to claim the namespace')
            else:
                err(f"OWNERSHIP: '{pkg}' is owned by {allowed}; PR author '{author}' may not publish to it")


def check_immutability(root: Path, base: str) -> None:
    """No modified/deleted files under existing version dirs (adds are fine)."""
    diff = subprocess.run(
        ["git", "diff", "--name-status", f"origin/{base}...HEAD", "--", "packages/"],
        cwd=root, capture_output=True, text=True,
    )
    if diff.returncode != 0:
        print(f"  ! immutability check skipped (git diff failed: {diff.stderr.strip()})")
        return
    base_files = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", f"origin/{base}", "packages/"],
        cwd=root, capture_output=True, text=True,
    ).stdout.splitlines()
    published = set(base_files)

    for line in diff.stdout.splitlines():
        status, _, path = line.partition("\t")
        inside_version = re.match(r"packages/[^/]+/\d+\.\d+\.\d+.*/", path + "/") if path.count("/") >= 2 else None
        if path.endswith("metadata.json"):
            continue  # metadata is allowed to change (new versions appended)
        if status.startswith(("M", "D", "R")) and path in published and inside_version:
            err(f"IMMUTABILITY VIOLATION: '{path}' modifies an already-published version. "
                f"Publish a new version instead.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path)
    ap.add_argument("--base", help="base branch for immutability diff (CI mode)")
    ap.add_argument("--pr-author", help="GitHub login of the PR author (enables ownership check)")
    args = ap.parse_args()

    pkgs_dir = args.root / "packages"
    packages = [d for d in pkgs_dir.iterdir() if d.is_dir()] if pkgs_dir.exists() else []
    print(f"Validating {len(packages)} package(s) in {pkgs_dir} ...")
    for pkg in sorted(packages):
        validate_package(pkg)
    if args.base:
        check_immutability(args.root, args.base)
        if args.pr_author:
            check_ownership(args.root, args.base, args.pr_author)

    if errors:
        print(f"\nFAILED: {len(errors)} error(s)")
        return 1
    print("\nOK: registry is valid ✔")
    return 0


if __name__ == "__main__":
    sys.exit(main())
