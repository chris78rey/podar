La mejor forma, con cero roturas, es **no tocar el servidor ni el repositorio original** y hacer un script nuevo en el equipo cliente que trabaje así:

1. consulta Oracle por JDBC en **solo lectura**;
2. obtiene los trámites filtrados, por ejemplo `DIG_PLANILLADO='S'` y `FE_PLA_ANIOMES='202602'`;
3. toma como origen una **copia local ya descargada por SFTP**;
4. genera una **copia podada** en otra carpeta, preservando únicamente el subárbol relativo desde el punto de corte.

Ese enfoque calza mejor con lo que ya existe en el proyecto: el repositorio ya usa Oracle por JDBC con `jaydebeapi`, `ojdbc`, `ORACLE_TARGETS`, `ORACLE_USER`, `ORACLE_PASSWORD` y `DIGI_BASE_DIR`; además ya existe un helper SFTP separado, así que conviene mantener **JDBC para consultar** y **filesystem local para podar**, sin mezclar lógica del servidor con la del cliente.   

También hay evidencia real de que en febrero 2026 aparecen registros con `DIG_PLANILLADO='S'`, `FE_PLA_ANIOMES='202602'`, `DIG_EXPEDIENTE='CEX02'` y trámites como `5840362`, `5840365`, `5840366`, por lo que el patrón de ruta esperable queda como `2026/CEX02/<tramite>`.  

## Impacto y riesgos

**Qué puede salir mal**

* Que la copia SFTP local esté incompleta y falten carpetas.
* Que existan registros Oracle con `DIG_TRAMITE` o `DIG_EXPEDIENTE` vacíos.
* Que el usuario ejecute el script apuntando al destino igual que al origen.
* Que el path base de corte sea incorrecto y copie más o menos de lo esperado.

**Qué se va a proteger**

* Oracle quedará en **solo lectura**.
* El origen local descargado por SFTP no se modifica.
* La copia podada se genera en **otro destino**.
* Se deja manifiesto CSV con `copied / missing / invalid`.
* Se incluye `--dry-run` para validar antes.

## Preparación

### 1) Estructura recomendada en el equipo cliente

Supóngase que la copia descargada por SFTP quedó aquí:

```bash
/mnt/copia_servidor/data/datos
```

y que la copia podada se quiere generar aquí:

```bash
/mnt/podado_202602
```

Entonces el punto de corte será:

```bash
/mnt/copia_servidor/data/datos
```

y el script preservará desde ahí:

```bash
2026/CEX02/5840362
2026/CEX02/5840365
...
```

### 2) Dependencias

```bash
python3 -m venv venv
source venv/bin/activate
pip install jaydebeapi JPype1
```

### 3) Archivo `.env`

```dotenv
ORACLE_USER=DIGITALIZACION
ORACLE_PASSWORD=SU_PASSWORD_REAL
ORACLE_JDBC_JAR=/ruta/real/ojdbc8.jar
ORACLE_TARGETS=172.16.60.20:1521:prdsgh1,172.16.60.21:1521:prdsgh2
ORACLE_OWNER=DIGITALIZACION
ORACLE_SOURCE_TABLE=DIGITALIZACION
```

El proyecto ya usa exactamente ese patrón de variables para JDBC y failover RAC.  

### 3) Backup y snapshot

Antes de ejecutar:

```bash
mkdir -p /mnt/backups_validacion
date > /mnt/backups_validacion/antes_poda_202602.txt
find /mnt/copia_servidor/data/datos -type d | wc -l >> /mnt/backups_validacion/antes_poda_202602.txt
find /mnt/copia_servidor/data/datos -type f | wc -l >> /mnt/backups_validacion/antes_poda_202602.txt
```

Si ya existe un destino viejo:

```bash
mv /mnt/podado_202602 /mnt/podado_202602_bak_$(date +%Y%m%d_%H%M%S)
```

## Implementación paso a paso

### Archivo nuevo

Ruta sugerida:

```bash
scripts/prune_local_mirror_from_oracle.py
```

### Código completo listo para copiar

```python
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
```

## Ejecución

### 1) Prueba segura

```bash
python prune_local_mirror_from_oracle.py \
  --source-base /mnt/copia_servidor/data/datos \
  --dest-base /mnt/podado_202602 \
  --fe-pla-aniomes 202602 \
  --dig-planillado S \
  --dry-run
```

### 2) Ejecución real

```bash
python prune_local_mirror_from_oracle.py \
  --source-base /mnt/copia_servidor/data/datos \
  --dest-base /mnt/podado_202602 \
  --fe-pla-aniomes 202602 \
  --dig-planillado S
```

### 3) Si se quiere todavía más quirúrgico

Solo `CEX02`:

```bash
python prune_local_mirror_from_oracle.py \
  --source-base /mnt/copia_servidor/data/datos \
  --dest-base /mnt/podado_202602_cex02 \
  --fe-pla-aniomes 202602 \
  --dig-planillado S \
  --expediente CEX02
```

Solo una generación:

```bash
python prune_local_mirror_from_oracle.py \
  --source-base /mnt/copia_servidor/data/datos \
  --dest-base /mnt/podado_gen_122533 \
  --fe-pla-aniomes 202602 \
  --dig-planillado S \
  --dig-id-generacion 122533
```

## Validación antes y después

### Validación Oracle antes

```sql
SELECT COUNT(DISTINCT DIG_TRAMITE) AS TOTAL_TRAMITES
FROM DIGITALIZACION.DIGITALIZACION
WHERE TRIM(NVL(DIG_PLANILLADO,'N')) = 'S'
  AND TRIM(FE_PLA_ANIOMES) = '202602';
```

Si además se usa expediente:

```sql
SELECT COUNT(DISTINCT DIG_TRAMITE) AS TOTAL_TRAMITES
FROM DIGITALIZACION.DIGITALIZACION
WHERE TRIM(NVL(DIG_PLANILLADO,'N')) = 'S'
  AND TRIM(FE_PLA_ANIOMES) = '202602'
  AND TRIM(DIG_EXPEDIENTE) = 'CEX02';
```

### Validación filesystem después

Contar carpetas de trámite copiadas:

```bash
find /mnt/podado_202602 -mindepth 3 -maxdepth 3 -type d | wc -l
```

Contar PDFs copiados:

```bash
find /mnt/podado_202602 -type f | wc -l
```

Ver faltantes detectados por el script:

```bash
grep MISSING_SOURCE /mnt/podado_202602_manifest.csv
```

## Pruebas de verificación y regresión

### Lo nuevo

* El script debe listar trámites válidos del periodo `202602`.
* En `--dry-run` no debe copiar nada.
* En modo real debe crear solo el árbol filtrado.
* Debe generar manifiesto CSV.

### Lo antiguo que debe seguir igual

* La copia SFTP local original debe quedar intacta.
* Oracle no debe recibir `UPDATE`, `INSERT` ni `DELETE`.
* El script no debe depender del FastAPI ni del Flask del servidor.
* No debe alterar `folders.sqlite`, `_audit` ni archivos del repo original.

### Checklist técnico

* `source-base` existe y contiene `anio/expediente/tramite`.
* `dest-base` es distinto del origen.
* `ORACLE_JDBC_JAR` existe.
* `ORACLE_TARGETS` tiene formato `host:port:sid`.
* El conteo Oracle de trámites coincide con `COPIED + MISSING_SOURCE + INVALID`.

## Plan de reversión

Como el proceso es de solo lectura sobre Oracle y no modifica el origen, el rollback es muy simple.

### Script de emergencia

Borrar la copia podada:

```bash
rm -rf /mnt/podado_202602
rm -f /mnt/podado_202602_manifest.csv
```

Si el destino anterior fue respaldado:

```bash
mv /mnt/podado_202602_bak_YYYYMMDD_HHMMSS /mnt/podado_202602
```

### Recuperación en menos de 2 minutos

1. detener el uso del destino podado;
2. eliminar la carpeta generada;
3. volver a ejecutar en `--dry-run`;
4. corregir `source-base` o filtros;
5. lanzar nuevamente.

## Observación importante de diseño

Para el escenario descrito, **no conviene mezclar en un mismo script la descarga SFTP y la poda** en la primera versión. La variante más estable es:

* **Paso A:** otro proceso descarga el espejo por SFTP al equipo cliente;
* **Paso B:** este script poda localmente usando Oracle como verdad de selección.

Así el riesgo operativo baja mucho: si falla el SFTP, no contamina la poda; y si falla la poda, no toca la descarga base.

Si se desea, en el siguiente paso se puede dejar una **segunda versión** que haga también el pull por SFTP y evite descargar carpetas que no estén en el select.
