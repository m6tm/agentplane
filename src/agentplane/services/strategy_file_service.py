"""Strategy file service.

Each agent has its own strategy file in data/strategies/.
Agents read their file at each heartbeat to know what to do.
The user can edit these files to change strategy at any time.

File format (Markdown with YAML frontmatter):
---
name: "EURUSD Scalper Strategy"
version: 1
role: scalper
preferred_pairs: ["EUR_USD", "GBP_USD", "USD_JPY"]
preferred_timeframes: ["1m", "5m", "15m", "1h"]
max_positions: 3
risk_per_trade_pct: 1.0
---

# Entry Rules

## Primary Setup
- Look for breakouts above previous 1h high
- Volume must be > 120% of 20-period average
- RSI(14) between 40 and 70 (not overbought)

## Confirmation
- Price above 20 EMA on 1h
- MACD histogram positive and increasing
- No major news events in next 2 hours

# Exit Rules

## Take Profit
- 1:2 risk/reward minimum
- Trail stop at 1.5x ATR(14)
- Exit if RSI > 80 (overbought)

## Stop Loss
- Fixed: 1.0x ATR(14)
- Breakeven after +0.5R
- Time stop: close after 4 hours if not in profit

# Risk Management

- Max 2% risk per trade
- Max 3 open positions
- No trading during high-impact news
- Correlation check: max 2 positions on USD pairs

# Market Selection Logic

1. Scan major pairs for volatility (ATR > 20% of price)
2. Prefer pairs with clear trend (ADX > 25)
3. Avoid ranging markets (Bollinger Bands squeeze)
4. Check economic calendar for news events

# Adaptation Rules

If win rate < 40% over last 20 trades:
- Reduce position size by 50%
- Add confirmation filter (wait for 2nd candle close)
- Focus only on A-grade setups

If win rate > 60% over last 20 trades:
- Can increase position size by 25%
- Accept B-grade setups
- Widen stop loss to 1.5x ATR
"""

import os
from datetime import datetime
from typing import Any

import structlog
import yaml

from agentplane.core.models import Agent

logger = structlog.get_logger()

STRATEGIES_DIR = os.path.join("data", "strategies")

DEFAULT_STRATEGIES = {
    "scalper": """---
name: "Scalper Strategy"
version: 1
role: scalper
preferred_pairs: ["EUR_USD", "GBP_USD", "USD_JPY", "EUR_GBP"]
preferred_timeframes: ["1m", "5m", "15m", "1h"]
max_positions: 3
risk_per_trade_pct: 1.0
---

# Entry Rules

## Primary Setup
- Look for quick momentum bursts
- Volume spike > 150% of average
- Price breaks recent consolidation

## Confirmation
- Trend aligned on 5m and 15m
- No immediate resistance within 10 pips
- Spread < 2 pips for major pairs

# Exit Rules

## Take Profit
- 1:1.5 risk/reward
- Trail stop aggressively
- Exit if momentum fades

## Stop Loss
- Tight: 0.5x ATR(14)
- Time stop: 15 minutes max
- Move to breakeven after +0.3R

# Risk Management

- Max 1% risk per trade
- Max 2 open positions
- Close all before major news
- No revenge trading after 2 losses

# Market Selection

1. Focus on most liquid pairs (EUR/USD, GBP/USD)
2. Trade during London/NY overlap
3. Avoid Asian session (low volatility)
4. Check for news events in next 30 minutes
""",
    "swing": """---
name: "Swing Strategy"
version: 1
role: swing
preferred_pairs: ["GBP_JPY", "EUR_JPY", "AUD_JPY", "USD_JPY"]
preferred_timeframes: ["4h", "1d"]
max_positions: 5
risk_per_trade_pct: 2.0
---

# Entry Rules

## Primary Setup
- Identify major support/resistance zones
- Wait for pullback to 38.2%-61.8% Fibonacci
- Volume confirmation on reversal candle

## Confirmation
- Trend aligned on daily and 4h
- MACD divergence or crossover
- Price action: pin bar, engulfing, or inside bar breakout

# Exit Rules

## Take Profit
- 1:3 risk/reward minimum
- Partial close at 1:1, trail remainder
- Exit at major support/resistance

## Stop Loss
- Below/above swing low/high
- 1.5x ATR(14) for volatility buffer
- Time stop: 5 days if not in profit

# Risk Management

- Max 2% risk per trade
- Max 5 open positions
- Correlation limit: max 2 JPY pairs
- Reduce size in high volatility periods

# Market Selection

1. Look for trending markets (ADX > 20)
2. Prefer pairs with clear S/R levels
3. Check weekly economic calendar
4. Focus on pairs with central bank divergence
""",
    "risk_manager": """---
name: "Risk Manager Strategy"
version: 1
role: risk_manager
preferred_pairs: ["EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD"]
preferred_timeframes: ["1d", "1w"]
max_positions: 10
risk_per_trade_pct: 0.5
---

# Risk Oversight Rules

## Portfolio Limits
- Total portfolio risk < 5% at any time
- Max correlation: 0.7 between any two positions
- Stop all trading if drawdown > 10%

## Position Monitoring
- Review all open positions every 4 hours
- Flag oversized positions (>3% risk)
- Alert on correlated moves > 2%

## Intervention Rules
- Close positions violating risk limits
- Reduce size if volatility spikes (VIX > 30)
- Hedge portfolio with inverse ETFs if needed

# Market Analysis

1. Monitor overall market sentiment
2. Track sector rotation and correlations
3. Watch for black swan events
4. Maintain cash buffer for opportunities

# Reporting

- Daily P&L summary
- Risk metrics: VaR, Sharpe, max drawdown
- Alert on strategy drift
- Recommend portfolio rebalancing weekly
""",
}


class StrategyFileService:
    """Manage strategy files for agents."""

    def __init__(self):
        os.makedirs(STRATEGIES_DIR, exist_ok=True)

    def _get_path(self, agent_id: str) -> str:
        return os.path.join(STRATEGIES_DIR, f"{agent_id}.md")

    def create_default(self, agent: Agent) -> str:
        """Create default strategy file for an agent."""
        path = self._get_path(agent.id)
        if os.path.exists(path):
            return path

        role = agent.role or "scalper"
        content = DEFAULT_STRATEGIES.get(role, DEFAULT_STRATEGIES["scalper"])

        # Personalize the strategy
        content = content.replace(
            f'name: "{role.title()} Strategy"',
            f'name: "{agent.name} Strategy"'
        )

        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info("strategy.created", agent_id=agent.id, path=path, role=role)
        return path

    def read(self, agent_id: str) -> dict[str, Any] | None:
        """Read and parse strategy file for an agent."""
        path = self._get_path(agent_id)
        if not os.path.exists(path):
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            # Parse YAML frontmatter
            if content.startswith("---"):
                _, yaml_part, body = content.split("---", 2)
                frontmatter = yaml.safe_load(yaml_part.strip())
            else:
                frontmatter = {}
                body = content

            result = {
                "frontmatter": frontmatter or {},
                "body": body.strip(),
                "raw": content,
                "last_modified": datetime.fromtimestamp(os.path.getmtime(path)).isoformat(),
            }

            logger.debug("strategy.read", agent_id=agent_id, path=path)
            return result

        except Exception as e:
            logger.error("strategy.read_failed", agent_id=agent_id, error=str(e))
            return None

    def write(self, agent_id: str, content: str) -> bool:
        """Write strategy file for an agent."""
        path = self._get_path(agent_id)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info("strategy.updated", agent_id=agent_id, path=path)
            return True
        except Exception as e:
            logger.error("strategy.write_failed", agent_id=agent_id, error=str(e))
            return False

    def list_all(self) -> list[dict[str, str]]:
        """List all strategy files."""
        files = []
        for filename in os.listdir(STRATEGIES_DIR):
            if filename.endswith(".md"):
                path = os.path.join(STRATEGIES_DIR, filename)
                files.append({
                    "agent_id": filename[:-3],
                    "path": path,
                    "last_modified": datetime.fromtimestamp(os.path.getmtime(path)).isoformat(),
                })
        return files

    def get_strategy_summary(self, agent_id: str) -> dict[str, Any]:
        """Get a quick summary of the strategy for LLM context."""
        strategy = self.read(agent_id)
        if strategy is None:
            return {"error": "No strategy file found"}

        fm = strategy["frontmatter"]
        return {
            "name": fm.get("name", "Unnamed"),
            "version": fm.get("version", 1),
            "role": fm.get("role", "unknown"),
            "preferred_pairs": fm.get("preferred_pairs", []),
            "preferred_timeframes": fm.get("preferred_timeframes", []),
            "max_positions": fm.get("max_positions", 1),
            "risk_per_trade_pct": fm.get("risk_per_trade_pct", 1.0),
            "entry_rules_summary": self._extract_section(strategy["body"], "Entry Rules"),
            "exit_rules_summary": self._extract_section(strategy["body"], "Exit Rules"),
            "risk_management_summary": self._extract_section(strategy["body"], "Risk Management"),
        }

    def _extract_section(self, body: str, section_name: str) -> str:
        """Extract a section from the markdown body."""
        lines = body.split("\n")
        in_section = False
        section_lines = []

        for line in lines:
            if line.startswith(f"# {section_name}") or line.startswith(f"## {section_name}"):
                in_section = True
                continue
            elif in_section and line.startswith("#"):
                break
            elif in_section:
                section_lines.append(line)

        return "\n".join(section_lines).strip()
