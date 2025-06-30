# src/api.py

import logging
import os
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, HttpUrl

from .celery_app import celery_app
from .config import app_config
from .manifest_loader import validate_request
from .worker import generate_task

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ComfyUI Production Service")

class GenerationRequest(BaseModel):
    """Pydantic model for validating the generation request body."""
    workflow_id: str
    params: Dict[str, Any] = {}
    callback_url: Optional[HttpUrl] = None

@app.post("/generate", status_code=202)
async def create_generation_task(request_data: GenerationRequest) -> Dict[str, str]:
    """
    Accepts a generation request, validates it, and enqueues it as a Celery task.
    Returns the task ID immediately for asynchronous processing.
    """
    try:
        validated_params = validate_request(request_data.workflow_id, request_data.params)
    except ValueError as e:
        logger.error(f"Validation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    
    callback_url_str = str(request_data.callback_url) if request_data.callback_url else None
    
    task = generate_task.delay(
        workflow_id=request_data.workflow_id, 
        params=validated_params,
        callback_url=callback_url_str
    )
    
    logger.info(f"Task {task.id} enqueued for workflow '{request_data.workflow_id}'.")
    return {"task_id": task.id}

@app.get("/tasks/{task_id}")
async def get_task_status(task_id: str) -> Dict[str, Any]:
    """
    Allows polling for a task's status. If successful, returns a download URL.
    This serves as a fallback or for clients that do not use webhooks.
    """
    task_result = celery_app.AsyncResult(task_id)
    status = task_result.status
    response = {"task_id": task_id, "status": status}

    if status == 'SUCCESS':
        result_data = task_result.result
        file_path_str = result_data.get('file_path')
        
        if file_path_str:
            # Build the URL using the public-facing IP from the config.
            base_url = f"http://{app_config.PUBLIC_IP}:{app_config.UVICORN_PORT}"
            file_name = os.path.basename(file_path_str)
            download_url = f"{base_url}/results/{task_id}/{file_name}"
            response["result"] = {"download_url": download_url}
        else:
            response["result"] = "Task succeeded but no file path was returned."

    elif status == 'FAILURE':
        response["result"] = str(task_result.info)
        
    return response

@app.get("/results/{task_id}/{filename}")
async def download_result_file(task_id: str, filename: str):
    """Serves the generated image file."""
    task_result = celery_app.AsyncResult(task_id)
    if not task_result.ready() or task_result.status != 'SUCCESS':
        raise HTTPException(status_code=404, detail="Task not found or not completed successfully.")
    
    file_path = task_result.result.get('file_path')
    if not file_path:
        raise HTTPException(status_code=404, detail="File path not found in task result.")

    if os.path.basename(file_path) != filename:
        raise HTTPException(status_code=403, detail="Forbidden: Filename mismatch.")
        
    if os.path.exists(file_path):
        return FileResponse(path=file_path, media_type='image/png', filename=filename)
    else:
        logger.error(f"Result file not found on disk for task {task_id}: {file_path}")
        raise HTTPException(status_code=404, detail="Result file not found on disk.")