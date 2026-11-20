# Local validation record

Validation date: 2026-11-19. Environment: macOS arm64, Docker Desktop Linux arm64, Python 3.12.13.

| Check | Result |
|---|---|
| Ruff lint and formatting | Passed |
| Python component tests | 13 passed; existing combined auth/tool test split by ownership |
| Compose configuration parsing | Passed |
| API and worker image builds | Passed |
| Real Docker / Chromium smoke test | Passed |
| Files, Python, downloads, page interactions, PNG, separate workspaces, command timeouts | Passed |
| Capacity, resource limits, dedicated networks, TTL, crash/restart cleanup | Passed |
| Static import cycles and component boundaries | Passed across 25 Python modules |
| Public and worker OpenAPI snapshots | Matched pre-refactor schemas exactly; freshness check passed |
| Wheel and source distribution builds | Passed; built wheel imported both applications without the source tree |
| Image entrypoints and source isolation | Passed; API image excludes worker, worker image excludes server/model integration |
| Documentation links, English-only content, and whitespace | Passed |
| Real model tool calling | Not run; no model key configured |
| Azure deployment | Not run |

Local builds used package mirrors. Component tests emit a Starlette warning about a deprecated AnyIO alias; it does not affect test results.

These checks were rerun after the repository structure refactor. The project has
no frontend, style pipeline, or configured type-checker. Live model and Azure
validation remain separate and were not performed.

Reproduce the checks:

~~~bash
make check
docker compose --env-file .env -f deploy/compose.yaml config -q
python3 tests/integration/smoke.py
python3 tests/integration/lifecycle.py
~~~

To validate the real model integration, configure .env and run python3 tests/integration/smoke.py --agent. Record the model path as passed only after the command generates and independently verifies the calculated artifact.


## Session MCP verification (2026-11-20)

- 17 unit tests passed, including session reuse/isolation/generation, edit conflicts,
  command polling/cancellation/timeout and no replacement on transport errors.
- Ruff, generated HTTP snapshot freshness and 30-module architecture checks passed.
- Both Docker images and Python wheel/sdist built.
- Official MCP client to real Docker passed discovery without allocation, reuse,
  file access, cancellation, recycling, stale process and identity/auth checks.
- Existing HTTP/Chromium smoke and capacity/TTL/crash recovery passed. Run lifecycle
  verification separately from other live tests because it consumes all capacity
  and restarts the controller.
- The Loop synthetic-model tool loop passed against the real MCP/Docker service.
  No real model API or Azure deployment was exercised.

## Credential setup verification (2026-11-20)

- 21 Python unit tests, Ruff, 32-module architecture and HTTP snapshots passed.
- API image, Compose configuration, wheel and source distribution built successfully.
- Live token_rotation.py confirmed immediate old-token rejection and unchanged
  worker/generation/files after rotation, then restored the original credential.
- Real MCP session integration and HTTP/Chromium smoke passed.
- Loop's synthetic model loop used a saved private connection to the real MCP and
  Docker workers and confirmed the token did not enter session history.
- Loop's built CLI passed hidden token input and URL normalization through a PTY.
- OS credential adapters use mocked tests; live Keychain/Secret Service interaction
  was not tested. No real model API was called. Lifecycle stress tests were not
  repeated for this authentication change.

## Public repository workflow verification (2026-11-20)

- Added contributor/security policies, public changelog, PR template, Renovate
  configuration, platform support and MCP-first setup documentation.
- make check passed 22 unit tests, Ruff, 32-module architecture, HTTP snapshots,
  English/whitespace and local Markdown file-link checks.
- make package built wheel/sdist and validated license, metadata, archive boundaries,
  CLI help and application imports from an installed wheel outside the checkout.
- Workflow YAML and Renovate JSON parsed; CI permissions, job dependencies and
  timeouts were checked locally. GitHub-hosted execution and Renovate activation
  require publication/maintainer configuration and have not occurred.
- Clean copied source setup generated private credentials with authenticated
  defaults and Compose parsed. A fresh full dependency download was interrupted
  by slow network transfers; cached offline installation lacked the Playwright
  wheel. This is not a completed clean full-install result.
- The API image rebuilt using the documented public package mirror after the
  default package source stalled. The running worker image was already available.

- Sequential make integration passed real HTTP/Chromium, MCP session tools,
  token rotation continuity, capacity/resource/network limits, TTL and crash recovery.
  Authenticated verification temporarily overrode the local bypass; local development
  bypass was restored afterward without changing private .env contents.
