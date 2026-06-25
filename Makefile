.PHONY: help install init run run-reload test test-q lint format check clean reset-db demo stop-demo

UV := uv
PORT := 3400
HOST := 127.0.0.1

# Termux/Android workaround: uv does not install Android wheels, so we fall back
# to pip; avoid uv run because it would try to re-sync the pip-managed venv.
ifeq ($(shell uname -o),Android)
    export ANDROID_API_LEVEL ?= $(shell getprop ro.build.version.sdk 2>/dev/null)
    PYTHON := .venv/bin/python
else
    PYTHON := uv run python
endif

help: ## Show this help
	@echo "Agentplane - available commands"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies (dev included)
ifeq ($(shell uname -o),Android)
	$(UV) venv --allow-existing
	.venv/bin/pip install -e ".[dev]"
else
	$(UV) sync --extra dev
endif

init: ## Initialize database and data directory
	$(PYTHON) -m agentplane init

run: ## Start the Agentplane server
	$(PYTHON) -m agentplane run --host $(HOST) --port $(PORT)

run-reload: ## Start the server with auto-reload
	$(PYTHON) -m agentplane run --host $(HOST) --port $(PORT) --reload

test: ## Run the test suite
	$(PYTHON) -m pytest -v

test-q: ## Run tests quietly
	$(PYTHON) -m pytest -q

lint: ## Run ruff linter
ifeq ($(shell uname -o),Android)
	@echo "ruff is skipped on Termux (not installed to avoid long Rust builds)"
else
	$(PYTHON) -m ruff check src tests
endif

format: ## Format code with ruff
ifeq ($(shell uname -o),Android)
	@echo "ruff is skipped on Termux (not installed to avoid long Rust builds)"
else
	$(PYTHON) -m ruff format src tests
endif

check: lint test ## Run lint + tests (CI gate)

clean: ## Remove cache files, database and generated artifacts
	rm -rf .pytest_cache .ruff_cache data/agentplane.db .demo-agent-id
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

reset-db: ## Delete the local SQLite database and re-initialize it
	rm -f data/agentplane.db
	$(PYTHON) -m agentplane init

# --- Quick trading setup via CLI ---

desk: ## Create a paper trading desk (Alpha Desk)
	$(PYTHON) -m agentplane trading create-desk "Alpha Desk" --capital 10000 --mode paper

strategy: ## Create a default daily momentum strategy
	$(PYTHON) -m agentplane trading create-strategy "Momentum Daily" --timeframe daily

skill: ## Create a default risk-management skill
	$(PYTHON) -m agentplane trading create-skill "Risk Management" --category risk

adapters: ## List registered adapters
	$(PYTHON) -m agentplane adapters

# --- Demo: run a complete offline agent in one command ---

demo: ## Create and start a demo agent using OANDA practice data (server must be running)
	$(PYTHON) scripts/demo_agent.py

stop-demo: ## Stop the demo agent heartbeat (server must be running)
	$(PYTHON) scripts/demo_agent.py --stop
