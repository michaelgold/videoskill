# INSTRUCTIONS.md

## Project Goal
Build a pipeline that turns course videos into structured markdown step guides.

## Engineering Rules
- Follow TDD: write/adjust tests first when adding behavior.
- Keep changes small, typed, and deterministic.
- Prefer additive, non-breaking changes.
- Use `make verify` before every commit.
- Keep test coverage at or above 90%.

## Commit Rules
- Use Conventional Commits.
- Examples:
  - `feat: add whisper transcript segmenter`
  - `fix: handle empty transcript windows`
  - `test: add parser edge-case coverage`
  - `docs: update markdown output schema`

## Suggested Workflow
1. Write failing test.
2. Implement minimal code to pass.
3. Run `make verify`.
4. Commit with conventional message.
