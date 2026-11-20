# Loop Sandbox

Licensed under the [MIT License](LICENSE). Third-party dependencies retain their own licenses.

Temporary container workspaces for code execution, file processing, and browser automation, with an optional tool-calling agent. Requires Python 3.12+, uv, Docker Engine, and Compose v2. Core capabilities do not require a model API key.

## Platform support

Linux runs Docker Engine natively. macOS uses Docker Desktop or another Linux
Docker VM. Windows requires WSL2 and a Linux checkout; native Windows credential
setup is unsupported because it uses POSIX file locking. Workers run headless
Linux and need no UI. The API requires Docker socket access; general managed
container platforms are not a drop-in deployment target.

## Quick start

Run from the project root:

~~~bash
make install
make setup
make build
make up
make smoke
~~~

The first build installs Chromium and CJK fonts. A successful smoke test prints PASS and saves downloaded JSON and a browser screenshot in artifacts/. It creates two real containers, verifies file isolation, Python execution, browser input and clicks, screenshots, downloads, and command timeouts, then removes the containers.

The API defaults to http://127.0.0.1:8080, with interactive documentation at /docs. All business endpoints require Authorization: Bearer <token>. Setup generates private credentials in the Git-ignored .loop-sandbox/credentials.json (mode 0600) and creates .env for deployment settings. Do not commit keys or put them in command history.

With dependencies installed, setup is also available as:

~~~bash
uv run loop-sandbox init
uv run loop-sandbox rotate-token
~~~

Init preserves credentials and imports a legacy .env DEMO_API_KEY once. Rotation
atomically replaces the token while keeping client_id. Compose rereads the mounted
credential file on every request: no restart is needed and live session bindings
remain unchanged. Reconnect clients with the new token. Setup never prints secrets.
Use the token field with Loop's hidden prompt: loop sandbox connect. On headless
machines choose loop sandbox connect --file explicitly if no credential store is
available. See [session MCP](docs/mcp.md) for identity and lifecycle details.

If port 8080 is occupied, set API_PORT=18080 in .env and verify with SANDBOX_BASE_URL=http://127.0.0.1:18080 python3 tests/integration/smoke.py.

## Connect a coding client over MCP

Add a Streamable HTTP service at http://127.0.0.1:8080/mcp/ in your client settings
(include the trailing slash). Configure Authorization: Bearer <token> using the
private credentials.json token. Session-aware clients must also supply a stable
Loop-Session-Id per conversation. Model tool arguments carry no IDs.

In Loop, add the service in Settings → MCP and select it as the execution provider
for a new chat. This excludes local execution tools. Other clients must support
the session header or configure a unique value per conversation. The six tools
read_file, write_file, edit_file, exec, get_process and cancel_process allocate
lazily: the first business call creates a worker and later calls reuse it.
See [MCP details](docs/mcp.md) for schemas, authentication and lifecycle.

## Capabilities

| Capability | Behavior |
|---|---|
| Lifecycle | Create, list, and destroy; default TTL of 15 minutes, configurable from 60 to 3600 seconds; up to 4 containers |
| Files | UTF-8 reads and writes, binary downloads, workspace path checks; files are removed with the container |
| Execution | Shell and Python; 1-60 second timeouts; exit codes, timeout flags, and a 64 KiB output limit |
| Browser | Chromium navigation, offline HTML, page text, clicks, form filling, and PNG screenshots |
| Agent | Chat Completions tools/tool_calls; executes tools step by step and returns answer and trace |
| Network | A dedicated bridge network per workspace; worker outbound access disabled by default; no published worker ports |

## Run model tasks

Set LLM_BASE_URL, LLM_MODEL, and LLM_API_KEY in .env. The integration uses Bearer authentication and /chat/completions; the model service must support this protocol.

~~~bash
docker compose --env-file .env -f deploy/compose.yaml up -d --force-recreate --wait api
python3 tests/integration/smoke.py --agent
~~~

The model test asks the agent to read a CSV, calculate its total with Python, and write a result file. The client independently verifies total=30 and saves the tool trace to artifacts/agent-trace.json. A natural-language answer alone does not pass artifact validation. Model calls may incur provider charges. Without a key, /agent returns 503. Each model request has a 120-second timeout; the overall agent budget is 600 seconds, with at most 20 rounds and 16 tool calls per round.

## HTTP API

| Method | Path | Request or result |
|---|---|---|
| GET | /health | Docker connectivity and sandbox count |
| POST | /sandboxes | {"ttl_seconds":900} -> sandbox_id, expires_at |
| GET | /sandboxes | Active workspaces |
| DELETE | /sandboxes/{id} | Remove the container and its dedicated network |
| POST | /sandboxes/{id}/files | {"path":"hello.txt","content":"hello"} |
| GET | /sandboxes/{id}/files?path=hello.txt | UTF-8 text |
| GET | /sandboxes/{id}/download?path=hello.txt | File bytes |
| POST | /sandboxes/{id}/commands | {"command":"python --version","timeout":30} |
| POST | /sandboxes/{id}/browser | action, url, selector, text |
| POST | /sandboxes/{id}/agent | prompt, max_steps |

Browser actions are open, set_content, snapshot, click, fill, and screenshot. Consecutive requests reuse one page. Screenshots return mime_type and base64. Commands execute serially, and browser operations execute serially. Text reads are limited to 1 MB, downloads to 5 MB, and the workspace tmpfs to 128 MiB.

## Architecture and extension

~~~mermaid
flowchart LR
    Client[HTTP client] --> API[Authentication and lifecycle API]
    API --> Docker[Docker provider]
    API --> Agent[Tool-calling loop]
    Agent --> Model[Model API]
    Agent --> Worker[Workspace worker]
    API --> Worker
    Worker --> Capabilities[Files / Shell / Chromium]
~~~

- src/loop_sandbox/server/: public HTTP application, routes, authentication, lifecycle, and worker transport.
- src/loop_sandbox/runtime/: Docker resource provisioning and cleanup.
- src/loop_sandbox/worker/: internal HTTP service and file, command, and browser capabilities.
- src/loop_sandbox/contracts/: shared request validation without runtime dependencies.
- src/loop_sandbox/integrations/mcp/: session-bound MCP adapter.
- src/loop_sandbox/integrations/model_agent/: optional model tools, execution loop, and endpoint.
- docker/ and deploy/: image definitions and local deployment configuration.
- specs/: generated public and worker HTTP contracts; update with make specs.
- tests/unit/ and tests/integration/: component tests and live Docker verification.

See the [repository architecture](docs/architecture/repository.md) for directory
ownership, dependency rules, research references, and migration instructions.

To add a capability, implement a worker handler, a fixed API forwarding route, result validation, and protocol wiring as needed. Update the optional model adapter only when relevant. To change the worker image, update WORKER_IMAGE and recreate the API. Existing containers are not upgraded automatically.

## Development and validation

Coding agents must read [AGENTS.md](AGENTS.md) before editing and update its feature
record in every change set. It is the single source for coding agent instructions,
feature inventory, and development history.

~~~bash
uv sync --frozen --extra worker
make check
python3 tests/integration/lifecycle.py
~~~

Python dependencies, including transitive versions, are recorded in uv.lock; container builds use the same lockfile. Chromium comes from Debian packages, and Playwright uses the system browser specified by CHROMIUM_EXECUTABLE. System packages may change between builds; pin the base image digest and validate browser behavior for releases.

The lifecycle verification script requires a running service. It creates four workspaces, waits approximately 70 seconds for TTL cleanup, and forcibly restarts this project's API. Finish active tasks before running it. Component tests cover authentication, file boundaries, cleanup order, and agent dispatch; they do not replace real Docker/Chromium smoke tests. See [validation results](docs/validation.md), [Azure deployment](docs/azure.md), and [troubleshooting](docs/troubleshooting.md).

## Operating boundaries

Intended for single-user local development or a personal Linux VM. Standard Docker containers share the host kernel. The controller mounts the Docker socket and has host-management privileges. This setup is unsuitable for a public API or hostile multi-tenant code execution. Workers run as a non-root user with a read-only root filesystem and dropped capabilities. Model keys are not passed to workers.

Worker outbound access is disabled by default. To enable internet access, set ALLOW_EGRESS=1 and recreate the API. This allows outbound access for the entire worker, including Shell commands, without a domain allowlist. Commands inside a container can access its processes and token; the token authenticates routing and is not a secret from code running inside the container.

Expiry is checked every 10 seconds. MCP defaults to 15-minute idle expiry and a one-hour hard lifetime; active leases defer idle expiry, but hard expiry may interrupt tasks. Live container records are in memory; SQLite persists client/session bindings and generation counters, not workspace files. API startup removes containers and networks labeled loop-sandbox.owner=local, so run only one instance per Docker Engine. Do not apply this label to unrelated resources. Stop the service with docker compose --env-file .env -f deploy/compose.yaml down; download any files you need to retain first.

If default package sources are slow, specify mirrors at build time. Dependency versions and hash validation remain unchanged:

~~~bash
docker build --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple --build-arg APT_MIRROR=https://mirrors.tuna.tsinghua.edu.cn -f docker/worker.Dockerfile -t loop-sandbox-worker:local .
docker compose --env-file .env -f deploy/compose.yaml build --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple api
~~~

## Contributing and security

See [Contributing](CONTRIBUTING.md), [Security policy](SECURITY.md),
[Changelog](CHANGELOG.md) and [validation](docs/validation.md). make package verifies
license, metadata and installed imports. make integration requires a dedicated
authenticated deployment and runs tests sequentially; lifecycle restarts the API.
Renovate must be enabled by a maintainer; configuration does not activate a bot,
automatically merge changes or publish releases.
