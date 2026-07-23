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
    evidence_strength: str
    confidence: float
    review_flag: bool


class StudentNotesModel(BaseModel):
    title: str
    lesson_objectives: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    key_takeaways: list[str] = Field(default_factory=list)
    markdown_body: str


class TopicStudyUnit(BaseModel):
    topic_title: str
    theory: str
    definitions: list[str] = Field(default_factory=list)
    practical_examples: list[str] = Field(default_factory=list)
    practice: list[str] = Field(default_factory=list)


class StudyGuideTopicsModel(BaseModel):
    title: str
    lecture_overview: str
    prerequisites: list[str] = Field(default_factory=list)
    topics: list[TopicStudyUnit] = Field(default_factory=list)
    recap: list[str] = Field(default_factory=list)


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
        row = StepRow(
            step_id=str(r.get("step_id", "")),
            start_s=float(r.get("start_s", 0.0)),
            end_s=float(r.get("end_s", 0.0)),
            instruction=str(r.get("instruction_text", "")).strip(),
            summary=str(j.get("summary", "")).strip(),
            evidence_strength=str(e.get("evidence_strength", "unknown")),
            confidence=float(j.get("confidence", 0.0) or 0.0),
            review_flag=bool(e.get("review_flag", False)),
        )
        rows.append(row)
    return rows


NEGATIVE_MARKERS = [
    "no visual evidence",
    "cannot be verified",
    "has not been completed",
    "not completed",
    "not visually confirmed",
    "failed",
    "missing",
    "not yet visible",
    "does not demonstrate",
    "no motion detected",
    "the evidence",
    "visual evidence",
    "verified",
    "detected",
]


def _normalize_text(s: str) -> str:
    return " ".join((s or "").lower().split())


def _is_negative_summary(summary: str) -> bool:
    text = _normalize_text(summary)
    return any(m in text for m in NEGATIVE_MARKERS)


def _dedupe_adjacent(rows: list[StepRow]) -> list[StepRow]:
    deduped: list[StepRow] = []
    last_key: str | None = None
    for r in rows:
        key = _normalize_text(r.instruction)
        if key and key == last_key:
            continue
        deduped.append(r)
        last_key = key
    return deduped


def filter_rows(rows: list[StepRow], min_conf: float = 0.8, max_steps: int = 40) -> list[StepRow]:
    out: list[StepRow] = []
    for r in rows:
        if r.review_flag:
            continue
        if r.evidence_strength == "low":
            continue
        if r.confidence < min_conf:
            continue
        if not r.instruction:
            continue
        if _is_negative_summary(r.summary):
            continue
        out.append(r)

    out = _dedupe_adjacent(out)
    if len(out) > max_steps:
        stride = len(out) / max_steps
        sampled = []
        idx = 0.0
        while len(sampled) < max_steps and int(idx) < len(out):
            sampled.append(out[int(idx)])
            idx += stride
        out = sampled
    return out


def build_prompt(lecture_name: str, rows: list[StepRow], profile: str = "student") -> str:
    if profile == "study-guide":
        guidance = [
            "Create a high-detail study guide for students revising this lecture.",
            "Do not invent tools, commands, or steps. Keep factual content grounded "
            "in source steps.",
            "Keep chronological flow and include explicit conceptual explanations "
            "(why it matters).",
            "Do NOT use verification/evidence/audit language (e.g., 'visual evidence', "
            "'cannot verify', 'detected', 'instruction intent', 'step completed').",
            "Never write in observer voice (avoid phrases like 'the user', "
            "'the learner', 'the screenshot shows').",
            "Write in direct teaching voice to students using second person ('you').",
            "Prefer concept-first structure over per-step adjudication.",
            "In markdown_body, use this exact structure and headings:",
            "## Overview",
            "## Core Concepts",
            "## Guided Workflow",
            "## Common Mistakes and Fixes",
            "## Quick Self-Check",
            "## Recap",
            "Under Guided Workflow, provide concise numbered actions with one-line "
            "why-this-matters notes.",
        ]
    elif profile == "study-guide-topic":
        guidance = [
            "Create a high-detail study guide organized by major lecture topics.",
            "Do not invent tools, commands, or steps. Keep factual content grounded "
            "in source steps.",
            "Split content into 3-6 major topics that reflect distinct concepts "
            "covered in the lecture.",
            "For EACH topic, provide exactly these parts: theory, definitions, "
            "practical examples, practice.",
            "Use direct teaching voice to students; never use observer/evidence language.",
            "Ensure every topic has non-empty content in all four parts.",
        ]
    else:
        guidance = [
            "Create student-friendly lecture notes in clear, concise teaching language.",
            "Do not invent tools, commands, or steps. Keep factual content grounded "
            "in source steps.",
            "Group related micro-steps into coherent chunks.",
            "Focus on practical actions students should perform.",
            "Avoid uncertainty/verification language and avoid repeating equivalent steps.",
            "In markdown_body, use this structure: Overview, Step-by-step Lab, "
            "Troubleshooting Tips, Recap.",
        ]

    lines = [
        f"Lecture: {lecture_name}",
        *guidance,
        "",
        "Source steps:",
    ]
    for i, r in enumerate(rows, 1):
        lines.append(
            f"{i}. [{ts(r.start_s)}–{ts(r.end_s)}] instruction={r.instruction} "
            f"| summary={r.summary}"
        )
    return "\n".join(lines)


def fallback_markdown(lecture_name: str, rows: list[StepRow]) -> str:
    lines = [f"# {lecture_name} — Student Notes", "", "## Step-by-step", ""]
    for i, r in enumerate(rows, 1):
        lines.append(f"### {i}. {r.instruction}")
        lines.append(f"Time: {ts(r.start_s)}–{ts(r.end_s)}")
        if r.summary:
            lines.append(f"Note: {r.summary}")
        lines.append("")
    return "\n".join(lines)


def render_notes(doc: StudentNotesModel, lecture_name: str) -> str:
    lines = [f"# {doc.title or (lecture_name + ' — Student Notes')}", ""]

    if doc.lesson_objectives:
        lines.append("## Learning Objectives")
        for x in doc.lesson_objectives:
            lines.append(f"- {x}")
        lines.append("")

    if doc.prerequisites:
        lines.append("## Prerequisites")
        for x in doc.prerequisites:
            lines.append(f"- {x}")
        lines.append("")

    lines.append("## Lesson Notes")
    lines.append(doc.markdown_body.strip())
    lines.append("")

    if doc.key_takeaways:
        lines.append("## Key Takeaways")
        for x in doc.key_takeaways:
            lines.append(f"- {x}")
        lines.append("")

    lines.append(f"_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}_")
    return "\n".join(lines)


def validate_topic_study_guide(doc: StudyGuideTopicsModel) -> None:
    if not doc.topics:
        raise ValueError("study-guide-topic validation failed: no topics returned")
    for i, t in enumerate(doc.topics, 1):
        if not t.topic_title.strip():
            raise ValueError(f"study-guide-topic validation failed: topic {i} missing title")
        if not t.theory.strip():
            raise ValueError(f"study-guide-topic validation failed: topic {i} missing theory")
        if not t.definitions:
            raise ValueError(f"study-guide-topic validation failed: topic {i} missing definitions")
        if not t.practical_examples:
            raise ValueError(
                f"study-guide-topic validation failed: topic {i} missing practical examples"
            )
        if not t.practice:
            raise ValueError(f"study-guide-topic validation failed: topic {i} missing practice")


def render_topic_study_guide(doc: StudyGuideTopicsModel, lecture_name: str) -> str:
    title = doc.title or f"{lecture_name} — Study Guide"
    lines = [f"# {title}", ""]

    if doc.prerequisites:
        lines.append("## Prerequisites")
        for x in doc.prerequisites:
            lines.append(f"- {x}")
        lines.append("")

    if doc.lecture_overview:
        lines.append("## Overview")
        lines.append(doc.lecture_overview.strip())
        lines.append("")

    for i, topic in enumerate(doc.topics, 1):
        lines.append(f"## Topic {i}: {topic.topic_title}")
        lines.append("")
        lines.append("### Theory")
        lines.append(topic.theory.strip())
        lines.append("")
        lines.append("### Definitions")
        for d in topic.definitions:
            lines.append(f"- {d}")
        lines.append("")
        lines.append("### Practical Examples")
        for ex in topic.practical_examples:
            lines.append(f"- {ex}")
        lines.append("")
        lines.append("### Practice")
        for p in topic.practice:
            lines.append(f"- {p}")
        lines.append("")

    if doc.recap:
        lines.append("## Recap")
        for x in doc.recap:
            lines.append(f"- {x}")
        lines.append("")

    lines.append(f"_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}_")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate student-friendly notes from calibrated lecture JSONLs"
    )
    parser.add_argument("--config", type=Path, default=Path("config.json"))
    parser.add_argument(
        "--pattern",
        default="td-2026-*.wordtimed.w120.o15.steps.enriched.normalized.aligned.calibrated.jsonl",
    )
    parser.add_argument("--out-dir", type=Path, default=Path("datasets/demo/lecture_notes_student"))
    parser.add_argument("--min-conf", type=float, default=0.8)
    parser.add_argument("--max-steps", type=int, default=40)
    parser.add_argument(
        "--profile",
        choices=["student", "study-guide", "study-guide-topic"],
        default="student",
    )
    args = parser.parse_args()

    cfg = AppConfig.load(args.config)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    paths = sorted(Path("datasets/demo").glob(args.pattern))
    if not paths:
        raise SystemExit("No input lecture files matched pattern")

    for path in paths:
        lecture_name = path.name.replace(
            ".wordtimed.w120.o15.steps.enriched.normalized.aligned.calibrated.jsonl", ""
        )
        raw_rows = load_rows(path)
        rows = filter_rows(raw_rows, min_conf=args.min_conf, max_steps=args.max_steps)

        if not rows:
            if args.profile == "study-guide-topic":
                raise RuntimeError(
                    f"study-guide-topic hard fail: no filtered rows for {lecture_name}"
                )
            body = fallback_markdown(lecture_name, raw_rows[:30])
            out = args.out_dir / f"{lecture_name}.student-notes.md"
            out.write_text(body, encoding="utf-8")
            print(f"WROTE {out} (fallback; no filtered rows)")
            continue

        prompt = build_prompt(lecture_name, rows, profile=args.profile)
        system = (
            "You are an expert teaching assistant writing polished student lecture notes. "
            "Return structured output only."
        )

        try:
            if args.profile == "study-guide-topic":
                last_exc: Exception | None = None
                text = ""
                for attempt in range(1, 4):
                    try:
                        doc = run_structured(
                            cfg.reasoning,
                            system_prompt=system,
                            user_prompt=prompt,
                            result_type=StudyGuideTopicsModel,
                            max_retries=4,
                        )
                        validate_topic_study_guide(doc)
                        text = render_topic_study_guide(doc, lecture_name)
                        break
                    except Exception as exc:  # noqa: BLE001
                        last_exc = exc
                if not text:
                    assert last_exc is not None
                    raise RuntimeError(
                        f"study-guide-topic hard fail for {lecture_name}: {last_exc}"
                    ) from last_exc
            else:
                doc = run_structured(
                    cfg.reasoning,
                    system_prompt=system,
                    user_prompt=prompt,
                    result_type=StudentNotesModel,
                    max_retries=4,
                )
                text = render_notes(doc, lecture_name)
        except Exception as exc:  # noqa: BLE001
            if args.profile == "study-guide-topic":
                raise RuntimeError(
                    f"study-guide-topic hard fail for {lecture_name}: {exc}"
                ) from exc
            text = fallback_markdown(lecture_name, rows)
            text = text + f"\n\n> Note: fallback rendering used due to model error: {exc}\n"

        out = args.out_dir / f"{lecture_name}.student-notes.md"
        out.write_text(text, encoding="utf-8")
        print(f"WROTE {out} ({len(rows)} filtered rows)")


if __name__ == "__main__":
    main()
