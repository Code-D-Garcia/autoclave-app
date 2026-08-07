# 🐘 Respuestas a la Prueba Técnica de PostgreSQL

> **PostgreSQL Technical Assessment Case Study**

> **Postulante:** Ing. David Garcia

---

## 1. Modelado e Integridad (5 puntos)

### Sentencias DDL (`CREATE TABLE`)

Se propone un diseño relacional normalizado con tipos de datos adecuados, integridad referencial, restricciones de dominio y reglas de unicidad.

```sql
-- 1. Tabla LOTE
CREATE TABLE IF NOT EXISTS lote (
        id_lote         VARCHAR(50) PRIMARY KEY,
        codigo_lote     VARCHAR(50) NOT NULL UNIQUE,
        producto        VARCHAR(150) NOT NULL,
        creado_en       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS ciclo_esterilizacion (
        id_ciclo              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        id_lote               VARCHAR(50) NOT NULL REFERENCES lote(id_lote) ON DELETE CASCADE ON UPDATE CASCADE,
        autoclave_id          VARCHAR(50) NOT NULL,
        inicio                TIMESTAMPTZ NOT NULL,
        fin                   TIMESTAMPTZ NOT NULL,
        temp_min_esperada     NUMERIC(5,2) NOT NULL,
        temp_max_esperada     NUMERIC(5,2) NOT NULL,
        presion_min_esperada  NUMERIC(4,2) NOT NULL,
        presion_max_esperada  NUMERIC(4,2) NOT NULL,
        estado                VARCHAR(20) NOT NULL DEFAULT 'EN_PROCESO',
        CONSTRAINT chk_ciclo_fechas CHECK (fin > inicio)
    );

    CREATE TABLE IF NOT EXISTS lectura (
        id_lectura     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        id_ciclo       BIGINT NOT NULL REFERENCES ciclo_esterilizacion(id_ciclo) ON DELETE CASCADE ON UPDATE CASCADE,
        fecha_hora     TIMESTAMPTZ NOT NULL,
        temperatura    NUMERIC(5,2) NOT NULL,
        presion        NUMERIC(4,2) NOT NULL,
        clasificacion  VARCHAR(20) NOT NULL DEFAULT 'NORMAL'
    );
```

### Justificación técnica

* **`TIMESTAMPTZ`**: permite manejar correctamente fechas y zonas horarias.
* **`NUMERIC(p,s)`**: proporciona precisión fija para las mediciones.
* **`ON DELETE CASCADE`**: elimina los registros dependientes cuando se elimina su registro padre.
* **`CHECK`**: garantiza rangos y estados válidos.
* **`UNIQUE(id_ciclo, fecha_hora)`**: evita lecturas duplicadas para un mismo ciclo e instante.

---

## 2. Consultas Analíticas (5 puntos)

### Consulta 1: Lotes con alertas, cantidad de alertas y mayor desviación de temperatura

```sql
SELECT 
    lo.id_lote,
    lo.producto,
    c.autoclave_id,
    COUNT(l.id_lectura) FILTER (WHERE l.clasificacion != 'NORMAL') AS cantidad_alertas,
    ROUND(
        MAX(
            GREATEST(
                0, 
                l.temperatura - c.temp_max_esperada, 
                c.temp_min_esperada - l.temperatura
            )
        ), 2
    ) AS mayor_desviacion_temperatura
FROM lote lo
JOIN ciclo_esterilizacion c ON lo.id_lote = c.id_lote
JOIN lectura l ON c.id_ciclo = l.id_ciclo
WHERE l.clasificacion != 'NORMAL'
GROUP BY lo.id_lote, lo.producto, c.autoclave_id
ORDER BY cantidad_alertas DESC, mayor_desviacion_temperatura DESC;
```

### Consulta 2: Resumen mensual por autoclave (% de aprobación y promedios)

```sql
SELECT 
    c.autoclave_id,
    TO_CHAR(DATE_TRUNC('month', c.inicio), 'YYYY-MM') AS mes,
    COUNT(DISTINCT c.id_ciclo) AS lotes_procesados,
    ROUND(AVG(l.temperatura), 2) AS temperatura_promedio,
    COUNT(l.id_lectura) FILTER (
        WHERE l.clasificacion != 'NORMAL'
    ) AS total_lecturas_fuera_de_rango,
    ROUND(
        (
            COUNT(DISTINCT CASE
                WHEN c.estado = 'APPROVED'
                THEN c.id_ciclo
            END)::NUMERIC
            / NULLIF(COUNT(DISTINCT c.id_ciclo), 0)
        ) * 100,
        2
    ) AS porcentaje_lotes_aprobados
FROM ciclo_esterilizacion c
LEFT JOIN lectura l
    ON c.id_ciclo = l.id_ciclo
GROUP BY
    c.autoclave_id,
    DATE_TRUNC('month', c.inicio)
ORDER BY
    mes DESC,
    c.autoclave_id ASC;
```

### Manejo de división por cero

Se utiliza `NULLIF` para evitar una división por cero:

```sql
NULLIF(COUNT(DISTINCT c.id_ciclo), 0)
```

Si el conteo es `0`, `NULLIF` devuelve `NULL`, por lo que la división también devuelve `NULL` en lugar de generar un error.

### Explicación

La consulta agrupa automáticamente por cada combinación de:

```sql
c.autoclave_id, DATE_TRUNC('month', c.inicio)
```

Por ejemplo:

| Autoclave | Mes     | Lotes | Aprobados | En observación |
| --------- | ------- | ----: | --------: | -------------: |
| AUT-01    | 2026-08 |     3 |         2 |              1 |
| AUT-01    | 2026-09 |     1 |         1 |              0 |
| AUT-02    | 2026-08 |     1 |         0 |              1 |
| AUT-02    | 2026-09 |     1 |         0 |              1 |
| AUT-03    | 2026-08 |     1 |         1 |              0 |

Resultado:

| Autoclave | Mes     | Lotes | Temp. Promedio | Alertas | % Aprobados |
| --------- | ------- | ----: | -------------: | ------: | ----------: |
| AUT-01    | 2026-09 |     1 |      118.50 °C |       0 |     100.00% |
| AUT-02    | 2026-09 |     1 |      124.00 °C |       1 |       0.00% |
| AUT-01    | 2026-08 |     3 |      119.58 °C |       2 |      66.67% |
| AUT-02    | 2026-08 |     1 |      119.00 °C |       3 |       0.00% |
| AUT-03    | 2026-08 |     1 |      119.23 °C |       0 |     100.00% |

Para `AUT-01` en agosto:

```text
2 / 3 * 100 = 66.67%
```

---

## 3. Índices y Plan de Ejecución (5 puntos)

### 1. Propuesta de índices
```sql
-- 1. Consultas por Lote (búsquedas e integridad referencial)
CREATE INDEX idx_ciclo_id_lote 
ON ciclo_esterilizacion (id_lote);

-- 2. Consultas por Autoclave y rango de fechas en ciclos
CREATE INDEX idx_ciclo_autoclave_inicio 
ON ciclo_esterilizacion (autoclave_id, inicio DESC);

-- 3. Consultas por rango de fechas y JOIN en lecturas de telemetría
CREATE INDEX idx_lectura_fechahora_ciclo 
ON lectura (fecha_hora DESC, id_ciclo);
```

### 2. Verificación con `EXPLAIN (ANALYZE, BUFFERS)`

```sql
EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT l.fecha_hora, l.temperatura, l.presion
FROM ciclo_esterilizacion c
JOIN lectura l
    ON c.id_ciclo = l.id_ciclo
WHERE c.autoclave_id = 'AUT-01'
  AND l.fecha_hora >= '2026-08-01 00:00:00-05'
ORDER BY l.fecha_hora DESC;
```

Métricas principales:

* **`Index Scan` / `Index Only Scan`**: uso de índices.
* **`Seq Scan`**: recorrido secuencial de la tabla.
* **`Sort`**: operación de ordenamiento.
* **`Buffers`**: accesos a memoria y disco.
* **`Execution Time`**: tiempo real de ejecución.

### 3. ¿Cuándo puede utilizar `Seq Scan`?

PostgreSQL puede preferir `Seq Scan` cuando:

* La tabla es pequeña.
* La consulta devuelve una gran parte de los registros.
* El costo estimado del índice es mayor que recorrer la tabla.

Por esto, la existencia de un índice no garantiza que PostgreSQL lo utilice.

---

## 4. Concurrencia y Transacciones (5 puntos)

### Escenario

Dos procesos intentan cerrar simultáneamente el mismo ciclo:

```text
EN_PROCESO → APPROVED
EN_PROCESO → REJECTED
```

### Solución: bloqueo pesimista con `FOR UPDATE`

```sql
BEGIN;

-- Bloquear la fila
SELECT id_ciclo, estado
FROM ciclo_esterilizacion
WHERE id_ciclo = 101
FOR UPDATE;

-- Actualizar únicamente si continúa EN_PROCESO
UPDATE ciclo_esterilizacion
SET estado = 'APPROVED',
    fin = CURRENT_TIMESTAMP
WHERE id_ciclo = 101
  AND estado = 'EN_PROCESO';

COMMIT;
```

### ¿Por qué funciona?

* El primer proceso adquiere el bloqueo de la fila.
* El segundo proceso queda esperando hasta que finalice la primera transacción.
* Al continuar, el segundo proceso obtiene el estado actualizado.
* Si el ciclo ya no está en `EN_PROCESO`, el `UPDATE` no modifica ninguna fila.

Esto evita la condición de carrera y garantiza una transición de estado consistente.

---

## 5. Características Modernas y Operación (5 puntos)

### 1. Particionamiento declarativo por rango

El particionamiento por `fecha_hora` es recomendable cuando la tabla `lectura` alcanza grandes volúmenes y las consultas utilizan rangos temporales.

Beneficios:

* **Partition Pruning**.
* Mejor administración de datos históricos.
* Eliminación de períodos completos sin ejecutar `DELETE` masivos.
* Menor impacto al administrar grandes volúmenes.

Ejemplo:

```sql
CREATE TABLE lectura (
    id_lectura     BIGINT GENERATED ALWAYS AS IDENTITY,
    id_ciclo       BIGINT NOT NULL,
    fecha_hora     TIMESTAMPTZ NOT NULL,
    temperatura    NUMERIC(5,2) NOT NULL,
    presion        NUMERIC(4,2) NOT NULL,
    clasificacion  VARCHAR(20) NOT NULL,

    PRIMARY KEY (fecha_hora, id_lectura)
) PARTITION BY RANGE (fecha_hora);
```

Partición mensual:

```sql
CREATE TABLE lectura_2026_m08
PARTITION OF lectura
FOR VALUES FROM ('2026-08-01 00:00:00-05')
             TO ('2026-09-01 00:00:00-05');
```

Para eliminar un período completo:

```sql
DROP TABLE lectura_2026_m08;
```

---

### 2. Mantenimiento y monitoreo en PostgreSQL 18

#### A. Ajuste de Autovacuum

Para tablas con operaciones frecuentes de actualización y eliminación se puede ajustar `autovacuum`:

```sql
ALTER TABLE lectura SET (
    autovacuum_vacuum_scale_factor = 0.02,
    autovacuum_vacuum_threshold = 5000
);
```

Esto permite ejecutar `VACUUM` con mayor frecuencia y controlar el *table bloat*.

#### B. Monitoreo de I/O y mantenimiento de índices

Monitoreo de I/O:

```sql
SELECT *
FROM pg_stat_io;
```

Monitoreo de WAL:

```sql
SELECT *
FROM pg_stat_wal;
```

Reconstrucción de índices con menor impacto sobre la concurrencia:

```sql
REINDEX INDEX CONCURRENTLY idx_lectura_ciclo_fechahora;
```

`REINDEX CONCURRENTLY` permite reconstruir el índice reduciendo el bloqueo sobre las operaciones normales de la base de datos.

---