# Changelog

User-visible changes are recorded here. Unreleased entries are not release claims.

## [Unreleased]

No changes yet.

## [0.1.0] - Initial release

Prepared for publication. Image availability requires the release workflow to pass
and both GHCR packages to allow anonymous pulls.

### Added

- Release-triggered GHCR API/worker publication with native Linux AMD64/ARM64
  integration gates and matching version tags, plus image-only Compose and
  container-based credential setup. Images require a successful maintainer release.
- Public HTTP sandbox lifecycle, files, commands and headless Chromium, plus an
  optional model tool-calling endpoint.
- Session-bound Streamable HTTP MCP at /mcp/ with file editing, background commands,
  polling/cancellation, lazy allocation, reuse and SQLite generation records.
  Recycled workspaces start empty.
- Private credential initialization and atomic token rotation with stable client
  identity and migration from legacy DEMO_API_KEY settings.
- Explicit local authentication bypass with LOOP_SANDBOX_AUTH_DISABLED=1;
  normal deployment defaults to token verification.
- MIT licensing, contributor/security policies, dependency updates, sequential
  integration commands and Python package verification.

### Changed

- Product/distribution names are Loop Sandbox and loop-sandbox; imports use
  loop_sandbox. Sources separate server, runtime, contracts, worker and adapters.
  Compose lives in deploy/ and images in docker/. See the
  [migration guide](docs/architecture/repository.md) for current paths.

### Limitations

- Single-user service with Docker socket authority; not hostile multi-tenant
  isolation. Public authentication uses one token principal, without OAuth.
- Workspaces are disposable; files and processes are lost on recycling or API
  restart. MCP clients must supply a stable session header and enforce remote
  execution boundaries.
- Core workers require a Linux Docker Engine or VM. Native credential setup uses
  POSIX locking; Windows uses WSL2. Real model and Azure deployment checks remain
  unvalidated.
