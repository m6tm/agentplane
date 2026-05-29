"""OpenAI Codex adapter."""

from typing import Any

from agentplane.adapters.builtin._cli_base import LocalCliAdapter
from agentplane.adapters.base import AdapterContext, AdapterResult
from agentplane.adapters.registry import register_adapter


@register_adapter
class CodexAdapter(LocalCliAdapter):
    """Run OpenAI Codex CLI locally."""

    @property
    def type(self) -> str:
        return "codex_local"

    @property
    def label(self) -> str:
        return "Codex (local)"

    @property
    def cli_command(self) -> str:
        return "codex"

    @property
    def default_model(self) -> str:
        return "gpt-5.3-codex"

    @property
    def models(self) -> list[dict[str, str]]:
        return [
            {"id": "gpt-5.3-codex", "label": "GPT-5.3 Codex"},
            {"id": "gpt-5.4", "label": "GPT-5.4"},
        ]

    async def execute(self, ctx: AdapterContext, on_log: Any | None = None) -> Any:
        config = ctx.config or {}
        command = self._resolve_command(config)
        model = config.get("model", self.default_model)
        max_turns = config.get("max_turns", 0)
        fast_mode = config.get("fastMode", False)

        args = ["--print", "-", "--output-format", "stream-json"]

        if ctx.session_id:
            args.extend(["--resume", ctx.session_id])
        if model:
            args.extend(["--model", model])
        if max_turns > 0:
            args.extend(["--max-turns", str(max_turns)])
        if fast_mode:
            args.append("--fast-mode")

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
