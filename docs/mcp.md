# Session-bound MCP workspaces

Streamable HTTP MCP is available at `/mcp/` on the API port. Include the trailing
slash to avoid redirects. Every request requires `Authorization: Bearer <key>`
and `Loop-Session-Id: <stable-chat-id>`. Session IDs accept 1–128 ASCII letters,
digits, underscores or hyphens and must remain stable across reconnects.

The session ID is not a credential and is independent of `Mcp-Session-Id`.
Bindings are scoped to the server-owned client_id authenticated by the token.
The current deployment uses one shared client credential: its holders share an authorization boundary, not separate users.

## Tools

| Tool | Arguments | Behavior |
|---|---|---|
| read_file | path | Read UTF-8, at most 1 MB |
| write_file | path, content | Write UTF-8, create parents, at most 1 MB |
| edit_file | path, old_text, new_text | Replace exactly one occurrence; conflicts return 409 |
| exec | command, optional cwd, timeout | Start Bash and return process_id; default 300 seconds, maximum 1800 |
| get_process | process_id, optional cursor | Status and up to 64 KiB output; at most 1 MB exposed per command |
| cancel_process | process_id | Kill the command process group |

Paths must remain inside /workspace. The worker permits four active commands and
retains at most 64 process records. There is no detached service persistence.

## Lifecycle and errors

Discovery allocates nothing. First use creates a sandbox; later calls reuse it.
SESSION_IDLE_SECONDS defaults to 900; SESSION_MAX_SECONDS defaults to 3600.
Configure positive integer values. Active operations and jobs hold an idle lease;
the hard maximum age can still terminate them. Reaping runs every ten seconds.

SESSION_DATABASE stores stable client identity, chat ID, sandbox ID and generation in
SQLite. Compose mounts a named volume. Use one API worker. Startup still removes
managed containers; the next call creates a new generation. The database preserves
the reset counter, not files. Rotating the token preserves the binding namespace.
The client never supplies client_id. This is a single-client deployment, not a
multi-user credential registry.

Responses include sandbox.generation, created, recreated and files_restored plus
result or error. New generations start empty: files and processes are discarded.
Clients must display resets and give them to the model. Stale process IDs fail
with 410 instead of restarting commands. Errors include status and message.
Network failures never authorize replaying an operation with an uncertain outcome.
Disconnecting a client does not immediately delete its worker.

Existing sandbox HTTP APIs remain available. MCP adapts the protocol-neutral
session operation service; tool definitions do not own Docker lifecycle logic.

## Verification

Run `make build`, `make up`, and
`uv run python tests/integration/mcp_sessions.py`. The official MCP client tests
real Docker discovery, reuse, files, cancellation, recycling, stale processes,
identity and authentication without making a model request.

## Credential setup

Run uv run loop-sandbox init once; repeat safely without replacing credentials.
Use uv run loop-sandbox rotate-token for explicit rotation. Both keep secrets
hidden. The private .loop-sandbox/credentials.json contains token and client_id.
Compose mounts its directory so atomic replacement is visible without restarting.
An unreadable or malformed credential file fails closed (503).
Legacy deployments can use DEMO_API_KEY without a credential file, but rotation
continuity requires migrating with init and using file-backed authentication.
Init preserves the old key-derived owner when importing existing .env settings.
The legacy key remains in .env for compatibility and is ignored by file-backed
Compose authentication. It is not accepted after file-backed token rotation.

Loop supports loop sandbox connect (hidden prompt; macOS Keychain or Linux Secret
Service), loop sandbox connect --file (explicit mode-0600 fallback), and environment
variables LOOP_SANDBOX_URL / LOOP_SANDBOX_TOKEN. Use HTTPS beyond localhost.

## Temporary local authentication bypass

Set LOOP_SANDBOX_AUTH_DISABLED=1 in .env and recreate the API with Compose to
accept public HTTP and MCP requests without a token. The default is 0. MCP still
requires Loop-Session-Id for routing; all callers share the anonymous principal.
This creates a separate binding namespace from authenticated sessions. Worker
transport authentication remains enabled. Set the switch back to 0 and recreate
the API to restore token verification. The local Compose port stays on localhost.
Loop's existing saved connection can still send its token; the controller ignores
it while bypass is enabled. Loop connection setup itself is unchanged.
