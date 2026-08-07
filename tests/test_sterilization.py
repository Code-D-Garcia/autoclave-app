"""
Pruebas automatizadas para el sistema de control de esterilización en autoclaves.
Incluye los 6 casos de prueba requeridos:
1. Caso correcto
2. Fecha inválida
3. Rango inválido
4. Lectura fuera del ciclo
5. Alerta múltiple
6. Cálculo de estado
"""

import pytest
from src.validators import validate_lot_data
from src.processors import process_single_lot, set_lot_status, classify_reading
from src.models import LotStatus, ReadingStatus
from src.exceptions import LoteValidationError, ReadingValidationError


# 1. Caso correcto
def test_caso_correcto():
    payload = {
        "lote_id": "AT-2026-OK",
        "producto": "Atún en aceite 170 g",
        "autoclave": "AUT-01",
        "inicio": "2026-08-01T08:00:00-05:00",
        "fin": "2026-08-01T09:00:00-05:00",
        "temperatura_minima": 116.0,
        "temperatura_maxima": 123.0,
        "presion_minima": 1.20,
        "presion_maxima": 1.80,
        "lecturas": [
            {"fecha_hora": "2026-08-01T08:15:00-05:00", "temperatura": 118.5, "presion": 1.40},
            {"fecha_hora": "2026-08-01T08:30:00-05:00", "temperatura": 120.0, "presion": 1.50}
        ]
    }
    lot = validate_lot_data(payload)
    report = process_single_lot(lot)

    assert report.lot_id == "AT-2026-OK"
    assert report.status == LotStatus.APPROVED
    assert report.summary.alert_count == 0
    assert len(report.readings) == 2


# 2. Fecha inválida
def test_fecha_invalida():
    payload = {
        "lote_id": "AT-2026-BAD-DATE",
        "producto": "Sardinas",
        "autoclave": "AUT-01",
        "inicio": "FECHA-INVALIDA-XYZ",
        "fin": "2026-08-01T09:00:00-05:00",
        "temperatura_minima": 115.0,
        "temperatura_maxima": 122.0,
        "presion_minima": 1.10,
        "presion_maxima": 1.70,
        "lecturas": []
    }
    with pytest.raises(LoteValidationError) as exc_info:
        validate_lot_data(payload)

    assert "no tiene un formato de fecha/hora válido" in str(exc_info.value)


# 3. Rango inválido
def test_rango_invalido():
    payload_temp = {
        "lote_id": "AT-2026-BAD-RANGE",
        "producto": "Sardinas",
        "autoclave": "AUT-01",
        "inicio": "2026-08-01T08:00:00-05:00",
        "fin": "2026-08-01T09:00:00-05:00",
        "temperatura_minima": 130.0,  # Mayor que la máxima
        "temperatura_maxima": 120.0,
        "presion_minima": 1.10,
        "presion_maxima": 1.70,
        "lecturas": []
    }
    with pytest.raises(LoteValidationError) as exc_info:
        validate_lot_data(payload_temp)

    assert "temperatura mínima no puede ser mayor" in str(exc_info.value)


# 4. Lectura fuera del ciclo
def test_lectura_fuera_del_ciclo():
    payload = {
        "lote_id": "AT-2026-OUT-OF-BOUNDS",
        "producto": "Atún",
        "autoclave": "AUT-01",
        "inicio": "2026-08-01T10:00:00-05:00",
        "fin": "2026-08-01T11:00:00-05:00",
        "temperatura_minima": 115.0,
        "temperatura_maxima": 122.0,
        "presion_minima": 1.10,
        "presion_maxima": 1.70,
        "lecturas": [
            {"fecha_hora": "2026-08-01T11:30:00-05:00", "temperatura": 118.0, "presion": 1.30}
        ]
    }
    with pytest.raises(ReadingValidationError) as exc_info:
        validate_lot_data(payload)

    assert "fuera del rango de tiempo del lote" in str(exc_info.value)


# 5. Alerta múltiple
def test_alerta_multiple():
    status = classify_reading(
        temperature=130.0,  # Fuera de rango (>122.0)
        pressure=2.50,      # Fuera de rango (>1.70)
        min_temp=115.0,
        max_temp=122.0,
        min_press=1.10,
        max_press=1.70
    )
    assert status == ReadingStatus.MULTI_ALERT


# 6. Cálculo de estado
def test_calculo_de_estado():
    # 0 Alertas -> APPROVED
    assert set_lot_status(0) == LotStatus.APPROVED

    # 1 o 2 Alertas -> ON_HOLD
    assert set_lot_status(1) == LotStatus.ON_HOLD
    assert set_lot_status(2) == LotStatus.ON_HOLD

    # > 2 Alertas -> REJECTED
    assert set_lot_status(3) == LotStatus.REJECTED
    assert set_lot_status(5) == LotStatus.REJECTED
