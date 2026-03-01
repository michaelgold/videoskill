## Executive summary (≤10 bullets)

1. **Use OTIO as the *edit-decision spine* (clips/gaps/tracks/markers/metadata), not as an effects container.** Resolve 18.5+ can import/export `.otio` and `.otioz` timelines via *File → Import/Export → Timeline*. ([Blackmagic Design Documents][1])
2. **Ship two deliverables every time:** (a) **portable OTIO** timeline with rich, namespaced metadata + markers, and (b) a **Resolve “materializer” script** that instantiates editable Fusion Titles/Generators from that metadata (because OTIO round-trip won’t reliably preserve Resolve/Fusion effect graphs). *(Inference based on OTIO scope + common adapter limitations; see confirmed OTIO scope below.)* ([Read the Docs][2])
3. **Prefer `.otio` for collaborative editorial** (small, relink to shared media) and **`.otioz` for “it just opens” pilots/demos** (bundles timeline + full media; can be huge). Resolve unzips `.otioz` media next to the bundle and auto-links. ([Blackmagic Design Documents][1])
4. **Make everything editable by design:** overlays/callouts are **Fusion Title templates (Macros)** with exposed controls; animation is parameterized and keyframe-ready in the Inspector. *(Confirmed Fusion scripting exists; template strategy is recommended.)* ([Blackmagic Design Documents][3])
5. **Deterministic templates handle “core” instructional graphics** (lower-thirds, step callouts, arrows, highlights, progress bars). Generative AI is constrained to **non-critical decorative assets** (icons, background plates, b-roll style images) with strict brand tokens + QC gates. *(Recommendation.)*
6. **Second-pass transcript distillation produces a “textpack” per step** (headline + 2–4 bullets + emphasis keywords + on-screen constraints), aligned to the enriched step timing and evidence. *(Recommendation.)*
7. **Adopt a namespaced metadata convention in OTIO** so Resolve scripting can materialize graphics deterministically and auditable (template_id + params + links to generated assets). *(Recommendation; conventions below.)*
8. **MVP in 2–4 weeks:** generate OTIO with cut structure + markers + metadata; in Resolve, run a script to insert Fusion Titles at marker ranges and bind parameters. *(Recommendation; scripting entry points exist.)* ([electron-rotoscope][4])
9. **V2:** smarter lane/track placement, collision avoidance, automatic safe-area layout, confidence-based styling, optional `.otioz` bundling for handoff. *(Recommendation.)*
10. **Pilot “go/no-go” is about import fidelity + editorial trust**, not model cleverness: measure how often editors keep vs delete auto-elements, and how often timing/text is adjusted.

---

## Recommended architecture diagram (text)

```
[Enriched step JSONL]
   |  (timing, evidence, signals, confidence)
   v
[Edit Intelligence Layer - Python]
   - step normalization + windowing
   - transcript distillation -> TextPack
   - template selection + param assembly
   - asset generation requests (optional AI) -> QC
   |
   +--> [Asset Store]
   |      - icons/plates/stills
   |      - template registry (Fusion Title macros)
   |
   v
[EditPlan + AssetManifest  (JSON)]
   |
   v
[OTIO Builder - Python (OpenTimelineIO)]
   - tracks: V1 base video, A1 audio
   - overlay intent lanes: V2 "GUIDES", V3 "GFX"
   - markers + metadata bindings (namespaced)
   - exports: .otio (default) and/or .otioz (pilot)
   |
   v
[DaVinci Resolve 18.5+]
   1) Import OTIO timeline (.otio/.otioz)
   2) Run "Materializer" script (Python)
        - reads OTIO markers/clip metadata
        - inserts Fusion Titles/Generators into timeline
        - sets parameters + creates keyframes
        - organizes bins, tracks, colors, flags
   |
   v
[Human editorial]
   - tweak text, timing, easing, layout
   - replace AI b-roll plates as needed
   - final grade/audio/mix/delivery
```

---

## 1) OTIO + DaVinci Resolve practical interoperability (confirmed vs inferred)

### Confirmed facts (sources)

* Resolve 18.5 introduced **import/export support for OpenTimelineIO** `.otio` and `.otioz`. ([Blackmagic Design Documents][1])
* `.otio` is **timeline metadata only**; `.otioz` **bundles timeline + media** and can be very large; Resolve unzips media next to the bundle and auto-links. ([Blackmagic Design Documents][1])
* OTIO is designed to represent **cuts, timing, tracks, transitions, markers, metadata** and references external media (it’s not itself a media container). ([Read the Docs][2])
* OTIOZ bundling expects locally accessible external references and can error when media isn’t locally referenced. ([opentimelineio.readthedocs.io][5])

### Practical implications (inferred recommendations)

* **What will round-trip cleanly in Resolve via OTIO:** cut order, clip timing, track structure, and basic markers/metadata are the safest bets. (OTIO’s core scope supports these; Resolve advertises this level of support.) ([Read the Docs][2])
* **What is risky/likely lossy:** anything Resolve-specific (Fusion node graphs, OFX params, advanced transitions, speed effects) because OTIO is not a native container for editor effect semantics and even OTIO’s own ecosystem treats “effects” as an area of ongoing discussion/limitations. ([GitHub][6])
* Therefore: **treat OTIO as “intent + timing,” then materialize Resolve-native editable elements via scripting.**

---

## OTIO vs OTIOZ tradeoffs and handoff practices

* **Use `.otio`** when:

  * Editors already have shared media (NAS/cloud sync).
  * You want small diffs in version control.
  * You expect frequent iteration / relinking. ([Blackmagic Design Documents][1])

* **Use `.otioz`** when:

  * You need “open-and-see” reproducibility for pilots, vendors, or stakeholders.
  * You’re archiving a specific cut + exact referenced media.
  * You can tolerate large bundles. ([Blackmagic Design Documents][1])

**Best practice handoff (recommended):**
Ship `.otio` **plus** a separate `asset_manifest.json` (and optionally a lightweight “proxy media pack”) so you don’t force full-res media into `.otioz` unless necessary.

---

## 2) Template architecture for animation generation (Resolve/Fusion)

### Recommended pattern (deterministic + editable)

**Template Registry (stable IDs)**

* `lower_third.v1`
* `step_callout_box.v2`
* `arrow_pointer.v1`
* `highlight_circle.v1`
* `progress_bar.v1`

Each template:

* Is a **Fusion Title Macro** (or Title) with:

  * Exposed controls: text fields, colors, layout, in/out animation style, safe-area padding, anchor point.
  * Default keyframable parameters.
  * Optional “Auto” modes (e.g., auto-size box to text). ([Blackmagic Design Documents][3])

**Instantiation in Resolve (scripting)**

* Resolve scripting APIs can insert titles / Fusion titles / generators into the timeline. ([electron-rotoscope][4])
* Resolve scripting can export/import OTIO as well (useful for automated roundtrip pipelines). ([Blackmagic Design Forum][7])

*(Exact parameter-setting APIs vary by Resolve version and object model; plan for a small “capability probe” script in MVP to discover which properties are settable in your target Resolve build.)*

### Keeping outputs editable

* Never bake overlays into the base video in MVP.
* Prefer **one graphic per timeline item** (so editors can move/trim/delete).
* Place generated graphics on dedicated tracks:

  * `V2: GUIDES` (optional, can be disabled)
  * `V3: GFX` (actual titles/callouts)
* Add **human-readable marker notes** that match the template binding so editors understand intent even if the script fails.

---

## 3) AI-assisted asset generation (safe use vs deterministic)

### Recommended division of labor

* **Deterministic templates (always):**

  * Typography systems (lower-thirds, captions/callouts)
  * Core instructional callouts (step boxes, arrows, highlights)
  * Brand motion language (easing, durations, entry/exit)
* **Constrained AI (optional, gated):**

  * Small **icons** that match a limited style set
  * Background plates / subtle textures
  * B-roll style stills when you *don’t* have licensed footage
  * Motion accents *as pre-approved template variants* (not freeform graphs)

### Latency / consistency / QC

* Use AI asynchronously *within the pipeline run* but **never block timeline generation**:

  * Generate OTIO + deterministic elements immediately.
  * Attach AI assets if they pass QC; otherwise fall back to a default library.
* QC gates (recommended):

  * Style-token compliance (palette, font pairing, no weird artifacts)
  * Content safety filters (brand/legal)
  * Similarity check vs existing approved icon set (avoid drift)

### Style token system (recommended)

A single JSON “brand token” document:

* Fonts (family, weights), sizes, line-height
* Color roles (primary, accent, warning, success)
* Safe-area margins, shadow/outline rules
* Motion presets (ease, durations, overshoot allowed?)
* Confidence mapping (e.g., low confidence → dotted outline + “Check” label)

---

## 4) Second-pass transcript distillation for motion text

### Output: “TextPack” per step (recommendation)

For each step:

* `headline` (≤ 42 chars recommended)
* `bullets` (2–4 bullets, each ≤ 52 chars)
* `emphasis_keywords` (1–4 tokens to bold/animate)
* `on_screen_constraints` (safe area, max lines, reading time)
* `spoken_alignment` (optional: word-time ranges)

### Alignment method (recommended)

1. **Clip the transcript** to the step window (plus small padding).
2. Use enriched “signal fields” and “visual evidence” to bias what’s on screen:

   * If evidence indicates “before/after change,” headline becomes the change.
   * If event detected (“click menu”), bullets become click path.
3. Enforce reading-time constraints:

   * Ensure total characters fit within `(duration_seconds × CPS)`; pick CPS ~ 12–15 for instructional overlays.
4. If confidence is low, generate a conservative textpack (“Review this step”) rather than assert specifics.

---

## 5) Data model & schema recommendations

### Namespaced OTIO metadata conventions (recommended)

Use a stable namespace, e.g. `com.yourorg.edit`:

* `com.yourorg.edit.step_id`
* `com.yourorg.edit.template_id`
* `com.yourorg.edit.template_params` (JSON-encoded dict)
* `com.yourorg.edit.textpack_ref` (pointer into external JSON)
* `com.yourorg.edit.asset_refs` (list of asset IDs)
* `com.yourorg.edit.confidence`
* `com.yourorg.edit.qc_status` (`pass|warn|fail`)
* `com.yourorg.edit.intent` (`callout|lowerthird|highlight|guide`)

### Schema: `editplan.json` (example)

```json
{
  "version": "1.0",
  "project": {"id": "proj_123", "frame_rate": "30/1"},
  "steps": [
    {
      "step_id": "step_001",
      "source_media": {"asset_id": "camA", "timebase": "30/1"},
      "window": {"start_s": 12.40, "end_s": 21.90, "handles_s": 0.40},
      "signals": {"event": "click", "change_detected": true, "confidence": 0.86},
      "textpack_id": "tp_step_001",
      "overlays": [
        {
          "overlay_id": "ov_001",
          "template_id": "step_callout_box.v2",
          "range_s": {"in": 13.20, "out": 20.80},
          "params": {
            "headline": "@textpack.headline",
            "bullets": "@textpack.bullets",
            "anchor": "top_left",
            "accent_role": "primary",
            "motion_preset": "pop_soft"
          }
        }
      ]
    }
  ]
}
```

### Schema: `textpack.json` (example)

```json
{
  "version": "1.0",
  "textpacks": [
    {
      "textpack_id": "tp_step_001",
      "headline": "Select the main hero",
      "bullets": ["Open Character panel", "Choose “Silver”", "Confirm selection"],
      "emphasis_keywords": ["Silver", "Character"],
      "constraints": {"max_lines": 5, "max_chars": 180, "reading_cps": 13},
      "provenance": {"model": "llm_x", "prompt_hash": "abc123", "qc": "pass"}
    }
  ]
}
```

### Schema: `asset_manifest.json` (example)

```json
{
  "version": "1.0",
  "assets": [
    {
      "asset_id": "camA",
      "type": "video",
      "uri": "media/camA.mp4",
      "hash": "sha256:...",
      "role": "source"
    },
    {
      "asset_id": "icon_click",
      "type": "image",
      "uri": "assets/icons/click.png",
      "role": "overlay_support",
      "license": {"type": "owned_or_generated", "notes": "AI-generated, reviewed"}
    }
  ],
  "template_registry": [
    {"template_id": "step_callout_box.v2", "resolve_title_name": "DM_StepCallout_v2"}
  ]
}
```

---

## 6) Detailed comparison tables

### A) OTIO capabilities vs Resolve behavior (practical)

| OTIO concept                    | In OTIO spec/ecosystem                                                                 | Resolve 18.5+ behavior                                                        | Notes                                                    |
| ------------------------------- | -------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- | -------------------------------------------------------- |
| Clips + timing                  | Core OTIO purpose ([PyPI][8])                                                          | Imports/exports via `.otio/.otioz` ([Blackmagic Design Documents][1])         | Safest interoperability surface                          |
| Tracks                          | Supported in OTIO ([Read the Docs][2])                                                 | Imports/exports timelines ([Blackmagic Design Documents][1])                  | Track semantics can vary across apps *(inferred)*        |
| Markers                         | Supported in OTIO ([Read the Docs][2])                                                 | Likely preserved; used in marketing claims ([Post Magazine][9])               | Use markers as “materialization anchors” *(recommended)* |
| Transitions                     | Supported in OTIO ([Read the Docs][2])                                                 | May import basic transitions; fidelity varies *(inferred)*                    | Prefer minimal transitions in MVP                        |
| Effects / Fusion graphs         | OTIO “effects” are not a universal interchange focus; ongoing discussion ([GitHub][6]) | Resolve-specific effects unlikely to roundtrip via OTIO *(inferred)*          | Use Resolve scripting to instantiate                     |
| Media bundling                  | OTIOZ/OTIOD supported ([opentimelineio.readthedocs.io][10])                            | Resolve unzips `.otioz` and auto-links ([Blackmagic Design Documents][1])     | `.otioz` can be huge                                     |
| External reference requirements | OTIOZ expects local external refs ([opentimelineio.readthedocs.io][5])                 | `.otio` may require relink if paths differ ([Blackmagic Design Documents][1]) | Prefer relative paths + manifest                         |

### B) Template approaches (recommended)

| Approach                                 | Pros                                            | Cons                                         | Best use                                             |
| ---------------------------------------- | ----------------------------------------------- | -------------------------------------------- | ---------------------------------------------------- |
| Fusion Title Macros (param exposed)      | Most editable; brand-consistent; keyframe-ready | Needs template installation/versioning       | Core instructional callouts, lower-thirds            |
| OFX Generators                           | Standardized in Resolve ecosystem               | Harder to fully customize than Fusion graphs | Simple backgrounds, shapes                           |
| Pre-rendered overlays (video with alpha) | Guaranteed look                                 | Not editable; heavy media                    | Only for “accent” elements, never core text          |
| Fully AI-generated motion graphics       | Fast variation                                  | Inconsistent, risky, hard to edit            | Avoid for MVP; allow only as optional “plate” assets |

### C) AI asset generation options (recommended)

| Asset type              |          AI okay? | Deterministic preferred? | QC must-have                            |
| ----------------------- | ----------------: | -----------------------: | --------------------------------------- |
| Icons                   | Yes (constrained) |                Sometimes | style token compliance + artifact check |
| Background plates       | Yes (constrained) |                Sometimes | brand palette + content safety          |
| Step callout typography |                No |                      Yes | font/spacing/legibility                 |
| Motion curves/easing    |     No (freeform) |                      Yes | consistent motion language              |
| Highlight shapes/arrows |                No |                      Yes | spatial accuracy                        |

---

## 7) Reference implementation plan (Python-first)

### MVP (2–4 weeks): minimal but useful

**Goal:** “Professional starting point” timeline + editable graphics with deterministic behavior.

1. **Python: build OTIO timeline**

   * Parse enriched step JSONL → `editplan`.
   * Construct OTIO `Timeline` with:

     * V1: source cut
     * V2: optional guide clips (slugs) for step ranges
     * Markers at step start + overlay in/out ranges with namespaced metadata.
   * Export `.otio`. Optionally export `.otioz` for demos. ([Blackmagic Design Documents][1])

2. **Resolve: materializer script (Python)**

   * Reads the active timeline and scans markers/metadata.
   * For each overlay instruction:

     * `InsertFusionTitleIntoTimeline(titleName)` using `template_registry`.
     * Set clip name/color, basic parameters (where supported), and leave keyframe handles ready.
   * Organize bins: `Generated_GFX`, `AI_Assets`, `Source`.
   * (If parameter setting is limited in your target Resolve build, store params as clip metadata + add a note for editors; still useful.)

   Scripting capability references exist for inserting Fusion titles/generators. ([electron-rotoscope][4])

3. **Template pack v1**

   * 3–5 Fusion Title Macros: `LowerThird`, `StepCallout`, `Arrow`, `HighlightBox`, `ProgressBar`.
   * Expose controls; ship with versioned IDs.

### V2 (higher-quality automation)

* Collision avoidance (don’t cover UI hotspots) using visual evidence boxes.
* Confidence-driven styling and “review needed” flags.
* Better textpack generation (reading time, punctuation, emphasis animation rules).
* Partial `.otioz` bundling (proxies only) + per-asset licensing metadata.
* Round-trip testing harness: import/export OTIO in Resolve and diff critical invariants.

**Toolchain suggestions (Python):**

* `opentimelineio` (core), `pydantic` (schemas), `ffmpeg`/`ffprobe` (media probing), `rapidjson` or `orjson` (fast JSONL), `pytest` (golden timeline tests). ([PyPI][8])

---

## 8) Suggested evaluation metrics / KPIs (editorial-quality first)

**Import & structural fidelity**

* % timelines that import without relink errors
* Marker count preserved / expected
* Step timing error (|expected - actual| in frames)

**Editorial acceptance**

* Keep rate: % autogenerated overlays retained in final cut
* Edit rate: average number of manual edits per overlay (text/timing/position)
* Delete rate by template type

**Readability & pacing**

* On-screen text CPS distribution (target band compliance)
* Overlay overlap/collision rate (two overlays competing in same region/time)

**Trust & safety**

* Hallucination flags per minute (claims not supported by evidence/signals)
* Licensing compliance rate (all third-party assets have license metadata)

---

## 9) Risk register (with mitigations)

### Technical

* **OTIO import fidelity varies by feature** (effects/transitions/retimes).
  *Mitigation:* keep MVP to cuts + markers + deterministic materialization; maintain a “feature whitelist.” ([GitHub][6])
* **Media relinking/path issues** across machines.
  *Mitigation:* asset manifest + relative paths; prefer `.otioz` only when needed. ([Blackmagic Design Documents][1])
* **Inconsistent timing from upstream step detection**.
  *Mitigation:* snap to edit-friendly boundaries (nearest frame), add handles, confidence-based warnings.

### Legal / licensing

* **Third-party templates/macros** may have restrictive licenses.
  *Mitigation:* ship your own template pack; store template source control + license headers.
* **AI-generated assets** may introduce IP/style imitation concerns.
  *Mitigation:* constrain to internal style tokens; log prompts/hashes; human QC + allow opt-out.

### Operational

* **Render farm cost/latency** if you start pre-rendering many elements.
  *Mitigation:* keep overlays editable, render only at final; use proxy workflows early.
* **Editor trust** (overlays that are “almost right” cost more than none).
  *Mitigation:* conservative generation; explicit confidence; “review needed” tags; measure keep/delete.

---

## Go / No-Go checklist for pilot launch

**Go if all are true:**

* Resolve imports `.otio` reliably for your test set and preserves clip timing within **±1 frame**.
* Materializer script successfully instantiates at least **3 core templates** (LowerThird, StepCallout, Highlight) on **≥90%** of steps.
* Editors report **net time saved** (e.g., ≥20% reduction in first-pass setup time).
* Hallucination / unsupported-claim rate is acceptably low (you define threshold; e.g., **<1 per 10 minutes** and clearly flagged).
* Asset licensing metadata is complete for all non-source assets.

**No-Go if any are true:**

* Frequent relink failures (paths) or broken timelines across machines.
* Editors delete most overlays (>60%) due to clutter/wrong intent.
* Timing is systematically off (step boundaries unreliable).
* You cannot keep template pack versioning stable across machines/projects.

---

### Confirmed facts vs inferred recommendations (how to read this)

* Anything tied to Resolve 18.5 OTIO import/export, `.otio` vs `.otioz`, and OTIOZ bundling constraints is **confirmed** by Blackmagic/OTIO docs. ([Blackmagic Design Documents][1])
* The “two-stage” strategy (OTIO intent → Resolve script materialization) and most template/AI/textpack design is **inferred + recommended** based on OTIO’s scope and typical NLE interchange realities, plus the lack of a universal OTIO-to-Resolve-effects interchange guarantee. ([Read the Docs][2])

If you want, I can also provide a concrete OTIO-building pseudocode sketch (Python OTIO objects + marker metadata layout) and a starter Resolve materializer script structure aligned to the schemas above.

[1]: https://documents.blackmagicdesign.com/SupportNotes/DaVinci_Resolve_18.5_New_Features_Guide.pdf?_v=1681801210000&utm_source=chatgpt.com "DaVinci Resolve 18.5 Beta New Features Guide"
[2]: https://readthedocs.org/projects/opentimelineio-deb/downloads/pdf/latest/?utm_source=chatgpt.com "OpenTimelineIO Documentation"
[3]: https://documents.blackmagicdesign.com/UserManuals/Fusion8_Scripting_Guide.pdf?utm_source=chatgpt.com "SCRIPTING GUIDE AND REFERENCE MANUAL February ..."
[4]: https://electron-rotoscope.github.io/DaVinciResolve-API-Docs/?utm_source=chatgpt.com "Unofficial DaVinci Resolve Scripting Documentation"
[5]: https://opentimelineio.readthedocs.io/en/v0.15/api/python/opentimelineio.adapters.otioz.html?utm_source=chatgpt.com "opentimelineio.adapters.otioz - Read the Docs"
[6]: https://github.com/AcademySoftwareFoundation/OpenTimelineIO/discussions/921?utm_source=chatgpt.com "Effects in OTIO #921"
[7]: https://forum.blackmagicdesign.com/viewtopic.php?p=982991&t=175315&utm_source=chatgpt.com "Creating Scripts for DaVinci Resolve - Blackmagic Forum • View topic"
[8]: https://pypi.org/project/OpenTimelineIO/0.16.0/?utm_source=chatgpt.com "OpenTimelineIO"
[9]: https://www.postmagazine.com/Press-Center/Daily-News/2023/DaVinci-Resolve-18-5-adds-AI-tools-more.aspx?utm_source=chatgpt.com "DaVinci Resolve 18.5 adds AI tools & more"
[10]: https://opentimelineio.readthedocs.io/en/latest/tutorials/otio-filebundles.html?utm_source=chatgpt.com "File Bundles — OpenTimelineIO 0.19.0.dev1 documentation"
