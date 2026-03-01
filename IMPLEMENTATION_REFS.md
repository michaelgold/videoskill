# Implementation References (OTIO + DaVinci Resolve)

Curated links from research for building the timeline + materialization pipeline.

## OpenTimelineIO (OTIO)

- OTIO docs (ReadTheDocs):
  - https://readthedocs.org/projects/opentimelineio-deb/downloads/pdf/latest/
- OTIO PyPI package:
  - https://pypi.org/project/OpenTimelineIO/0.16.0/
- OTIO file bundles tutorial (`.otioz` / `.otiod`):
  - https://opentimelineio.readthedocs.io/en/latest/tutorials/otio-filebundles.html
- OTIO `otioz` adapter API docs:
  - https://opentimelineio.readthedocs.io/en/v0.15/api/python/opentimelineio.adapters.otioz.html
- OTIO effects discussion (interchange caveats):
  - https://github.com/AcademySoftwareFoundation/OpenTimelineIO/discussions/921

## DaVinci Resolve / Fusion

- DaVinci Resolve 18.5 new features guide (OTIO import/export support):
  - https://documents.blackmagicdesign.com/SupportNotes/DaVinci_Resolve_18.5_New_Features_Guide.pdf?_v=1681801210000
- Fusion scripting guide and reference (official):
  - https://documents.blackmagicdesign.com/UserManuals/Fusion8_Scripting_Guide.pdf
- Resolve scripting API docs (unofficial mirror, practical reference):
  - https://electron-rotoscope.github.io/DaVinciResolve-API-Docs/
- Blackmagic forum thread on Resolve scripts / OTIO scripting menu:
  - https://forum.blackmagicdesign.com/viewtopic.php?p=982991&t=175315

## Quick Practical Notes

- Treat OTIO as timeline + metadata interchange spine.
- Use Resolve scripting/Fusion templates to materialize editable graphics/effects.
- Prefer `.otio` for iterative workflows; use `.otioz` for bundled handoff demos.
