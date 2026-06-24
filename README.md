# Agentplane

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-131%20passing-green.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> Agentic trading control plane. Traders are agents. They learn from their mistakes.

## What is Agentplane?

**Agentplane** is a control plane for autonomous trading desks. It orchestrates AI traders that can scalp or trade daily, manage risk, and continuously improve from their trade journal.

- **Agentic philosophy** — Inspired by Paperclip: traders are agents with skills, goals, and memory.
- **Plugin-based adapters** — Connect any broker or data provider (paper, Alpaca, Binance, OANDA, etc.).
- **Paper-first** — Every strategy is validated in paper trading and backtests before live capital.
- **Learning loop** — Trades are journaled; lessons are extracted and injected into future decisions.
- **Async-first** — Handles many concurrent traders without blocking.
- **Contributor-friendly** — Pure Python, minimal deps, clear module boundaries.

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)

### Install & Run

```bash
# Clone
git clone https://github.com/m6tm/agentplane.git
cd agentplane

# Install dependencies and initialize the database
make install
make init

# Start server
make run
```

Server is now at `http://127.0.0.1:3400`.

At startup, Agentplane boots a special **Orchestrator** agent. The Orchestrator creates a default team of traders (EUR/USD scalper, GBP/JPY swing, and a global risk manager) if none exist yet, then resumes heartbeats for every agent whose status is not `paused` and whose trading desk is active. In other words, a simple `make run` starts the entire autonomous trading floor from a blank database.

### Makefile shortcuts

A `Makefile` is provided for the most common tasks:

```bash
make help          # show all commands
make install       # uv sync --extra dev
make init          # initialize database and data directory
make run           # start the server
make run-reload    # start the server with auto-reload
make test          # run the test suite
make lint          # run ruff
make format        # format code with ruff
make check         # lint + tests (CI gate)
make clean         # remove cache files and local database
make desk          # create Alpha Desk via CLI
make strategy      # create Momentum Daily strategy via CLI
make skill         # create Risk Management skill via CLI
make adapters      # list registered adapters
make demo          # start a complete offline demo agent
make stop-demo     # stop the demo agent heartbeat
```

### Verify

```bash
# Check health
curl http://localhost:3400/api/health

# Create a trading desk
uv run python -m agentplane trading create-desk "Alpha Desk" --capital 50000

# Create a strategy
uv run python -m agentplane trading create-strategy "Momentum Daily" --timeframe daily

# Create a skill
uv run python -m agentplane trading create-skill "Risk Management" --category risk

# List adapters
uv run python -m agentplane adapters
```

### Run your first agent

Agents use **OANDA** market data by default. Make sure you have copied `.env.example` to `.env` and filled in `AGENTPLANE_OANDA_TOKEN` and `AGENTPLANE_OANDA_ACCOUNT_ID`.

1. Start the server:

   ```bash
   uv run python -m agentplane run
   ```

2. In another terminal, create a desk, a strategy, and a skill:

   ```bash
   curl -X POST http://localhost:3400/api/trading-desks \
        -H "Content-Type: application/json" \
        -d '{"name":"Alpha Desk","mode":"paper","initial_capital_usd":10000}'

   curl -X POST http://localhost:3400/api/strategies \
        -H "Content-Type: application/json" \
        -d '{"name":"Momentum Daily","timeframe":"daily","entry_rules":{"type":"price_above_previous_close"}}'

   curl -X POST http://localhost:3400/api/skills \
        -H "Content-Type: application/json" \
        -d '{"name":"Risk Management","category":"risk","prompt_injection":"Never risk more than 1% per trade."}'
   ```

3. Create an agent (replace `<DESK_ID>` and `<STRATEGY_ID>` with the IDs returned above):

   ```bash
   curl -X POST http://localhost:3400/api/agents \
        -H "Content-Type: application/json" \
        -d '{
          "name": "EURUSD OANDA Scalper",
          "role": "scalper",
          "trading_desk_id": "<DESK_ID>",
          "strategy_id": "<STRATEGY_ID>",
          "adapter_type": "paper_broker",
          "adapter_config": {
            "symbol": "EUR_USD",
            "data_adapter": "oanda",
            "broker_adapter": "paper_broker",
            "environment": "practice",
            "interval": "1h",
            "period": "5d"
          },
          "risk_profile": "moderate",
          "heartbeat_interval_seconds": 10
        }'
   ```

4. Start the heartbeat:

   ```bash
   curl -X POST http://localhost:3400/api/heartbeats/<AGENT_ID>/start
   ```

5. Watch it work:

   ```bash
   # Active heartbeats
   curl http://localhost:3400/api/heartbeats

   # Agent state
   curl http://localhost:3400/api/agents/<AGENT_ID>

   # Generated signals
   curl http://localhost:3400/api/agents/<AGENT_ID>/signals

   # Open positions
   curl http://localhost:3400/api/agents/<AGENT_ID>/positions

   # Filled orders
   curl http://localhost:3400/api/agents/<AGENT_ID>/orders
   ```

6. Stop the agent:

   ```bash
   curl -X POST http://localhost:3400/api/heartbeats/<AGENT_ID>/stop
   ```

Execution stays on `paper_broker` until you explicitly switch the desk to `live`.

## Orchestrator

Agentplane includes an auto-starting **Orchestrator** agent that manages the trading floor.

On every server start the Orchestrator:

1. Creates a dedicated **Orchestrator Desk** if it does not exist.
2. Creates baseline strategies (`Scalping Momentum`, `Swing Momentum`, `Daily Momentum`) if they do not exist.
3. Creates itself as an agent with the `orchestrator` adapter if it does not exist.
4. Spawns a default team of three traders when the database has no other agents:
   - **EURUSD Scalper** — 1h bars, aggressive risk profile, 30s heartbeat
   - **GBPJPY Swing** — 4h bars, moderate risk profile, 5m heartbeat
   - **Risk Manager** — daily bars, conservative risk profile, 10m heartbeat
5. Broadcasts a `status` message to the team on each heartbeat so agents can coordinate.

The Orchestrator is just another agent with `adapter_type: orchestrator`. You can inspect it via the API like any other agent and replace the default team with your own traders at any time.

## LLM Provider

Every agent is connected to an LLM adapter for decision-making. By default this is **Kimi Code** (`kimi_local`).

The LLM is used for:

- **Traders** — deciding `LONG`, `SHORT`, or `HOLD` based on market data, strategy rules, and memory context. If the LLM is unavailable, the agent falls back to deterministic strategy rules.
- **Orchestrator** — generating a plain-text terminal reply when it receives a message.

The provider is configured per agent inside `adapter_config.llm_adapter`:

```json
{
  "adapter_type": "paper_broker",
  "adapter_config": {
    "symbol": "EUR_USD",
    "data_adapter": "oanda",
    "broker_adapter": "paper_broker",
    "llm_adapter": "kimi_local"
  }
}
```

Install the corresponding CLI locally (e.g. `kimi`) for the LLM calls to succeed. If the CLI is missing, agents still run using their rule-based fallback.

## Supported Adapters

Agentplane ships with built-in adapters for brokers and data providers:

| Adapter | Type | Purpose |
|---|---|---|
| `paper_broker` | Broker | Simulated order execution for paper trading |
| `orchestrator` | Meta | Auto-starts the trading desk and default trader team |
| `oanda` | Data | OANDA REST v3 forex/CFD candles and pricing (default) |
| `static_data` | Data | Deterministic offline bars used only by the test suite |
| `process` | Utility | Run any shell command |
| `claude_local` | AI CLI | Claude Code |
| `kimi_local` | AI CLI | Kimi Code |
| `codex_local` | AI CLI | OpenAI Codex |
| `cursor_local` | AI CLI | Cursor CLI |
| `cursor_cloud` | Cloud | Cursor Cloud API |
| `gemini_local` | AI CLI | Gemini CLI |
| `grok_local` | AI CLI | Grok Build CLI |
| `opencode_local` | AI CLI | OpenCode CLI |
| `pi_local` | AI CLI | Pi CLI |
| `acpx_local` | Protocol | Agent Client Protocol |

## Configuration

Copy `.env.example` to `.env` and adjust the values:

```bash
cp .env.example .env
```

Agentplane uses `pydantic-settings` with the prefix `AGENTPLANE_`, so every variable in `.env.example` is loaded automatically.

## Data Providers

Agentplane connects to **OANDA** by default for real market data. A local SQLite cache stores fetched bars so the API is not hit on every heartbeat.

### OANDA (default)

Create an agent with the `oanda` data adapter:

```json
{
  "name": "EURUSD Scalper",
  "adapter_type": "paper_broker",
  "adapter_config": {
    "symbol": "EUR_USD",
    "data_adapter": "oanda",
    "broker_adapter": "paper_broker",
    "environment": "practice",
    "interval": "1h",
    "period": "5d"
  }
}
```

- `environment`: `practice` (default) or `live`.
- `symbol`: OANDA instrument format, e.g. `EUR_USD`, `GBP_JPY`, `XAU_USD`.
- Credentials can be provided in `adapter_config` or, preferably, via `.env` (`AGENTPLANE_OANDA_TOKEN`, `AGENTPLANE_OANDA_ACCOUNT_ID`).

#### How to get your OANDA credentials

1. **Token**: open the OANDA portal, go to **Manage API Access** and generate a token.
2. **Account ID**: it is the **v20 Account Number** shown in the OANDA web dashboard, formatted as `###-###-########-###` (for example `101-004-1435156-001`).
   If you already have a token, you can list account IDs with:

   ```bash
   curl -H "Authorization: Bearer <YOUR_OANDA_TOKEN>" \
        https://api-fxpractice.oanda.com/v3/accounts
   ```

   For live accounts use `https://api-fxtrade.oanda.com/v3/accounts`. The response contains `accounts[].id`.
3. Copy `.env.example` to `.env` and fill in both values. The adapter falls back to `AGENTPLANE_OANDA_TOKEN` / `AGENTPLANE_OANDA_ACCOUNT_ID` when they are not provided in `adapter_config`.

> **Note:** `static_data` still exists but is reserved for the automated test suite. It is not used by default at runtime.

## Core Concepts

### Trading Desk
A container for capital, risk limits, and traders. Mode can be `paper`, `backtest`, or `live`.

### Trader (Agent)
An autonomous trader attached to a desk and a strategy. Has a risk profile, skills, and a heartbeat schedule.

### Strategy
Entry/exit rules and risk parameters. Timeframe can be `scalping`, `daily`, or `swing`.

### Skill
A behavior module attached to a trader (e.g. technical analysis, risk management, trade psychology). Skills inject context into the trader's decisions.

### Trade Journal & Lessons
Every trade is journaled. The system extracts lessons from losses and mistakes, then injects active lessons into future trader heartbeats so the same error is not repeated.

## Architecture

```
agentplane/
├── src/agentplane/
│   ├── core/              # Config, DB (SQLModel), models
│   ├── adapters/          # Broker/data provider adapters
│   ├── api/               # FastAPI REST server
│   ├── services/          # Business logic
│   └── cli/               # Typer CLI
├── adapters/              # Drop external adapter plugins here
├── tests/                 # 122 integration tests
└── data/                  # SQLite + runtime files
```

## Writing a Custom Adapter

Create `adapters/my_broker.py`:

```python
from agentplane.adapters.base import Adapter, AdapterContext, AdapterResult
from agentplane.adapters.registry import register_adapter

@register_adapter
class MyBrokerAdapter(Adapter):
    @property
    def type(self) -> str:
        return "my_broker"

    @property
    def label(self) -> str:
        return "My Broker"

    async def execute(self, ctx: AdapterContext, on_log=None) -> AdapterResult:
        config = ctx.config or {}
        action = config.get("action")  # buy | sell
        symbol = config.get("symbol")
        quantity = config.get("quantity")
        # ... call broker API
        return AdapterResult(success=True, stdout="filled")

    async def probe(self, config: dict) -> dict:
        return {"available": True}
```

Restart the server — your adapter appears automatically.

## Scaling Up

| Scale | Change |
|---|---|
| **Local dev** | SQLite (default), zero config |
| **Team** | Swap `database_url` to PostgreSQL |
| **Production** | Run behind Uvicorn workers / reverse proxy |
| **Many traders** | Deploy multiple instances, shared DB |
| **Custom brokers** | Add adapters |

Environment variables:

```bash
AGENTPLANE_DATABASE_URL="postgresql+asyncpg://user:pass@localhost/agentplane"
AGENTPLANE_HOST=0.0.0.0
AGENTPLANE_PORT=3400
AGENTPLANE_DEBUG=false
```

## Development

```bash
# Run tests
uv run pytest

# Type check
uv run mypy src

# Lint
uv run ruff check src
uv run ruff format src
```

## Roadmap

- [x] Trading desk / strategy / skill models
- [x] Paper broker adapter
- [x] OANDA data adapter
- [x] Static data adapter (offline/tests)
- [x] Heartbeat scheduler
- [x] Signal generation
- [x] Signal execution → orders and positions
- [x] Position and order tracking
- [x] Trade journal and lesson extraction
- [x] Agentic memory influencing decisions
- [x] Local market-data cache
- [ ] Backtesting engine
- [ ] Live broker adapters (Alpaca, Binance, OANDA)
- [ ] Desktop vision / GUI automation adapter (future)

## License

MIT
