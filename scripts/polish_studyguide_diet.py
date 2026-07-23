from __future__ import annotations

import argparse
import re
from pathlib import Path


def _split_long_paragraph(text: str, max_chars: int = 320) -> str:
    s = text.strip()
    if len(s) <= max_chars:
        return s
    # naive sentence split; keep punctuation
    parts = re.split(r"(?<=[.!?])\s+", s)
    chunks: list[str] = []
    cur: list[str] = []
    cur_len = 0
    for p in parts:
        if not p:
            continue
        if cur_len + len(p) + 1 > max_chars and cur:
            chunks.append(" ".join(cur).strip())
            cur = [p]
            cur_len = len(p)
        else:
            cur.append(p)
            cur_len += len(p) + 1
    if cur:
        chunks.append(" ".join(cur).strip())
    return "\n\n".join(chunks)


def polish_file(src: Path, dst: Path) -> None:
    lines = src.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    in_reflow = False

    for line in lines:
        stripped = line.strip()

        if stripped in {"## Overview", "### Theory"}:
            in_reflow = True
            out.append(line)
            continue

        if stripped.startswith("## ") or stripped.startswith("### "):
            in_reflow = False
            out.append(line)
            continue

        if in_reflow and stripped and not stripped.startswith("-") and not stripped.startswith("_"):
            out.append(_split_long_paragraph(stripped))
        else:
            out.append(line)

    text = "\n".join(out)
    text = re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"
    dst.write_text(text, encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Apply cleaner, lighter formatting to study-guide markdown"
    )
    ap.add_argument("--in-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(args.in_dir.glob("*.student-notes.md"))
    if not files:
        raise SystemExit(f"No study-guide files found in {args.in_dir}")

    for f in files:
        out = args.out_dir / f.name
        polish_file(f, out)
        print(f"WROTE {out}")


if __name__ == "__main__":
    main()
