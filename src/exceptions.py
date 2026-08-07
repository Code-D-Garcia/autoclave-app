"""
Excepciones personalizadas para el dominio de control de esterilización.
"""


class SterilizationDomainError(Exception):
    """Excepción base para errores de dominio en el sistema de esterilización."""
    pass


class LoteValidationError(SterilizationDomainError):
    """Excepción lanzada cuando los datos de un lote no cumplen con las reglas de validación."""
    def __init__(self, lote_id: str, message: str):
        self.lote_id = lote_id
        self.message = message
        super().__init__(f"Error de validación en el lote '{lote_id}': {message}")


class ReadingValidationError(SterilizationDomainError):
    """Excepción lanzada cuando una lectura no cumple las reglas dentro del lote."""
    def __init__(self, lote_id: str, fecha_hora: str, message: str):
        self.lote_id = lote_id
        self.fecha_hora = fecha_hora
        self.message = message
        super().__init__(f"Error en lectura [{fecha_hora}] del lote '{lote_id}': {message}")


class InvalidJSONDataError(SterilizationDomainError):
    """Excepción lanzada cuando la estructura general del archivo JSON es inválida."""
    pass
