# Poda de Repositorio desde Oracle

Este proyecto genera una copia podada de un repositorio documental local (descargado por SFTP) usando filtros desde Oracle. Copia solo los trámites válidos preservando la estructura `<AÑO>/<EXPEDIENTE>/<TRÁMITE>` y produce un manifiesto CSV para auditoría.

## Instalación Rápida
- Clonar: `git clone https://github.com/chris78rey/podar.git && cd podar`
- Crear venv: `python -m venv venv && source venv/bin/activate`
- Instalar deps: `pip install -r requirements.txt`
- JDBC: coloque `ojdbc8.jar` en `jdbc/` y configure `.env` desde `.env.example`.
- Validar entorno: `python scripts/check_env.py`

## Uso (CLI)
- Prueba Oracle: `python scripts/test_oracle.py`
- Poda simulada: `python scripts/prune_local_mirror_from_oracle.py --source-base /ruta/src --dest-base /ruta/dest --fe-pla-aniomES 202602 --dry-run --limit 25`
- Con generación: añadir `--dig-id-generacion 12345` (opcional `--expediente CEX02`).
- Poda efectiva: quitar `--dry-run`.

## Interfaz Gráfica
- Ejecutar GUI: `python scripts/gui_launcher.py`
- Permite seleccionar rutas y filtros, probar Oracle y ejecutar la poda mostrando el log.

## Archivos Clave
- `scripts/prune_local_mirror_from_oracle.py`: lógica principal de consulta y copiado.
- `scripts/test_oracle.py`: verificación JDBC/Oracle.
- `scripts/check_env.py`: validación de Python/Java/paquetes/JAR/vars.
- `jdbc/ojdbc8.jar`: driver JDBC (no incluido).
- `AGENTS.md`, `docs/skills.md`, `reglas.md`: documentación operativa.

Para más detalles de contribución y comandos, ver `AGENTS.md`.
