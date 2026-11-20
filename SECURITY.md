# Security policy

Loop Sandbox is a single-user development service for a local machine or personal
Linux VM. It is not a hardened public execution service or a multi-tenant platform.

## Report a vulnerability

Use GitHub's **Security → Advisories → Report a vulnerability** on this repository
if private vulnerability reporting is enabled. If unavailable, ask maintainers for
a private reporting channel without posting reproduction details in a public issue.
Include the affected version/commit, runtime, configuration, a synthetic reproduction,
expected boundary, observed impact and mitigation. Never include real credentials,
private files or user data. Test only systems you own or are authorized to assess.
No response deadline is promised. Fixes target current development and the latest
published release; older versions have no guaranteed backports.

## Boundaries and limitations

- Public HTTP and MCP require a token by default. One credential represents a
  shared principal; there are no user roles, tenant isolation or OAuth login.
- LOOP_SANDBOX_AUTH_DISABLED=1 bypasses public authentication and gives callers
  one anonymous identity. Keep this development mode on localhost.
- Session IDs route MCP operations; they are not authentication credentials.
- Workers have independent transport tokens and no mounted controller credentials
  or Docker socket. Worker code can read its own environment/token.
- The controller mounts the Docker socket with host-management authority. Treat
  the controller, its configuration and access credentials as trusted host code.
- Workers use non-root containers, resource limits, dedicated networks, dropped
  capabilities and read-only roots. Containers share the host kernel; these controls
  do not guarantee isolation from hostile code or kernel exploits.
- Outbound access is disabled by default. ALLOW_EGRESS=1 allows general outbound
  networking without domain restrictions or data-exfiltration prevention.
- Files and processes are disposable. Startup sweeps this project's ownership label.
  Use one controller per Docker Engine; do not label unrelated workloads as owned.

Report token verification bypasses, unintended disclosure, workspace escapes and
reachable dependency vulnerabilities. Deliberately disabled controls, authorized
shell operations and pre-existing same-user host access do not alone establish a
new boundary violation.

Keep .env, .loop-sandbox/, databases, traces and screenshots private. Use HTTPS and
authenticated private access remotely. Public source does not mean the service is
safe to expose to arbitrary users.
