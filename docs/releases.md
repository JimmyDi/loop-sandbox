# Container releases

The image publication workflow is prepared; v0.1.0 images are not available until
a maintainer publishes that release and the workflow succeeds. Source builds in
the [README](../README.md) remain available before the first image release.

## Install a published version

Requires Docker Engine with Compose v2 on Linux, or a Linux Docker VM on macOS.
Windows uses WSL2. No host Python, uv, source checkout or graphical interface is
required. Commands below use a POSIX shell and the default Docker socket.

Use matching API and worker versions. The version tags are 0.1.0, without a v
prefix; the Git release tag is v0.1.0. There is no automatically updated latest tag.
Both images include Linux AMD64 and ARM64 variants after native integration checks.

~~~bash
mkdir loop-sandbox
cd loop-sandbox
mkdir deploy
curl --fail --location https://raw.githubusercontent.com/JimmyDi/loop-sandbox/v0.1.0/deploy/compose.images.yaml --output deploy/compose.images.yaml
docker pull ghcr.io/jimmydi/loop-sandbox-api:0.1.0
docker pull ghcr.io/jimmydi/loop-sandbox-worker:0.1.0
docker run --rm --network none --user "$(id -u):$(id -g)" --volume "$PWD:/config" ghcr.io/jimmydi/loop-sandbox-api:0.1.0 python -m loop_sandbox.server.cli init --directory /config
docker compose --env-file .env -f deploy/compose.images.yaml up -d --wait
~~~

Init creates private .loop-sandbox/credentials.json and .env in the current
directory. It preserves existing credentials and does not print the token. The
empty .env uses authenticated localhost defaults from Compose. A bind mount stores
credentials on the host; run setup with your host UID/GID so files remain owned by
you. Only the API runs continuously: it creates worker containers on demand. Pull
the worker explicitly; the controller does not download missing worker images.

Open http://127.0.0.1:8080/docs. In a private editor, read the token field from
.loop-sandbox/credentials.json and configure your client with:

| Setting | Value |
|---|---|
| Transport | Streamable HTTP |
| URL | http://127.0.0.1:8080/mcp/ |
| Authorization header | Bearer followed by the private token |
| Loop-Session-Id header | A stable, unique value for each conversation |

See [MCP setup](mcp.md) for Loop configuration and execution boundaries. To verify
the installation, call write_file with path hello.txt and content hello sandbox,
then read_file with the same path, then exec with command cat hello.txt. Confirm
the content and exit code 0. This creates a disposable worker; files are lost when
it expires or the controller restarts.

Rotate credentials using the same pinned API image and host directory:

~~~bash
docker run --rm --network none --user "$(id -u):$(id -g)" --volume "$PWD:/config" ghcr.io/jimmydi/loop-sandbox-api:0.1.0 python -m loop_sandbox.server.cli rotate-token --directory /config
~~~

Reconnect clients with the new token. Rotation takes effect without restarting.
To stop, run docker compose --env-file .env -f deploy/compose.images.yaml down.
The controller owns the Docker socket: run one controller per Docker Engine.
The [security boundaries](../SECURITY.md) also apply to prebuilt images.

## Upgrade

Download files you need to retain before upgrading. Set API_IMAGE and WORKER_IMAGE
in .env to the two matching ghcr.io/jimmydi/loop-sandbox image versions, explicitly
pull both images, then run the Compose up command above. Recreating the controller
clears live workspaces; the credential directory and session binding volume remain.
For reproducible installations, record each multi-platform image digest reported by
docker buildx imagetools inspect and use image@sha256 references in .env.

## Maintainer publication

1. Merge the publication workflow PR after verify and integration pass.
2. Set the package version, finalize the changelog, and update both default image
   versions and examples in this document in a release preparation PR.
3. After that PR passes and merges, create a GitHub Release targeting its main
   commit with tag v followed by the exact stable package version. Publish the
   release; drafts do not trigger image publication.
4. The workflow checks the tag/version and main ancestry, runs package checks, then
   builds and tests native AMD64/ARM64 images. Each architecture passes the full
   sequential HTTP/Chromium, MCP, rotation and lifecycle suite before pushing
   sha-<commit>-<architecture> candidate tags. Candidates are not release tags.
5. Only after both architectures pass does the workflow assemble the two versioned
   multi-platform manifests. A partial registry failure can publish one manifest;
   rerun the failed workflow and verify both before announcing availability.
6. On the first publication, open each package from the repository Packages area,
   choose Package settings and change visibility to Public. Repository visibility
   does not automatically make a new GHCR package public. Anonymous docker pull
   must work for both images before the release is ready for users.
7. Verify the documented installation and MCP round-trip from a fresh directory
   on both supported architectures, then record digests in the release notes.

The workflow uses GitHub's short-lived GITHUB_TOKEN with packages: write in publish
jobs; no personal access token or additional repository secret is needed. Image
source/license labels link packages to this repository. PR checks never push images.
Only stable X.Y.Z releases are supported; prereleases are rejected. Do not move
published release tags; reruns of the same release can update its image tags if
system packages changed. Use recorded digests for immutable deployments. Release
publication, package visibility and tag creation are explicit maintainer actions.
