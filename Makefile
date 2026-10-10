.DEFAULT_GOAL := help
.PHONY: help install hooks dev dev-backend dev-frontend check check-backend check-frontend format

help: ## Show available commands
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  %-16s %s\n", $$1, $$2}'

install: hooks ## Install backend and frontend dependencies and git hooks
	cd backend && uv sync --locked
	cd frontend && npm ci

hooks: ## Use the repository's git hooks
	git config core.hooksPath .githooks

dev: ## Run backend (:8000) and frontend (:5173) together
	@trap 'kill 0' INT TERM; $(MAKE) dev-backend & $(MAKE) dev-frontend & wait

dev-backend: ## Run the Django API on :8000
	cd backend && uv run python manage.py runserver 127.0.0.1:8000

dev-frontend: ## Run the Vite dev server on :5173
	cd frontend && npm run dev

check: check-backend check-frontend ## Run every lint, type check, test and build

check-backend: ## Lint, type-check and test the backend
	cd backend && uv run ruff format --check . && uv run ruff check . && uv run mypy . && uv run pytest -q

check-frontend: ## Lint, type-check, test and build the frontend
	cd frontend && npm run lint && npm run format:check && npm run typecheck && npm test && npm run build

format: ## Auto-format backend and frontend
	cd backend && uv run ruff format . && uv run ruff check --fix .
	cd frontend && npm run format
