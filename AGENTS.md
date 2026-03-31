# Repository Guidelines

## Project Structure & Modules
- `scripts/`: Python utilities for Oracle access and file pruning.
  - `prune_local_mirror_from_oracle.py`: Copies a pruned local mirror based on Oracle filters.
  - `test_oracle.py`: Minimal JDBC connectivity check to Oracle.
- `jdbc/`: JDBC drivers (e.g., `ojdbc8.jar`).
- `.env`: Local config for Oracle and paths (not committed to VCS by default).
- `venv/`: Optional local virtual environment (ignored by Git).

## Build, Test, and Dev Commands
- Install deps: `python -m venv venv && source venv/bin/activate && pip install jaydebeapi`.
- Oracle test: `python scripts/test_oracle.py` — verifies JDBC connectivity using `.env`.
- Prune run (dry): `python scripts/prune_local_mirror_from_oracle.py --source-base /path/src --dest-base /path/dest --fe-pla-aniomes 202602 --dry-run`.
- Prune run (copy): add credentials and remove `--dry-run` to execute copies.

## Coding Style & Naming
- Language: Python 3.11+.
- Style: PEP 8; 4-space indentation; descriptive function/variable names in `snake_case`.
- Modules live under `scripts/`; keep single-responsibility scripts with clear `main()` entrypoints.

## Testing Guidelines
- Framework: ad‑hoc scripts; no pytest configured yet.
- Smoke tests: use `scripts/test_oracle.py` and `--dry-run` mode for copy logic.
- Add new tests as small Python scripts in `scripts/` with self-contained execution.

## Commit & Pull Requests
- Commits: present-tense, concise scope, e.g., "Add Oracle failover connect".
- Include: rationale, impacted scripts, and any `.env` variable changes.
- PRs: describe scenario, sample command lines, expected output, and risks. Attach logs from `--dry-run` and manifest CSV snippets when relevant.

## Security & Configuration
- Secrets: never commit credentials. Use `.env` with keys like `ORACLE_USER`, `ORACLE_PASSWORD`, `ORACLE_TARGETS`, `ORACLE_JDBC_JAR`.
- JDBC: store drivers in `jdbc/`; reference via `.env`.
- Paths: prefer absolute paths; validate sources/destinations are under intended bases.

## Operational Notes
- Manifest: pruning writes a CSV manifest next to `--dest-base` by default.
- Connectivity: targets format `host:port:sid` (comma-separated for failover).
- Large runs: start with `--limit` and `--dry-run` to validate filters.
