# src/api.py (Финальная версия с правильной инициализацией и валидацией)

import logging
import os
import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from typing import Dict, Any, List

# --- Настройка путей ---
# Это нужно сделать до импорта других модулей, которые зависят от ComfyUI
project_root = Path(__file__).resolve().parent.parent
comfyui_path = project_root / "ComfyUI"
if str(comfyui_path) not in sys.path:
    sys.path.insert(0, str(comfyui_path))

# --- Основные импорты ---
import folder_paths
from worker import generate_task
from celery_app import celery_app
from manifest_loader import validate_request

# --- Глобальные переменные для хранения списков файлов ---
# Мы заполним их при старте сервера
AVAILABLE_MODELS: List[str] = []
AVAILABLE_LORAS: List[str] = []

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ComfyUI Production Service")


@app.on_event("startup")
async def startup_event():
    """
    Эта функция выполняется один раз при запуске FastAPI сервера.
    Ее задача - проинициализировать ComfyUI folder_paths, чтобы
    валидатор мог находить модели, LoRA и т.д.
    """
    logger.info("FastAPI server starting up...")
    
    # Эта функция из ComfyUI сканирует все директории с моделями,
    # читает extra_model_paths.yaml и заполняет все необходимые переменные.
    # После ее выполнения get_filename_list() будет возвращать правильные данные.
    folder_paths.initialize_paths()
    
    logger.info("ComfyUI folder paths initialized for API.")
    # Проверочный лог, чтобы убедиться, что модели найдены
    models = folder_paths.get_filename_list("checkpoints")
    unets = folder_paths.get_filename_list("unet")
    logger.info(f"Found {len(models)} checkpoints и {len(unets)} unets.")


# --- API Эндпоинты ---

@app.post("/generate", status_code=202)
async def create_generation_task(request_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Принимает запрос, валидирует его по манифестам и ставит в очередь.
    """
    try:
        workflow_id = request_data.get("workflow_id")
        params_from_request = request_data.get("params", {})
        
        if not workflow_id:
            raise ValueError("'workflow_id' is required.")

        validated_params = validate_request(workflow_id, params_from_request)

    except ValueError as e:
        logger.error(f"Validation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")

    logger.info(f"Received valid task for workflow: {workflow_id}")
    task = generate_task.delay(
        workflow_id=workflow_id,
        params=validated_params
    )
    logger.info(f"Task {task.id} enqueued for workflow {workflow_id}.")
    return {"task_id": task.id}


@app.get("/tasks/{task_id}")
async def get_task_status(task_id: str, request: Request) -> Dict[str, Any]:
    """Проверяет статус задачи по ее ID."""
    task_result = celery_app.AsyncResult(task_id)
    status = task_result.status
    
    response = {"task_id": task_id, "status": status}

    if status == 'SUCCESS':
        file_path_str = task_result.result
        base_url = str(request.base_url)
        file_name = os.path.basename(file_path_str)
        download_url = f"{base_url}results/{task_id}/{file_name}"
        response["result"] = { "download_url": download_url, "server_path": file_path_str }
    elif status == 'FAILURE':
        response["result"] = str(task_result.info)

    return response


@app.get("/results/{task_id}/{filename}")
async def download_result_file(task_id: str, filename: str):
    """Отдает сгенерированный файл по ID задачи."""
    task_result = celery_app.AsyncResult(task_id)
    if not task_result.ready() or task_result.status != 'SUCCESS':
        raise HTTPException(status_code=404, detail="Task not found or not completed successfully.")
    
    file_path = task_result.result
    if os.path.basename(file_path) != filename:
        raise HTTPException(status_code=403, detail="Forbidden.")

    if os.path.exists(file_path):
        return FileResponse(path=file_path, media_type='image/png', filename=filename)
    else:
        logger.error(f"File not found on disk for task {task_id}: {file_path}")
        raise HTTPException(status_code=404, detail="Result file not found on disk.")