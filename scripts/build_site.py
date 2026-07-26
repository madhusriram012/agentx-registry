#!/usr/bin/env python3
"""Generate site/index.json from the registry — run by CI on every merge.
The static UI (site/index.html) fetches this to render search + package pages.
Stdlib + pyyaml only."""
from __future__ import annotations
import json
import sys
from pathlib import Path

import yaml


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    pkgs_dir = root / "packages"
    out: list[dict] = []

    for pkg_dir in sorted(p for p in pkgs_dir.iterdir() if p.is_dir()):
        meta_path = pkg_dir / "metadata.json"
        if not meta_path.exists():
            continue
        meta = json.loads(meta_path.read_text())
        latest = meta.get("latest")
        manifest = {}
        vdir = pkg_dir / latest if latest else None
        if vdir and vdir.exists():
            for mf in ("skill.yaml", "agent.yaml"):
                if (vdir / mf).exists():
                    manifest = yaml.safe_load((vdir / mf).read_text()) or {}
                    break

        owners_path = root / "OWNERS.json"
        owners = json.loads(owners_path.read_text()) if owners_path.exists() else {}

        out.append({
            "name": meta["name"],
            "kind": manifest.get("kind", "?"),
            "latest": latest,
            "versions": meta.get("versions", []),
            "description": (manifest.get("description") or "").strip(),
            "dependencies": manifest.get("dependencies", []) or [],
            "model": manifest.get("model"),
            "owners": owners.get(meta["name"], []),
        })

    site = root / "site"
    site.mkdir(exist_ok=True)
    (site / "index.json").write_text(json.dumps({"packages": out}, indent=2) + "\n")
    print(f"site/index.json: {len(out)} packages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
