# Publishing to agentx-registry

1. **Fork** this repository and clone your fork.
2. **Build your package** with the agentx CLI:
   ```bash
   pip install agentx-cli
   agentx init skill my-skill --ver 1.0.0
   # edit my-skill/SKILL.md and skill.yaml (add dependencies if any)
   ```
3. **Publish into your local fork checkout:**
   ```bash
   AGENTX_REGISTRY=/path/to/your/agentx-registry agentx publish my-skill
   ```
   This creates `packages/my-skill/1.0.0/` with the tarball, sha256, and manifest, and updates `metadata.json`.
4. **Commit and open a Pull Request:**
   ```bash
   cd /path/to/your/agentx-registry
   git checkout -b publish/my-skill-1.0.0
   git add packages/my-skill
   git commit -m "publish my-skill@1.0.0"
   git push -u origin publish/my-skill-1.0.0
   ```
5. CI validates automatically (schema, sha256, metadata consistency, immutability). A maintainer merges → your package is live immediately.

## Rules

- Package names: lowercase, alphanumeric + dashes
- Versions: semver (`1.2.3`), **immutable once merged** — never modify a published version, publish a new one
- Dependencies: `name@range` (npm-style ranges: `^1.0.0`, `1.x`, `>=2.0.0 <3.0.0`)
- No secrets, no malicious instructions in SKILL.md files (reviewed before merge)
