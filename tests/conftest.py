import os
import tempfile

os.environ.setdefault("DEMO_API_KEY", "test-key")
os.environ.setdefault("WORKER_TOKEN", "test-worker")
os.environ["WORKSPACE_ROOT"] = tempfile.mkdtemp(prefix="loop-sandbox-tests-")
