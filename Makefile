.PHONY: help install dev dev-backend dev-web test test-unit test-integration \
        test-mcp-servers lint lint-mcp-servers fmt cov build

BACKEND = cd backend && uv run

# The port lives here, not in config.json: the frontend's dev proxy
# (frontend/next.config.ts) has to agree with it and cannot read Python config,
# so a setting would look authoritative while the proxy silently kept using the
# old value. See the note in harness/web/server.py.
#
# No --host: uvicorn defaults to 127.0.0.1, which is what we want. This server
# has no authentication in front of a model loop holding a provider key.
BACKEND_RUN  = cd backend && uv run uvicorn harness.web.server:create_web_app --factory --reload --port 4896
FRONTEND_RUN = cd frontend && npm run dev

help:
	@echo "cell-harness — targets:"
	@echo "  make install           backend (uv) + frontend (npm)"
	@echo "  make dev               backend (:4896) + frontend (:4897) together"
	@echo "  make dev-backend       backend only  (:4896)"
	@echo "  make dev-web           frontend only (:4897)"
	@echo "  make test              all tests with the 80% coverage gate (pytest)"
	@echo "  make test-unit         unit tests only, no coverage gate"
	@echo "  make test-integration  integration tests only, no coverage gate"
	@echo "  make test-mcp-servers   each MCP server's own suite and its own gate"
	@echo "  make lint              ruff check + format check + every file under 300 lines"
	@echo "  make lint-mcp-servers   ruff check + format check in each MCP server"
	@echo "  make fmt               ruff format + fix"
	@echo "  make cov               tests with an HTML coverage report"
	@echo "  make build             frontend production build"
	@echo ""
	@echo "Current phase and its acceptance criteria: PHASES.md"

install:
	cd backend && uv sync
	cd frontend && npm install

dev:
	@echo "backend :4896  ·  frontend :4897   (Ctrl-C stops both)"
	@echo "note: the API key belongs in backend/config.local.json"
	@trap 'kill 0' INT TERM EXIT; \
	( $(BACKEND_RUN) ) & \
	( $(FRONTEND_RUN) ) & \
	wait

dev-backend:
	$(BACKEND_RUN)

dev-web:
	$(FRONTEND_RUN)

test:
	$(BACKEND) pytest

# --no-cov on the split targets: the gate is a whole-suite property, and a
# partial run failing it reports "coverage too low" for work that is fine.
test-unit:
	$(BACKEND) pytest tests/unit --no-cov

test-integration:
	$(BACKEND) pytest tests/integration --no-cov

# Deliberately NOT part of `test`: each server under mcp-servers/ is a separate
# uv project with its own 80% gate, and folding a second --cov source into one
# pytest run makes the gate mean nothing about either. One server's flake must
# not fail the harness's suite. `uv run` syncs on demand, so no install target.
MCP_SERVERS = mcp-servers/instagram mcp-servers/places mcp-servers/markets

test-mcp-servers:
	@for s in $(MCP_SERVERS); do (cd $$s && uv run pytest) || exit 1; done

# The sandbox shim is real code the model's programs run inside, so it gets the
# same treatment as the Python. Deno is already required to start the harness.
lint:
	$(BACKEND) ruff check .
	$(BACKEND) ruff format --check .
	cd backend/harness/sandbox/js && deno check shim.ts && deno lint && deno fmt --check
	./scripts/check-file-lengths.sh

lint-mcp-servers:
	@for s in $(MCP_SERVERS); do \
		(cd $$s && uv run ruff check . && uv run ruff format --check .) || exit 1; \
	done

fmt:
	$(BACKEND) ruff format .
	cd backend/harness/sandbox/js && deno fmt
	$(BACKEND) ruff check --fix .

cov:
	$(BACKEND) pytest --cov-report=html
	@echo "open backend/htmlcov/index.html"

build:
	cd frontend && npm run build
