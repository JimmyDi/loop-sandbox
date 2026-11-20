# Loop Sandbox: coding agent guide and feature record

Read this file before editing. Update it in the same change set as every repository
change, including fixes, refactoring, tests, configuration, and documentation.
Read-only investigations do not require an update.
Public behavior and migration changes also update CHANGELOG.md under Unreleased;
AGENTS.md remains the detailed coding-agent feature record. See CONTRIBUTING.md
and SECURITY.md before preparing content for public review.

## Project conventions

- Product: Loop Sandbox. Repository/distribution: loop-sandbox. Import: loop_sandbox.
- Keep all repository content in English; do not introduce Chinese text.
- Inspect the working tree and preserve existing changes before editing.
- Keep scope focused. Preserve the optional model integration when working on
  sandbox HTTP capabilities unless explicitly asked to remove it.
- Never commit credentials or expose their values in logs or documentation.
- Use Python 3.12+, uv, the root pyproject.toml and uv.lock. Do not introduce a
  second package manager, lockfile, or empty service/SDK directory without need.

## Architecture and ownership

Full directory map, migration notes, and reviewed open-source references:
[repository architecture](docs/architecture/repository.md).

Paths below are relative to src/loop_sandbox/ unless stated otherwise.

| Files or directories | Responsibility |
|---|---|
| server/main.py | Compose the public FastAPI app and register core/optional routers |
| server/auth.py, server/routes/ | Public authentication and HTTP route registration |
| server/lifecycle.py, server/state.py | Allocation, in-memory leases, TTL, cancellation/recovery, shutdown cleanup |
| server/client.py | Worker addressing, internal authentication, forwarding, capability calls |
| runtime/docker.py | Docker provisioning, networks, limits, deletion, startup sweep |
| contracts/models.py | Shared request schemas and limits; no service dependencies |
| worker/app.py | Internal authenticated HTTP service and command serialization |
| worker/files.py, worker/commands.py, worker/browser.py | File, process, and browser capabilities |
| server/workspaces.py, server/session_tools.py | Session bindings, generations, leases and operation dispatch |
| integrations/mcp/app.py | Authenticated session-scoped Streamable HTTP MCP |
| worker/processes.py | Background Bash polling, timeouts and cancellation |
| integrations/model_agent/ | Optional model endpoint, runner, tool schemas, budgets, trace |
| docker/, deploy/ (root) | Image definitions and local deployment |
| specs/ (root) | Generated public and worker OpenAPI snapshots |
| scripts/ (root) | Local setup, architecture/content checks, schema export and package verification |
| tests/unit/, tests/integration/ (root) | Component tests and live Docker verification |
| README.md, docs/ (root) | User documentation, architecture, deployment, validation |

A logical sandbox maps to one worker container, a dedicated network, an internal
token, and expiration time. Clients call the controller, which forwards capability
requests to the worker. State is in memory; startup clears managed sandboxes.
Files are temporary and worker outbound access is disabled by default.

### Dependency rules

- contracts and runtime must not import controller, worker, or model code.
- worker may import only contracts and its own modules within loop_sandbox.
- server routes use lifecycle/client services; those services share state.
- Optional integrations may use server/client.py; core services must not import
  integrations. Only server/main.py composes the optional endpoint into the app.
- Use absolute package imports and empty __init__.py markers, without re-export
  barrels. Keep dependency direction checked by scripts/check_architecture.py.
- Preserve HTTP behavior during structural changes. Record intentional contract
  changes and regenerate specs; do not hand-edit generated JSON snapshots.

## Feature development workflow

1. Read the relevant implementation, tests, architecture guide, and feature row.
2. Add an in-progress change-log entry with intended behavior, affected components,
   acceptance criteria, and any migration requirements before implementation.
3. Implement at the owning layer. A new HTTP capability normally touches contracts,
   a worker handler, server client/route wiring, documentation, and verification.
   Update model tools only when relevant to the requested feature.
4. Run checks appropriate to the change; add meaningful regression coverage for
   changed behavior. Documentation-only changes do not need new runtime tests.
5. Update the inventory and entry below with final behavior, files, actual check
   results, and remaining gaps. Update README, architecture, and validation docs
   when affected. Do not claim earlier verification as a newly executed result.

Every change set must update this file. A concise log entry is sufficient when
behavior and feature inventory are unchanged.

## Verification

Run commands from the repository root. Bootstrap with make setup and make install.

| Change | Required or relevant checks |
|---|---|
| Python behavior | make check: Ruff, formatting, unit tests, import boundaries, HTTP snapshots, source language/whitespace and Markdown links |
| HTTP models or routes | make specs for intentional changes; inspect specs diff and run affected request tests |
| Packaging/dependencies | make install; make check; make package verifies archives, license, metadata, CLI and installed imports |
| Compose | docker compose --env-file .env -f deploy/compose.yaml config -q |
| Images or worker integration | make build and make up, then make smoke |
| Lifecycle/runtime | make lifecycle; creates sandboxes, waits for TTL, and forcibly restarts the controller; finish active tasks first |
| Real model integration | make agent with a configured model; report separately from mock-model tests |
| Documentation only | Check links, path references, English content, git diff --check |

Builds use docker/api.Dockerfile and docker/worker.Dockerfile. Compose is under
deploy/compose.yaml with repository-root build context and explicit loop-sandbox
project name. Do not rely on a root compose.yaml or obsolete Python module paths.
There is no frontend, style pipeline, or configured type-checker. Do not imply
these checks ran. Do not run live tests against unrelated deployments.

## Public contribution and automation

- Follow CONTRIBUTING.md and the PR template; use Conventional Commits titles.
- Check outgoing files/history/attachments locally for secrets and private data.
  Do not publish discovered values or change Git history without authorization.
- Native CLI/setup supports Linux/macOS; Windows uses WSL2. Core workers are Linux.
- CI pins Ubuntu 24.04, read-only contents permissions and job timeouts. It runs
  offline/package checks before a separate sequential Docker integration job.
- make integration runs smoke, mcp, rotation and lifecycle in sequence, including
  under make -j. Finish sessions first and enable authentication. Token rotation
  restores the credential; lifecycle deliberately restarts the controller.
- Renovate needs maintainer activation and never auto-merges. Private vulnerability
  reporting needs GitHub repository configuration. Neither is activated by files.
- Stable GitHub Releases trigger GHCR publication after native AMD64/ARM64 checks.
  Image-only Compose and container credential setup are documented in
  [container releases](docs/releases.md); PR CI uses local images and never pushes.

## Feature inventory

| Feature | Behavior | Main owners | Acceptance evidence |
|---|---|---|---|
| Credentials | Idempotent init, private atomic rotation, stable server-owned client identity, legacy migration | server/cli.py, server/credentials.py, server/auth.py | tests/unit/test_credentials.py, tests/integration/token_rotation.py |
| Session MCP | Stable client session header, lazy allocation/reuse, disposable recreation, SQLite generation bindings, six file/process tools | integrations/mcp/, server/workspaces.py, server/session_tools.py, worker/processes.py | tests/unit/test_sessions.py, tests/integration/mcp_sessions.py |
| Lifecycle | Create/list/delete; 60-3600 second TTL, default 900; capacity 4; periodic/startup cleanup | server/lifecycle.py, server/state.py, runtime/docker.py | tests/unit/test_server.py, tests/unit/test_docker.py, live lifecycle test |
| Files | UTF-8 read/write up to 1 MB; binary download up to 5 MB; workspace path checks; temporary storage | worker/files.py, worker/app.py, server/client.py, contracts/models.py | tests/unit/test_files.py, live smoke test |
| Commands | Shell/Python in /workspace; 1-60 second timeout; exit code, timeout/truncation flags; 64 KiB returned output | worker/commands.py, worker/app.py, server/client.py | tests/unit/test_commands.py, live smoke test |
| Browser | Headless Chromium; open/set_content/snapshot/click/fill/screenshot; one reused page per sandbox | worker/browser.py, worker/app.py, docker/worker.Dockerfile | Real Chromium smoke test |
| Runtime boundaries | Non-root, read-only root, CPU/memory/PID limits, dedicated networks, no published worker ports, offline by default | runtime/docker.py, deploy/compose.yaml, docker/worker.Dockerfile | Live lifecycle test; not hostile multi-tenant isolation |
| Optional model integration | Compatible Chat Completions tools, budgets and trace; requires LLM_API_KEY | integrations/model_agent/, server/main.py | tests/unit/test_model_agent.py; real model check pending |
| HTTP contracts | Generated public/internal OpenAPI snapshots; no API changes during reorganization | contracts/, server/routes/, specs/, scripts/export_specs.py | Snapshot checks and pre/post schema comparison |
| Architecture | Explicit control/runtime/worker/contracts/integrations boundaries; single distribution, image-specific source copying | src/loop_sandbox/, docker/, scripts/check_architecture.py | Static import checks, wheel/image builds, live tests |
| Developer workflow | Locked dependencies, focused unit tests, live integration scripts, CI | Makefile, pyproject.toml, uv.lock, tests/, .github/workflows/check.yml | See docs/validation.md |
| Identity/language | Loop Sandbox / loop-sandbox / loop_sandbox; English content | Package, Docker config, README.md, docs/ | Rename and English documentation retained |
| Coding agent maintenance | AGENTS.md is the single guide and feature record; update it in every change set | AGENTS.md, docs/architecture/repository.md | Documentation checks |

The inventory describes implementation, not a release guarantee. Azure deployment
and real model calls have not been validated. See docs/validation.md for evidence.

## Change log

Newest first. Include date, status, behavior, files, verification, remaining gaps.

### 2026-11-20: v0.1.0 release preparation (complete; publication pending)

- Finalize the initial version changelog and make installation availability depend
  on successful release publication. Package and both image defaults already match
  0.1.0; no dependency/runtime changes are intended.
- Verification: English content/local links, whitespace and package/image/changelog
  version consistency passed. Documentation-only changes; runtime tests were not
  rerun locally. PR CI remains required before merge.
- Files: CHANGELOG.md, README.md, docs/releases.md and AGENTS.md. Release creation
  and GHCR visibility remain separate maintainer actions.

### 2026-11-20: GHCR release images (complete; publication pending)

- Add release-triggered image publication gated by native AMD64/ARM64 checks and
  Docker integration. Publish matching API/worker version tags, without latest.
- Add standalone image-only Compose, container-based credential setup and release
  instructions. Preserve source development deployment and local private settings.
- Verification: make check passed 22 unit tests and static/content checks; make
  package passed archive/metadata/import checks. Both Compose files parsed and
  actionlint passed both workflows. Container-only init/re-init/rotation passed
  on ARM64, preserving identity and private file permissions. API rebuilt using
  the documented public mirror/cache after slow default dependency downloads.
  Worker rebuild was stopped during slow package downloads; its full build is
  delegated to PR CI. No fresh local worker build is claimed.
- CI now runs full integration through image-only Compose with locally built
  images. No local lifecycle tests were run against the active user deployment.
- Both native release checks, registry push/manifest assembly and anonymous pull
  need the release event; this change does not create a release or publish images.
- Files: release-images.yml, check.yml, both Dockerfiles and Compose files,
  docs/releases.md, README.md, CONTRIBUTING.md, CHANGELOG.md and this record.

### 2026-11-20: Public contributor and release readiness (complete)

- Add security/contributor guidance, public changelog, PR template and dependency updates.
- Improve MCP-first startup docs, platform support, state/lifecycle descriptions.
- Extend CI and Make commands with sequential MCP/rotation checks and package verification.
- Verification: make check passed 22 unit tests and all static/content checks;
  make package passed archive/license/metadata/CLI/import checks. Clean copied
  source bootstrap and Compose passed; full fresh dependency download remained
  incomplete due to slow network/cache gaps. No clean full install is claimed.
- Sequential make integration passed HTTP/Chromium, MCP, token revocation/reuse and
  capacity/TTL/crash recovery. API image rebuilt with a documented public mirror.
  Local authentication bypass was restored after authenticated integration checks.
- CI YAML/controls and Renovate JSON parsed locally. Actual GitHub checks, private
  reporting and Renovate activation require maintainer configuration after publication.
- Files: SECURITY.md, CONTRIBUTING.md, CHANGELOG.md, README.md, AGENTS.md,
  .github/, renovate.json, .gitattributes, Makefile, pyproject.toml, scripts/,
  architecture/validation docs and the rotation test prerequisite.

### 2026-11-20: Open-source license (complete)

- Add MIT licensing with project contributor attribution, without personal details.
- Declare package licensing and link the license from README.
- Verified lockfile consistency, wheel/source builds, MIT package metadata,
  license inclusion in both distributions, README link and whitespace.
- Files: LICENSE, pyproject.toml, README.md and AGENTS.md. Attribution is
  Loop Sandbox contributors; third-party dependencies retain their own licenses.
- No runtime behavior changed; application tests were not rerun.

### 2026-11-20: Temporary authentication bypass (complete)

- Add an explicit development switch for public HTTP/MCP token verification.
- Use one stable anonymous client identity; preserve session IDs and worker auth.
- Enabled locally through .env; tracked defaults remain authenticated (0).
- Owners: server/auth.py, server/main.py, deploy/compose.yaml, .env.example,
  tests/unit/test_credentials.py and docs/mcp.md. Health probes support bypass.
- Verification: 22 unit tests, Ruff, architecture and HTTP snapshots passed;
  Compose parsed and the rebuilt controller is healthy. Live HTTP and MCP discovery
  passed without Authorization; an invalid token was also accepted. Default-mode
  rejection and required MCP session routing remain covered.

### 2026-11-20: Credential setup and rotation (complete)

- Add idempotent init and explicit rotation with private atomic credential files.
- Authenticate a stable server-owned client identity independently of token values.
- Integrate Loop connection setup; verify rotation, identity continuity and MCP access.
- Owners: server/cli.py and credentials.py implement locked init, legacy migration,
  private files and atomic rotation; auth.py rereads verified credentials per request.
  MCP takes client_id from verified scope; Compose mounts the credential directory.
- Legacy .env keys migrate without changing binding owners. Default Compose ignores
  the legacy env token after migration. New secrets stay out of .env and stdout.
- Verification: 21 unit tests, Ruff, 32-module architecture, HTTP snapshots,
  wheel/sdist, Compose validation and API image build passed. Real MCP/Docker
  rotation rejected the old key and retained the same worker, generation and files;
  the test restored the original credential afterward. MCP session integration and
  HTTP/Chromium smoke passed. Loop's synthetic-model end-to-end test passed using
  the saved private connection, without a token in session records.
- Limits: one configured principal; no multi-user registry, OAuth or pairing UI.
  macOS/Linux credential adapters have mocked coverage; live OS store unlock/access
  behavior was not exercised. Loop's built CLI hidden-input flow passed via a PTY.

### 2026-11-20: Session-bound disposable MCP workspaces (complete)

- Add authenticated Streamable HTTP MCP tools bound by client session identity.
- Keep lazy allocation, reuse, generation changes, idle cleanup and execution leases
  in server services; retain existing sandbox HTTP APIs.
- Add exact file editing and bounded background command polling/cancellation.
- Acceptance: official MCP client to real Docker, session isolation, reuse/reset,
  file round-trip, command execution/cancellation, and Loop local-tool exclusion.
- Disposable workspaces do not restore files after recycling or controller restart.
- Implemented six MCP tools, API-key-scoped client session binding, SQLite generation
  records, single-flight allocation, active leases, exact edits and bounded Bash
  background jobs with process-group cancellation. Confirmed stopped containers
  can be replaced; transient transport errors do not trigger replay or replacement.
- Verification: 17 unit tests, Ruff, HTTP snapshots and 30-module architecture checks
  passed. Both images and wheel/sdist built. Official MCP-to-Docker integration,
  original Docker/Chromium smoke, and capacity/TTL/crash-recovery tests passed.
  Loop's synthetic-model tool loop also passed against the live service; no real
  model API was called. The lifecycle check was rerun sequentially after an initial
  capacity collision with the concurrent end-to-end check.
- Limits: shared API-key authorization, one controller worker, empty disposable
  workspaces, four sandboxes, no project sync or persistent files. See docs/mcp.md.


### 2026-11-19: Consolidated coding agent documentation (complete)

- Made AGENTS.md the single coding agent guide, feature inventory, and change log.
- Removed the separate guide after preserving its development instructions and
  feature history; updated README and the repository architecture map.
- Verified documentation links, English-only content, obsolete-reference removal,
  and git diff --check. Runtime tests were not rerun for this documentation change.

### 2026-11-19: Repository structure refactor (complete)

- Separated public HTTP composition/routes, lifecycle state, worker transport,
  Docker runtime, shared request contracts, browser execution, and optional model
  integration. Retained existing HTTP paths, payloads, limits, and cleanup logic.
- Grouped image definitions under docker/, local Compose under deploy/, generated
  contracts under specs/, and focused tests under tests/unit/ and tests/integration/.
- Added import cycle/boundary and OpenAPI freshness checks to make check.
- Updated CI, commands, README, migration/reference guide, and coding agent docs.
- Verification: 13 unit tests passed (one existing test split by component),
  lint/format passed, 25 modules passed dependency checks, public and internal
  OpenAPI matched pre-refactor schemas, Compose parsed, wheel/sdist and both Docker
  images built. Both built images passed entrypoint/component-isolation checks;
  the built wheel imported both applications without the source tree. Live Docker
  and Chromium smoke tests and capacity/TTL/crash-recovery checks passed. Local
  documentation links, English-only content, lockfile consistency, and whitespace
  were checked. No frontend or type-checking suite is configured.
- Real model and Azure tests require external configuration and remain unrun.

### 2026-11-19: Coding agent development reference (complete)

- Added development conventions, architecture ownership, a feature inventory,
  verification guidance, and mandatory record updates for every change set.
- Established coding agent instructions and linked them from README; consolidated
  the guide and feature record into AGENTS.md.
- Current files: AGENTS.md, README.md.
- Verified local documentation links, English-only instructions, and whitespace.
- Runtime tests were not rerun for the documentation-only change.
