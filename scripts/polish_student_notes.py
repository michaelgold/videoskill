from __future__ import annotations

import argparse
import re
from pathlib import Path

HEADING_RE = re.compile(r"^#\s+")
GENERIC_PHRASES = {
    "this lecture explores": "In this lecture, you will learn",
    "this lecture covers": "In this lecture, you will practice",
    "students will learn": "You will learn",
}

BANNED_NOTE_SNIPPETS = [
    "visual evidence",
    "cannot be verified",
    "not yet visible",
    "no motion detected",
    "the evidence",
    "detected",
    "not completed",
    "has not been completed",
    "instruction intent",
    "the user",
    "the learner",
    "the screenshot",
]


def clean_duplicate_title(lines: list[str]) -> list[str]:
    out: list[str] = []
    seen_top = False
    for line in lines:
        if HEADING_RE.match(line):
            if seen_top:
                # drop repeated top-level headers
                continue
            seen_top = True
        out.append(line)
    return out


def clean_generic_phrasing(text: str) -> str:
    out = text
    for src, dst in GENERIC_PHRASES.items():
        out = re.sub(src, dst, out, flags=re.IGNORECASE)
    return out


def normalize_sections(lines: list[str]) -> list[str]:
    text = "\n".join(lines)
    # Ensure canonical section headings if present with variants
    text = text.replace("## Step-by-step Lab", "## Step-by-step Lab")
    text = text.replace("## Step-by-step", "## Step-by-step Lab")
    # Remove duplicated consecutive section headers
    text = text.replace("## Lesson Notes\n\n## Overview", "## Overview")
    text = text.replace("## Lesson Notes\n\n## Step-by-step Lab", "## Step-by-step Lab")
    text = text.replace("## Lesson Notes Lab", "## Step-by-step Lab")
    # collapse 3+ blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.splitlines()


def _drop_banned_lines(lines: list[str]) -> list[str]:
    out: list[str] = []
    for line in lines:
        low = line.lower()
        if any(b in low for b in BANNED_NOTE_SNIPPETS):
            continue
        out.append(line)
    return out


def polish_file(path: Path) -> None:
    raw = path.read_text(encoding="utf-8")
    raw = clean_generic_phrasing(raw)
    lines = raw.splitlines()
    lines = clean_duplicate_title(lines)
    lines = normalize_sections(lines)
    lines = _drop_banned_lines(lines)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deterministic polish pass for generated student notes"
    )
    parser.add_argument(
        "--in-dir",
        type=Path,
        default=Path("datasets/demo/lecture_notes_student_v2"),
        help="Directory containing *.student-notes.md files",
    )
    args = parser.parse_args()

    files = sorted(args.in_dir.glob("*.student-notes.md"))
    if not files:
        raise SystemExit(f"No student notes found in {args.in_dir}")

    for f in files:
        polish_file(f)
        print(f"POLISHED {f}")


if __name__ == "__main__":
    main()
