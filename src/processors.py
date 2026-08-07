"""
Módulo de procesamiento de lecturas, 
cálculo de estadísticas y clasificación de lotes.
"""

from typing import List, Tuple
from src.models import (
    Reading,
    Lot,
    ReadingStatus,
    LotStatus,
    LotSummary,
    AlertDetails,
    LotReport
)


def classify_reading(
    temperature: float,
    pressure: float,
    min_temp: float,
    max_temp: float,
    min_press: float,
    max_press: float
) -> ReadingStatus:
    """
    Clasifica una lectura basada en los valores de temperatura y presión.
    
    Args:
        temperature (float): La temperatura de la lectura.
        pressure (float): La presión de la lectura.
        min_temp (float): La temperatura mínima permitida.
        max_temp (float): La temperatura máxima permitida.
        min_press (float): La presión mínima permitida.
        max_press (float): La presión máxima permitida.
    
    Returns:
        ReadingStatus: El estado de la lectura (NORMAL, ALERTA, CRÍTICA).
    """
    temp_ok = temp_min <= temperature <= temp_max
    press_ok = press_min <= pressure <= press_max

    if temp_ok and press_ok:
        return ReadingStatus.NORMAL
    elif not temp_ok and press_ok:
        return ReadingStatus.TEMP_ALERT
    elif temp_ok and not press_ok:
        return ReadingStatus.PRESSURE_ALERT
    else:
        return ReadingStatus.MULTI_ALERT
    

def set_lot_status(alert_counts: int) -> LotStatus:
    """
    Determina el estado del lote basado en la cantidad de alertas.
    
    Args:
        alert_counts (int): La cantidad de alertas encontradas en las lecturas.

    Returns:
        LotStatus: El estado del lote (APROBADO, OBSERVADO, RECHAZADO).
    """
    if alert_counts == 0:
        return LotStatus.APPROVED
    elif alert_counts in (1,2):
        return LotStatus.ON_HOLD
    else:
        return LotStatus.REJECTED


def calculate_lot_summary(lot: Lot) -> Tuple[LotSummary, List[AlertDetails]]:
    """
    Calcula un resumen del lote y genera detalles de alertas.
    
    Args:
        lot (Lot): El lote a procesar.
    
    Returns:
        Tuple[LotSummary, List[AlertDetails]]: Un resumen del lote y una lista de detalles de alertas.
    """

    total_readings = len(lot.readings)
    if total_readings == 0:
        summary = LotSummary(
            total_readings=0,
            avg_temperature=0.0,
            avg_pressure=0.0,
            min_temperature_registered=0.0,
            max_temperature_registered=0.0,
            min_pressure_registered=0.0,
            max_pressure_registered=0.0,
            alert_count=0,
            conformance_rate=0.0
        )
        return summary, []


    temperatures = [r.temperature for r in lot.readings]
    pressures = [r.pressure for r in lot.readings]

    list_alerts: List[AlertDetails] = []
    ok_readings = 0

    for r in lot.readings:
        classification = classify_reading(
            r.temperature,
            r.pressure,
            lot.min_temperature,
            lot.max_temperature,
            lot.min_pressure,
            lot.max_pressure
        )
        r.classification = classification

        if classification == ReadingStatus.NORMAL:
            ok_readings += 1
        else:
            list_alerts.append(AlertDetails(
                timestamp=r.timestamp,
                temperature=r.temperature,
                pressure=r.pressure,
                classification=classification
            ))

    alert_count = len(list_alerts)
    conformance_rate = (ok_readings / total_readings) * 100

    summary = LotSummary(
        total_readings=total_readings,
        avg_temperature=sum(temperatures) / total_readings,
        avg_pressure=sum(pressures) / total_readings,
        min_temperature_registered=min(temperatures),
        max_temperature_registered=max(temperatures),
        min_pressure_registered=min(pressures),
        max_pressure_registered=max(pressures),
        alert_count=alert_count,
        conformance_rate=conformance_rate
    )
    
    return summary, list_alerts

def process_single_lot(lot: Lot) -> LotReport:
    """
    Procesa un lote individual, calculando su resumen y estado.
    
    Args:
        lot (Lot): El lote a procesar.

    Returns:
        LotReport: Un informe detallado del lote, incluyendo su resumen y alertas.
    """
    summary, alerts = calculate_lot_summary(lot)
    status = set_lot_status(summary.alert_count)

    return LotReport(
        lot_id=lot.lot_id,
        product=lot.product,
        autoclave=lot.autoclave,
        start_time=lot.start_time,
        end_time=lot.end_time,
        status=status,
        summary=summary,
        alerts=alerts
    )