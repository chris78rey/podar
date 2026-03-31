#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# =========================================================
# NUEVO SCRIPT: prune_local_mirror_from_oracle.py
# Objetivo:
#   - Consultar Oracle por JDBC en solo lectura
#   - Filtrar DIGITALIZACION por DIG_PLANILLADO / FE_PLA_ANIOMES
#   - Tomar un espejo local descargado por SFTP
#   - Generar una copia podada en otro destino
#   - Preservar el subarbol relativo desde --source-base
# FIN DEL ENCABEZADO NUEVO
# =========================================================

from __future__ import annotations

import argparse
import csv
import os
import shutil
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path

import jaydebeapi


# =========================================================
# INICIO: utilidades de entorno y JDBC
# =========================================================

def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except OSError:
        return


def parse_target(value: str) -> tuple[str, int, str]:
    parts = value.split(":")
    if len(parts) != 3:
        raise argparse.ArgumentTypeError(
            f"Target inválido '{value}'. Formato esperado: host:port:sid"
        )
    host, port_s, sid = parts
    try:
        port = int(port_s)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Puerto inválido en target '{value}'"
        ) from exc
    if not host or not sid:
        raise argparse.ArgumentTypeError(
            f"Target inválido '{value}'"
        )
    return host, port, sid


def jdbc_url(host: str, port: int, sid: str) -> str:
    return f"jdbc:oracle:thin:@{host}:{port}:{sid}"


def connect_with_failover(
    *,
    driver: str,
    jar: Path,
    user: str,
    password: str,
    targets: list[tuple[str, int, str]],
):
    last_exc: BaseException | None = None

    for host, port, sid in targets:
        url = jdbc_url(host, port, sid)
        try:
            conn = jaydebeapi.connect(
                driver,
                url,
                [user, password],
                jars=[str(jar)],
            )
            return conn, (host, port, sid)
        except BaseException as exc:
            last_exc = exc
            continue

    raise RuntimeError("No se pudo conectar a ningún target Oracle") from last_exc


# =========================================================
# FIN: utilidades de entorno y JDBC
# =========================================================


# =========================================================
# INICIO: modelo y consulta Oracle
# =========================================================

@dataclass(frozen=True)
class TramiteRow:
    dig_id: str
    dig_tramite: str
    dig_expediente: str
    fe_pla_aniomes: str
    dig_anio: str
    dig_planillado: str


def clean_component(value: object) -> str:
    s = "" if value is None else str(value)
    s = s.strip()
    s = s.replace("\\", "_").replace("/", "_")
    s = " ".join(s.split())
    return s


def fetch_tramites(
    conn,
    *,
    owner: str,
    table: str,
    dig_planillado: str,
    fe_pla_aniomes: str,
    expediente: str | None,
    id_generacion: str | None,
    limit: int,
) -> list[TramiteRow]:
    where = [
        "TRIM(NVL(DIG_PLANILLADO, 'N')) = TRIM(?)",
        "TRIM(FE_PLA_ANIOMES) = TRIM(?)",
    ]
    params: list[object] = [dig_planillado, fe_pla_aniomes]

    if expediente:
        where.append("TRIM(DIG_EXPEDIENTE) = TRIM(?)")
        params.append(expediente)

    if id_generacion:
        where.append("TO_CHAR(DIG_ID_GENERACION) = TO_CHAR(?)")
        params.append(id_generacion)

    sql = f"""
        SELECT
            TO_CHAR(DIG_ID) AS DIG_ID,
            TRIM(TO_CHAR(DIG_TRAMITE)) AS DIG_TRAMITE,
            TRIM(DIG_EXPEDIENTE) AS DIG_EXPEDIENTE,
            TRIM(FE_PLA_ANIOMES) AS FE_PLA_ANIOMES,
            TRIM(NVL(DIG_ANIO, SUBSTR(FE_PLA_ANIOMES, 1, 4))) AS DIG_ANIO,
            TRIM(NVL(DIG_PLANILLADO, 'N')) AS DIG_PLANILLADO
        FROM {owner}.{table}
        WHERE {" AND ".join(where)}
        ORDER BY TRIM(DIG_EXPEDIENTE), TRIM(TO_CHAR(DIG_TRAMITE))
    """

    cur = conn.cursor()
    cur.execute(sql, params)

    rows: list[TramiteRow] = []
    seen: set[tuple[str, str, str]] = set()

    for raw in cur.fetchall():
        row = TramiteRow(
            dig_id=clean_component(raw[0]),
            dig_tramite=clean_component(raw[1]),
            dig_expediente=clean_component(raw[2]),
            fe_pla_aniomes=clean_component(raw[3]),
            dig_anio=clean_component(raw[4]),
            dig_planillado=clean_component(raw[5]),
        )

        if not row.dig_tramite or not row.dig_expediente:
            continue

        key = (row.dig_anio, row.dig_expediente, row.dig_tramite)
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)

        if limit > 0 and len(rows) >= limit:
            break

    return rows


# =========================================================
# FIN: modelo y consulta Oracle
# =========================================================


# =========================================================
# INICIO: copia podada local
# =========================================================

def safe_resolve(path: Path) -> Path:
    return path.expanduser().resolve()


def ensure_under_base(base: Path, candidate: Path) -> bool:
    try:
        base_r = base.resolve()
        cand_r = candidate.resolve()
        return cand_r == base_r or base_r in cand_r.parents
    except OSError:
        return False


def build_source_path(source_base: Path, row: TramiteRow) -> Path:
    return source_base / row.dig_anio / row.dig_expediente / row.dig_tramite


def build_dest_path(dest_base: Path, row: TramiteRow) -> Path:
    return dest_base / row.dig_anio / row.dig_expediente / row.dig_tramite


def count_files(folder: Path) -> int:
    total = 0
    try:
        for item in folder.rglob("*"):
            if item.is_file():
                total += 1
    except OSError:
        return total
    return total


def copy_tramite_tree(
    *,
    source_base: Path,
    dest_base: Path,
    row: TramiteRow,
    dry_run: bool,
) -> dict[str, object]:
    src = build_source_path(source_base, row)
    dst = build_dest_path(dest_base, row)

    result: dict[str, object] = {
        "dig_id": row.dig_id,
        "dig_tramite": row.dig_tramite,
        "dig_expediente": row.dig_expediente,
        "fe_pla_aniomes": row.fe_pla_aniomes,
        "dig_anio": row.dig_anio,
        "source_path": str(src),
        "dest_path": str(dst),
        "status": "",
        "files_found": 0,
    }

    if not ensure_under_base(source_base, src):
        result["status"] = "INVALID_SOURCE_OUTSIDE_BASE"
        return result

    if not src.exists() or not src.is_dir():
        result["status"] = "MISSING_SOURCE"
        return result

    result["files_found"] = count_files(src)

    if dry_run:
        result["status"] = "WOULD_COPY"
        return result

    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst, dirs_exist_ok=True, copy_function=shutil.copy2)
    result["status"] = "COPIED"
    return result


def write_manifest(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "dig_id",
                "dig_tramite",
                "dig_expediente",
                "fe_pla_aniomes",
                "dig_anio",
                "source_path",
                "dest_path",
                "status",
                "files_found",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


# =========================================================
# FIN: copia podada local
# =========================================================


# =========================================================
# INICIO: main
# =========================================================

def main(argv: list[str]) -> int:
    load_dotenv(Path(".env"))

    parser = argparse.ArgumentParser(
        description="Genera una copia podada local desde un espejo SFTP, filtrando por Oracle."
    )
    parser.add_argument("--source-base", required=True, help="Base local ya descargada por SFTP. Ej: /mnt/copia_servidor/data/datos")
    parser.add_argument("--dest-base", required=True, help="Destino para la copia podada. Ej: /mnt/podado_202602")
    parser.add_argument("--fe-pla-aniomes", required=True, help="Periodo YYYYMM. Ej: 202602")
    parser.add_argument("--dig-planillado", default="S", help="Valor de DIG_PLANILLADO. Default: S")
    parser.add_argument("--expediente", default="", help="Filtro opcional de expediente. Ej: CEX02")
    parser.add_argument("--dig-id-generacion", default="", help="Filtro opcional por DIG_ID_GENERACION")
    parser.add_argument("--limit", type=int, default=0, help="Limitar cantidad de trámites (0=todos)")
    parser.add_argument("--dry-run", action="store_true", help="Solo diagnostica, no copia")
    parser.add_argument("--manifest-csv", default="", help="Ruta del manifiesto CSV")
    parser.add_argument("--jar", default=os.environ.get("ORACLE_JDBC_JAR", "jdbc/ojdbc8 copy.jar"))
    parser.add_argument("--user", default=os.environ.get("ORACLE_USER", "DIGITALIZACION"))
    parser.add_argument("--password", default=os.environ.get("ORACLE_PASSWORD", ""))
    parser.add_argument("--targets", default=os.environ.get("ORACLE_TARGETS", ""))
    parser.add_argument("--owner", default=os.environ.get("ORACLE_OWNER", "DIGITALIZACION"))
    parser.add_argument("--source-table", default=os.environ.get("ORACLE_SOURCE_TABLE", "DIGITALIZACION"))
    args = parser.parse_args(argv)

    source_base = safe_resolve(Path(args.source_base))
    dest_base = safe_resolve(Path(args.dest_base))

    if source_base == dest_base:
        print("ERROR: --source-base y --dest-base no pueden ser la misma ruta", file=sys.stderr)
        return 2

    if not source_base.exists() or not source_base.is_dir():
        print(f"ERROR: source-base inválido: {source_base}", file=sys.stderr)
        return 2

    jar = safe_resolve(Path(args.jar))
    if not jar.exists():
        print(f"ERROR: no existe el JDBC jar: {jar}", file=sys.stderr)
        return 2

    if not args.password:
        print("ERROR: falta ORACLE_PASSWORD", file=sys.stderr)
        return 2

    raw_targets = [x.strip() for x in str(args.targets).split(",") if x.strip()]
    if not raw_targets:
        print("ERROR: falta ORACLE_TARGETS", file=sys.stderr)
        return 2

    targets = [parse_target(x) for x in raw_targets]
    driver = "oracle.jdbc.OracleDriver"

    manifest_csv = (
        safe_resolve(Path(args.manifest_csv))
        if str(args.manifest_csv).strip()
        else dest_base.parent / f"{dest_base.name}_manifest.csv"
    )

    conn = None
    try:
        conn, target = connect_with_failover(
            driver=driver,
            jar=jar,
            user=args.user,
            password=args.password,
            targets=targets,
        )
        print(f"OK Oracle conectado a {target[0]}:{target[1]}:{target[2]}")

        tramites = fetch_tramites(
            conn,
            owner=args.owner,
            table=args.source_table,
            dig_planillado=args.dig_planillado,
            fe_pla_aniomes=args.fe_pla_aniomes,
            expediente=(args.expediente or "").strip() or None,
            id_generacion=(args.dig_id_generacion or "").strip() or None,
            limit=int(args.limit or 0),
        )

        if not tramites:
            print("Sin trámites para el filtro indicado.")
            return 0

        if not args.dry_run:
            dest_base.mkdir(parents=True, exist_ok=True)

        results: list[dict[str, object]] = []
        copied = 0
        missing = 0
        invalid = 0

        for row in tramites:
            result = copy_tramite_tree(
                source_base=source_base,
                dest_base=dest_base,
                row=row,
                dry_run=args.dry_run,
            )
            results.append(result)

            status = str(result["status"])
            if status in {"COPIED", "WOULD_COPY"}:
                copied += 1
            elif status == "MISSING_SOURCE":
                missing += 1
            else:
                invalid += 1

        write_manifest(manifest_csv, results)

        print("========================================")
        print(f"source_base : {source_base}")
        print(f"dest_base   : {dest_base}")
        print(f"periodo     : {args.fe_pla_aniomes}")
        print(f"planillado  : {args.dig_planillado}")
        print(f"tramites    : {len(tramites)}")
        print(f"ok          : {copied}")
        print(f"missing     : {missing}")
        print(f"invalid     : {invalid}")
        print(f"manifest    : {manifest_csv}")
        print("========================================")

        return 0

    except Exception:
        traceback.print_exc()
        return 1
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


# =========================================================
# FIN: main
# =========================================================

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
