.PHONY: install format lint test coverage verify notes-student notes-pdf

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

notes-student:
	uv run python scripts/generate_student_notes.py --config config.json --out-dir datasets/demo/lecture_notes_student_v2 --max-steps 40
	uv run python scripts/polish_student_notes.py --in-dir datasets/demo/lecture_notes_student_v2

notes-pdf:
	uv run python scripts/notes_markdown_to_pdf.py --in-dir datasets/demo/lecture_notes_student_v2 --out-dir datasets/demo/lecture_notes_student_v2_pdf
