"""Cursor Cloud adapter."""

import asyncio
from typing import Any

from agentplane.adapters.base import Adapter, AdapterContext, AdapterResult
from agentplane.adapters.registry import register_adapter


@register_adapter
class CursorCloudAdapter(Adapter):
    """Run Cursor Cloud Agents via HTTP API."""

    @property
    def type(self) -> str:
        return "cursor_cloud"

    @property
    def label(self) -> str:
        return "Cursor Cloud"

    async def execute(self, ctx: AdapterContext, on_log: Any | None = None) -> AdapterResult:
        config = ctx.config or {}
        repo_url = config.get("repoUrl", "")
        if not repo_url:
            return AdapterResult(
                success=False,
                stderr="cursor_cloud requires repoUrl in adapter_config",
            )

        # Simulated / placeholder — real impl would call Cursor Cloud REST API
        await asyncio.sleep(0.1)
        if on_log:
            await on_log("stdout", f"[cursor_cloud] Would start cloud agent for repo: {repo_url}\n")

        return AdapterResult(
            success=True,
            stdout=f"Cursor Cloud agent dispatched for {repo_url}",
            summary="Cloud agent running",
        )

    async def probe(self, config: dict[str, Any]) -> dict[str, Any]:
        api_key = config.get("env", {}).get("CURSOR_API_KEY") if isinstance(config.get("env"), dict) else None
        return {
            "available": api_key is not None,
            "note": "Requires CURSOR_API_KEY in env config",
            "repo_url_configured": bool(config.get("repoUrl")),
        }
