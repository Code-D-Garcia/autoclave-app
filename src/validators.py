"""
Módulo de validación para los
datos de entrada de esterilización.
"""

from datetime import datetime
from math import isfinite
from typing import Dict, Any, List

from src.exceptions import LoteValidationError, ReadingValidationError
from src.models import Lot, Reading


MANDATORY_LOT_FIELDS = [
    "lot_id",
    "product",
    "autoclave",
    "start_time",
    "end_time",
    "min_temperature",
    "max_temperature",
    "min_pressure",
    "max_pressure",
    "readings"
]

MANDATORY_READING_FIELDS = [
    "timestamp",
    "temperature",
    "pressure"
]


def parse_datetime(
    dt_str: str,
    field_name: str,
    lot_id: str
) -> datetime:
    """
    Convierte una cadena de fecha y hora en un objeto datetime.

    Args:
        dt_str (str): La cadena de fecha y hora a convertir.
        field_name (str): El nombre del campo para mensajes de error.
        lot_id (str): El ID del lote para mensajes de error.

    Returns:
        datetime: El objeto datetime correspondiente.

    Raises:
        LoteValidationError: Si la cadena no tiene un formato válido.
    """

    if not isinstance(dt_str, str) or not dt_str.strip():
        raise LoteValidationError(
            lot_id,
            message=(
                f"El campo '{field_name}' es obligatorio "
                "y debe ser una cadena no vacía."
            )
        )

    try:
        return datetime.fromisoformat(dt_str)
    except ValueError as exc:
        raise LoteValidationError(
            lot_id,
            message=(
                f"El campo '{field_name}' debe tener "
                "un formato ISO 8601 válido."
            )
        ) from exc


def validate_lot_data(dat: Dict[str, Any]) -> Lot:
    """
    Valida los datos de un lote y sus lecturas.

    Args:
        dat (Dict[str, Any]): Diccionario con los datos del lote.

    Returns:
        Lot: Objeto Lot validado.

    Raises:
        LoteValidationError:
            Si los datos del lote no cumplen con las reglas de validación.
        ReadingValidationError:
            Si alguna lectura no cumple con las reglas de validación.
    """

    if not isinstance(dat, dict):
        raise LoteValidationError(
            "DESCONOCIDO",
            "El lote debe ser un objeto JSON."
        )

    lot_id = dat.get("lot_id")

    if not isinstance(lot_id, str) or not lot_id.strip():
        raise LoteValidationError(
            "DESCONOCIDO",
            "El campo 'lot_id' es obligatorio."
        )

    lot_id = lot_id.strip()

    # Validación de campos obligatorios del lote
    for field in MANDATORY_LOT_FIELDS:
        value = dat.get(field)

        if value is None or (
            isinstance(value, str) and not value.strip()
        ):
            raise LoteValidationError(
                lot_id,
                f"El campo '{field}' es obligatorio."
            )

    # Validación de límites de temperatura y presión
    try:
        min_temp = float(dat["min_temperature"])
        max_temp = float(dat["max_temperature"])
        min_press = float(dat["min_pressure"])
        max_press = float(dat["max_pressure"])
    except (ValueError, TypeError) as exc:
        raise LoteValidationError(
            lot_id,
            "Los campos de temperatura y presión "
            "deben ser números válidos."
        ) from exc

    if not all(
        isfinite(value)
        for value in [
            min_temp,
            max_temp,
            min_press,
            max_press
        ]
    ):
        raise LoteValidationError(
            lot_id,
            "Los valores de temperatura y presión "
            "deben ser números finitos."
        )

    if min_temp > max_temp:
        raise LoteValidationError(
            lot_id,
            "La temperatura mínima no puede ser mayor que la máxima."
        )

    if min_press > max_press:
        raise LoteValidationError(
            lot_id,
            "La presión mínima no puede ser mayor que la máxima."
        )

    # Validación de fechas del lote
    start_time = parse_datetime(
        dat["start_time"],
        "start_time",
        lot_id
    )

    end_time = parse_datetime(
        dat["end_time"],
        "end_time",
        lot_id
    )

    if start_time >= end_time:
        raise LoteValidationError(
            lot_id,
            "El 'start_time' debe ser anterior al 'end_time'."
        )

    # Validación de lecturas
    raw_readings = dat["readings"]

    if not isinstance(raw_readings, list):
        raise LoteValidationError(
            lot_id,
            "El campo 'readings' debe ser una lista de lecturas."
        )

    readings_parsed: List[Reading] = []

    for idx, reading in enumerate(raw_readings):

        if not isinstance(reading, dict):
            raise ReadingValidationError(
                lot_id,
                "DESCONOCIDO",
                (
                    f"La lectura en la posición {idx} "
                    "debe ser un objeto JSON."
                )
            )

        # Validación de campos obligatorios de la lectura
        for field_name in MANDATORY_READING_FIELDS:
            value = reading.get(field_name)

            if value is None or (
                isinstance(value, str) and not value.strip()
            ):
                raise ReadingValidationError(
                    lot_id,
                    "DESCONOCIDO",
                    (
                        f"El campo '{field_name}' es obligatorio "
                        f"en la lectura en la posición {idx}."
                    )
                )

        # Validación de timestamp
        date_str = reading["timestamp"]

        date_time = parse_datetime(
            date_str,
            "timestamp",
            lot_id
        )

        # Validación de temperatura y presión
        try:
            temp = float(reading["temperature"])
            press = float(reading["pressure"])
        except (ValueError, TypeError) as exc:
            raise ReadingValidationError(
                lot_id,
                date_str,
                (
                    "Los campos 'temperature' y 'pressure' "
                    "deben ser números válidos."
                )
            ) from exc

        if not isfinite(temp) or not isfinite(press):
            raise ReadingValidationError(
                lot_id,
                date_str,
                (
                    "Los valores de 'temperature' y 'pressure' "
                    "deben ser números finitos."
                )
            )

        # Validación del rango temporal
        if not (start_time <= date_time <= end_time):
            raise ReadingValidationError(
                lot_id,
                date_str,
                (
                    "La lectura debe estar dentro del rango "
                    "de tiempo del lote."
                )
            )

        readings_parsed.append(
            Reading(
                timestamp=date_time,
                temperature=temp,
                pressure=press
            )
        )

    return Lot(
        lot_id=lot_id,
        product=str(dat["product"]).strip(),
        autoclave=str(dat["autoclave"]).strip(),
        start_time=start_time,
        end_time=end_time,
        min_temperature=min_temp,
        max_temperature=max_temp,
        min_pressure=min_press,
        max_pressure=max_press,
        readings=readings_parsed
    )