# Operational Skills

## Probar conectividad Oracle
- Objetivo: Validar credenciales, reachability y driver JDBC.
- Entrada: `.env` con `ORACLE_USER`, `ORACLE_PASSWORD`, `ORACLE_TARGETS`, `ORACLE_JDBC_JAR`.
- Salida: Éxito/fallo y diagnóstico.
- Comando: `python scripts/test_oracle.py`

## Poda simulada de espejo
- Objetivo: Previsualizar sin copiar archivos.
- Entrada: `--source-base`, `--dest-base`, `--fe-pla-aniomes`, opcionales `--expediente`, `--dig-id-generacion`, `--limit`.
- Salida: Resumen por estado y CSV de manifiesto.
- Comando: `python scripts/prune_local_mirror_from_oracle.py --source-base /ruta/src --dest-base /ruta/dest --fe-pla-aniomes 202602 --dry-run --limit 25`

## Poda efectiva de espejo
- Objetivo: Copiar subárboles válidos al destino.
- Entrada: Igual a la simulada, sin `--dry-run`.
- Salida: Archivos copiados y manifiesto CSV.
- Comando: `python scripts/prune_local_mirror_from_oracle.py --source-base /ruta/src --dest-base /ruta/dest --fe-pla-aniomes 202602`

## Validación de entorno
- Objetivo: Verificar Python, dependencias y jar JDBC.
- Pasos: `python --version` (>=3.11), `pip show jaydebeapi`, existencia de `jdbc/ojdbc8.jar`.

## Muestreo controlado
- Objetivo: Validar filtros en pequeño.
- Entrada: `--limit` bajo y `--dry-run`.
- Resultado: Ajustes antes de ejecución completa.

## Auditoría post-ejecución
- Objetivo: Verificar consistencia del manifest con el filesystem.
- Entrada: Ruta del manifest CSV.
- Acción: Comparar `files_found` con recuento real y reportar faltantes.
