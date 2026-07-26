# agentx-registry

Central package registry for [agentx](https://github.com/YOUR_USERNAME/agentx) — AI agents & skills, Maven-style.

**No server. This git repository IS the registry**, served via GitHub raw URLs.

## Install packages from this registry

```bash
pip install agentx-cli
export AGENTX_REGISTRY=https://raw.githubusercontent.com/YOUR_USERNAME/agentx-registry/main
agentx install my-agent
```

## Layout

```
packages/
  <name>/
    metadata.json                 # versions list + latest
    <version>/
      <name>-<version>.tgz        # the artifact
      <name>-<version>.tgz.sha256 # integrity hash
      skill.yaml | agent.yaml     # manifest (read by the resolver)
```

Published versions are **immutable** — CI rejects any PR that modifies an existing version. Ship a new version instead.

## Publish a package

See [CONTRIBUTING.md](CONTRIBUTING.md).
