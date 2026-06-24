#!/usr/bin/env python3
"""Bootstrap a demo agent against a running Agentplane server.

Uses the OANDA practice adapter with the credentials from `.env`.
Make sure AGENTPLANE_OANDA_TOKEN and AGENTPLANE_OANDA_ACCOUNT_ID are set.
The agent ID is saved to `.demo-agent-id` so `demo_agent.py --stop`
can stop its heartbeat later.
"""

import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path

BASE_URL = "http://127.0.0.1:3400/api"
STATE_FILE = Path(__file__).parent.parent / ".demo-agent-id"


def api_call(method: str, path: str, data: dict | None = None) -> dict:
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()
        raise SystemExit(f"API error {exc.code} on {method} {path}: {detail}") from exc


def find_or_create_desk() -> str:
    desks = api_call("GET", "/trading-desks")
    for desk in desks:
        if desk.get("name") == "Alpha Desk":
            return desk["id"]
    desk = api_call(
        "POST",
        "/trading-desks",
        {"name": "Alpha Desk", "mode": "paper", "initial_capital_usd": 10000},
    )
    return desk["id"]


def find_or_create_strategy() -> str:
    strategies = api_call("GET", "/strategies")
    for strategy in strategies:
        if strategy.get("name") == "Momentum Daily":
            return strategy["id"]
    strategy = api_call(
        "POST",
        "/strategies",
        {
            "name": "Momentum Daily",
            "timeframe": "daily",
            "entry_rules": {"type": "price_above_previous_close"},
        },
    )
    return strategy["id"]


def find_or_create_skill() -> str:
    skills = api_call("GET", "/skills")
    for skill in skills:
        if skill.get("name") == "Risk Management":
            return skill["id"]
    skill = api_call(
        "POST",
        "/skills",
        {
            "name": "Risk Management",
            "category": "risk",
            "prompt_injection": "Never risk more than 1% per trade.",
        },
    )
    return skill["id"]


DEMO_AGENT_NAME = "EURUSD OANDA Scalper"
DEMO_AGENT_CONFIG = {
    "symbol": "EUR_USD",
    "data_adapter": "oanda",
    "broker_adapter": "paper_broker",
    "environment": "practice",
    "interval": "1h",
    "period": "5d",
}


def find_or_create_agent(desk_id: str, strategy_id: str, skill_id: str) -> str:
    agents = api_call("GET", "/agents")
    for agent in agents:
        if agent.get("name") == DEMO_AGENT_NAME:
            agent_id = agent["id"]
            # Ensure the existing agent is wired to OANDA
            if agent.get("adapter_config", {}).get("data_adapter") != "oanda":
                api_call(
                    "PATCH",
                    f"/agents/{agent_id}",
                    {
                        "adapter_config": {
                            **agent.get("adapter_config", {}),
                            **DEMO_AGENT_CONFIG,
                        }
                    },
                )
            return agent_id

    agent = api_call(
        "POST",
        "/agents",
        {
            "name": DEMO_AGENT_NAME,
            "description": "Demo agent using real OANDA practice market data.",
            "role": "scalper",
            "trading_desk_id": desk_id,
            "strategy_id": strategy_id,
            "adapter_type": "paper_broker",
            "adapter_config": DEMO_AGENT_CONFIG,
            "risk_profile": "moderate",
            "skills": [skill_id],
            "heartbeat_interval_seconds": 10,
        },
    )
    return agent["id"]


def start_demo() -> None:
    desk_id = find_or_create_desk()
    strategy_id = find_or_create_strategy()
    skill_id = find_or_create_skill()
    agent_id = find_or_create_agent(desk_id, strategy_id, skill_id)

    api_call("POST", f"/heartbeats/{agent_id}/start")
    STATE_FILE.write_text(agent_id)

    print(f"Demo agent started: {agent_id}")
    print(f"  Heartbeat: POST /api/heartbeats/{agent_id}/start")
    print(f"  State:     GET  /api/agents/{agent_id}")
    print(f"  Signals:   GET  /api/agents/{agent_id}/signals")
    print(f"  Positions: GET  /api/agents/{agent_id}/positions")
    print(f"  Orders:    GET  /api/agents/{agent_id}/orders")
    print(f"\nStop later with: make stop-demo")


def stop_demo() -> None:
    if not STATE_FILE.exists():
        raise SystemExit("No demo agent ID found. Run `make demo` first.")
    agent_id = STATE_FILE.read_text().strip()
    api_call("POST", f"/heartbeats/{agent_id}/stop")
    STATE_FILE.unlink(missing_ok=True)
    print(f"Demo agent heartbeat stopped: {agent_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Agentplane demo agent helper")
    parser.add_argument("--stop", action="store_true", help="Stop the demo agent heartbeat")
    args = parser.parse_args()

    if args.stop:
        stop_demo()
    else:
        start_demo()


if __name__ == "__main__":
    main()
