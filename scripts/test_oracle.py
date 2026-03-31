import os
import traceback
from pathlib import Path

import jaydebeapi

try:
    from .oracle_defaults import (
        DEFAULT_ORACLE_JDBC_JAR,
        DEFAULT_ORACLE_TARGETS,
        DEFAULT_ORACLE_USER,
    )
    from .jvm_utils import resolve_app_path, start_jvm
except ImportError:  # pragma: no cover - direct script execution fallback
    from oracle_defaults import (
        DEFAULT_ORACLE_JDBC_JAR,
        DEFAULT_ORACLE_TARGETS,
        DEFAULT_ORACLE_USER,
    )
    from jvm_utils import resolve_app_path, start_jvm


def load_dotenv(path: Path):
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip().strip('"').strip("'")


def _mask_secret(value: str | None) -> str:
    if not value:
        return "<vacia>"
    return f"<cargada:{len(value)} chars>"


def main():
    env_path = resolve_app_path(".env")
    load_dotenv(env_path)

    jar = resolve_app_path(os.environ.get("ORACLE_JDBC_JAR", DEFAULT_ORACLE_JDBC_JAR))
    user = os.environ.get("ORACLE_USER", DEFAULT_ORACLE_USER)
    password = os.environ.get("ORACLE_PASSWORD", "")
    targets_raw = os.environ.get("ORACLE_TARGETS", DEFAULT_ORACLE_TARGETS)

    missing = []
    if not password:
        missing.append("ORACLE_PASSWORD")
    if not targets_raw:
        missing.append("ORACLE_TARGETS")
    if missing:
        print(f"ERROR: faltan variables Oracle: {', '.join(missing)}")
        print(f"Archivo .env revisado: {env_path}")
        print(f"Defaults visibles: user={DEFAULT_ORACLE_USER}, targets={DEFAULT_ORACLE_TARGETS}, jar={DEFAULT_ORACLE_JDBC_JAR}")
        return 2

    start_jvm([str(jar)])

    print(f"Archivo .env: {env_path}")
    print(f"JDBC jar: {jar}")
    print(f"Usuario Oracle: {user}")
    print(f"Clave Oracle: {_mask_secret(password)}")
    print(f"Targets Oracle: {targets_raw or '<vacios>'}")

    targets = []
    for t in targets_raw.split(","):
        if t.strip():
            h, p, s = t.strip().split(":")
            targets.append((h, int(p), s))

    print(f"Total de targets: {len(targets)}")
    print(f"Intentando conectar como {user}...")

    conn = None
    for host, port, sid in targets:
        url = f"jdbc:oracle:thin:@{host}:{port}:{sid}"
        print(f"Probando {url} con usuario={user} y clave={_mask_secret(password)}...")
        try:
            conn = jaydebeapi.connect("oracle.jdbc.OracleDriver", url, [user, password], jars=[str(jar)])
            print(f"¡CONECTADO EXITOSAMENTE a {host}:{port}:{sid}!")
            curs = conn.cursor()
            curs.execute("SELECT 'Oracle responde correctamente' FROM DUAL")
            print("Prueba de consulta:", curs.fetchone()[0])
            break
        except Exception as e:
            print(f"Fallo en {host}:{port}:{sid} ({type(e).__name__}): {e}")
            traceback.print_exc()

    if conn:
        conn.close()
    else:
        print("NO SE PUDO CONECTAR A NINGÚN NODO.")


if __name__ == "__main__":
    main()
