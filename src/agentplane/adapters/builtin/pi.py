"""Pi adapter."""

from typing import Any

from agentplane.adapters.base import AdapterContext
from agentplane.adapters.builtin._cli_base import LocalCliAdapter
from agentplane.adapters.registry import register_adapter


@register_adapter
class PiAdapter(LocalCliAdapter):
    """Run Pi CLI locally."""

    @property
    def type(self) -> str:
        return "pi_local"

    @property
    def label(self) -> str:
        return "Pi (local)"

    @property
    def cli_command(self) -> str:
        return "pi"

    @property
    def default_model(self) -> str:
        return "auto"

    @property
    def models(self) -> list[dict[str, str]]:
        return [
            {"id": "auto", "label": "Auto"},
        ]

    async def execute(self, ctx: AdapterContext, on_log: Any | None = None) -> Any:
        config = ctx.config or {}
        command = self._resolve_command(config)
        model = config.get("model", self.default_model)
        provider = config.get("provider", "")

        args = ["--print", "-", "--output-format", "stream-json"]

        if ctx.session_id:
            args.extend(["--session", ctx.session_id])
        if provider:
            args.extend(["--provider", provider])
        if model and model != "auto":
            args.extend(["--model", model])

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
