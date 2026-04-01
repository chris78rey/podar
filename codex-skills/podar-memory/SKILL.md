---
name: podar-memory
description: Remember current podar project context. Use when working on the Oracle pruning repo, resuming a task, or needing the current destination layout, report format, GUI launcher, or PDF-flattening rules.
---

# Podar Memory

Use this skill when working on `C:\codexprojects\podar` and you need the current project state, conventions, or recent decisions before editing code.

## Procedure

1. Read [references/project-memory.md](references/project-memory.md) first.
2. Treat it as the current source of truth for paths, output layout, and report behavior.
3. Keep the code aligned with the memory notes when changing workflow.
4. Update the memory reference when behavior changes.

## Current Conventions

- Filter by `DIG_ID_GENERACION`; `FE_PLA_ANIOMES` stays required.
- Output layout: `dest-base/<NUMERO_TRAMITE_ISSFA>/<TRAMITE>`.
- `DIG_ID_GENERACION` is the Oracle filter; the ISSFA tramite number is the output folder name.
- Flatten PDFs found inside tramite subfolders into the tramite folder.
- Preserve the original PDF filename; add `_2`, `_3`, etc. for duplicates.
- Do not copy tramites with no PDFs; report them as `NO_PDFS`.
- Produce both `*_manifest.csv` and `*_detalle.xlsx`.
- The Excel file contains `Resumen`, `Detalle`, and `Expedientes` sheets.
- The GUI launcher is `run_gui.ps1` / `run_gui.bat`, backed by `scripts/gui_launcher_app.py`.
- Oracle access uses `.env`, `ojdbc8.jar`, and `jvm_utils.start_jvm`.
- Packaged builds prefer the bundled `jre` generated with `jlink` before falling back to system Java.

## When To Refresh Memory

Update the reference after any change to:

- output folder structure
- naming rules
- Oracle filters
- GUI inputs
- report columns or sheets

