"""
API REST para el sistema de control y procesamiento de ciclos de esterilización en autoclaves.
Proporciona endpoints para validar, procesar lotes individuales o en lote (JSON/Archivos) y servir la interfaz web.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, UploadFile, File, Body, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from pydantic import BaseModel, Field

from src.service import SterilizationService
from src.exceptions import SterilizationDomainError, InvalidJSONDataError, LoteValidationError, ReadingValidationError
from src.validators import validate_lot_data
from src.processors import process_single_lot

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("autoclave_api")

app = FastAPI(
    title="Autoclave Sterilization Control API",
    description="API para orquestación, validación y análisis de telemetría de esterilización",
    version="1.0.0"
)

# Habilitar CORS para integración frontend/backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

service = SterilizationService()

# Servir archivos estáticos
import os
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", response_class=HTMLResponse)
def read_root():
    """
    Sirve la interfaz web principal del sistema.
    """
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse("<h1>Autoclave Sterilization API Running</h1><p>Visita /docs para la documentación interactiva.</p>")


@app.on_event("startup")
def startup_event():
    try:
        from src.database import init_db
        init_db()
    except Exception as e:
        logger.debug(f"DB startup init info: {e}")

@app.get("/api/health")
def health_check():
    """
    Endpoint de estado del servicio.
    """
    return {
        "status": "healthy",
        "service": "Autoclave Sterilization Control API",
        "version": "1.0.0"
    }

@app.get("/api/analytics")
def get_analytics():
    """
    Retorna los resultados de la consulta analítica de PostgreSQL (Pregunta 2 de la prueba técnica).
    """
    try:
        from src.database import get_analytical_summary
        metrics = get_analytical_summary()
        return {"status": "ok", "metrics": metrics}
    except Exception as e:
        return {"status": "error", "detail": str(e), "metrics": []}

@app.get("/api/lots")
def get_stored_lots():
    """
    Retorna todos los lotes guardados en la BD / memoria para mantener el estado al recargar la página.
    """
    try:
        from src.database import get_all_stored_lots
        lots = get_all_stored_lots()
        return {
            "total_processed_lots": len(lots),
            "total_failed_lots": 0,
            "Lots": lots
        }
    except Exception as e:
        return {"total_processed_lots": 0, "total_failed_lots": 0, "Lots": []}

@app.delete("/api/lots")
def clear_stored_lots():
    """
    Elimina todos los lotes de la base de datos PostgreSQL y de la memoria cuando se presiona 'Limpiar'.
    """
    try:
        from src.database import clear_all_stored_lots
        clear_all_stored_lots()
        return {"status": "cleared", "message": "Base de datos e historial limpiados correctamente."}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.post("/api/process-data")
def process_data(data: Any = Body(...)):
    """
    Procesa un objeto JSON que contiene una lista de lotes.
    Format esperado: {"lotes": [ {...}, {...} ]}
    """
    try:
        result = service.process_data(data)
        return JSONResponse(status_code=status.HTTP_200_OK, content=result)
    except InvalidJSONDataError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Error interno al procesar datos JSON")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error interno: {str(e)}")


@app.post("/api/process-file")
async def process_file(file: UploadFile = File(...)):
    """
    Procesa un archivo JSON subido por el usuario.
    """
    if not file.filename.endswith(".json"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se admiten archivos en formato JSON (.json)"
        )
    
    try:
        content = await file.read()
        data = json.loads(content.decode("utf-8"))
        result = service.process_data(data)
        return JSONResponse(status_code=status.HTTP_200_OK, content=result)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Formato JSON inválido en el archivo subido: {str(e)}"
        )
    except InvalidJSONDataError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Error al procesar el archivo cargado")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error interno: {str(e)}")


@app.post("/api/process-lot")
def process_single_lot_endpoint(lot_data: Dict[str, Any] = Body(...)):
    """
    Procesa un único lote directo (objeto individual de lote).
    """
    try:
        from src.database import is_lot_registered, save_lot_report
        raw_id = lot_data.get("lot_id") or lot_data.get("lote_id") or lot_data.get("id_lote") if isinstance(lot_data, dict) else None
        if raw_id and is_lot_registered(raw_id):
            raise LoteValidationError(str(raw_id), f"El lote '{raw_id}' ya fue registrado previamente en la base de datos (Lote duplicado).")

        lot_obj = validate_lot_data(lot_data)
        report = process_single_lot(lot_obj)
        try:
            save_lot_report(report)
        except Exception as db_err:
            logger.debug(f"Nota DB: {db_err}")
        return JSONResponse(status_code=status.HTTP_200_OK, content=report.to_dict())
    except SterilizationDomainError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        logger.exception("Error al procesar el lote individual")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error interno: {str(e)}")


@app.get("/api/sample-data")
def get_sample_data():
    """
    Retorna un conjunto de datos de muestra representativo con varios estados (Aprobado, En Observación, Con Error).
    """
    sample = {
        "lotes": [
            {
                "lote_id": "AT-2026-0002",
                "producto": "Sardinas en salsa de tomate 425 g",
                "autoclave": "AUT-01",
                "inicio": "2026-08-01T10:00:00-05:00",
                "fin": "2026-08-01T11:30:00-05:00",
                "temperatura_minima": 115.0,
                "temperatura_maxima": 122.0,
                "presion_minima": 1.10,
                "presion_maxima": 1.70,
                "lecturas": [
                    {"fecha_hora": "2026-08-01T10:15:00-05:00", "temperatura": 118.0, "presion": 1.30},
                    {"fecha_hora": "2026-08-01T10:30:00-05:00", "temperatura": 123.5, "presion": 1.40},
                    {"fecha_hora": "2026-08-01T10:45:00-05:00", "temperatura": 119.0, "presion": 1.85}
                ]
            },
            {
                "lote_id": "AT-2026-0001",
                "producto": "Atún en aceite 170 g",
                "autoclave": "AUT-03",
                "inicio": "2026-08-01T08:00:00-05:00",
                "fin": "2026-08-01T09:15:00-05:00",
                "temperatura_minima": 116.0,
                "temperatura_maxima": 123.0,
                "presion_minima": 1.20,
                "presion_maxima": 1.80,
                "lecturas": [
                    {"fecha_hora": "2026-08-01T08:10:00-05:00", "temperatura": 117.2, "presion": 1.35},
                    {"fecha_hora": "2026-08-01T08:20:00-05:00", "temperatura": 121.0, "presion": 1.62},
                    {"fecha_hora": "2026-08-01T08:30:00-05:00", "temperatura": 119.5, "presion": 1.50}
                ]
            },
            {
                "lote_id": "AT-2026-0003",
                "producto": "Lomitos de atún en agua 170 g",
                "autoclave": "AUT-02",
                "inicio": "2026-08-01T12:00:00-05:00",
                "fin": "2026-08-01T13:30:00-05:00",
                "temperatura_minima": 116.0,
                "temperatura_maxima": 123.0,
                "presion_minima": 1.20,
                "presion_maxima": 1.80,
                "lecturas": [
                    {"fecha_hora": "2026-08-01T12:15:00-05:00", "temperatura": 114.0, "presion": 1.10},
                    {"fecha_hora": "2026-08-01T12:30:00-05:00", "temperatura": 125.0, "presion": 1.30},
                    {"fecha_hora": "2026-08-01T12:45:00-05:00", "temperatura": 118.0, "presion": 2.00}
                ]
            }
        ]
    }
    return sample


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=True)
