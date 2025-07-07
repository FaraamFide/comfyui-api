# src/api.py

import logging
import os
from typing import Any, Dict, Optional, List

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, HttpUrl
from fastapi.concurrency import run_in_threadpool

from .celery_app import celery_app
from .config import app_config
from .manifest_loader import validate_request, load_manifests
from .worker import generate_task

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ComfyUI Production Service")

@app.get("/ping")
async def ping():
    """A simple endpoint to check if the server is alive and responsive."""
    return {"message": "pong"}

class GenerationRequest(BaseModel):
    workflow_id: str
    params: Dict[str, Any] = {}
    callback_url: Optional[HttpUrl] = None

@app.post("/generate", status_code=202)
async def create_generation_task(request_data: GenerationRequest) -> Dict[str, str]:
    """
    Accepts a generation request, validates it, and enqueues it as a Celery task.
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

@app.get("/loras", response_model=List[Dict[str, Any]])
async def list_available_loras():
    """
    Returns a list of LoRAs described in the loras.yaml manifest.
    The manifest is the single source of truth.
    """
    if not app_config.initialized:
        raise HTTPException(status_code=503, detail="Server is not yet initialized. Please try again in a moment.")

    lora_manifest = load_manifests().get("loras", {})
    
    if not lora_manifest:
        return []

    response_data = []
    for lora_filename, lora_info in lora_manifest.items():
        
        # Optional but useful check: does this file exist on disk?
        if lora_filename not in app_config.AVAILABLE_LORAS:
            logger.warning(f"LoRA '{lora_filename}' is defined in loras.yaml but not found on disk. Skipping.")
            continue

        # Assemble data only from the lora_info obtained from the manifest
        response_data.append({
            "name": lora_filename,
            "description": lora_info.get("description", "No description available."),
            "prefix": lora_info.get("prefix"),
            "suffix": lora_info.get("suffix"),
            "examples": lora_info.get("examples", [])
        })
        
    return response_data

@app.get("/tasks/{task_id}")
async def get_task_status(task_id: str) -> Dict[str, Any]:
    """
    Retrieves the status and result of a Celery task.
    This runs the blocking Celery check in a threadpool to avoid blocking the event loop.
    """
    def check_celery_status():
        """This synchronous function will be executed in a separate thread."""
        task_result = celery_app.AsyncResult(task_id)
        status = task_result.state
        
        response = {"task_id": task_id, "status": status}
        
        if status == 'SUCCESS':
            result_data = task_result.result
            file_path_str = result_data.get('file_path')
            if file_path_str:
                base_url = app_config.PUBLIC_IP
                file_name = os.path.basename(file_path_str)
                # Ensure PUBLIC_IP in .env is a full URL like http://127.0.0.1:8000
                download_url = f"{base_url}/results/{task_id}/{file_name}"
                response["result"] = {"download_url": download_url}
            else:
                response["result"] = "Task succeeded but no file path was returned."
        elif status == 'FAILURE':
            response["result"] = str(task_result.info)
        elif status == 'PROGRESS':
            response["progress"] = task_result.info
        elif status == 'PENDING':
            response["result"] = "Task is waiting in the queue."
            
        return response

    # Execute the blocking function in the threadpool and await the result
    return await run_in_threadpool(check_celery_status)

@app.get("/results/{task_id}/{filename}")
async def download_result_file(task_id: str, filename: str):
    """
    Serves the generated image file for a completed task.
    """
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