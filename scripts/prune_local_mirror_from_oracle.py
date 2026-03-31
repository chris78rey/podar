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
from datetime import datetime, timezone
import os
import shutil
import sys
import traceback
from zipfile import ZIP_DEFLATED, ZipFile
from dataclasses import dataclass
from pathlib import Path

import jaydebeapi

try:
    from .oracle_defaults import (
        DEFAULT_ORACLE_JDBC_JAR,
        DEFAULT_ORACLE_OWNER,
        DEFAULT_ORACLE_SOURCE_TABLE,
        DEFAULT_ORACLE_TARGETS,
        DEFAULT_ORACLE_USER,
    )
    from .jvm_utils import app_root, resolve_app_path, start_jvm
except ImportError:  # pragma: no cover - direct script execution fallback
    from oracle_defaults import (
        DEFAULT_ORACLE_JDBC_JAR,
        DEFAULT_ORACLE_OWNER,
        DEFAULT_ORACLE_SOURCE_TABLE,
        DEFAULT_ORACLE_TARGETS,
        DEFAULT_ORACLE_USER,
    )
    from jvm_utils import app_root, resolve_app_path, start_jvm


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


def _mask_secret(value: str | None) -> str:
    if not value:
        return "<vacia>"
    return f"<cargada:{len(value)} chars>"


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
    start_jvm([str(jar)])
    last_exc: BaseException | None = None

    for host, port, sid in targets:
        url = jdbc_url(host, port, sid)
        print(f"Probando {url} con usuario={user} y clave={_mask_secret(password)}...")
        try:
            conn = jaydebeapi.connect(
                driver,
                url,
                [user, password],
                jars=[str(jar)],
            )
            return conn, (host, port, sid)
        except BaseException as exc:
            print(f"Fallo en {host}:{port}:{sid} ({type(exc).__name__}): {exc}")
            last_exc = exc
            continue

    if last_exc is not None:
        raise RuntimeError(f"No se pudo conectar a ningún target Oracle. Ultimo error: {type(last_exc).__name__}: {last_exc}") from last_exc
    raise RuntimeError("No se pudo conectar a ningún target Oracle")


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
    id_generacion: str | None,
    limit: int,
) -> list[TramiteRow]:
    where = [
        "TRIM(NVL(DIG_PLANILLADO, 'N')) = TRIM(?)",
        "TRIM(FE_PLA_ANIOMES) = TRIM(?)",
    ]
    params: list[object] = [dig_planillado, fe_pla_aniomes]

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
    return dest_base / row.dig_tramite


def count_files(folder: Path) -> int:
    total = 0
    try:
        for item in folder.rglob("*"):
            if item.is_file():
                total += 1
    except OSError:
        return total
    return total


def list_pdfs(folder: Path) -> list[Path]:
    pdfs: list[Path] = []
    try:
        for item in folder.rglob("*"):
            if item.is_file() and item.suffix.lower() == ".pdf":
                pdfs.append(item)
    except OSError:
        return pdfs
    return pdfs


def flattened_pdf_name(src: Path) -> str:
    return src.name


def unique_dest_path(folder: Path, filename: str) -> Path:
    candidate = folder / filename
    if not candidate.exists():
        return candidate

    stem = Path(filename).stem
    suffix = Path(filename).suffix
    index = 2
    while True:
        alt = folder / f"{stem}_{index}{suffix}"
        if not alt.exists():
            return alt
        index += 1


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
    pdfs = list_pdfs(src)
    result["pdfs_found"] = len(pdfs)

    if not pdfs:
        result["pdfs_copied"] = 0
        result["status"] = "NO_PDFS" if not dry_run else "WOULD_SKIP_NO_PDFS"
        return result

    if dry_run:
        result["status"] = "WOULD_FLATTEN_PDFS"
        return result

    dst.mkdir(parents=True, exist_ok=True)
    copied = 0
    for pdf in pdfs:
        rel_name = flattened_pdf_name(pdf)
        target = unique_dest_path(dst, rel_name)
        shutil.copy2(pdf, target)
        copied += 1

    result["pdfs_copied"] = copied
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
                "pdfs_found",
                "pdfs_copied",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _xml_escape(value: object) -> str:
    text = "" if value is None else str(value)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _excel_col_name(index: int) -> str:
    name = ""
    while index:
        index, rem = divmod(index - 1, 26)
        name = chr(65 + rem) + name
    return name


def _worksheet_xml(rows: list[list[object]]) -> str:
    parts = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
        "<sheetData>",
    ]
    for row_idx, row in enumerate(rows, start=1):
        parts.append(f'<row r="{row_idx}">')
        for col_idx, value in enumerate(row, start=1):
            ref = f"{_excel_col_name(col_idx)}{row_idx}"
            if isinstance(value, bool):
                parts.append(f'<c r="{ref}" t="inlineStr"><is><t>{_xml_escape(value)}</t></is></c>')
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                parts.append(f'<c r="{ref}" t="n"><v>{value}</v></c>')
            else:
                parts.append(f'<c r="{ref}" t="inlineStr"><is><t>{_xml_escape(value)}</t></is></c>')
        parts.append("</row>")
    parts.append("</sheetData></worksheet>")
    return "".join(parts)


def write_excel_report(path: Path, summary: dict[str, object], detail_rows: list[dict[str, object]]) -> None:
    summary_rows = [["Campo", "Valor"]]
    for key, value in summary.items():
        summary_rows.append([key, value])

    expediente_totals: dict[str, dict[str, object]] = {}
    for row in detail_rows:
        expediente = str(row.get("dig_expediente", ""))
        bucket = expediente_totals.setdefault(
            expediente,
            {
                "dig_expediente": expediente,
                "tramites": 0,
                "pdfs_found": 0,
                "pdfs_copied": 0,
            },
        )
        bucket["tramites"] = int(bucket["tramites"]) + 1
        bucket["pdfs_found"] = int(bucket["pdfs_found"]) + int(row.get("pdfs_found", 0) or 0)
        bucket["pdfs_copied"] = int(bucket["pdfs_copied"]) + int(row.get("pdfs_copied", 0) or 0)

    detail_headers = [
        "dig_id",
        "dig_expediente",
        "dig_tramite",
        "fe_pla_aniomes",
        "dig_anio",
        "source_path",
        "dest_path",
        "status",
        "files_found",
        "pdfs_found",
        "pdfs_copied",
    ]
    detail_table = [detail_headers]
    for row in detail_rows:
        detail_table.append([row.get(h, "") for h in detail_headers])

    expediente_headers = ["dig_expediente", "tramites", "pdfs_found", "pdfs_copied"]
    expediente_table = [expediente_headers]
    for expediente, bucket in sorted(
        expediente_totals.items(),
        key=lambda item: (-int(item[1]["tramites"]), item[0]),
    ):
        expediente_table.append([bucket.get(h, "") for h in expediente_headers])

    path.parent.mkdir(parents=True, exist_ok=True)

    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/worksheets/sheet3.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>
"""
    root_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>
"""
    workbook_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="Resumen" sheetId="1" r:id="rId1"/>
    <sheet name="Detalle" sheetId="2" r:id="rId2"/>
    <sheet name="Expedientes" sheetId="3" r:id="rId3"/>
  </sheets>
</workbook>
"""
    workbook_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet3.xml"/>
  <Relationship Id="rId4" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>
"""
    styles_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>
  <fills count="1"><fill><patternFill patternType="none"/></fill></fills>
  <borders count="1"><border/></borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>
</styleSheet>
"""

    with ZipFile(path, "w", compression=ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", root_rels)
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        zf.writestr("xl/styles.xml", styles_xml)
        zf.writestr("xl/worksheets/sheet1.xml", _worksheet_xml(summary_rows))
        zf.writestr("xl/worksheets/sheet2.xml", _worksheet_xml(detail_table))
        zf.writestr("xl/worksheets/sheet3.xml", _worksheet_xml(expediente_table))


# =========================================================
# FIN: copia podada local
# =========================================================


# =========================================================
# INICIO: main
# =========================================================

def main(argv: list[str]) -> int:
    load_dotenv(app_root() / ".env")

    parser = argparse.ArgumentParser(
        description="Genera una copia podada local desde un espejo SFTP, filtrando por Oracle."
    )
    parser.add_argument("--source-base", required=True, help="Base local ya descargada por SFTP. Ej: /mnt/copia_servidor/data/datos")
    parser.add_argument("--dest-base", required=True, help="Destino para la copia podada. Ej: /mnt/podado_202602")
    parser.add_argument("--fe-pla-aniomes", required=True, help="Periodo YYYYMM. Ej: 202602")
    parser.add_argument("--dig-planillado", default="S", help="Valor de DIG_PLANILLADO. Default: S")
    parser.add_argument("--dig-id-generacion", required=True, help="Filtro por DIG_ID_GENERACION")
    parser.add_argument(
        "--numero-tramite-issfa",
        "--carpeta-salida",
        "--output-folder",
        dest="output_folder_name",
        default="",
        help="Nombre de la carpeta de salida. Si se omite, usa el ID de generacion",
    )
    parser.add_argument("--limit", type=int, default=0, help="Limitar cantidad de trámites (0=todos)")
    parser.add_argument("--dry-run", action="store_true", help="Solo diagnostica, no copia")
    parser.add_argument("--manifest-csv", default="", help="Ruta del manifiesto CSV")
    parser.add_argument("--jar", default=os.environ.get("ORACLE_JDBC_JAR", DEFAULT_ORACLE_JDBC_JAR))
    parser.add_argument("--user", default=os.environ.get("ORACLE_USER", DEFAULT_ORACLE_USER))
    parser.add_argument("--password", default=os.environ.get("ORACLE_PASSWORD", ""))
    parser.add_argument("--targets", default=os.environ.get("ORACLE_TARGETS", DEFAULT_ORACLE_TARGETS))
    parser.add_argument("--owner", default=os.environ.get("ORACLE_OWNER", DEFAULT_ORACLE_OWNER))
    parser.add_argument("--source-table", default=os.environ.get("ORACLE_SOURCE_TABLE", DEFAULT_ORACLE_SOURCE_TABLE))
    args = parser.parse_args(argv)

    source_base = safe_resolve(Path(args.source_base))
    dest_base = safe_resolve(Path(args.dest_base))
    generation_id = str(args.dig_id_generacion).strip()
    if not generation_id:
        print("ERROR: falta DIG_ID_GENERACION", file=sys.stderr)
        return 2

    output_folder_name = str(args.output_folder_name).strip() or generation_id
    final_dest_base = dest_base / output_folder_name

    if source_base == final_dest_base:
        print("ERROR: --source-base y el destino final no pueden ser la misma ruta", file=sys.stderr)
        return 2

    if not source_base.exists() or not source_base.is_dir():
        print(f"ERROR: source-base inválido: {source_base}", file=sys.stderr)
        return 2

    jar = resolve_app_path(args.jar)
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

    print(f"Archivo .env: {resolve_app_path('.env')}")
    print(f"JDBC jar: {jar}")
    print(f"Usuario Oracle: {args.user}")
    print(f"Clave Oracle: {_mask_secret(args.password)}")
    print(f"Targets Oracle: {args.targets}")
    print(f"Target count: {len(targets)}")

    manifest_csv = (
        safe_resolve(Path(args.manifest_csv))
        if str(args.manifest_csv).strip()
        else dest_base / f"{output_folder_name}_manifest.csv"
    )
    report_xlsx = dest_base / f"{output_folder_name}_detalle.xlsx"

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
            id_generacion=generation_id,
            limit=int(args.limit or 0),
        )

        if not tramites:
            print("Sin trámites para el filtro indicado.")
            return 0

        if not args.dry_run:
            final_dest_base.mkdir(parents=True, exist_ok=True)

        results: list[dict[str, object]] = []
        copied = 0
        missing = 0
        invalid = 0
        no_pdfs = 0

        for row in tramites:
            result = copy_tramite_tree(
                source_base=source_base,
                dest_base=final_dest_base,
                row=row,
                dry_run=args.dry_run,
            )
            results.append(result)

            status = str(result["status"])
            if status == "COPIED" or status.startswith("WOULD_"):
                copied += 1
            elif status == "MISSING_SOURCE":
                missing += 1
            elif status in {"NO_PDFS", "WOULD_SKIP_NO_PDFS"}:
                no_pdfs += 1
            else:
                invalid += 1

        write_manifest(manifest_csv, results)
        write_excel_report(
            report_xlsx,
            summary={
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "generation_id": generation_id,
                "output_folder_name": output_folder_name,
                "periodo": args.fe_pla_aniomes,
                "planillado": args.dig_planillado,
                "source_base": str(source_base),
                "dest_base": str(final_dest_base),
                "tramites": len(tramites),
                "ok": copied,
                "missing": missing,
                "no_pdfs": no_pdfs,
                "invalid": invalid,
                "manifest_csv": str(manifest_csv),
            },
            detail_rows=results,
        )

        print("========================================")
        print(f"source_base : {source_base}")
        print(f"dest_base   : {final_dest_base}")
        print(f"generation  : {generation_id}")
        print(f"periodo     : {args.fe_pla_aniomes}")
        print(f"planillado  : {args.dig_planillado}")
        print(f"tramites    : {len(tramites)}")
        print(f"ok          : {copied}")
        print(f"missing     : {missing}")
        print(f"invalid     : {invalid}")
        print(f"manifest    : {manifest_csv}")
        print(f"report_xlsx : {report_xlsx}")
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
