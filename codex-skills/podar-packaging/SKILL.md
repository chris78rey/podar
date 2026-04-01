---
name: podar-packaging
description: Build, bundle, and debug the PODA Windows distributable. Use when packaging the Oracle pruning app, making the installer portable, bundling the Java runtime, or troubleshooting connectivity on another machine.
---

# PODA Packaging

Use this skill when building, releasing, or debugging the distributable PODA app for Windows.

## Read First

1. Read [references/lessons-learned.md](references/lessons-learned.md).
2. If you need the current workflow or folder conventions, read the `podar-memory` skill.

## Core Rules

- Prefer the bundled `jre` generated with `jlink`. Do not rely on system Java on the target machine.
- Keep `DIG_ID_GENERACION` as the Oracle filter.
- Keep the ISSFA tramite number separate as the output folder name.
- Keep Oracle defaults visible except for `ORACLE_PASSWORD`.

## Build Flow

1. Run `build_windows.ps1`.
2. Verify the build produces:
   - `dist\PODA\PODA.exe`
   - `dist\PODA\jre`
   - `installer_output\PODA_Setup.exe`
3. Test Oracle with `scripts/test_oracle.py`.
4. If portability matters, validate on a clean machine or a VM without system Java.

## Debug Flow

- If Oracle fails on another PC, check:
  - `.env` in `%APPDATA%\PODA\.env`
  - bundled `dist\PODA\jre`
  - `jdbc\ojdbc8.jar`
  - `ORACLE_TARGETS`
- If JPype cannot find classes, confirm the bundled JRE is being used.
- If the installer works only on the build machine, assume the runtime is missing from the package until proven otherwise.

