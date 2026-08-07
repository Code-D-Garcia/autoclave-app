"""
Módulo de persistencia y conexión a PostgreSQL para la aplicación de Autoclaves.
Soporta persistencia de lotes, detección de duplicados, recuperación de historial en UI,
eliminación de BD y modo de degradación elegante (fallback in-memory).
"""

import os
import logging
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

# Cargar automáticamente variables de entorno desde archivo .env si existe
load_dotenv()

from src.models import LotReport

logger = logging.getLogger("autoclave_database")

# Memoria caché en servidor para fallback si PostgreSQL no está conectado
_in_memory_lots: List[Dict[str, Any]] = []

# Configuración de variables de entorno para PostgreSQL
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# Estado de disponibilidad de la base de datos para evitar bloqueos TCP repetidos
_db_available: Optional[bool] = None
_last_db_check_time: float = 0.0

def get_connection(force_recheck: bool = False):
    """Intenta conectar a PostgreSQL de forma optimizada sin bloquear la aplicación si la BD no está disponible."""
    global _db_available, _last_db_check_time
    import time

    now = time.time()
    # Si ya sabemos que PostgreSQL no está disponible y la verificación fue reciente, responder al instante (0ms)
    if not force_recheck and _db_available is False and (now - _last_db_check_time) < 20:
        return None

    try:
        import psycopg2
        conn = psycopg2.connect(
            host=DB_HOST or "127.0.0.1",
            port=DB_PORT or 5432,
            dbname=DB_NAME or "db_autoclave_esterilizacion",
            user=DB_USER or "postgres",
            password=DB_PASSWORD or "postgres",
            connect_timeout=1
        )
        _db_available = True
        _last_db_check_time = now
        return conn
    except Exception as e:
        _db_available = False
        _last_db_check_time = now
        logger.debug(f"PostgreSQL no disponible ({e}). Operando en modo memoria ultrarrápido.")
        return None


def init_db() -> bool:
    """Inicializa las tablas en PostgreSQL si la conexión está disponible."""
    conn = get_connection()
    if not conn:
        return False

    ddl = """
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
    """
    try:
        with conn.cursor() as cur:
            cur.execute(ddl)
        conn.commit()
        conn.close()
        logger.info("Tablas de PostgreSQL inicializadas correctamente.")
        return True
    except Exception as e:
        logger.error(f"Error al inicializar la base de datos: {e}")
        if conn: conn.close()
        return False


def is_lot_registered(lot_id: str) -> bool:
    """
    Verifica si un id_lote ya fue registrado previamente en PostgreSQL o en la memoria del servidor.
    Permite prevenir procesar lotes duplicados.
    """
    if not lot_id:
        return False

    lot_id_str = str(lot_id).strip()

    # 1. Verificar en caché en memoria
    if any(l.get("lot_id") == lot_id_str for l in _in_memory_lots):
        return True

    # 2. Verificar en PostgreSQL si la BD está conectada
    conn = get_connection()
    if not conn:
        return False

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM lote WHERE id_lote = %s;", (lot_id_str,))
            exists = cur.fetchone() is not None
        conn.close()
        return exists
    except Exception as e:
        logger.error(f"Error verificando existencia de lote '{lot_id_str}': {e}")
        if conn: conn.close()
        return False


def save_lot_report(report: LotReport) -> bool:
    """
    Persiste un objeto LotReport procesado en PostgreSQL.
    Mantiene una caché en memoria para fallback.
    """
    report_dict = report.to_dict()

    # Guardar en memoria caché del servidor
    idx = next((i for i, l in enumerate(_in_memory_lots) if l.get("lot_id") == report.lot_id), -1)
    if idx >= 0:
        _in_memory_lots[idx] = report_dict
    else:
        _in_memory_lots.append(report_dict)

    conn = get_connection()
    if not conn:
        return False

    try:
        with conn:
            with conn.cursor() as cur:
                # 1. UPSERT en Lote
                cur.execute("""
                    INSERT INTO lote (id_lote, codigo_lote, producto)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (id_lote) DO UPDATE 
                    SET producto = EXCLUDED.producto;
                """, (report.lot_id, report.lot_id, report.product))

                # 2. Verificar si ya existe ciclo para este lote
                cur.execute("SELECT id_ciclo FROM ciclo_esterilizacion WHERE id_lote = %s;", (report.lot_id,))
                existing = cur.fetchone()

                if existing:
                    id_ciclo = existing[0]
                    cur.execute("""
                        UPDATE ciclo_esterilizacion 
                        SET autoclave_id = %s, inicio = %s, fin = %s, 
                            temp_min_esperada = %s, temp_max_esperada = %s, 
                            presion_min_esperada = %s, presion_max_esperada = %s, 
                            estado = %s
                        WHERE id_ciclo = %s;
                    """, (
                        report.autoclave, report.start_time, report.end_time,
                        report.summary.min_temperature_registered, report.summary.max_temperature_registered,
                        report.summary.min_pressure_registered, report.summary.max_pressure_registered,
                        report.status.value, id_ciclo
                    ))
                    cur.execute("DELETE FROM lectura WHERE id_ciclo = %s;", (id_ciclo,))
                else:
                    cur.execute("""
                        INSERT INTO ciclo_esterilizacion 
                        (id_lote, autoclave_id, inicio, fin, temp_min_esperada, temp_max_esperada, presion_min_esperada, presion_max_esperada, estado)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id_ciclo;
                    """, (
                        report.lot_id, report.autoclave, report.start_time, report.end_time,
                        report.summary.min_temperature_registered, report.summary.max_temperature_registered,
                        report.summary.min_pressure_registered, report.summary.max_pressure_registered,
                        report.status.value
                    ))
                    id_ciclo = cur.fetchone()[0]

                # 3. Insertar lecturas actualizadas
                for r in report.readings:
                    cur.execute("""
                        INSERT INTO lectura (id_ciclo, fecha_hora, temperatura, presion, clasificacion)
                        VALUES (%s, %s, %s, %s, %s);
                    """, (
                        id_ciclo, r.timestamp, r.temperature, r.pressure,
                        r.classification.value if r.classification else 'NORMAL'
                    ))

        conn.close()
        logger.info(f"Lote '{report.lot_id}' guardado en PostgreSQL.")
        return True
    except Exception as e:
        logger.error(f"Error al guardar lote '{report.lot_id}' en PostgreSQL: {e}")
        if conn: conn.close()
        return False


def get_all_stored_lots() -> List[Dict[str, Any]]:
    """
    Retorna la lista de lotes almacenados en PostgreSQL o en memoria.
    Permite reconstruir el estado de la UI al recargar la página.
    """
    conn = get_connection()
    if not conn:
        return _in_memory_lots

    try:
        lots = []
        with conn.cursor() as cur:
            cur.execute("""
                SELECT l.id_lote, l.producto, c.autoclave_id, c.inicio, c.fin, c.estado, c.id_ciclo
                FROM ciclo_esterilizacion c
                JOIN lote l ON c.id_lote = l.id_lote
                ORDER BY c.inicio DESC;
            """)
            ciclos = cur.fetchall()

            for c in ciclos:
                lot_id, producto, autoclave, inicio, fin, estado, id_ciclo = c

                cur.execute("""
                    SELECT fecha_hora, temperatura, presion, clasificacion
                    FROM lectura
                    WHERE id_ciclo = %s
                    ORDER BY fecha_hora ASC;
                """, (id_ciclo,))
                raw_readings = cur.fetchall()

                readings = []
                alerts = []
                ok_count = 0
                temps = []
                press = []

                for r in raw_readings:
                    f_hora, temp, presion_val, clasif = r
                    f_iso = f_hora.isoformat() if hasattr(f_hora, 'isoformat') else str(f_hora)
                    t_val = float(temp)
                    p_val = float(presion_val)
                    temps.append(t_val)
                    press.append(p_val)

                    reading_dict = {
                        "timestamp": f_iso,
                        "temperature": t_val,
                        "pressure": p_val,
                        "classification": clasif
                    }
                    readings.append(reading_dict)

                    if clasif != 'NORMAL':
                        alerts.append({
                            "date": f_iso,
                            "temperature": t_val,
                            "pressure": p_val,
                            "classification": clasif
                        })
                    else:
                        ok_count += 1

                total_r = len(readings)
                avg_t = sum(temps) / total_r if total_r > 0 else 0.0
                avg_p = sum(press) / total_r if total_r > 0 else 0.0
                min_t = min(temps) if temps else 0.0
                max_t = max(temps) if temps else 0.0
                min_p = min(press) if press else 0.0
                max_p = max(press) if press else 0.0
                conf_rate = (ok_count / total_r * 100.0) if total_r > 0 else 0.0

                lots.append({
                    "lot_id": lot_id,
                    "product": producto,
                    "autoclave": autoclave,
                    "start_time": inicio.isoformat() if hasattr(inicio, 'isoformat') else str(inicio),
                    "end_time": fin.isoformat() if hasattr(fin, 'isoformat') else str(fin),
                    "status": estado,
                    "summary": {
                        "total_readings": total_r,
                        "avg_temperature": round(avg_t, 2),
                        "avg_pressure": round(avg_p, 2),
                        "min_temperature_registered": round(min_t, 2),
                        "max_temperature_registered": round(max_t, 2),
                        "min_pressure_registered": round(min_p, 2),
                        "max_pressure_registered": round(max_p, 2),
                        "alert_count": len(alerts),
                        "conformance_rate": round(conf_rate, 2)
                    },
                    "alerts": alerts,
                    "readings": readings
                })

        conn.close()
        return lots
    except Exception as e:
        logger.error(f"Error recuperando lotes almacenados: {e}")
        if conn: conn.close()
        return _in_memory_lots


def clear_all_stored_lots() -> bool:
    """
    Vacía la base de datos PostgreSQL (DELETE FROM lote) y la memoria del servidor.
    Se ejecuta cuando el usuario hace clic en 'Limpiar'.
    """
    global _in_memory_lots
    _in_memory_lots = []

    conn = get_connection()
    if not conn:
        return True

    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM lote;")
        conn.close()
        logger.info("Base de datos y caché en memoria vaciadas correctamente.")
        return True
    except Exception as e:
        logger.error(f"Error limpiando base de datos: {e}")
        if conn: conn.close()
        return False


def _get_in_memory_analytical_summary() -> List[Dict[str, Any]]:
    """Calcula las métricas analíticas agrupadas por autoclave y mes desde la memoria caché."""
    if not _in_memory_lots:
        return []

    groups: Dict[tuple, List[Dict[str, Any]]] = {}
    for lot in _in_memory_lots:
        autoclave = lot.get("autoclave") or "AUT-01"
        start_time = str(lot.get("start_time", ""))
        month = start_time[:7] if len(start_time) >= 7 else "2026-08"
        key = (autoclave, month)
        if key not in groups:
            groups[key] = []
        groups[key].append(lot)

    results = []
    for (autoclave_id, mes), lots_list in sorted(groups.items(), key=lambda x: (x[0][1], x[0][0]), reverse=True):
        lotes_procesados = len(lots_list)
        total_readings = 0
        sum_temp = 0.0
        alerts_out_of_range = 0
        approved_count = 0

        for lot in lots_list:
            if lot.get("status") == "APPROVED":
                approved_count += 1

            for r in lot.get("readings", []):
                total_readings += 1
                sum_temp += float(r.get("temperature", 0.0))
                if r.get("classification") and r.get("classification") != "NORMAL":
                    alerts_out_of_range += 1

        avg_temp = round(sum_temp / total_readings, 2) if total_readings > 0 else 0.0
        pct_approved = round((approved_count / lotes_procesados) * 100.0, 2) if lotes_procesados > 0 else 0.0

        results.append({
            "autoclave_id": autoclave_id,
            "mes": mes,
            "lotes_procesados": lotes_procesados,
            "temperatura_promedio": avg_temp,
            "total_lecturas_fuera_de_rango": alerts_out_of_range,
            "porcentaje_lotes_aprobados": pct_approved
        })

    return results


def get_analytical_summary() -> List[Dict[str, Any]]:
    """
    Ejecuta la Consulta Analítica de la Pregunta 2 en PostgreSQL (o fallback en memoria).
    """
    conn = get_connection()
    if not conn:
        return _get_in_memory_analytical_summary()

    sql = """
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
    """
    try:
        results = []
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
            for row in rows:
                results.append({
                    "autoclave_id": row[0],
                    "mes": row[1],
                    "lotes_procesados": row[2],
                    "temperatura_promedio": float(row[3]) if row[3] else 0.0,
                    "total_lecturas_fuera_de_rango": row[4],
                    "porcentaje_lotes_aprobados": float(row[5]) if row[5] else 0.0
                })
        conn.close()

        if not results and _in_memory_lots:
            return _get_in_memory_analytical_summary()

        return results
    except Exception as e:
        logger.error(f"Error al consultar métricas analíticas: {e}")
        if conn: conn.close()
        return _get_in_memory_analytical_summary()
