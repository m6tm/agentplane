"""Kimi Code adapter."""

from typing import Any

from agentplane.adapters.base import AdapterContext
from agentplane.adapters.builtin._cli_base import LocalCliAdapter
from agentplane.adapters.registry import register_adapter


@register_adapter
class KimiAdapter(LocalCliAdapter):
    """Run Kimi Code CLI locally."""

    @property
    def type(self) -> str:
        return "kimi_local"

    @property
    def label(self) -> str:
        return "Kimi Code (local)"

    @property
    def cli_command(self) -> str:
        return "kimi"

    @property
    def default_model(self) -> str:
        return "kimi-k2.6"

    @property
    def models(self) -> list[dict[str, str]]:
        return [
            {"id": "kimi-k2.6", "label": "kimi-k2.6"},
            {"id": "kimi-k2.5", "label": "kimi-k2.5"},
        ]

    async def execute(self, ctx: AdapterContext, on_log: Any | None = None) -> Any:
        config = ctx.config or {}
        command = self._resolve_command(config)
        model = config.get("model", self.default_model)

        args = ["-p", ctx.prompt or "No prompt provided", "--output-format", "stream-json"]

        if ctx.session_id:
            args.extend(["-S", ctx.session_id])
        if model and model != self.default_model:
            args.extend(["-m", model])

        extra = config.get("extraArgs", [])
        if isinstance(extra, list):
            args.extend([str(a) for a in extra])

        env = self._build_env(ctx)
        cwd = self._build_cwd(ctx)
        timeout = self._build_timeout(ctx)

        result = await self._run_cli(command, args, cwd, env, timeout, on_log)
        result.model = model
        return result

    def describe(self) -> dict[str, Any]:
        return {
            **super().describe(),
            "models": self.models,
            "default_model": self.default_model,
        }
