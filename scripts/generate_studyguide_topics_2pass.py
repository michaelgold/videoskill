from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from video_skill_extractor.ai_adapter import run_structured
from video_skill_extractor.settings import AppConfig


@dataclass
class StepRow:
    step_id: str
    start_s: float
    end_s: float
    instruction: str
    summary: str
    confidence: float
    review_flag: bool


class TopicListModel(BaseModel):
    title: str
    lecture_overview: str
    prerequisites: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)


class TopicSectionModel(BaseModel):
    objective: str
    steps: list[str] = Field(default_factory=list)
    summary: str


def ts(seconds: float) -> str:
    s = max(0, int(round(float(seconds))))
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    return f"{h:02d}:{m:02d}:{sec:02d}"


def load_rows(path: Path) -> list[StepRow]:
    rows: list[StepRow] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        e = r.get("enrichment", {})
        j = e.get("vlm_judgement", {})
        rows.append(
            StepRow(
                step_id=str(r.get("step_id", "")),
                start_s=float(r.get("start_s", 0.0)),
                end_s=float(r.get("end_s", 0.0)),
                instruction=str(r.get("instruction_text", "")).strip(),
                summary=str(j.get("summary", "")).strip(),
                confidence=float(j.get("confidence", 0.0) or 0.0),
                review_flag=bool(e.get("review_flag", False)),
            )
        )
    return rows


def filter_rows(rows: list[StepRow], max_steps: int = 180, min_conf: float = 0.75) -> list[StepRow]:
    out = [r for r in rows if (not r.review_flag and r.instruction and r.confidence >= min_conf)]
    if len(out) > max_steps:
        stride = len(out) / max_steps
        sampled = []
        i = 0.0
        while len(sampled) < max_steps and int(i) < len(out):
            sampled.append(out[int(i)])
            i += stride
        out = sampled
    return out


def steps_text(rows: list[StepRow], max_items: int | None = None) -> str:
    parts = []
    use_rows = rows[:max_items] if max_items is not None else rows
    for i, r in enumerate(use_rows, 1):
        parts.append(f"{i}. [{ts(r.start_s)}–{ts(r.end_s)}] {r.instruction} | {r.summary}")
    return "\n".join(parts)


def truncate_chars(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars]


def render_markdown(
    title: str, overview: str, prereqs: list[str], topics: list[tuple[str, TopicSectionModel]]
) -> str:
    lines = [f"# {title}", ""]
    if prereqs:
        lines.append("## Prerequisites")
        for p in prereqs:
            lines.append(f"- {p}")
        lines.append("")

    lines.append("## Overview")
    lines.append(overview.strip())
    lines.append("")

    for idx, (topic_name, sec) in enumerate(topics, 1):
        lines.append(f"## Topic {idx}: {topic_name}")
        lines.append("")
        lines.append("### Objective")
        lines.append(sec.objective.strip())
        lines.append("")
        lines.append("### Steps")
        for step in sec.steps:
            lines.append(f"- {step}")
        lines.append("")
        lines.append("### Summary")
        lines.append(sec.summary.strip())
        lines.append("")

    lines.append(f"_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}_")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("config.json"))
    parser.add_argument(
        "--pattern",
        default="gen-ai-01-12-2026.wordtimed.w120.o15.steps.enriched.normalized.aligned.calibrated.jsonl",
    )
    parser.add_argument(
        "--out-dir", type=Path, default=Path("datasets/demo/lecture_notes_studyguide_2pass")
    )
    parser.add_argument("--max-steps", type=int, default=180)
    parser.add_argument("--topic-list-max-items", type=int, default=70)
    parser.add_argument("--topic-detail-max-items", type=int, default=40)
    parser.add_argument("--topic-list-max-chars", type=int, default=14000)
    parser.add_argument("--topic-detail-max-chars", type=int, default=7000)
    args = parser.parse_args()

    cfg = AppConfig.load(args.config)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(Path("datasets/demo").glob(args.pattern))
    if not files:
        raise SystemExit("No matching files")

    for p in files:
        lecture = p.name.replace(
            ".wordtimed.w120.o15.steps.enriched.normalized.aligned.calibrated.jsonl", ""
        )
        rows = filter_rows(load_rows(p), max_steps=args.max_steps)
        if not rows:
            raise RuntimeError(f"No filtered rows for {lecture}")

        src_topic_list = truncate_chars(
            steps_text(rows, max_items=args.topic_list_max_items),
            args.topic_list_max_chars,
        )

        topic_list_prompt = (
            f"Lecture: {lecture}\n"
            "From the source steps, produce 3-5 major topic names for a student study guide. "
            "Use direct teaching voice, no audit language.\n\n"
            f"Source steps:\n{src_topic_list}"
        )
        topic_list = run_structured(
            cfg.reasoning,
            system_prompt="Return structured topic list for a student study guide.",
            user_prompt=topic_list_prompt,
            result_type=TopicListModel,
            max_retries=4,
        )

        topics: list[tuple[str, TopicSectionModel]] = []
        src_topic_detail = truncate_chars(
            steps_text(rows, max_items=args.topic_detail_max_items),
            args.topic_detail_max_chars,
        )
        for t in topic_list.topics[:5]:
            prompt = (
                f"Lecture: {lecture}\n"
                f"Topic: {t}\n"
                "Generate study-guide content for this topic only. "
                "Must be direct teaching voice, no observer/evidence wording.\n"
                "Return exactly: objective, steps, summary.\n"
                "Keep steps concise and actionable."
                f"\n\nSource steps:\n{src_topic_detail}"
            )
            sec = run_structured(
                cfg.reasoning,
                system_prompt="Return strict topic section content for student study guide.",
                user_prompt=prompt,
                result_type=TopicSectionModel,
                max_retries=4,
            )
            if not sec.objective.strip() or not sec.steps or not sec.summary.strip():
                raise RuntimeError(
                    "Topic section incomplete (required objective/steps/summary) "
                    f"for {lecture}: {t}"
                )
            topics.append((t, sec))

        if not topics:
            raise RuntimeError(f"No topics generated for {lecture}")

        md = render_markdown(
            topic_list.title or f"{lecture} — Study Guide",
            topic_list.lecture_overview,
            topic_list.prerequisites,
            topics,
        )

        out = args.out_dir / f"{lecture}.student-notes.md"
        out.write_text(md, encoding="utf-8")
        print(f"WROTE {out} topics={len(topics)}")


if __name__ == "__main__":
    main()
