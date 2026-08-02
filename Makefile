.PHONY: install dev up down logs migrate test lint format seed

install:
	cd backend && uv sync --all-groups
	cd frontend && pnpm install --frozen-lockfile

dev:
	docker compose up --build

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

migrate:
	cd backend && uv run alembic upgrade head

test:
	cd backend && uv run pytest
	cd frontend && pnpm test

lint:
	cd backend && uv run ruff check app tests && uv run mypy app
	cd frontend && pnpm run lint && pnpm run typecheck

format:
	cd backend && uv run ruff format app tests && uv run ruff check app tests --fix
	cd frontend && pnpm run format

seed:
	cd backend && uv run python -m app.scripts.seed
