# Logica de negocio de OrganizaPlanillas

## Objetivo

OrganizaPlanillas toma un archivo Excel y una carpeta origen con PDFs sin ordenar, y genera una estructura de salida ordenada sin tocar el origen.

## Columnas de entrada

El Excel debe contener estas columnas:

- `dig_id`
- `dig_anio`
- `dig_expediente`
- `dig_id_tramite`
- `dig_tramite`

## Estructura de salida

La salida se construye como:

- `dest-base/dig_anio/dig_expediente/dig_id_tramite/dig_tramite`

Si el usuario activa la opcion de omitir `dig_id_tramite`, la ruta queda como:

- `dest-base/dig_anio/dig_expediente/dig_tramite`

## Regla de expedientes multiples

Esta es la ultima regla de negocio vigente:

- Si un mismo `dig_id_tramite` aparece en varios expedientes, se toma el expediente de mayor numero.
- Ese expediente ganador se usa como expediente de destino para todas las filas de ese `dig_id_tramite`.
- El origen puede seguir resolviendose con el expediente real de cada fila.

### Ejemplo

Si `dig_id_tramite = 16270` aparece en `HSP01` y `HSP02`, el destino final se organiza bajo `HSP02`.

Eso evita que el mismo tramite quede repartido entre carpetas como:

- `2026/HSP01/16270/...`
- `2026/HSP02/16270/...`

y fuerza que todo quede consolidado en:

- `2026/HSP02/16270/...`

## Regla de filtrado

La interfaz permite dos modos:

- procesar todo el Excel
- procesar solo un `dig_id_tramite`

## Regla de PDFs

- Los PDFs se copian desde la carpeta origen a la carpeta final del tramite.
- Si hay PDFs repetidos en un mismo destino, se renombran con sufijo `_2`, `_3`, etc.
- Los tramites sin PDFs no se copian y quedan reportados.

## Reportes

Cada corrida genera:

- `organiza_planillas_manifest.csv`
- `organiza_planillas_detalle.xlsx`

El Excel de detalle incluye:

- `Resumen`
- `Detalle`
- `Agrupado`

