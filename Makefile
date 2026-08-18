.PHONY: install lint format format-check test check migrations-check run docker-up docker-down

install:
	uv sync --frozen

lint:
	uv run ruff check .

format:
	uv run ruff format .

format-check:
	uv run ruff format --check .

test:
	uv run pytest

check:
	uv run python manage.py check

migrations-check:
	uv run python manage.py makemigrations --check

run:
	uv run python manage.py runserver

docker-up:
	docker compose up --build

docker-down:
	docker compose down
