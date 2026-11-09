# Teaching & courses — project plan

## Authority and repository boundary

This is the whole-project direction and scope index for **Teaching & courses**. It is hosted in `michaelgold/videoskill`, the project's mapped production-support repository. Hosting this index here does **not** make the video-skill-extractor library the whole teaching product, a course platform, or a podcast service.

[README.md](README.md) documents the component's installation and usage. [BACKLOG.md](BACKLOG.md) remains its historical engineering backlog; [IMPLEMENTATION_REFS.md](IMPLEMENTATION_REFS.md) and [v2-research.md](v2-research.md) contain implementation references and research directions. This index takes precedence for whole-project scope and commitments, without replacing those component documents or adopting their sprint language, priorities, metrics, or proposed features as teaching commitments.

Direction reconciled on 2026-11-09. Implementation inspection below is pinned to [`6ad658cf775679f5a765580fc4e5a0d9aaa06cd5`](https://github.com/michaelgold/videoskill/tree/6ad658cf775679f5a765580fc4e5a0d9aaa06cd5); it is source inspection, not a fresh production acceptance run.

## Confirmed direction

- Teach people to hack and innovate with AI.
- Reuse lectures as shorter lessons, notes, and course material.
- Explore a podcast that breaks down papers, implements them, and includes conversations with their authors.

These are goals, not evidence of a launched course, a produced podcast, or a completed lecture-reuse workflow. Teaching and online courses remain exploratory paths; no first course, learner audience, syllabus, delivery format, or teaching engagement is selected by this plan.

## Shared support, distinct activities

Teaching, online courses, and the exploratory podcast can use the same production-support tools without becoming a single committed offering. The new podcast concept is distinct from any separate guest appearance. Historical class material is context, not an active course assignment or automatic enrollment of its repository into this project.

The Physical AI and Robotics LinkedIn group supports the podcast flow. The exact mix of topics, guests, and audience remains open; no acquisition or distribution mechanics are selected here. TechDrinkUp is separate: this plan does not authorize cross-promotion, event programming, or community outreach.

## Existing component capabilities and limits

Source inspection identifies:

| Area | Present in the repository | Boundary |
| --- | --- | --- |
| Transcription | [OpenAI-compatible Whisper client](src/video_skill_extractor/transcribe.py) and `transcribe` command | Requires configured providers and input media; no lecture was uploaded or processed for this reconciliation. |
| Transcript and step processing | [CLI](src/video_skill_extractor/cli.py), parsing/chunking, step extraction and postprocessing modules | Structured intermediate artifacts are not a finished lesson or validated curriculum. |
| Visual support | [Frame extraction](src/video_skill_extractor/frames.py), [clip extraction](src/video_skill_extractor/clips.py), and [enrichment](src/video_skill_extractor/enrich.py) | Extraction/enrichment code is not evidence of editorially accepted short lessons or a complete podcast pipeline. |
| Written outputs | [Markdown rendering](src/video_skill_extractor/render.py), [student-note script](scripts/generate_student_notes.py), and [two-pass study-guide script](scripts/generate_studyguide_topics_2pass.py) | Script presence does not certify educational quality or establish a dedicated syllabus generator. |

No dedicated podcast audio-production pipeline or course-syllabus generator was identified in this inspected source. Chapter generation, ranked short selection, text packs, course orchestration, and OTIO/editor handoff are described in the historical backlog, not verified delivered by their appearance there. Robotics and timeline research in the component documents is not a separate teaching commitment.

The existing tests and `make verify` describe component quality checks. This documentation update does not claim fresh provider, media-processing, educational, or publishing acceptance.

## Proposals, not adopted commitments

A video-first pilot, a practical workshop, and reusing one research topic across both have been suggested. **No pilot-plus-workshop experiment has been adopted.** These options do not select a topic, audience, duration, group size, author/guest, publishing format, or cadence.

The component backlog's proposed course-repurposing outputs may support the lecture-reuse goal if separately selected and verified. They are not an approved implementation sequence for the whole project.

## Decisions still open

- First learner audience and course or research topic.
- Whether to pursue a course, a podcast experiment, another teaching format, or a combination first.
- Which lecture material may be reused, with appropriate rights and participant permissions.
- Delivery and publishing format, editorial acceptance criteria, and the role of author conversations.
- The LinkedIn group's precise contribution to podcast topics, guests, or audience.
- Any budget, pricing, schedule, cadence, teaching engagement, or launch decision.

No dates, budget, revenue expectation, audience demand, or production readiness are established here. Confirming direction does not resolve these choices.

## Change and execution boundaries

This reconciliation publishes a plan only. It does not authorize lecture processing or upload, syllabus or course creation, podcast production, content publishing, outreach, events, spending, or commitments to learners or authors. Those require separately selected scope and permission.

Keep private relationship records, contact details, source recordings, student information, internal operational evidence, and credentials out of this public repository. A future approved production run must verify input rights, provider handling, output accuracy, and intended publication permissions rather than treating this plan as consent.

Downstream plan copies should reproduce this committed document with its exact source URL and commit. A successful synchronization proves source fidelity, not that an exploratory offering has launched or that component capabilities passed runtime acceptance.
