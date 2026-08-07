-- =============================================================================
-- SCRIPT DE VERIFICACIÓN Y PRUEBA DE RESPUESTAS POSTGRESQL
-- =============================================================================
-- NOTA DE EJECUCIÓN EN PGADMIN:
-- 1. Para crear una base de datos nueva se debe ejecutar primero la siguiente línea:
--    CREATE DATABASE db_autoclave_esterilizacion;
-- 2. Conéctate a la nueva base de datos 'db_autoclave_esterilizacion' en pgAdmin.
-- 3. Abre el Query Tool en esa base de datos y ejecuta todo este script (F5) O ejecutar por parte para mejor comprensión.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 0. CREACIÓN DE LA BASE DE DATOS (OPCIONAL)
-- -----------------------------------------------------------------------------
-- CREATE DATABASE db_autoclave_esterilizacion;

-- -----------------------------------------------------------------------------
-- 1. LIMPIEZA E INICIALIZACIÓN DEL ESQUEMA
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS lectura_particionada CASCADE;
DROP TABLE IF EXISTS lectura CASCADE;
DROP TABLE IF EXISTS ciclo_esterilizacion CASCADE;
DROP TABLE IF EXISTS lote CASCADE;

-- -----------------------------------------------------------------------------
-- 2. CREACIÓN DE TABLAS E INTEGRIDAD DE DATOS (PREGUNTA 1)
-- -----------------------------------------------------------------------------

-- Tabla LOTE
CREATE TABLE lote (
    id_lote         VARCHAR(50) PRIMARY KEY,
    codigo_lote     VARCHAR(50) NOT NULL UNIQUE,
    producto        VARCHAR(150) NOT NULL,
    creado_en       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Tabla CICLO_ESTERILIZACION
CREATE TABLE ciclo_esterilizacion (
    id_ciclo              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_lote               VARCHAR(50) NOT NULL REFERENCES lote(id_lote) 
                          ON DELETE CASCADE ON UPDATE CASCADE,
    autoclave_id          VARCHAR(50) NOT NULL,
    inicio                TIMESTAMPTZ NOT NULL,
    fin                   TIMESTAMPTZ NOT NULL,
    temp_min_esperada     NUMERIC(5,2) NOT NULL,
    temp_max_esperada     NUMERIC(5,2) NOT NULL,
    presion_min_esperada  NUMERIC(4,2) NOT NULL,
    presion_max_esperada  NUMERIC(4,2) NOT NULL,
    estado                VARCHAR(20) NOT NULL DEFAULT 'EN_PROCESO',

    CONSTRAINT chk_ciclo_fechas CHECK (fin > inicio),
    CONSTRAINT chk_ciclo_temp CHECK (temp_max_esperada >= temp_min_esperada AND temp_min_esperada > 0),
    CONSTRAINT chk_ciclo_presion CHECK (presion_max_esperada >= presion_min_esperada AND presion_min_esperada >= 0),
    CONSTRAINT chk_ciclo_estado CHECK (estado IN ('EN_PROCESO', 'APPROVED', 'ON_HOLD', 'REJECTED'))
);

-- Tabla LECTURA
CREATE TABLE lectura (
    id_lectura     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_ciclo       BIGINT NOT NULL REFERENCES ciclo_esterilizacion(id_ciclo) 
                   ON DELETE CASCADE ON UPDATE CASCADE,
    fecha_hora     TIMESTAMPTZ NOT NULL,
    temperatura    NUMERIC(5,2) NOT NULL,
    presion        NUMERIC(4,2) NOT NULL,
    clasificacion  VARCHAR(20) NOT NULL DEFAULT 'NORMAL',

    CONSTRAINT chk_lectura_clasificacion CHECK (clasificacion IN ('NORMAL', 'TEMP_ALERT', 'PRESSURE_ALERT', 'MULTI_ALERT')),
    CONSTRAINT uq_lectura_ciclo_instante UNIQUE (id_ciclo, fecha_hora)
);

-- -----------------------------------------------------------------------------
-- 3. POBLADO DE DATOS DE PRUEBA
-- -----------------------------------------------------------------------------

-- Insertar Lotes
INSERT INTO lote (id_lote, codigo_lote, producto) VALUES
('AT-2026-0001', 'COD-001', 'Atún en aceite 170 g'),
('AT-2026-0002', 'COD-002', 'Sardinas en salsa de tomate 425 g'),
('AT-2026-0003', 'COD-003', 'Lomitos de atún en agua 170 g');

-- Insertar Ciclos de Esterilización
INSERT INTO ciclo_esterilizacion 
(id_lote, autoclave_id, inicio, fin, temp_min_esperada, temp_max_esperada, presion_min_esperada, presion_max_esperada, estado)
VALUES
('AT-2026-0001', 'AUT-03', '2026-08-01 08:00:00-05', '2026-08-01 09:15:00-05', 116.0, 123.0, 1.20, 1.80, 'APPROVED'),
('AT-2026-0002', 'AUT-01', '2026-08-01 10:00:00-05', '2026-08-01 11:30:00-05', 115.0, 122.0, 1.10, 1.70, 'ON_HOLD'),
('AT-2026-0003', 'AUT-02', '2026-08-01 12:00:00-05', '2026-08-01 13:30:00-05', 116.0, 123.0, 1.20, 1.80, 'REJECTED');

-- Insertar Lecturas utilizando subconsultas seguras por id_lote
INSERT INTO lectura (id_ciclo, fecha_hora, temperatura, presion, clasificacion) VALUES
((SELECT id_ciclo FROM ciclo_esterilizacion WHERE id_lote = 'AT-2026-0001'), '2026-08-01 08:10:00-05', 117.2, 1.35, 'NORMAL'),
((SELECT id_ciclo FROM ciclo_esterilizacion WHERE id_lote = 'AT-2026-0001'), '2026-08-01 08:20:00-05', 121.0, 1.62, 'NORMAL'),
((SELECT id_ciclo FROM ciclo_esterilizacion WHERE id_lote = 'AT-2026-0001'), '2026-08-01 08:30:00-05', 119.5, 1.50, 'NORMAL'),

((SELECT id_ciclo FROM ciclo_esterilizacion WHERE id_lote = 'AT-2026-0002'), '2026-08-01 10:15:00-05', 118.0, 1.30, 'NORMAL'),
((SELECT id_ciclo FROM ciclo_esterilizacion WHERE id_lote = 'AT-2026-0002'), '2026-08-01 10:30:00-05', 123.5, 1.40, 'TEMP_ALERT'),
((SELECT id_ciclo FROM ciclo_esterilizacion WHERE id_lote = 'AT-2026-0002'), '2026-08-01 10:45:00-05', 119.0, 1.85, 'PRESSURE_ALERT'),

((SELECT id_ciclo FROM ciclo_esterilizacion WHERE id_lote = 'AT-2026-0003'), '2026-08-01 12:15:00-05', 114.0, 1.10, 'TEMP_ALERT'),
((SELECT id_ciclo FROM ciclo_esterilizacion WHERE id_lote = 'AT-2026-0003'), '2026-08-01 12:30:00-05', 125.0, 1.30, 'TEMP_ALERT'),
((SELECT id_ciclo FROM ciclo_esterilizacion WHERE id_lote = 'AT-2026-0003'), '2026-08-01 12:45:00-05', 118.0, 2.00, 'PRESSURE_ALERT');

-- -----------------------------------------------------------------------------
-- 4. DEMOSTRACIÓN DE CONSULTAS ANALÍTICAS (PREGUNTA 2 Y REQUERIMIENTO)
-- -----------------------------------------------------------------------------

-- 4.1. Consulta 1: Lotes con alertas, cantidad de alertas y mayor desviación de temperatura
SELECT 
    lo.id_lote,
    lo.producto,
    c.autoclave_id,
    COUNT(l.id_lectura) FILTER (WHERE l.clasificacion != 'NORMAL') AS cantidad_alertas,
    ROUND(MAX(GREATEST(0, l.temperatura - c.temp_max_esperada, c.temp_min_esperada - l.temperatura)), 2) AS mayor_desviacion_temperatura
FROM lote lo
JOIN ciclo_esterilizacion c ON lo.id_lote = c.id_lote
JOIN lectura l ON c.id_ciclo = l.id_ciclo
WHERE l.clasificacion != 'NORMAL'
GROUP BY lo.id_lote, lo.producto, c.autoclave_id
ORDER BY cantidad_alertas DESC, mayor_desviacion_temperatura DESC;

-- 4.2. Consulta 2: Resumen mensual por autoclave (% de aprobación y promedios)
SELECT 
    c.autoclave_id,
    TO_CHAR(DATE_TRUNC('month', c.inicio), 'YYYY-MM') AS mes,
    COUNT(DISTINCT c.id_ciclo) AS lotes_procesados,
    ROUND(AVG(l.temperatura), 2) AS temperatura_promedio,
    COUNT(l.id_lectura) FILTER (WHERE l.clasificacion != 'NORMAL') AS total_lecturas_fuera_de_rango,
    ROUND(
        (COUNT(DISTINCT CASE WHEN c.estado = 'APPROVED' THEN c.id_ciclo END)::NUMERIC 
        / NULLIF(COUNT(DISTINCT c.id_ciclo), 0)) * 100, 
        2
    ) AS porcentaje_lotes_aprobados
FROM ciclo_esterilizacion c
LEFT JOIN lectura l ON c.id_ciclo = l.id_ciclo
GROUP BY c.autoclave_id, DATE_TRUNC('month', c.inicio)
ORDER BY mes DESC, c.autoclave_id ASC;

-- -----------------------------------------------------------------------------
-- 5. CREACIÓN DE ÍNDICES Y PLAN DE EJECUCIÓN (PREGUNTA 3)
-- -----------------------------------------------------------------------------
-- Índices para búsquedas eficientes por Lote, Autoclave y Rango de Fechas
CREATE INDEX IF NOT EXISTS idx_ciclo_id_lote ON ciclo_esterilizacion (id_lote);
CREATE INDEX IF NOT EXISTS idx_ciclo_autoclave_inicio ON ciclo_esterilizacion (autoclave_id, inicio DESC);
CREATE INDEX IF NOT EXISTS idx_lectura_fechahora_ciclo ON lectura (fecha_hora DESC, id_ciclo);

EXPLAIN (ANALYZE, BUFFERS)
SELECT l.fecha_hora, l.temperatura, l.presion
FROM ciclo_esterilizacion c
JOIN lectura l ON c.id_ciclo = l.id_ciclo
WHERE c.autoclave_id = 'AUT-01'
  AND l.fecha_hora >= '2026-08-01 00:00:00-05'
ORDER BY l.fecha_hora DESC;

-- -----------------------------------------------------------------------------
-- 6. SIMULACIÓN DE CONCURRENCIA Y BLOQUEO PESIMISTA (PREGUNTA 4)
-- -----------------------------------------------------------------------------
DO $$
DECLARE
    v_estado VARCHAR(20);
    v_id BIGINT;
BEGIN
    SELECT id_ciclo INTO v_id FROM ciclo_esterilizacion WHERE id_lote = 'AT-2026-0001';

    -- Simular la primera transacción que bloquea la fila con FOR UPDATE
    SELECT estado INTO v_estado
    FROM ciclo_esterilizacion
    WHERE id_ciclo = v_id
    FOR UPDATE;

    RAISE NOTICE 'Estado del ciclo % antes del cierre: %', v_id, v_estado;

    -- Actualizar a estado cerrado
    UPDATE ciclo_esterilizacion
    SET estado = 'APPROVED'
    WHERE id_ciclo = v_id AND estado = 'EN_PROCESO';

    RAISE NOTICE 'Transacción ejecutada con éxito mediante bloqueo FOR UPDATE.';
END $$;

-- -----------------------------------------------------------------------------
-- 7. PARTICIONAMIENTO DECLARATIVO POR RANGO (PREGUNTA 5)
-- -----------------------------------------------------------------------------
CREATE TABLE lectura_particionada (
    id_lectura     BIGINT GENERATED ALWAYS AS IDENTITY,
    id_ciclo       BIGINT NOT NULL,
    fecha_hora     TIMESTAMPTZ NOT NULL,
    temperatura    NUMERIC(5,2) NOT NULL,
    presion        NUMERIC(4,2) NOT NULL,
    clasificacion  VARCHAR(20) NOT NULL,
    PRIMARY KEY (fecha_hora, id_lectura)
) PARTITION BY RANGE (fecha_hora);

-- Crear partición mensual para Agosto 2026
CREATE TABLE lectura_y2026m08 PARTITION OF lectura_particionada
    FOR VALUES FROM ('2026-08-01 00:00:00-05') TO ('2026-09-01 00:00:00-05');

-- Insertar lectura de prueba en la partición
INSERT INTO lectura_particionada (id_ciclo, fecha_hora, temperatura, presion, clasificacion)
VALUES (1, '2026-08-01 08:30:00-05', 120.0, 1.50, 'NORMAL');

-- Verificar Partition Pruning con EXPLAIN
EXPLAIN SELECT * FROM lectura_particionada WHERE fecha_hora = '2026-08-01 08:30:00-05';
