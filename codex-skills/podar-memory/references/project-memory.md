# Podar Project Memory

## Snapshot

- Repo: `C:\codexprojects\podar`
- Purpose: prune a local SFTP mirror using Oracle filters and generate an audit trail.
- Main filter: `DIG_ID_GENERACION`
- Output folder name: the ISSFA tramite number supplied separately by the user
- Required period filter: `FE_PLA_ANIOMES`

## Current Output Rules

- Destination root is selected by the user.
- Final output path is `dest-base/<NUMERO_TRAMITE_ISSFA>/`.
- Each tramite is copied directly under that output folder.
- PDFs inside tramite subfolders are flattened into the tramite folder.
- Keep the original PDF filename.
- If a filename already exists, append `_2`, `_3`, etc.
- Tramites with no PDFs are not copied and are reported as `NO_PDFS`.

## Reports

- CSV manifest: `dest-base/<NUMERO_TRAMITE_ISSFA>_manifest.csv`
- Excel report: `dest-base/<NUMERO_TRAMITE_ISSFA>_detalle.xlsx`
- Excel sheets:
  - `Resumen`
  - `Detalle`
  - `Expedientes`
- `Expedientes` is ordered by tramite count descending.

## GUI

- Launcher: `run_gui.ps1` and `run_gui.bat`
- GUI file: `scripts/gui_launcher_app.py`
- GUI inputs:
  - Source base
  - Destination base parent
  - `FE_PLA_ANIOMES`
  - `DIG_PLANILLADO`
  - `DIG_ID_GENERACION` (Oracle filter)
  - `Numero de tramite ISSFA / carpeta de salida`
  - Oracle user, password, targets, JDBC jar, owner, and source table are visible in the GUI; only the password is masked.

## Oracle / Runtime

- Oracle connection uses `scripts/test_oracle.py` and `scripts/prune_local_mirror_from_oracle.py`
- JDBC driver path comes from `.env`
- JVM startup is centralized in `scripts/jvm_utils.py`
- `ojdbc8.jar` lives in `jdbc/`
- Oracle diagnostics print the resolved `.env` path, JDBC jar, user, targets, and whether the password is loaded, but do not expose the password in plain text.
- The installer creates `%APPDATA%\PODA\.env` with visible Oracle defaults and a blank password; the current default target is `172.16.60.21:1521:PRDSGH2`. Packaged builds look there first, then next to the executable, then in the frozen bundle/dev repo.
- The GUI has a `Guardar config` action that writes Oracle settings back to `%APPDATA%\PODA\.env`, so `ORACLE_TARGETS` can be updated without reinstalling.
- Packaged builds include a bundled `jre` generated with `jlink` so the app does not rely on system Java on the target machine.

## OrganizaPlanillas

- New Excel-driven organizer: `scripts/organiza_planillas.py`
- GUI: `scripts/organiza_planillas_app.py`
- Launchers: `run_organiza_planillas.ps1` and `run_organiza_planillas.bat`
- Build: `build_organiza_planillas.ps1`
- Input Excel columns: `dig_id`, `dig_anio`, `dig_expediente`, `dig_id_tramite`, `dig_tramite`
- Output layout: `dest-base/dig_anio/dig_expediente[/dig_id_tramite]/dig_tramite`
- `dig_id_tramite` is optional in the output when the user selects omit mode or the cell is blank
- The app reads source folders locally, flattens PDFs into the final tramite folder, and generates CSV + Excel reports
- Excel parsing uses `openpyxl`
- The GUI can process the full Excel or filter down to a single `dig_id_tramite`
- If one `dig_id_tramite` appears in multiple expedientes, use the highest expediente number for the destination path across all rows of that `dig_id_tramite`
- Installer build: `build_organiza_planillas_installer.ps1`
- Installer definition: `installer/OrganizaPlanillas.iss`

## Current Example Paths

- Source mirror example: `C:\Users\Administrador\Desktop\leti`
- Destination example: `C:\Users\Administrador\Desktop\destino`
- Example generation: `122369`

## Notes

- The project has been validated with direct Oracle connectivity.
- The current workflow uses `DIG_ID_GENERACION` as the Oracle filter and a separate ISSFA tramite number for the output folder, not expediente-first.
- If the workflow changes, update this file immediately.
