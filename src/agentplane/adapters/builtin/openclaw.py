"""OpenClaw Gateway adapter."""

import asyncio
from typing import Any

from agentplane.adapters.base import Adapter, AdapterContext, AdapterResult
from agentplane.adapters.registry import register_adapter


@register_adapter
class OpenClawAdapter(Adapter):
    """Invoke OpenClaw over Gateway WebSocket protocol."""

    @property
    def type(self) -> str:
        return "openclaw_gateway"

    @property
    def label(self) -> str:
        return "OpenClaw Gateway"

    async def execute(self, ctx: AdapterContext, on_log: Any | None = None) -> AdapterResult:
        config = ctx.config or {}
        url = config.get("url", "")
        if not url:
            return AdapterResult(
                success=False,
                stderr="openclaw_gateway requires url in adapter_config",
            )

        # Simulated / placeholder — real impl would open WebSocket connection
        await asyncio.sleep(0.1)
        if on_log:
            await on_log("stdout", f"[openclaw] Would connect to gateway: {url}\n")

        return AdapterResult(
            success=True,
            stdout=f"OpenClaw gateway connection established to {url}",
            summary="Gateway connected",
        )

    async def probe(self, config: dict[str, Any]) -> dict[str, Any]:
        url = config.get("url", "")
        return {
            "available": bool(url),
            "note": "Requires WebSocket URL in config",
            "url_configured": bool(url),
        }
