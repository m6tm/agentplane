"""Base class for local CLI adapters (Claude, Codex, Kimi, etc.)."""

import asyncio
import shutil
from abc import abstractmethod
from typing import Any

from agentplane.adapters.base import Adapter, AdapterContext, AdapterResult


class LocalCliAdapter(Adapter):
    """Abstract base for adapters that shell out to a local CLI."""

    @property
    @abstractmethod
    def cli_command(self) -> str:
        """The CLI binary name (e.g. 'claude', 'kimi')."""

    @property
    @abstractmethod
    def default_model(self) -> str:
        """Default model identifier."""

    def _resolve_command(self, config: dict[str, Any]) -> str:
        return config.get("command", self.cli_command)

    def _build_env(self, ctx: AdapterContext) -> dict[str, str]:
        base = dict(ctx.env)
        config_env = ctx.config.get("env", {})
        if isinstance(config_env, dict):
            base.update({k: str(v) for k, v in config_env.items()})
        return base

    def _build_cwd(self, ctx: AdapterContext) -> str | None:
        return ctx.config.get("cwd") or None

    def _build_timeout(self, ctx: AdapterContext) -> int:
        return ctx.config.get("timeout_seconds", 300)

    async def _run_cli(
        self,
        command: str,
        args: list[str],
        cwd: str | None,
        env: dict[str, str],
        timeout: int,
        on_log: Any | None = None,
    ) -> AdapterResult:
        import os
        import shutil
        proc = None
        try:
            resolved = shutil.which(command)
            if resolved is None:
                return AdapterResult(
                    success=False,
                    exit_code=-1,
                    stderr=f"Command not found: {command}",
                )
            resolved = os.path.normpath(resolved)
            proc = await asyncio.create_subprocess_exec(
                resolved,
                *args,
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
        except TimeoutError:
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
        command = self._resolve_command(config)
        resolved = shutil.which(command)
        return {
            "available": resolved is not None,
            "resolved_path": resolved,
            "command": command,
        }
