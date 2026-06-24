"""Cursor CLI adapter."""

from typing import Any

from agentplane.adapters.base import AdapterContext
from agentplane.adapters.builtin._cli_base import LocalCliAdapter
from agentplane.adapters.registry import register_adapter


@register_adapter
class CursorAdapter(LocalCliAdapter):
    """Run Cursor CLI locally."""

    @property
    def type(self) -> str:
        return "cursor_local"

    @property
    def label(self) -> str:
        return "Cursor CLI (local)"

    @property
    def cli_command(self) -> str:
        return "cursor"

    @property
    def default_model(self) -> str:
        return "auto"

    @property
    def models(self) -> list[dict[str, str]]:
        return [
            {"id": "auto", "label": "Auto"},
            {"id": "composer-1.5", "label": "Composer 1.5"},
            {"id": "composer-1", "label": "Composer 1"},
            {"id": "gpt-5.3-codex-low", "label": "GPT-5.3 Codex Low"},
            {"id": "gpt-5.3-codex", "label": "GPT-5.3 Codex"},
            {"id": "gpt-5.3-codex-high", "label": "GPT-5.3 Codex High"},
            {"id": "gpt-5.3-codex-xhigh", "label": "GPT-5.3 Codex XHigh"},
            {"id": "gpt-5.2", "label": "GPT-5.2"},
        ]

    async def execute(self, ctx: AdapterContext, on_log: Any | None = None) -> Any:
        config = ctx.config or {}
        command = self._resolve_command(config)
        model = config.get("model", self.default_model)
        mode = config.get("mode", "")

        args = ["--print", "-", "--output-format", "stream-json"]

        if ctx.session_id:
            args.extend(["--resume", ctx.session_id])
        if model and model != "auto":
            args.extend(["--model", model])
        if mode in ("plan", "ask"):
            args.extend(["--mode", mode])

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
