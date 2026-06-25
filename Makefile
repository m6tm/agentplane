.PHONY: help install init run run-reload test test-q lint format check clean reset-db demo stop-demo \
        desktop desktop-build desktop-dev desktop-preview stop status logs \
        agents desks strategies skills positions signals send-message \
        db-shell db-dump db-restore migrate

UV := uv
PORT := 3400
HOST := 127.0.0.1
API_BASE := http://$(HOST):$(PORT)

# Termux/Android workaround: uv does not install Android wheels, so we fall back
# to pip; avoid uv run because it would try to re-sync the pip-managed venv.
ifeq ($(shell uname -o),Android)
    export ANDROID_API_LEVEL ?= $(shell getprop ro.build.version.sdk 2>/dev/null)
    PYTHON := .venv/bin/python
else
    export UV_LINK_MODE := copy
    PYTHON := uv run python
endif

help: ## Show this help
	@echo "Agentplane - available commands"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# =============================================================================
# Installation & Setup
# =============================================================================

install: ## Install dependencies (dev included)
ifeq ($(shell uname -o),Android)
	$(UV) venv --allow-existing
	.venv/bin/pip install -e ".[dev]"
else
	$(UV) sync --extra dev
endif

init: ## Initialize database and data directory
	$(PYTHON) -m agentplane init

reset-db: ## Delete the local SQLite database and re-initialize it
	rm -f data/agentplane.db
	$(PYTHON) -m agentplane init

# =============================================================================
# Server (Backend)
# =============================================================================

run: ## Start the Agentplane server
	$(PYTHON) -m agentplane run --host $(HOST) --port $(PORT)

run-reload: ## Start the server with auto-reload
	$(PYTHON) -m agentplane run --host $(HOST) --port $(PORT) --reload

stop: ## Stop the running server (find and kill the process)
	@echo "Stopping Agentplane server..."
	@taskkill /F /IM python.exe 2>/dev/null || pkill -f "agentplane run" 2>/dev/null || true
	@echo "Server stopped"

status: ## Check if the server is running
	@curl -s $(API_BASE)/api/health > /dev/null && echo "Server is ONLINE at $(API_BASE)" || echo "Server is OFFLINE"

# =============================================================================
# Desktop Interface
# =============================================================================

desktop-install: ## Install desktop dependencies
	cd desktop && pnpm install

desktop-dev: ## Start desktop in development mode
	cd desktop && pnpm run dev

desktop-build: ## Build desktop for production
	cd desktop && pnpm run build

desktop-preview: ## Preview built desktop
	cd desktop && pnpm run preview

stop-desktop: ## Stop the desktop preview server
	@echo "Stopping desktop server..."
	@taskkill //F //IM node.exe 2>/dev/null || echo "No desktop server running"
	@echo "Desktop server stopped"

# =============================================================================
# Testing & Quality
# =============================================================================

test: ## Run the test suite
	$(PYTHON) -m pytest -v

test-q: ## Run tests quietly
	$(PYTHON) -m pytest -q

test-cov: ## Run tests with coverage
	$(PYTHON) -m pytest -v --cov=src/agentplane --cov-report=html

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

# =============================================================================
# Database Operations
# =============================================================================

db-shell: ## Open SQLite shell
	sqlite3 data/agentplane.db

db-dump: ## Dump database schema and data
	sqlite3 data/agentplane.db .dump > data/backup_$(shell date +%Y%m%d_%H%M%S).sql

db-restore: ## Restore database from latest backup (prompts for confirmation)
	@echo "Available backups:"
	@ls -1 data/backup_*.sql 2>/dev/null || echo "No backups found"
	@echo "Run: sqlite3 data/agentplane.db < backup_file.sql"

migrate: ## Run database migrations (if any)
	@echo "Migrations are handled automatically by SQLModel"
	@echo "To reset: make reset-db"

# =============================================================================
# Trading Setup
# =============================================================================

desk: ## Create a paper trading desk (Alpha Desk)
	$(PYTHON) -m agentplane trading create-desk "Alpha Desk" --capital 10000 --mode paper

desk-list: ## List all trading desks
	@curl -s $(API_BASE)/api/trading-desks | $(PYTHON) -m json.tool 2>/dev/null || echo "Server not running"

strategy: ## Create a default daily momentum strategy
	$(PYTHON) -m agentplane trading create-strategy "Momentum Daily" --timeframe daily

strategy-list: ## List all strategies
	@curl -s $(API_BASE)/api/strategies | $(PYTHON) -m json.tool 2>/dev/null || echo "Server not running"

skill: ## Create a default risk-management skill
	$(PYTHON) -m agentplane trading create-skill "Risk Management" --category risk

skill-list: ## List all skills
	@curl -s $(API_BASE)/api/skills | $(PYTHON) -m json.tool 2>/dev/null || echo "Server not running"

adapters: ## List registered adapters
	$(PYTHON) -m agentplane adapters

# =============================================================================
# Agent Operations
# =============================================================================

agents: ## List all agents
	@curl -s $(API_BASE)/api/agents | $(PYTHON) -m json.tool 2>/dev/null || echo "Server not running"

agent-create: ## Create a new agent (interactive)
	@echo "Usage: make agent-create NAME=MyAgent ROLE=scalper SYMBOL=EUR_USD"
	@test -n "$(NAME)" || (echo "Error: NAME is required" && exit 1)
	@test -n "$(ROLE)" || (echo "Error: ROLE is required (scalper, swing, day)" && exit 1)
	@test -n "$(SYMBOL)" || (echo "Error: SYMBOL is required (e.g., EUR_USD)" && exit 1)
	@curl -s -X POST $(API_BASE)/api/agents \
		-H "Content-Type: application/json" \
		-d '{"name":"$(NAME)","role":"$(ROLE)","adapter_type":"paper_broker","adapter_config":{"symbol":"$(SYMBOL)","environment":"practice"}}' \
		| $(PYTHON) -m json.tool

agent-delete: ## Delete an agent by ID
	@test -n "$(ID)" || (echo "Error: ID is required" && exit 1)
	@curl -s -X DELETE $(API_BASE)/api/agents/$(ID) | $(PYTHON) -m json.tool

agent-pause: ## Pause an agent
	@test -n "$(ID)" || (echo "Error: ID is required" && exit 1)
	@curl -s -X POST $(API_BASE)/api/agents/$(ID)/pause | $(PYTHON) -m json.tool

agent-resume: ## Resume an agent
	@test -n "$(ID)" || (echo "Error: ID is required" && exit 1)
	@curl -s -X POST $(API_BASE)/api/agents/$(ID)/resume | $(PYTHON) -m json.tool

# =============================================================================
# Positions & Signals
# =============================================================================

positions: ## List all open positions
	@curl -s $(API_BASE)/api/positions | $(PYTHON) -m json.tool 2>/dev/null || echo "Server not running"

signals: ## List all signals
	@curl -s $(API_BASE)/api/signals | $(PYTHON) -m json.tool 2>/dev/null || echo "Server not running"

# =============================================================================
# Orchestrator Communication
# =============================================================================

send-message: ## Send a message to the orchestrator
	@curl -s -X POST $(API_BASE)/api/orchestrator/messages \
		-H "Content-Type: application/json" \
		-d '{"message_type": "command", "payload": {"action": "debriefing", "question": "$(MSG)"}}' \
		| $(PYTHON) -m json.tool 2>/dev/null || echo "Server not running"

orchestrator-status: ## Get orchestrator status
	@curl -s $(API_BASE)/api/orchestrator/status | $(PYTHON) -m json.tool 2>/dev/null || echo "Server not running"

# =============================================================================
# Logs & Monitoring
# =============================================================================

logs: ## Show recent server logs (follow mode)
	@echo "Server logs are written to stdout. Use your terminal scrollback or:"
	@echo "  make run > data/server.log 2>&1 &"
	@echo "  tail -f data/server.log"

health: ## Check server health
	@curl -s $(API_BASE)/api/health | $(PYTHON) -m json.tool 2>/dev/null || echo "Server not running"

# =============================================================================
# Demo
# =============================================================================

demo: ## Create and start a demo agent using OANDA practice data (server must be running)
	$(PYTHON) scripts/demo_agent.py

stop-demo: ## Stop the demo agent heartbeat (server must be running)
	$(PYTHON) scripts/demo_agent.py --stop

# =============================================================================
# Maintenance
# =============================================================================

clean: ## Remove cache files, database and generated artifacts
	rm -rf .pytest_cache .ruff_cache data/agentplane.db .demo-agent-id
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "Cleaned generated files"

clean-all: ## Deep clean including node_modules and dist
	make clean
	rm -rf desktop/node_modules desktop/dist
	@echo "Deep clean complete"

update: ## Update all dependencies
	$(UV) sync --upgrade
	cd desktop && pnpm update

# =============================================================================
# Development Helpers
# =============================================================================

format-check: ## Check code formatting without fixing
ifeq ($(shell uname -o),Android)
	@echo "ruff is skipped on Termux"
else
	$(PYTHON) -m ruff format --check src tests
endif

type-check: ## Run type checker (mypy)
	$(PYTHON) -m mypy src/agentplane

pre-commit: format lint test ## Run all checks before committing

# =============================================================================
# Strategy Files (User-managed)
# =============================================================================

strategy-files: ## List all agent strategy files
	@ls -la data/strategies/ 2>/dev/null || echo "No strategy files yet"

strategy-edit: ## Open a strategy file for editing (requires AGENT_ID)
	@test -n "$(AGENT_ID)" || (echo "Error: AGENT_ID is required" && exit 1)
	@echo "Edit file: data/strategies/$(AGENT_ID).md"
	@echo "The agent will pick up changes on next heartbeat"

# =============================================================================
# Quick Start
# =============================================================================

quickstart: ## Full setup: install, init, run
	make install
	make init
	@echo ""
	@echo "Setup complete! Run: make run"
	@echo "Then: make desktop-dev (in another terminal)"
