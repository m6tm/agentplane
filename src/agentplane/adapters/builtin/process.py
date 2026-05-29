"""Built-in local process adapter.

Runs any shell command as an agent. Useful for scripts, tools,
and as a template for external CLI adapters (Claude Code, Kimi, etc.).
"""

import asyncio
import shutil
from typing import Any

from agentplane.adapters.base import Adapter, AdapterContext, AdapterResult
from agentplane.adapters.registry import register_adapter


@register_adapter
class ProcessAdapter(Adapter):
    """Run a local shell command."""

    @property
    def type(self) -> str:
        return "process"

    @property
    def label(self) -> str:
        return "Local Process"

    async def execute(
        self,
        ctx: AdapterContext,
        on_log: Any | None = None,
    ) -> AdapterResult:
        config = ctx.config or {}
        command = config.get("command", "echo")
        args = config.get("args", ["No command configured"])
        cwd = config.get("cwd")
        timeout = config.get("timeout_seconds", 300)
        env = {**config.get("env", {}), **ctx.env}

        cmd = [command, *([str(a) for a in args] if isinstance(args, list) else [str(args)])]

        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env if env else None,
            )
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
            stdout = stdout_b.decode("utf-8", errors="replace")
            stderr = stderr_b.decode("utf-8", errors="replace")

            if on_log:
                if stdout:
                    await on_log("stdout", stdout)
                if stderr:
                    await on_log("stderr", stderr)

            return AdapterResult(
                success=proc.returncode == 0,
                exit_code=proc.returncode,
                stdout=stdout,
                stderr=stderr,
                summary=stdout[:500] if stdout else None,
            )
        except asyncio.TimeoutError:
            if proc is not None and proc.returncode is None:
                proc.kill()
                await proc.wait()
            return AdapterResult(
                success=False,
                exit_code=-1,
                stderr=f"Timed out after {timeout}s",
            )
        except Exception as e:
            return AdapterResult(
                success=False,
                exit_code=-1,
                stderr=str(e),
            )

    async def probe(self, config: dict[str, Any]) -> dict[str, Any]:
        command = config.get("command", "echo")
        resolved = shutil.which(command)
        return {
            "available": resolved is not None,
            "resolved_path": resolved,
            "command": command,
        }
