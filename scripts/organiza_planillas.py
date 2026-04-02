from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

try:
    from .organiza_planillas_core import (
        copy_planilla_tree,
        build_destination_expediente_map,
        filter_rows_by_dig_id_tramite,
        format_timestamp,
        load_dotenv,
        read_rows_from_excel,
        safe_resolve,
        select_rows_with_highest_expediente,
        SourceFinder,
        summarize_results,
        write_excel_report,
        write_manifest,
    )
except ImportError:  # pragma: no cover - direct script execution fallback
    from organiza_planillas_core import (
        copy_planilla_tree,
        build_destination_expediente_map,
        filter_rows_by_dig_id_tramite,
        format_timestamp,
        load_dotenv,
        read_rows_from_excel,
        safe_resolve,
        select_rows_with_highest_expediente,
        SourceFinder,
        summarize_results,
        write_excel_report,
        write_manifest,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Organiza planillas desde un Excel y copia los PDFs a una estructura ordenada."
    )
    parser.add_argument("--source-base", required=True, help="Base donde estan las carpetas o PDFs sin organizar")
    parser.add_argument("--dest-base", required=True, help="Destino para la estructura organizada")
    parser.add_argument("--excel", required=True, help="Archivo Excel con la metadata de planillas")
    parser.add_argument("--sheet", default="", help="Nombre de la hoja Excel a leer. Por defecto usa la primera")
    parser.add_argument(
        "--dig-id-tramite",
        default="",
        help="Procesar solo las filas cuyo dig_id_tramite coincida con este valor",
    )
    parser.add_argument(
        "--omit-dig-id-tramite",
        "--omit-dig-id-generacion",
        dest="omit_dig_id_tramite",
        action="store_true",
        help="No incluir dig_id_tramite en la ruta de salida",
    )
    parser.add_argument("--limit", type=int, default=0, help="Limitar cantidad de filas procesadas (0=todas)")
    parser.add_argument("--dry-run", action="store_true", help="Solo diagnostica, no copia")
    parser.add_argument("--manifest-csv", default="", help="Ruta del manifiesto CSV")
    parser.add_argument("--report-xlsx", default="", help="Ruta del reporte Excel")
    return parser


def main(argv: list[str]) -> int:
    load_dotenv(Path(".env"))

    parser = build_parser()
    args = parser.parse_args(argv)

    source_base = safe_resolve(Path(args.source_base))
    dest_base = safe_resolve(Path(args.dest_base))
    excel_path = safe_resolve(Path(args.excel))
    include_id_tramite = not bool(args.omit_dig_id_tramite)
    dig_id_tramite_filter = str(args.dig_id_tramite).strip()

    if source_base == dest_base:
        print("ERROR: source-base y dest-base no pueden ser la misma ruta", file=sys.stderr)
        return 2

    if source_base in dest_base.parents:
        print("ERROR: dest-base no puede quedar dentro de source-base", file=sys.stderr)
        return 2

    if not source_base.exists() or not source_base.is_dir():
        print(f"ERROR: source-base invalido: {source_base}", file=sys.stderr)
        return 2

    if not dest_base.exists() and not args.dry_run:
        dest_base.mkdir(parents=True, exist_ok=True)

    if not excel_path.exists() or not excel_path.is_file():
        print(f"ERROR: no existe el archivo Excel: {excel_path}", file=sys.stderr)
        return 2

    manifest_csv = (
        safe_resolve(Path(args.manifest_csv))
        if str(args.manifest_csv).strip()
        else dest_base / "organiza_planillas_manifest.csv"
    )
    report_xlsx = (
        safe_resolve(Path(args.report_xlsx))
        if str(args.report_xlsx).strip()
        else dest_base / "organiza_planillas_detalle.xlsx"
    )

    try:
        rows = read_rows_from_excel(excel_path, sheet_name=str(args.sheet).strip() or None)
    except Exception as exc:
        print(f"ERROR: no se pudo leer el Excel: {exc}", file=sys.stderr)
        return 2

    rows = filter_rows_by_dig_id_tramite(rows, dig_id_tramite_filter)
    rows, discarded_rows = select_rows_with_highest_expediente(rows)

    if int(args.limit or 0) > 0:
        rows = rows[: int(args.limit)]

    destination_expediente_map = build_destination_expediente_map(rows)

    if not rows:
        print("Sin filas para procesar en el Excel.")
        return 0

    print("========================================")
    print(f"timestamp   : {format_timestamp()}")
    print(f"source_base : {source_base}")
    print(f"dest_base   : {dest_base}")
    print(f"excel       : {excel_path}")
    print(f"sheet       : {args.sheet or '<primera>'}")
    print(f"dig_id_tramite : {dig_id_tramite_filter or '<todos>'}")
    print(f"id_tramite  : {'incluido' if include_id_tramite else 'omitido'}")
    print(f"dry_run     : {args.dry_run}")
    print(f"filas       : {len(rows)}")
    print(f"descartadas : {len(discarded_rows)}")
    print("========================================")

    finder = SourceFinder(source_base)
    results: list[dict[str, object]] = []

    try:
        for row in rows:
            destination_expediente = destination_expediente_map.get(
                row.dig_id_tramite,
                row.dig_expediente,
            )
            result = copy_planilla_tree(
                source_base=source_base,
                dest_base=dest_base,
                row=row,
                include_id_tramite=include_id_tramite,
                dry_run=args.dry_run,
                source_finder=finder,
                expediente_override=destination_expediente,
            )
            results.append(result)
            print(
                f"[{row.row_number}] {row.dig_anio}/{destination_expediente}/"
                f"{row.dig_id_tramite + '/' if include_id_tramite and row.dig_id_tramite else ''}"
                f"{row.dig_tramite} -> {result['status']}"
            )

        write_manifest(manifest_csv, results)
        write_excel_report(
            report_xlsx,
            summary={
                "generated_at": format_timestamp(),
                "source_base": str(source_base),
                "dest_base": str(dest_base),
                "excel": str(excel_path),
                "sheet": args.sheet or "<primera>",
                "dig_id_tramite": dig_id_tramite_filter or "<todos>",
                "include_id_tramite": include_id_tramite,
                "dry_run": args.dry_run,
                "rows": len(rows),
                "discarded_duplicate_tramites": len(discarded_rows),
                **summarize_results(results),
            },
            detail_rows=results,
            include_id_tramite=include_id_tramite,
        )

        summary = summarize_results(results)
        print("========================================")
        print(f"copied      : {summary['copied']}")
        print(f"would_copy  : {summary['would_copy']}")
        print(f"missing     : {summary['missing_source']}")
        print(f"no_pdfs     : {summary['no_pdfs']}")
        print(f"invalid     : {summary['invalid_row']}")
        print(f"ambiguous   : {summary['ambiguous_source']}")
        print(f"discarded   : {len(discarded_rows)}")
        print(f"manifest    : {manifest_csv}")
        print(f"report_xlsx : {report_xlsx}")
        print("========================================")
        return 0

    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
