# src/api.py (ИЗМЕНЕННАЯ ВЕРСИЯ)

import logging
import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from typing import Dict, Any, Optional # Добавляем Optional
from pydantic import BaseModel, HttpUrl # Используем Pydantic для валидации URL

from .config import app_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from .worker import generate_task
from .celery_app import celery_app
from .manifest_loader import validate_request

app = FastAPI(title="ComfyUI Production Service")

# --- Новая Pydantic модель для валидации тела запроса ---
class GenerationRequest(BaseModel):
    workflow_id: str
    params: Dict[str, Any] = {}
    callback_url: Optional[HttpUrl] = None # Опциональное поле, которое должно быть валидным URL

@app.post("/generate", status_code=202)
async def create_generation_task(request_data: GenerationRequest) -> Dict[str, str]:
    try:
        # Валидация параметров воркфлоу
        validated_params = validate_request(request_data.workflow_id, request_data.params)

    except ValueError as e:
        logger.error(f"Validation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")

    # Передаем callback_url в задачу Celery
    # Важно преобразовать HttpUrl обратно в строку
    callback_url_str = str(request_data.callback_url) if request_data.callback_url else None
    
    task = generate_task.delay(
        workflow_id=request_data.workflow_id, 
        params=validated_params,
        callback_url=callback_url_str # Новое поле
    )
    
    logger.info(f"Task {task.id} enqueued for workflow '{request_data.workflow_id}'.")
    return {"task_id": task.id}

# ... остальная часть файла (GET /tasks/{task_id} и GET /results/{...}) остается без изменений ...
@app.get("/tasks/{task_id}")
async def get_task_status(task_id: str, request: Request) -> Dict[str, Any]:
    task_result = celery_app.AsyncResult(task_id)
    status = task_result.status
    response = {"task_id": task_id, "status": status}
    if status == 'SUCCESS':
        result_data = task_result.result
        base_url = f"http://{app_config.PUBLIC_IP}:{app_config.UVICORN_PORT}"
        file_name = os.path.basename(result_data['file_path'])
        download_url = f"{base_url}/results/{task_id}/{file_name}"
        response["result"] = {"download_url": download_url}
    elif status == 'FAILURE':
        response["result"] = str(task_result.info)
    return response

@app.get("/results/{task_id}/{filename}")
async def download_result_file(task_id: str, filename: str):
    task_result = celery_app.AsyncResult(task_id)
    if not task_result.ready() or task_result.status != 'SUCCESS':
        raise HTTPException(status_code=404, detail="Task not found or not completed successfully.")
    file_path = task_result.result['file_path']
    if os.path.basename(file_path) != filename:
        raise HTTPException(status_code=403, detail="Forbidden.")
    if os.path.exists(file_path):
        return FileResponse(path=file_path, media_type='image/png', filename=filename)
    else:
        logger.error(f"File not found on disk for task {task_id}: {file_path}")
        raise HTTPException(status_code=404, detail="Result file not found on disk.")
