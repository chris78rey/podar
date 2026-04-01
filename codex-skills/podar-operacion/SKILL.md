---
name: podar-operacion
description: Operate the PODA Windows app as an end user. Use when the user needs quick instructions for opening the GUI, filling the Oracle filter and ISSFA output folder fields, saving config, or running the download.
---

# PODA Operacion

Use this skill for short, user-facing guidance on how to run PODA.

## What The User Needs

- Open the GUI with `run_gui.ps1` or `run_gui.bat`.
- Fill in the source and destination folders.
- Enter `FE_PLA_ANIOMES`.
- Enter the `ID de generacion` to filter Oracle.
- Enter the `Numero de tramite ISSFA / carpeta de salida` for the output folder name.
- Keep `Oracle password` filled in.
- Save config if Oracle settings change.
- Click `Probar Oracle` before `Ejecutar`.

## What The App Does

- Reads Oracle using the saved config.
- Copies the selected generation into the destination folder.
- Creates one folder per tramite.
- Flattens PDFs found inside subfolders.
- Keeps PDF names and adds `_2`, `_3`, etc. if a name repeats.
- Skips tramites without PDFs and marks them in the Excel report.

## Expected Output

- Manifest CSV in the destination root.
- Excel report in the destination root.
- Final copied content under the chosen output folder name.

## Common Guidance

- If Oracle changes, update `Oracle targets` and click `Guardar config`.
- If Oracle fails, click `Probar Oracle` and read the message shown in the GUI.
- If the folder looks empty, check whether the run was a simulation or a real execution.

