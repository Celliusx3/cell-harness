.PHONY: help install test test-unit test-integration lint fmt cov

BACKEND = cd backend && uv run

help:
	@echo "cell-harness — targets:"
	@echo "  make install           install the backend package + dev deps (uv)"
	@echo "  make test              all tests with the 80% coverage gate (pytest)"
	@echo "  make test-unit         unit tests only, no coverage gate"
	@echo "  make test-integration  integration tests only, no coverage gate"
	@echo "  make lint              ruff check + format check"
	@echo "  make fmt               ruff format + fix"
	@echo "  make cov               tests with an HTML coverage report"
	@echo ""
	@echo "Current phase and its acceptance criteria: PHASES.md"

install:
	cd backend && uv sync

test:
	$(BACKEND) pytest

# --no-cov on the split targets: the gate is a whole-suite property, and a
# partial run failing it reports "coverage too low" for work that is fine.
test-unit:
	$(BACKEND) pytest tests/unit --no-cov

test-integration:
	$(BACKEND) pytest tests/integration --no-cov

lint:
	$(BACKEND) ruff check .
	$(BACKEND) ruff format --check .

fmt:
	$(BACKEND) ruff format .
	$(BACKEND) ruff check --fix .

cov:
	$(BACKEND) pytest --cov-report=html
	@echo "open backend/htmlcov/index.html"
