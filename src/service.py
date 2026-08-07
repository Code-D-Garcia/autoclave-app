"""
Servicio principal de orquestación para procesamiento de ciclos de esterilización.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from src.exceptions import SterilizationDomainError, InvalidJSONDataError
from src.validators import validate_lote_data
from src.processors import process_single_lote
from src.models import LotReport

logger = logging.getLogger("esterilization_service")

def configure_logging(level: int = logging.INFO) -> None:
    """
    Configura el sistema de logging para el servicio.

    Args:
        level (int): Nivel de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    """
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

    def process_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Procesa el diccionario cargado desde JSON.
        Valida y procesa cada lote, maneja errores individualmente por lote.
        Retorna un diccionario con los reportes ordenados por fecha de inicio.
        """

        if not isinstance(data, dict) or "lotes" not in data:
            raise InvalidJSONDataError("El archivo JSON debe contener un objeto con la clave 'lotes'.")
        
        raw_lots = data.get("lotes", [])
        if not isinstance(raw_lots, list):
            raise InvalidJSONDataError("La clave 'lotes' debe ser una lista de lotes.")
        
        reports: List[LotReport] = []
        lot_errors: List[Dict[str, Any]] = []

        self.logger.info(f"Procesando {len(raw_lots)} lotes.")

        for idx, item in enumerate(raw_lots):
            lot_id = item.get("lot_id") if isinstance(item, dict) else f"Índice {idx}"
            try:
                lot_parsed = validate_lot_data(item)
                report = process_single_lote(lot_parsed)
                reports.append(report)
                self.logger.info(
                    "Lote '%s' procesado con éxito. Estado: %s, Alertas: %d",
                    report.lot_id,
                    report.status.value,
                    report.summary.alert_count)
            except SterilizationDomainError as e:
                self.logger.error("Error procesando lote '%s': %s", lot_id, str(e))
                lot_errors.append({
                    "lot_id": lot_id,
                    "error": str(e)
                })
            except Exception as e:
                self.logger.exception("Error inesperado procesando lote '%s': %s", lot_id, str(e))
                lot_errors.append({
                    "lot_id": lot_id,
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

    def process_file(self, input_filepath:str, output_filepath: Optional[str] = None) -> None:
        """
        Procesa un archivo JSON de entrada y opcionalmente guarda el resultado en un archivo de salida.

        Args:
            input_filepath (str): Ruta del archivo JSON de entrada.
            output_filepath (Optional[str]): Ruta del archivo JSON de salida. Si es None, no se guarda.
        """
        try:
            with open(input_filepath, 'r', encoding='utf-8') as infile:
                data = json.load(infile)
            self.logger.info("Archivo '%s' cargado correctamente.", input_filepath)

            result = self.process_data(data)

            if output_filepath:
                with open(output_filepath, 'w', encoding='utf-8') as outfile:
                    json.dump(result, outfile, ensure_ascii=False, indent=4)
                self.logger.info("Resultado guardado en '%s'.", output_filepath)
            else:
                self.logger.info("No se especificó archivo de salida. Resultado no guardado.")

        except FileNotFoundError:
            self.logger.error("Archivo '%s' no encontrado.", input_filepath)
        except json.JSONDecodeError as e:
            self.logger.error("Error decodificando JSON en '%s': %s", input_filepath, str(e))
        except Exception as e:
            self.logger.exception("Error inesperado al procesar el archivo '%s': %s", input_filepath, str(e))