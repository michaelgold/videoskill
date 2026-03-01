.PHONY: install format lint test coverage verify

install:
	uv sync --dev

format:
	uv run ruff format .

lint:
	uv run ruff check .

test:
	uv run pytest

coverage:
	uv run pytest --cov=video_skill_extractor --cov-report=term-missing --cov-fail-under=90

verify: lint test
