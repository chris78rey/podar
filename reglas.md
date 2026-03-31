# Documentación de onboarding

## Proyecto de poda local de repositorio usando Oracle + copia SFTP

## 1. Resumen ejecutivo

Este proyecto busca generar una **copia reducida o podada** de un repositorio documental que originalmente vive en un servidor. La poda se realiza **en otro equipo**, a partir de una **copia local descargada por SFTP**, y la selección de qué carpetas conservar se define consultando la tabla `DIGITALIZACION` en Oracle.

La idea principal es muy simple:

* el servidor original mantiene el repositorio completo;
* otro equipo descarga una copia por SFTP;
* un script consulta Oracle para saber qué trámites pertenecen a un filtro determinado;
* con ese resultado, el script conserva únicamente las carpetas de esos trámites en una nueva ubicación local.

En otras palabras, el sistema no trabaja directamente sobre producción ni sobre el servidor fuente, sino sobre una **copia local de trabajo**.

---

## 2. Problema que resuelve

En la operación diaria puede existir la necesidad de entregar, revisar, auditar o procesar solo una parte del repositorio documental, por ejemplo:

* todos los trámites planillados de un mes específico;
* solo una generación determinada;
* solo un expediente específico;
* solo un subconjunto de carpetas necesario para revisión externa.

Sin una herramienta de poda, el equipo tendría que:

* descargar grandes volúmenes de información innecesaria;
* buscar manualmente carpeta por carpeta;
* correr el riesgo de omitir trámites o copiar carpetas que no corresponden.

Este proyecto automatiza ese proceso y lo vuelve repetible, auditable y mucho menos propenso a errores.

---

## 3. Objetivo funcional

El objetivo funcional del proyecto es:

**consultar Oracle, identificar los trámites válidos según filtros de negocio y construir una copia local reducida del repositorio, manteniendo únicamente el subárbol necesario**.

Ejemplo de filtro típico:

* `DIG_PLANILLADO = 'S'`
* `FE_PLA_ANIOMES = '202602'`

Eso representa, por ejemplo, los trámites planillados del mes de febrero de 2026.

---

## 4. Qué sí hace y qué no hace

### Sí hace

* se conecta a Oracle por JDBC;
* consulta la tabla `DIGITALIZACION`;
* obtiene los trámites que cumplen los filtros indicados;
* arma el path esperado de cada trámite;
* revisa si la carpeta existe en la copia local descargada por SFTP;
* copia únicamente esas carpetas a un nuevo destino local;
* genera un manifiesto de resultados para auditoría y revisión.

### No hace

* no modifica Oracle;
* no borra datos del servidor original;
* no cambia la copia base descargada por SFTP;
* no reindexa el repositorio;
* no corrige metadata en la base de datos;
* no reemplaza los procesos normales de carga, control documental o generación de carpetas.

---

## 5. Contexto técnico del proyecto

Este proyecto vive dentro del ecosistema de herramientas de digitalización que ya utiliza:

* Python
* Oracle 11gR2
* JDBC (`ojdbc`)
* `jaydebeapi` + `JPype`
* scripts auxiliares para Oracle, árbol de carpetas y exportación SFTP

El repositorio actual ya contiene patrones establecidos para:

* leer configuración desde `.env`;
* conectarse a Oracle con failover RAC;
* trabajar con el esquema `DIGITALIZACION`;
* usar rutas base configurables como `DIGI_BASE_DIR`.

Este nuevo proceso debe seguir ese mismo estilo para mantener consistencia con el resto del proyecto.

---

## 6. Conceptos básicos para alguien nuevo

### Repositorio documental

Es la estructura de carpetas y PDFs donde se almacenan los documentos digitalizados.

### Copia SFTP

Es una réplica descargada desde el servidor hacia otro equipo. Sobre esa copia sí se puede trabajar para hacer podas, validaciones o empaquetados sin afectar el origen.

### Tabla `DIGITALIZACION`

Es la tabla de Oracle que contiene la metadata de los trámites y permite identificar cómo deberían organizarse documentalmente.

### Trámite

Es la unidad principal que se usa para ubicar una carpeta documental. Normalmente se representa por `DIG_TRAMITE`.

### Expediente

Es la categoría o agrupador documental, por ejemplo `CEX02`, `EME02`, `HSP02`, etc.

### `FE_PLA_ANIOMES`

Es el año-mes en formato `YYYYMM`, por ejemplo `202602`.

### `DIG_PLANILLADO`

Indica si el trámite está planillado. Un valor típico de interés es `S`.

### Poda

Significa generar una copia reducida dejando únicamente lo necesario según filtros definidos.

---

## 7. Campos clave utilizados

Aunque la tabla puede tener muchos más campos, para este proceso los más importantes son:

* `DIG_ID`
* `DIG_TRAMITE`
* `DIG_EXPEDIENTE`
* `FE_PLA_ANIOMES`
* `DIG_ANIO`
* `DIG_PLANILLADO`
* `DIG_ID_GENERACION` (opcional para filtros más finos)

Estos campos permiten reconstruir la ruta esperada del trámite dentro del espejo local.

Ejemplo lógico de ruta:

`<source_base>/<DIG_ANIO>/<DIG_EXPEDIENTE>/<DIG_TRAMITE>`

Ejemplo real:

`/mnt/copia_servidor/data/datos/2026/CEX02/5840362`

---

## 8. Flujo general del proceso

### Paso 1. Descarga del espejo local

Primero se obtiene una copia del repositorio por SFTP en el equipo de trabajo.

Ejemplo:

`/mnt/copia_servidor/data/datos`

### Paso 2. Consulta Oracle

El script consulta Oracle con filtros como:

* `DIG_PLANILLADO = 'S'`
* `FE_PLA_ANIOMES = '202602'`

### Paso 3. Reconstrucción del path esperado

Con los datos obtenidos se calcula dónde debería estar cada trámite dentro de la copia local.

### Paso 4. Validación del origen

Se verifica si la carpeta realmente existe en la copia descargada.

### Paso 5. Copia podada

Se copian solo las carpetas válidas a un nuevo destino.

### Paso 6. Manifiesto de salida

Se genera un CSV con el detalle de:

* trámite
* expediente
* período
* path origen
* path destino
* estado (`COPIED`, `MISSING_SOURCE`, etc.)

---

## 9. Arquitectura simplificada

```text
Servidor original
    │
    ├── Repositorio documental completo
    │
    └── Oracle (tabla DIGITALIZACION)

Equipo cliente
    │
    ├── Copia descargada por SFTP
    ├── Script de consulta Oracle + poda local
    └── Carpeta destino con copia reducida
```

Este diseño separa claramente:

* el origen documental;
* la fuente de verdad de metadata;
* el entorno donde se hace la poda.

---

## 10. Requisitos

### Requisitos funcionales

* disponer de acceso a Oracle;
* disponer de una copia local del repositorio descargada por SFTP;
* conocer el punto de corte desde donde se desea conservar el subárbol;
* conocer el filtro de negocio a aplicar.

### Requisitos técnicos

* Python 3;
* `jaydebeapi`;
* `JPype1`;
* driver JDBC de Oracle (`ojdbc`);
* acceso de red al RAC de Oracle o al target definido.

---

## 11. Configuración esperada

La configuración debería manejarse con `.env` para seguir el patrón del repositorio.

Ejemplo:

```dotenv
ORACLE_USER=DIGITALIZACION
ORACLE_PASSWORD=SU_PASSWORD_REAL
ORACLE_JDBC_JAR=/ruta/real/ojdbc8.jar
ORACLE_TARGETS=172.16.60.20:1521:prdsgh1,172.16.60.21:1521:prdsgh2
ORACLE_OWNER=DIGITALIZACION
ORACLE_SOURCE_TABLE=DIGITALIZACION
```

---

## 12. Parámetros operativos del script

Los parámetros recomendados son:

* `--source-base`: base local descargada por SFTP;
* `--dest-base`: destino de la copia podada;
* `--fe-pla-aniomes`: período en formato `YYYYMM`;
* `--dig-planillado`: normalmente `S`;
* `--expediente`: filtro opcional;
* `--dig-id-generacion`: filtro opcional;
* `--dry-run`: modo de validación sin copiar;
* `--manifest-csv`: ruta del manifiesto de salida.

---

## 13. Ejemplo de uso

### Validación sin copiar

```bash
python prune_local_mirror_from_oracle.py \
  --source-base /mnt/copia_servidor/data/datos \
  --dest-base /mnt/podado_202602 \
  --fe-pla-aniomes 202602 \
  --dig-planillado S \
  --dry-run
```

### Ejecución real

```bash
python prune_local_mirror_from_oracle.py \
  --source-base /mnt/copia_servidor/data/datos \
  --dest-base /mnt/podado_202602 \
  --fe-pla-aniomes 202602 \
  --dig-planillado S
```

---

## 14. Estructura esperada del resultado

Si Oracle devuelve trámites como:

* `5840361`
* `5840362`
* `5840363`

y todos pertenecen a:

* `DIG_ANIO = 2026`
* `DIG_EXPEDIENTE = CEX02`

entonces el destino final tendrá algo como:

```text
/mnt/podado_202602/
└── 2026/
    └── CEX02/
        ├── 5840361/
        ├── 5840362/
        └── 5840363/
```

---

## 15. Resultados posibles del manifiesto

### `COPIED`

La carpeta fue encontrada y copiada correctamente.

### `WOULD_COPY`

La carpeta sería copiada, pero la ejecución fue en `dry-run`.

### `MISSING_SOURCE`

Oracle indicó que el trámite existe, pero la carpeta no fue encontrada en la copia local descargada por SFTP.

### `INVALID_SOURCE_OUTSIDE_BASE`

El path calculado no quedó contenido dentro de la base permitida. Esto se considera protección de seguridad contra rutas incorrectas.

---

## 16. Validaciones importantes

Antes de ejecutar en real, siempre se recomienda:

* comprobar que `source-base` exista;
* comprobar que `dest-base` sea distinto del origen;
* ejecutar primero con `--dry-run`;
* revisar el CSV de salida;
* comparar el total de trámites esperados versus el total encontrado.

---

## 17. Riesgos operativos

### Riesgo 1. La copia SFTP está incompleta

Puede pasar que Oracle devuelva trámites válidos, pero la copia local no los tenga. En ese caso aparecerán como `MISSING_SOURCE`.

### Riesgo 2. Filtro equivocado

Si el período o el expediente están mal, la poda se hará sobre un conjunto incorrecto.

### Riesgo 3. Origen y destino iguales

Eso podría mezclar la copia base con la copia podada. Debe bloquearse explícitamente.

### Riesgo 4. Campos inconsistentes en Oracle

Si hay registros sin `DIG_TRAMITE` o `DIG_EXPEDIENTE`, esos registros no deberían generar rutas válidas.

---

## 18. Medidas de protección

Para mantener el enfoque de cero roturas, el proyecto debe conservar estas reglas:

* Oracle solo lectura;
* origen local intacto;
* destino separado;
* manifiesto obligatorio;
* `dry-run` antes de producción;
* validación de que toda ruta copiada esté debajo de `source-base`.

---

## 19. Qué parte del proyecto ya existe y qué parte es nueva

### Ya existe en el repositorio

* patrón de conexión Oracle por JDBC;
* lectura de variables desde `.env`;
* failover por `ORACLE_TARGETS`;
* scripts que operan con `DIGITALIZACION`;
* lógica de SFTP en otros flujos del proyecto.

### Sería nueva

* la utilidad específica para **podar una copia local descargada por SFTP** basada en filtros Oracle.

Esto es importante porque evita que un lector crea que ya existe exactamente ese flujo implementado de punta a punta.

---

## 20. Cómo explicar el proyecto a una persona no técnica

Una forma simple de explicarlo es:

> Este proyecto permite sacar una copia reducida de un repositorio grande de documentos. En vez de copiar todo, primero se revisa en Oracle cuáles trámites interesan y solo se conservan esas carpetas en una nueva ubicación.

Otra versión más operativa:

> El servidor tiene demasiados documentos. Este proceso permite descargar una copia y recortarla automáticamente para dejar solo lo que pertenece a un período o conjunto de trámites específico.

---

## 21. Casos de uso más comunes

* entregar a otra área solo los trámites de un mes;
* preparar un subconjunto para auditoría;
* reducir el volumen de información antes de análisis;
* revisar una generación concreta;
* obtener una copia controlada sin exponer el repositorio completo.

---

## 22. Qué revisar cuando algo falla

### Si no conecta a Oracle

Revisar:

* usuario y contraseña;
* driver JDBC;
* targets RAC;
* conectividad de red;
* formato `host:port:sid`.

### Si no encuentra carpetas

Revisar:

* si la copia SFTP realmente contiene ese período;
* si el `source-base` apunta al nivel correcto;
* si `DIG_ANIO`, `DIG_EXPEDIENTE` y `DIG_TRAMITE` corresponden a la estructura física.

### Si el resultado trae demasiadas carpetas

Revisar:

* filtro de `FE_PLA_ANIOMES`;
* filtro de expediente;
* filtro de `DIG_ID_GENERACION`;
* si la tabla tiene duplicados o inconsistencias.

---

## 23. Validación posterior a la ejecución

Después de correr el proceso se recomienda:

* contar cuántas carpetas de trámite se copiaron;
* contar cuántos archivos quedaron en el destino;
* revisar el manifiesto CSV;
* comparar contra el conteo esperado desde Oracle.

---

## 24. Reversión

La reversión es simple porque el proceso no modifica Oracle ni el origen.

Si algo sale mal, basta con eliminar la carpeta destino y volver a ejecutar con los parámetros corregidos.

Ejemplo:

```bash
rm -rf /mnt/podado_202602
rm -f /mnt/podado_202602_manifest.csv
```

---

## 25. Recomendación de evolución futura

La primera versión debería mantenerse simple:

1. descarga SFTP por separado;
2. poda local en otro paso;
3. manifiesto de auditoría;
4. validación previa con `dry-run`.

En una segunda etapa, si el proceso se estabiliza, podría integrarse:

* descarga selectiva por SFTP;
* empaquetado ZIP final;
* generación de hashes;
* interfaz web para selección de filtros;
* reportes de faltantes.

---

## 26. Conclusión operativa

Este proyecto no es un reemplazo del repositorio original ni del sistema de digitalización. Es una utilidad de apoyo para construir subconjuntos controlados, verificables y reproducibles a partir de una copia local, usando Oracle como criterio de selección.

Su mayor valor es reducir trabajo manual, minimizar errores y evitar tocar producción cuando solo se necesita una porción bien definida del repositorio.
