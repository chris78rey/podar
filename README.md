# Poda de Repositorio desde Oracle

Este proyecto genera una copia podada de un repositorio documental local usando filtros desde Oracle. `DIG_ID_GENERACION` se usa para filtrar en Oracle y el numero de tramite ISSFA se usa para nombrar la carpeta de salida. La salida deja los tramites directamente debajo de esa carpeta y aplana los PDFs de subcarpetas sin perder archivos. Tambien genera un CSV y un Excel con el detalle del proceso.

## Instalacion rapida
- Clonar: `git clone https://github.com/chris78rey/podar.git && cd podar`
- Crear venv: `python -m venv venv && source venv/bin/activate`
- Instalar deps: `pip install -r requirements.txt`
- JDBC: colocar `ojdbc8.jar` en `jdbc/` y configurar `.env` desde `.env.example`
- Validar entorno: `python scripts/check_env.py`

## Uso
- Probar Oracle: `python scripts/test_oracle.py`
- Ejecutar poda: `python scripts/prune_local_mirror_from_oracle.py --source-base /ruta/src --dest-base /ruta/dest --fe-pla-aniomes 202602 --dig-id-generacion 12345 --numero-tramite-issfa 67890`
- La salida queda en `dest-base/<NUMERO_TRAMITE_ISSFA>/<TRAMITE>`
- Reportes: `dest-base/<NUMERO_TRAMITE_ISSFA>_manifest.csv` y `dest-base/<NUMERO_TRAMITE_ISSFA>_detalle.xlsx`
- Los tramites sin PDFs no se descargan y quedan marcados en el Excel
- GUI: `powershell -ExecutionPolicy Bypass -File run_gui.ps1` o doble clic en `run_gui.bat`

## Distribucion Windows
- Build portable: `powershell -ExecutionPolicy Bypass -File build_windows.ps1`
- Ejecutable portable: `dist\PODA\PODA.exe`
- Instalador generado: `installer_output\PODA_Setup.exe`
- El instalador copia la app y deja el launcher listo en el menu Inicio y el escritorio opcional
- El instalador incluye un runtime Java portable generado con `jlink`, por lo que no depende del Java del sistema para conectar a Oracle
- El instalador crea `%APPDATA%\PODA\.env` con los valores visibles y deja la clave vacia
- La app busca `.env` en `%APPDATA%\PODA\.env`, junto al ejecutable instalado, o en desarrollo en la raiz del repo
- La GUI muestra `ORACLE_USER`, `ORACLE_TARGETS`, `ORACLE_JDBC_JAR`, `ORACLE_OWNER` y `ORACLE_SOURCE_TABLE` con valores visibles; solo la clave se mantiene oculta
- La GUI permite guardar la configuracion Oracle en `%APPDATA%\PODA\.env`, incluido `ORACLE_TARGETS` por si cambia la base
- `.env.example` ya viene alineado con esos valores visibles y deja la clave vacia

## Interfaz grafica
- Permite seleccionar rutas, ejecutar la descarga y ver la salida en vivo

## Archivos clave
- `scripts/prune_local_mirror_from_oracle.py`: logica principal de consulta y copiado
- `scripts/test_oracle.py`: verificacion JDBC/Oracle
- `scripts/check_env.py`: validacion de Python/Java/paquetes/JAR/vars
- `scripts/gui_launcher_app.py`: interfaz grafica
- `jdbc/ojdbc8.jar`: driver JDBC
- `run_gui.ps1` y `run_gui.bat`: lanzadores de la GUI
- `build_windows.ps1`: build portable e instalador
- `installer/PODA.iss`: definicion del instalador Inno Setup

## Notas
- Oracle se usa solo en lectura
- El filtro principal sigue siendo `DIG_ID_GENERACION`
- La carpeta de salida se define con el numero de tramite ISSFA
- Los PDFs repetidos en un tramite se renombran con sufijo `_2`, `_3`, etc.
