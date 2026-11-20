# Contributing

Use Python 3.12+, uv, Docker Engine and Compose v2. Native development and credential
setup support Linux and macOS. On Windows use WSL2 with a Linux checkout and reachable
Linux Docker Engine; the CLI uses POSIX file locking.

## Setup and checks

Run from the repository root:

~~~bash
make install
make setup
make check
make package
make build
make up
make integration
make down
~~~

make check is offline: lint, formatting, unit tests, architecture, HTTP snapshots
and content checks. Run affected tests first for focused edits, then static checks.
Use make specs for intentional API changes; never edit snapshots manually.

make integration runs HTTP/Chromium, MCP, token rotation and lifecycle sequentially.
Use a dedicated authenticated deployment with no active user sessions. Rotation
changes the token temporarily and restores it in finally. Lifecycle consumes all
capacity and hard-restarts the controller. Never run live checks concurrently or
against another person's deployment. make agent additionally needs a model key
and may incur provider charges.

## Ownership and records

Read [AGENTS.md](AGENTS.md) and [architecture](docs/architecture/repository.md).
Keep controller, runtime, contracts, workers and adapters in their owning layers.
Keep repository text in English and preserve existing edits. Core HTTP/MCP changes
need not change the optional model adapter. Update AGENTS.md for every change set
and feature docs when behavior changes.

[CHANGELOG.md](CHANGELOG.md) records user-visible changes under one Unreleased
section. Refine related entries instead of recording each edit. Use Added, Changed,
Fixed, Removed and Breaking Changes as applicable; explain breaking migrations.
Pure documentation, formatting and tests need no entry unless usage changes.

## Pull requests and sensitive data

Use Conventional Commits titles, such as feat(mcp): add a tool. Explain resulting
behavior, validation and limits in the PR template. Do not upload secrets, personal
paths, private endpoints, conversations, local configuration, databases, logs or
screenshots. Check outgoing content and history, including filenames and archives,
before pushing. Report findings without values; use synthetic examples. An ignored
copy does not protect a tracked copy. See [SECURITY.md](SECURITY.md) for private
reports. Contributions use the [MIT License](LICENSE); dependencies retain theirs.

## Dependencies and releases

Renovate proposes reviewed updates and weekly lockfile maintenance. Maintainers
must install/enable Renovate; configuration alone does not activate the bot.
Updates do not auto-merge. Update pyproject.toml and uv.lock together, then verify
affected tests, images and packages. Review Docker system packages separately.

Before release, confirm a version, finalize changelog/migrations, run make check,
make package and dedicated make integration. Validate release images and supported
architectures. Package checks cover license, metadata, CLI and imports outside the
checkout. Publishing, creating tags and enabling GitHub private vulnerability
reporting are separate maintainer actions; these commands publish nothing.
