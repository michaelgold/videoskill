from __future__ import annotations

import json
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def render_markdown(steps: list[dict], title: str = "Lesson Steps") -> str:
    lines: list[str] = [f"# {title}", "", f"Generated steps: {len(steps)}", ""]
    for idx, s in enumerate(steps, start=1):
        lines.append(f"## Step {idx}: {s.get('instruction_text','(missing)')}")
        lines.append("")
        lines.append(f"- **Step ID:** `{s.get('step_id','')}`")
        lines.append(f"- **Intent:** {s.get('intent','')}")
        lines.append(f"- **Expected outcome:** {s.get('expected_outcome','')}")
        lines.append(
            f"- **Timecode:** `{s.get('start_s',0)}s → {s.get('end_s',0)}s` "
            f"(clip `{s.get('clip_start_s',0)}s → {s.get('clip_end_s',0)}s`)"
        )
        enrich = s.get("enrichment", {})
        sampling = enrich.get("sampling", {})
        if sampling:
            lines.append(
                f"- **Sampling:** {sampling.get('count','?')} frames; "
                f"rationale: {sampling.get('rationale','')}"
            )
        vlm = enrich.get("vlm_judgement", {})
        if vlm:
            lines.append(f"- **VLM judgement:** {vlm.get('summary','')}")
            lines.append(f"- **VLM confidence:** {vlm.get('confidence','')} ")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_markdown(content: str, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")
