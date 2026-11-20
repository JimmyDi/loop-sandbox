import asyncio

from loop_sandbox.contracts.models import Command
from loop_sandbox.worker import app as worker


def test_command_timeout_and_bounded_output():
    async def exercise():
        result = await worker.command(Command(command="sleep 2", timeout=1))
        assert result["timed_out"] is True
        assert result["exit_code"] != 0
        result = await worker.command(Command(command="python -c 'print(\"x\" * 70000)'"))
        assert result["exit_code"] == 0
        assert result["truncated"] is True
        assert len(result["output"].encode()) == 65536

    asyncio.run(exercise())
