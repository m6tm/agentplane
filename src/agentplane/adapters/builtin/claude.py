"""Claude Code adapter."""

from typing import Any

from agentplane.adapters.builtin._cli_base import LocalCliAdapter
from agentplane.adapters.base import AdapterContext, AdapterResult
from agentplane.adapters.registry import register_adapter


@register_adapter
class ClaudeAdapter(LocalCliAdapter):
    """Run Claude Code CLI locally."""

    @property
    def type(self) -> str:
        return "claude_local"

    @property
    def label(self) -> str:
        return "Claude Code (local)"

    @property
    def cli_command(self) -> str:
        return "claude"

    @property
    def default_model(self) -> str:
        return "claude-sonnet-4-6"

    @property
    def models(self) -> list[dict[str, str]]:
        return [
            {"id": "claude-opus-4-7", "label": "Claude Opus 4.7"},
            {"id": "claude-opus-4-6", "label": "Claude Opus 4.6"},
            {"id": "claude-sonnet-4-6", "label": "Claude Sonnet 4.6"},
            {"id": "claude-haiku-4-6", "label": "Claude Haiku 4.6"},
            {"id": "claude-sonnet-4-5-20250929", "label": "Claude Sonnet 4.5"},
            {"id": "claude-haiku-4-5-20251001", "label": "Claude Haiku 4.5"},
        ]

    async def execute(self, ctx: AdapterContext, on_log: Any | None = None) -> Any:
        config = ctx.config or {}
        command = self._resolve_command(config)
        model = config.get("model", self.default_model)
        effort = config.get("effort", "")
        chrome = config.get("chrome", False)
        max_turns = config.get("max_turns", 0)
        dangerously_skip_permissions = config.get("dangerouslySkipPermissions", True)

        args = ["--print", "-", "--output-format", "stream-json", "--verbose"]

        if ctx.session_id:
            args.extend(["--resume", ctx.session_id])
        if dangerously_skip_permissions:
            args.append("--dangerously-skip-permissions")
        if chrome:
            args.append("--chrome")
        if model:
            args.extend(["--model", model])
        if effort:
            args.extend(["--effort", effort])
        if max_turns > 0:
            args.extend(["--max-turns", str(max_turns)])

        extra = config.get("extraArgs", [])
        if isinstance(extra, list):
            args.extend([str(a) for a in extra])

        env = self._build_env(ctx)
        cwd = self._build_cwd(ctx)
        timeout = self._build_timeout(ctx)

        result = await self._run_cli(command, args, cwd, env, timeout, on_log)

        # Parse session id from stdout if present (simplified)
        session_id = ctx.session_id
        if result.stdout and '"session_id"' in result.stdout:
            # In real impl, parse JSON stream properly
            pass

        result.session_id = session_id
        result.model = model
        result.cost_usd = None
        return result

    def describe(self) -> dict[str, Any]:
        return {
            **super().describe(),
            "models": self.models,
            "default_model": self.default_model,
        }
