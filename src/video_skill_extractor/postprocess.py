from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from video_skill_extractor.models import TranscriptSegment


def read_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def write_jsonl_rows(rows: list[dict[str, Any]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def _clean_list(values: list[Any] | None) -> list[str]:
    if not values:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for v in values:
        txt = str(v).strip()
        low = txt.lower()
        if not txt or low in {"yes", "none", "n/a", "na", "null", "unknown"}:
            continue
        if low in seen:
            continue
        seen.add(low)
        out.append(txt)
    return out


def _normalize_text(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def normalize_steps(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        r = dict(row)
        enrich = dict(r.get("enrichment", {}))
        judge = dict(enrich.get("vlm_judgement", {}))
        signal = dict(enrich.get("signal_pass", {}) or {})

        # clean list-like signal fields
        for key in [
            "detected_events",
            "observations",
            "before_observations",
            "after_observations",
            "changes_detected",
            "unchanged_signals",
        ]:
            signal[key] = _clean_list(signal.get(key))

        # confidence downweight for explicit weak evidence
        summary = str(judge.get("summary", ""))
        low_summary = summary.lower()
        if any(t in low_summary for t in ["no evidence", "unable to", "not visible", "unclear"]):
            try:
                judge["confidence"] = min(float(judge.get("confidence", 0.0)), 0.35)
            except Exception:
                judge["confidence"] = 0.35

        enrich["signal_pass"] = signal
        enrich["vlm_judgement"] = judge
        r["enrichment"] = enrich

        # simple adjacent dedupe
        if normalized:
            prev = normalized[-1]
            prev_text = _normalize_text(str(prev.get("instruction_text", "")))
            curr_text = _normalize_text(str(r.get("instruction_text", "")))
            same_instruction = prev_text == curr_text
            try:
                close = float(r.get("start_s", 0.0)) - float(prev.get("end_s", 0.0)) <= 1.0
            except Exception:
                close = False
            if same_instruction and close:
                # keep earlier, stretch end if needed
                prev["end_s"] = max(float(prev.get("end_s", 0.0)), float(r.get("end_s", 0.0)))
                prev["clip_end_s"] = max(
                    float(prev.get("clip_end_s", 0.0)),
                    float(r.get("clip_end_s", 0.0)),
                )
                continue

        normalized.append(r)

    return normalized


def align_steps_with_transcript(
    rows: list[dict[str, Any]],
    segments: list[TranscriptSegment],
    snippet_count: int = 2,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        r = dict(row)
        start = float(r.get("start_s", 0.0))
        end = float(r.get("end_s", 0.0))

        overlaps: list[TranscriptSegment] = [
            s for s in segments if not (s.end_s < start or s.start_s > end)
        ]
        seg_ids = [s.segment_id for s in overlaps]
        snippets = [s.text.strip() for s in overlaps if s.text.strip()][:snippet_count]
        span_start = min((s.start_s for s in overlaps), default=start)
        span_end = max((s.end_s for s in overlaps), default=end)

        if end <= start:
            conf = 0.0
        else:
            overlap_dur = max(0.0, min(end, span_end) - max(start, span_start)) if overlaps else 0.0
            conf = max(0.0, min(1.0, overlap_dur / (end - start)))

        r["transcript_support"] = {
            "segment_ids": seg_ids,
            "start_s": span_start,
            "end_s": span_end,
            "quoted_snippets": snippets,
            "alignment_confidence": round(conf, 3),
        }
        out.append(r)

    return out



def calibrate_steps(
    rows: list[dict[str, Any]],
    weak_conf_cap: float = 0.25,
    weak_alignment_threshold: float = 0.4,
) -> list[dict[str, Any]]:
    calibrated: list[dict[str, Any]] = []
    weak_tokens = [
        "no evidence",
        "not visible",
        "unable to",
        "unclear",
        "cannot determine",
    ]

    for row in rows:
        r = dict(row)
        enrich = dict(r.get("enrichment", {}))
        judge = dict(enrich.get("vlm_judgement", {}))
        signal = dict(enrich.get("signal_pass", {}) or {})
        support = dict(r.get("transcript_support", {}) or {})

        summary = str(judge.get("summary", ""))
        low_summary = summary.lower()

        try:
            conf = float(judge.get("confidence", 0.0))
        except Exception:
            conf = 0.0

        try:
            align_conf = float(support.get("alignment_confidence", 0.0))
        except Exception:
            align_conf = 0.0

        evidence_strength = "high"
        review_reasons: list[str] = []

        if any(tok in low_summary for tok in weak_tokens):
            conf = min(conf, weak_conf_cap)
            evidence_strength = "low"
            review_reasons.append("weak_visual_evidence")

        changes = [str(x).strip().lower() for x in (signal.get("changes_detected") or [])]
        if not changes or changes == ["no changes"]:
            signal["changes_detected"] = []
            if evidence_strength != "low":
                evidence_strength = "medium"
            review_reasons.append("no_actionable_changes")

        if align_conf < weak_alignment_threshold:
            conf = min(conf, 0.35)
            review_reasons.append("low_transcript_alignment")
            if evidence_strength == "high":
                evidence_strength = "medium"

        judge["confidence"] = round(max(0.0, min(1.0, conf)), 3)
        enrich["vlm_judgement"] = judge
        enrich["signal_pass"] = signal
        enrich["evidence_strength"] = evidence_strength
        enrich["review_flag"] = bool(review_reasons)
        enrich["review_reasons"] = review_reasons
        r["enrichment"] = enrich
        calibrated.append(r)

    return calibrated
