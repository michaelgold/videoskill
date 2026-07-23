from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert student markdown notes to PDF")
    parser.add_argument(
        "--in-dir",
        type=Path,
        default=Path("datasets/demo/lecture_notes_student_v2"),
        help="Directory containing *.student-notes.md",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("datasets/demo/lecture_notes_student_v2_pdf"),
        help="Output directory for PDFs",
    )
    parser.add_argument(
        "--pdf-engine",
        default="weasyprint",
        help="Pandoc PDF engine (default: weasyprint)",
    )
    parser.add_argument(
        "--css",
        type=Path,
        default=Path("scripts/pandoc_notes.css"),
        help="CSS file for markdown->PDF styling",
    )
    args = parser.parse_args()

    pandoc = shutil.which("pandoc")
    if not pandoc:
        raise SystemExit("pandoc not found on PATH. Install pandoc to enable PDF export.")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(args.in_dir.glob("*.student-notes.md"))
    if not files:
        raise SystemExit(f"No markdown notes found in {args.in_dir}")

    for md in files:
        pdf = args.out_dir / md.with_suffix(".pdf").name
        cmd = [
            pandoc,
            str(md),
            "-o",
            str(pdf),
            "--pdf-engine",
            args.pdf_engine,
            "--css",
            str(args.css),
        ]
        subprocess.run(cmd, check=True)
        print(f"PDF {pdf}")


if __name__ == "__main__":
    main()
