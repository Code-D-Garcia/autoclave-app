"""
Módulo de validación flexible para los datos de entrada de esterilización.
Soporta mapeo de claves en español e inglés y múltiples formatos de fecha.
"""

from datetime import datetime
from math import isfinite
from typing import Dict, Any, List, Optional

from src.exceptions import LoteValidationError, ReadingValidationError
from src.models import Lot, Reading


def get_field_value(data: Dict[str, Any], aliases: List[str]) -> Optional[Any]:
    """Obtiene el valor de un diccionario buscando entre una lista de alias de claves."""
    for alias in aliases:
        if alias in data and data[alias] is not None:
            return data[alias]
    return None


def parse_datetime(dt_str: str, field_name: str, lot_id: str) -> datetime:
    """
    Convierte una cadena de fecha y hora en un objeto datetime.
    Soporta formatos ISO 8601 y formatos comunes adicionales.
    """
    if not isinstance(dt_str, str) or not dt_str.strip():
        raise LoteValidationError(
            lot_id,
            message=f"El campo '{field_name}' es obligatorio y debe ser una cadena no vacía."
        )

    dt_clean = dt_str.strip()
    if dt_clean.endswith("Z"):
        dt_clean = dt_clean[:-1] + "+00:00"

    try:
        return datetime.fromisoformat(dt_clean)
    except ValueError:
        pass

    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(dt_clean, fmt)
        except ValueError:
            pass

    raise LoteValidationError(
        lot_id,
        message=f"El campo '{field_name}' ('{dt_str}') no tiene un formato de fecha/hora válido (ej. ISO 8601 YYYY-MM-DDTHH:MM:SS)."
    )


def validate_lot_data(dat: Dict[str, Any]) -> Lot:
    """
    Valida los datos de un lote y sus lecturas, tolerando variaciones en nombres de campos.
    """
    if not isinstance(dat, dict):
        raise LoteValidationError("DESCONOCIDO", "El lote debe ser un objeto JSON.")

    # 1. lot_id
    lot_id_val = get_field_value(dat, ["lot_id", "id_lote", "lote_id", "id", "lotId"])
    if not lot_id_val or not str(lot_id_val).strip():
        raise LoteValidationError("DESCONOCIDO", "El campo 'lot_id' (o 'id_lote') es obligatorio.")
    lot_id = str(lot_id_val).strip()

    # 2. product
    product_val = get_field_value(dat, ["product", "producto", "item", "product_name"])
    if not product_val or not str(product_val).strip():
        raise LoteValidationError(lot_id, "El campo 'product' (o 'producto') es obligatorio.")
    product = str(product_val).strip()

    # 3. autoclave
    autoclave_val = get_field_value(dat, ["autoclave", "equipo", "machine", "autoclave_id"])
    if not autoclave_val or not str(autoclave_val).strip():
        raise LoteValidationError(lot_id, "El campo 'autoclave' (o 'equipo') es obligatorio.")
    autoclave = str(autoclave_val).strip()

    # 4. min_temperature / max_temperature / min_pressure / max_pressure
    min_temp_val = get_field_value(dat, ["min_temperature", "min_temp", "temperatura_minima", "temp_min"])
    max_temp_val = get_field_value(dat, ["max_temperature", "max_temp", "temperatura_maxima", "temp_max"])
    min_press_val = get_field_value(dat, ["min_pressure", "min_press", "presion_minima", "press_min"])
    max_press_val = get_field_value(dat, ["max_pressure", "max_press", "presion_maxima", "press_max"])

    for name, val in [("min_temperature", min_temp_val), ("max_temperature", max_temp_val),
                      ("min_pressure", min_press_val), ("max_pressure", max_press_val)]:
        if val is None:
            raise LoteValidationError(lot_id, f"El campo '{name}' es obligatorio.")

    try:
        min_temp = float(min_temp_val)
        max_temp = float(max_temp_val)
        min_press = float(min_press_val)
        max_press = float(max_press_val)
    except (ValueError, TypeError) as exc:
        raise LoteValidationError(lot_id, "Los campos de temperatura y presión deben ser números válidos.") from exc

    if not all(isfinite(v) for v in [min_temp, max_temp, min_press, max_press]):
        raise LoteValidationError(lot_id, "Los valores de temperatura y presión deben ser números finitos.")

    if min_temp > max_temp:
        raise LoteValidationError(lot_id, "La temperatura mínima no puede ser mayor que la máxima.")
    if min_press > max_press:
        raise LoteValidationError(lot_id, "La presión mínima no puede ser mayor que la máxima.")

    # 5. start_time & end_time
    start_str = get_field_value(dat, ["start_time", "inicio", "fecha_inicio", "start", "startTime"])
    end_str = get_field_value(dat, ["end_time", "fin", "fecha_fin", "end", "endTime"])

    if not start_str:
        raise LoteValidationError(lot_id, "El campo 'start_time' (o 'fecha_inicio') es obligatorio.")
    if not end_str:
        raise LoteValidationError(lot_id, "El campo 'end_time' (o 'fecha_fin') es obligatorio.")

    start_time = parse_datetime(str(start_str), "start_time", lot_id)
    end_time = parse_datetime(str(end_str), "end_time", lot_id)

    if start_time >= end_time:
        raise LoteValidationError(lot_id, "El 'start_time' debe ser anterior al 'end_time'.")

    # 6. readings
    raw_readings = get_field_value(dat, ["readings", "lecturas", "data", "telemetry"])
    if not isinstance(raw_readings, list):
        raise LoteValidationError(lot_id, "El campo 'readings' (o 'lecturas') debe ser una lista de lecturas.")

    readings_parsed: List[Reading] = []

    for idx, reading in enumerate(raw_readings):
        if not isinstance(reading, dict):
            raise ReadingValidationError(lot_id, "DESCONOCIDO", f"La lectura en la posición {idx} debe ser un objeto JSON.")

        date_str = get_field_value(reading, ["timestamp", "fecha_hora", "date", "time", "fecha"])
        temp_val = get_field_value(reading, ["temperature", "temperatura", "temp", "t"])
        press_val = get_field_value(reading, ["pressure", "presion", "press", "p"])

        if not date_str:
            raise ReadingValidationError(lot_id, "DESCONOCIDO", f"El campo 'timestamp' (o 'fecha_hora') es obligatorio en la lectura #{idx + 1}.")
        if temp_val is None or press_val is None:
            raise ReadingValidationError(lot_id, str(date_str), f"Los campos 'temperature' y 'pressure' son obligatorios en la lectura #{idx + 1}.")

        date_time = parse_datetime(str(date_str), "timestamp", lot_id)

        try:
            temp = float(temp_val)
            press = float(press_val)
        except (ValueError, TypeError) as exc:
            raise ReadingValidationError(lot_id, str(date_str), f"Temperatura y presión deben ser números válidos en lectura #{idx + 1}.") from exc

        if not isfinite(temp) or not isfinite(press):
            raise ReadingValidationError(lot_id, str(date_str), f"Valores de temperatura y presión deben ser finitos en lectura #{idx + 1}.")

        if not (start_time <= date_time <= end_time):
            raise ReadingValidationError(
                lot_id,
                str(date_str),
                f"La lectura ({date_str}) está fuera del rango de tiempo del lote [{start_time.isoformat()} - {end_time.isoformat()}]."
            )

        readings_parsed.append(Reading(timestamp=date_time, temperature=temp, pressure=press))

    return Lot(
        lot_id=lot_id,
        product=product,
        autoclave=autoclave,
        start_time=start_time,
        end_time=end_time,
        min_temperature=min_temp,
        max_temperature=max_temp,
        min_pressure=min_press,
        max_pressure=max_press,
        readings=readings_parsed
    )