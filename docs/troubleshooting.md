# Troubleshooting

| Symptom | Check |
|---|---|
| Docker socket unavailable | docker version must show both Client and Server |
| 401 | Reconnect using the current credentials.json token; rotation invalidates old tokens immediately |
| Worker startup timed out | Check docker ps -a, worker logs, image architecture, memory, and PID limits |
| 404 | Sandbox missing, expired, or removed during API restart |
| Chromium executable missing | Check CHROMIUM_EXECUTABLE and Chromium installation in the image |
| Browser crashed | Check Docker memory, the 1 GiB worker limit, and 256 MiB shared memory |
| Network access fails | Offline by default; enable ALLOW_EGRESS, then recreate the API and sandboxes |
| Agent 503 | LLM_API_KEY is not configured |
| Agent 502 | Upstream rejection, incompatible protocol, network error, or malformed response |
| Agent 422 | Step budget exhausted; error detail includes the trace |
| Agent 504 | Overall execution exceeded 600 seconds |

Do not expose .env, .loop-sandbox/credentials.json, Authorization headers, or model credentials in public logs, screenshots, or issues.
