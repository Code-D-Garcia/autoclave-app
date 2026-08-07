"""
Modelo de datos para la aplicación 
de control de ciclos de esterilización.

"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any

class ReadingStatus(str, Enum):
    """Enum para representar el estado de la lectura."""
    NORMAL = "NORMAL"
    TEMP_ALERT = "TEMP_ALERT"
    PRESSURE_ALERT = "PRESSURE_ALERT"
    MULTI_ALERT = "MULTI_ALERT"

class LotStatus(str, Enum):
    """Enum para representar el estado del Lote."""
    APPROVED  = "APPROVED"
    ON_HOLD = "ON_HOLD"
    REJECTED = "REJECTED"


@dataclass
class Reading:
    """Clase de la lectura de un ciclo de esterilización."""
    timestamp: datetime
    temperature: float
    pressure: float
    classification: Optional[ReadingStatus] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "temperature": self.temperature,
            "pressure": self.pressure,
            "classification": self.classification.value if self.classification else None
        }

@dataclass
class Lot: 
    lot_id: str
    product: str
    autoclave: str
    start_time: datetime
    end_time: datetime
    min_temperature: float
    max_temperature: float
    min_pressure: float
    max_pressure: float
    readings: List[Reading] = field(default_factory=list)


@dataclass
class LotSummary:
    total_readings: int
    avg_temperature: float
    avg_pressure: float
    min_temperature_registered: float
    max_temperature_registered: float
    min_pressure_registered: float
    max_pressure_registered: float
    alert_count: int
    conformance_rate: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_readings": self.total_readings,
            "avg_temperature": round(self.avg_temperature, 2),
            "avg_pressure": round(self.avg_pressure, 2),
            "min_temperature_registered": round(self.min_temperature_registered, 2),
            "max_temperature_registered": round(self.max_temperature_registered, 2),
            "min_pressure_registered": round(self.min_pressure_registered, 2),
            "max_pressure_registered": round(self.max_pressure_registered, 2),
            "alert_count": self.alert_count,
            "conformance_rate": round(self.conformance_rate, 2)
        }

@dataclass
class AlertDetails:
    date: datetime
    temperature: float
    pressure: float
    classification: ReadingStatus

    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date.isoformat(),
            "temperature": self.temperature,
            "pressure": self.pressure,
            "classification": self.classification.value
        }

@dataclass
class LotReport: 
    lot_id: str
    product: str
    autoclave: str
    start_time: datetime
    end_time: datetime
    status: LotStatus
    summary: LotSummary
    alerts: List[AlertDetails] = field(default_factory=list)
    readings: List[Reading] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lot_id": self.lot_id,
            "product": self.product,
            "autoclave": self.autoclave,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "status": self.status.value,
            "summary": self.summary.to_dict(),
            "alerts": [alert.to_dict() for alert in self.alerts],
            "readings": [reading.to_dict() for reading in self.readings]
        }