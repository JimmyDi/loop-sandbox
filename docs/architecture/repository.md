# Repository architecture

## Organization

Separate the public control plane, platform runtime, sandbox data plane, shared
contracts, and optional integrations. Retain one Python distribution and lockfile;
each Docker image copies only its owned modules. There are no empty SDK or
Kubernetes implementation directories.

~~~text
loop-sandbox/
  AGENTS.md                     Coding agent guide, feature inventory, change log
  README.md                     User setup, MCP and HTTP API guide
  CONTRIBUTING.md                Development and contribution workflow
  SECURITY.md                    Trust boundaries and private reporting
  CHANGELOG.md                   User-visible pending and released changes
  LICENSE                        MIT license
  renovate.json                  Reviewed dependency update configuration
  pyproject.toml / uv.lock       Packaging, dependencies, and tooling
  Makefile                      Root development commands
  .env.example                  Configuration template
  .github/workflows/check.yml   CI validation
  src/loop_sandbox/
    contracts/models.py         Shared request schemas
    server/
      main.py                   Public FastAPI composition
      auth.py                   Token verification and stable client identity
      credentials.py            Private atomic credential storage
      cli.py                    Init, legacy migration and token rotation
      state.py                  In-memory registry and lifecycle lock
      lifecycle.py              Allocation, leases, recovery, cleanup
      client.py                 Authenticated worker HTTP transport
      routes/
        health.py               Docker connectivity and sandbox count
        sandboxes.py            Lifecycle route registration
        capabilities.py         File, command, browser route registration
    runtime/docker.py           Docker containers, networks, limits
    worker/
      app.py                    Internal HTTP routes and authentication
      files.py                  Workspace files and downloads
      commands.py               Shell execution and process cleanup
      browser.py                Chromium state, actions, shutdown
    integrations/model_agent/
      routes.py                 Optional public model endpoint
      runner.py                 Model loop, dispatch, budgets
      tools.py                  Model-facing tool schemas
  docker/
    api.Dockerfile              Controller image
    worker.Dockerfile           Worker image with Chromium
  deploy/compose.yaml           Local deployment and health check
  specs/
    sandbox-api.json            Generated public OpenAPI contract
    worker-api.json             Generated internal OpenAPI contract
  scripts/
    setup.py                    Generate local configuration
    check_architecture.py       Check cycles and import boundaries
    export_specs.py             Export/check OpenAPI snapshots offline
    check_content.py            Source whitespace, language and local docs links
    verify_package.py           Archives, license, metadata and installed imports
  tests/
    conftest.py                 Shared test environment
    unit/                       Tests grouped by component
    integration/
      smoke.py                  Live file, command, browser checks
      lifecycle.py              Live capacity, TTL, restart checks
      mcp_sessions.py           Live MCP session and tool verification
      token_rotation.py         Live credential revocation and binding continuity
  docs/
    architecture/repository.md  Architecture decision and migration guide
    azure.md                    Personal Azure VM deployment
    troubleshooting.md          Operational troubleshooting
    validation.md               Verification evidence
~~~

Package __init__.py files are empty markers. Local .env, .loop-sandbox, .venv, caches, dist, and
artifacts are ignored and are not source components.

## Dependency boundaries

- contracts depends on Pydantic and standard library only.
- runtime owns Docker operations and does not import server or worker modules.
- worker imports contracts and its own capabilities. It never imports server,
  runtime, or model integration code.
- server routes delegate to lifecycle or client modules. Both share state;
  lifecycle uses runtime for resource management and client for readiness checks.
- integrations/model_agent uses contracts and the worker client. Core server
  services do not depend on integrations.
- server/main.py is the composition root that registers core and optional routes.

The HTTP flow remains client -> controller -> worker. This refactor does not add
direct client-to-worker access, a runtime, persistent state, extra services, or an
API version. IDs, routes, payloads, limits, authentication, TTL, and startup cleanup
semantics remain unchanged.

## Contracts and checks

Pydantic models and FastAPI routes remain the implementation source of truth.
JSON files in specs/ are generated snapshots. Run make specs after intentional
contract changes; make check rejects stale snapshots. Export uses placeholder
credentials without starting lifespans or contacting Docker or a model service.

scripts/check_architecture.py scans absolute local imports, detects cycles, and
enforces component boundaries without importing applications. This is a Python
project with no frontend, style pipeline, or configured type-checking suite.

## Migration and commands

Run commands from the repository root:

~~~bash
python3 scripts/setup.py
make install
make check
make build
make up
make smoke
make lifecycle
make down
~~~

Compose now lives under deploy/. Use Make targets or specify the file and root
environment explicitly:

~~~bash
docker compose --env-file .env -f deploy/compose.yaml up -d --wait
~~~

The explicit Compose project name remains loop-sandbox. Build context is the
repository root, not deploy/.

| Previous path or command | Current path or command |
|---|---|
| loop_sandbox.api:app | loop_sandbox.server.main:app |
| src/loop_sandbox/provider.py | src/loop_sandbox/runtime/docker.py |
| src/loop_sandbox/models.py | src/loop_sandbox/contracts/models.py |
| src/loop_sandbox/agent.py | src/loop_sandbox/integrations/model_agent/runner.py and tools.py |
| Dockerfile.api / Dockerfile.worker | docker/api.Dockerfile / docker/worker.Dockerfile |
| compose.yaml | deploy/compose.yaml |
| scripts/smoke.py | tests/integration/smoke.py |
| scripts/verify_lifecycle.py | tests/integration/lifecycle.py |
| tests/test_components.py / tests/test_runtime.py | Component-focused tests under tests/unit/ |

Python module paths changed; HTTP routes did not. Rebuild both images after
upgrading. Existing worker containers do not update automatically. Finish active
tasks before recreating the controller because startup clears managed sandboxes.

## Reference review

Reviewed official repositories on 2026-11-19. These references informed directory
boundaries; no upstream implementation was copied.

| Project | Observed organization | Decision for Loop Sandbox |
|---|---|---|
| [OpenSandbox](https://github.com/opensandbox-group/OpenSandbox/blob/main/docs/architecture/index.md) | server for lifecycle, components for execution, specs for protocols, separate deployment and tests | Separate server, worker, runtime, contracts, specifications, deployment |
| [E2B runtime](https://github.com/e2b-dev/runtime/blob/main/docs/ARCHITECTURE.md) | packages/api, packages/orchestrator, packages/envd, shared contracts and infrastructure | Separate public HTTP orchestration from in-sandbox execution and platform management |
| [Daytona public repository](https://github.com/daytonaio/daytona) | Describes interface/control/compute planes and SDK libraries; public repository is archived and states core development moved private | Historical architecture reference, not a current maintained source layout |

Separate publishable service packages would add lockfile, release, and shared
schema overhead without an independent release requirement. Component boundaries
therefore live inside loop_sandbox, with image-specific source copying and
automated dependency checks.

## Session MCP integration

The integrations/mcp adapter calls server/session_tools.py. The server/workspaces.py
service owns persistent bindings, lazy allocation, generations and execution
leases. The worker/processes.py module manages background Bash jobs.
See [MCP contracts](../mcp.md).
