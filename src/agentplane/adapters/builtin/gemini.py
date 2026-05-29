"""Gemini CLI adapter."""

from typing import Any

from agentplane.adapters.builtin._cli_base import LocalCliAdapter
from agentplane.adapters.base import AdapterContext, AdapterResult
from agentplane.adapters.registry import register_adapter


@register_adapter
class GeminiAdapter(LocalCliAdapter):
    """Run Gemini CLI locally."""

    @property
    def type(self) -> str:
        return "gemini_local"

    @property
    def label(self) -> str:
        return "Gemini CLI (local)"

    @property
    def cli_command(self) -> str:
        return "gemini"

    @property
    def default_model(self) -> str:
        return "auto"

    @property
    def models(self) -> list[dict[str, str]]:
        return [
            {"id": "auto", "label": "Auto"},
            {"id": "gemini-2.5-pro", "label": "Gemini 2.5 Pro"},
            {"id": "gemini-2.5-flash", "label": "Gemini 2.5 Flash"},
            {"id": "gemini-2.5-flash-lite", "label": "Gemini 2.5 Flash Lite"},
            {"id": "gemini-2.0-flash", "label": "Gemini 2.0 Flash"},
            {"id": "gemini-2.0-flash-lite", "label": "Gemini 2.0 Flash Lite"},
        ]

    async def execute(self, ctx: AdapterContext, on_log: Any | None = None) -> Any:
        config = ctx.config or {}
        command = self._resolve_command(config)
        model = config.get("model", self.default_model)

        args = ["--print", "-", "--output-format", "stream-json"]

        if ctx.session_id:
            args.extend(["--resume", ctx.session_id])
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
