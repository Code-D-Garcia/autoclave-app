"""
Servicio principal de orquestación para 
procesamiento de ciclos de esterilización.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from src.exceptions import SterilizationDomainError, InvalidJSONDataError
from src.validators import validate_lot_data
from src.processors import process_single_lot
from src.models import LotReport

logger = logging.getLogger("esterilization_service")

def configure_logging(level: int = logging.INFO) -> None:
    """Configura el sistema de logging para el servicio."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

class SterilizationService:
    """
    Servicio principal para la orquestación del procesamiento de ciclos de esterilización.
    """

    def __init__(self, log_level: int = logging.INFO):
        configure_logging(log_level)
        self.logger = logging.getLogger(self.__class__.__name__)

    def process_data(self, data: Any) -> Dict[str, Any]:
        """
        Procesa datos JSON (objeto con 'lotes'/'lots', lista de lotes, o lote individual).
        Valida y procesa cada lote, recopilando errores descriptivos individualmente.
        """

        raw_lots = []
        if isinstance(data, list):
            raw_lots = data
        elif isinstance(data, dict):
            if "lotes" in data and isinstance(data["lotes"], list):
                raw_lots = data["lotes"]
            elif "lots" in data and isinstance(data["lots"], list):
                raw_lots = data["lots"]
            elif any(k in data for k in ["lot_id", "id_lote", "product", "producto"]):
                raw_lots = [data]
            else:
                raise InvalidJSONDataError("El archivo JSON debe ser un objeto con la clave 'lotes' (o 'lots'), una lista de lotes, o un lote individual.")
        else:
            raise InvalidJSONDataError("Estructura de archivo JSON no válida.")

        reports: List[LotReport] = []
        lot_errors: List[Dict[str, Any]] = []

        self.logger.info(f"Procesando {len(raw_lots)} lotes.")

        for idx, item in enumerate(raw_lots):
            lot_id = item.get("lot_id") or item.get("id_lote") if isinstance(item, dict) else f"Índice {idx}"
            if not lot_id:
                lot_id = f"Lote #{idx + 1}"
                
            try:
                lot_parsed = validate_lot_data(item)
                report = process_single_lot(lot_parsed)
                reports.append(report)
                self.logger.info(
                    "Lote '%s' procesado con éxito. Estado: %s, Alertas: %d",
                    report.lot_id,
                    report.status.value,
                    report.summary.alert_count)
            except SterilizationDomainError as e:
                self.logger.error("Error procesando lote '%s': %s", lot_id, str(e))
                lot_errors.append({
                    "lot_id": str(lot_id),
                    "error": str(e)
                })
            except Exception as e:
                self.logger.exception("Error inesperado procesando lote '%s': %s", lot_id, str(e))
                lot_errors.append({
                    "lot_id": str(lot_id),
                    "error": f"Error inesperado: {str(e)}"
                })
            
        reports.sort(key=lambda r: r.start_time)

        result = {
            "total_processed_lots": len(reports),
            "total_failed_lots": len(lot_errors),
            "Lots": [report.to_dict() for report in reports],
        }

        if lot_errors:
            result["errors"] = lot_errors

        self.logger.info(
            "Procesamiento finalizado. Lotes procesados: %d, Lotes con errores: %d",
            len(reports),
            len(lot_errors)
        )

        return result

    def process_file(self, input_filepath: str, output_filepath: Optional[str] = None) -> None:
        try:
            with open(input_filepath, 'r', encoding='utf-8') as infile:
                data = json.load(infile)
            self.logger.info("Archivo '%s' cargado correctamente.", input_filepath)

            result = self.process_data(data)

            if output_filepath:
                with open(output_filepath, 'w', encoding='utf-8') as outfile:
                    json.dump(result, outfile, ensure_ascii=False, indent=4)
                self.logger.info("Resultado guardado en '%s'.", output_filepath)
        except Exception as e:
            self.logger.exception("Error al procesar el archivo '%s': %s", input_filepath, str(e))