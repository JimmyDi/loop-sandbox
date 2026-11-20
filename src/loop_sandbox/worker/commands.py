import asyncio
import os
from pathlib import Path

from loop_sandbox.contracts.models import Command


async def run_command(root: Path, body: Command):
    # Output goes to a bounded tmpfs, avoiding unbounded PIPE accumulation.
    # Commands run with the worker user permissions.
    import signal
    import tempfile

    with tempfile.TemporaryFile(dir="/tmp") as output:
        proc = await asyncio.create_subprocess_exec(
            "/bin/sh",
            "-lc",
            body.command,
            cwd=root,
            stdout=output,
            stderr=asyncio.subprocess.STDOUT,
            start_new_session=True,
        )
        timed_out = False
        try:
            await asyncio.wait_for(proc.wait(), timeout=body.timeout)
        except TimeoutError:
            timed_out = True
        finally:
            # Also clean up descendants left running after their shell exits.
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            await proc.wait()
        output.seek(0)
        data = output.read(65537)
    return {
        "exit_code": proc.returncode,
        "timed_out": timed_out,
        "output": data[:65536].decode("utf-8", errors="replace"),
        "truncated": len(data) > 65536,
    }
