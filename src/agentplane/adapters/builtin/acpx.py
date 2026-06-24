"""ACPX (Agent Client Protocol) adapter."""

from typing import Any

from agentplane.adapters.base import AdapterContext
from agentplane.adapters.builtin._cli_base import LocalCliAdapter
from agentplane.adapters.registry import register_adapter


@register_adapter
class AcpxAdapter(LocalCliAdapter):
    """Run ACPX (Agent Client Protocol) locally."""

    @property
    def type(self) -> str:
        return "acpx_local"

    @property
    def label(self) -> str:
        return "ACPX (local)"

    @property
    def cli_command(self) -> str:
        return "acpx"

    @property
    def default_model(self) -> str:
        return ""

    @property
    def agent_options(self) -> list[dict[str, str]]:
        return [
            {"id": "claude", "label": "Claude via ACPX"},
            {"id": "codex", "label": "Codex via ACPX"},
            {"id": "custom", "label": "Custom ACP command"},
        ]

    async def execute(self, ctx: AdapterContext, on_log: Any | None = None) -> Any:
        config = ctx.config or {}
        command = config.get("agentCommand", "acpx")
        agent = config.get("agent", "claude")
        mode = config.get("mode", "persistent")
        model = config.get("model", "")

        args = ["--agent", agent, "--mode", mode]

        if model:
            args.extend(["--model", model])

        extra = config.get("extraArgs", [])
        if isinstance(extra, list):
            args.extend([str(a) for a in extra])

        env = self._build_env(ctx)
        cwd = self._build_cwd(ctx)
        timeout = self._build_timeout(ctx)

        result = await self._run_cli(command, args, cwd, env, timeout, on_log)
        return result

    def describe(self) -> dict[str, Any]:
        return {
            **super().describe(),
            "agent_options": self.agent_options,
        }
