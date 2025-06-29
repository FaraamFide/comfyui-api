# src/worker.py

import os
import sys
import logging
import json
import uuid
import aiohttp
import asyncio
from pathlib import Path
from typing import Dict, Any
import subprocess
import time
import urllib.request
import urllib.error

from celery.signals import worker_process_init

# Используем относительные импорты
from .config import app_config
from .celery_app import celery_app
from .workflow_utils import populate_workflow

project_root = Path(__file__).resolve().parent.parent
COMFYUI_ROOT = project_root / "ComfyUI"
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

comfy_server_instance = None
comfy_server_url = None
comfy_output_dir = None

def ensure_comfy_server_is_running():
    global comfy_server_instance, comfy_server_url, comfy_output_dir
    
    if comfy_server_instance and comfy_server_instance.poll() is None:
        return

    if comfy_server_instance:
        logger.warning(f"ComfyUI process has died with code {comfy_server_instance.poll()}. Restarting...")
    
    logger.info("Starting a fresh ComfyUI server instance.")
    
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0)); port = s.getsockname()[1]
    
    comfy_output_dir = COMFYUI_ROOT / "output"
    comfy_output_dir.mkdir(exist_ok=True)
    
    command = [
        sys.executable, "main.py",
        "--port", str(port),
        "--output-directory", str(comfy_output_dir),
        "--preview-method", "none",
        "--dont-print-server"
    ]
    
    def preexec_fn(): os.setpgrp()

    proc = subprocess.Popen(command, cwd=str(COMFYUI_ROOT), preexec_fn=preexec_fn if os.name == 'posix' else None)
    
    url_to_check = f"http://127.0.0.1:{port}/object_info"
    
    for _ in range(app_config.COMFYUI_STARTUP_TIMEOUT):
        if proc.poll() is not None:
            raise RuntimeError(f"ComfyUI process terminated unexpectedly during startup with code {proc.poll()}.")
        try:
            with urllib.request.urlopen(url_to_check, timeout=1) as response:
                if response.status == 200:
                    logger.info(f"ComfyUI server is ready on port {port}.")
                    comfy_server_instance = proc
                    comfy_server_url = f"http://127.0.0.1:{port}"
                    return
        except Exception:
            time.sleep(1)
    
    proc.terminate(); proc.wait()
    raise RuntimeError(f"ComfyUI server failed to start on port {port}.")

@worker_process_init.connect
def on_worker_start(**kwargs):
    logger.info("Worker process started. Initializing and pre-warming ComfyUI server...")
    try:
        ensure_comfy_server_is_running()
    except Exception as e:
        logger.critical(f"FATAL: Failed to start ComfyUI on worker init: {e}", exc_info=True)

async def execute_workflow_async(populated_workflow: Dict[str, Any]) -> str:
    request_id = uuid.uuid4().hex
    prompt_id = None
    timeout = aiohttp.ClientTimeout(total=app_config.CELERY_TASK_AIOHTTP_TIMEOUT)

    try:
        async with aiohttp.ClientSession(timeout=timeout, connector=aiohttp.TCPConnector(ssl=False)) as session:
            prompt_data = {'prompt': populated_workflow, "client_id": request_id}
            
            async with session.post(f"{comfy_server_url}/prompt", json=prompt_data) as response:
                response.raise_for_status()
                result = await response.json()
                if "error" in result:
                    raise IOError(f"ComfyUI API error: {result['error']['type']} - {result['error']['message']}")
                prompt_id = result.get("prompt_id")
            
            while True:
                await asyncio.sleep(1)
                async with session.get(f"{comfy_server_url}/history/{prompt_id}") as history_resp:
                    history_resp.raise_for_status()
                    history = await history_resp.json()
                    if prompt_id in history:
                        outputs = history[prompt_id]['outputs']
                        for _, node_output in outputs.items():
                            if "images" in node_output:
                                image = node_output["images"][0]
                                return str(comfy_output_dir / image.get("subfolder", "") / image["filename"])
        raise FileNotFoundError("Could not find the output file in ComfyUI's history.")
    except asyncio.TimeoutError:
        logger.error(f"ComfyUI task timed out for prompt_id: {prompt_id if prompt_id else 'N/A'}.")
        if comfy_server_instance and comfy_server_instance.poll() is None:
            logger.warning(f"Terminating potentially hung ComfyUI process (PID: {comfy_server_instance.pid}).")
            comfy_server_instance.terminate()
            try:
                comfy_server_instance.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.error("ComfyUI process did not terminate gracefully, killing.")
                comfy_server_instance.kill()
        raise RuntimeError("ComfyUI task execution timed out.")
    except Exception as e:
        logger.error(f"An error occurred while communicating with ComfyUI: {e}", exc_info=True)
        raise

@celery_app.task(name="generate_task", bind=True, acks_late=True, time_limit=app_config.CELERY_TASK_TIME_LIMIT)
def generate_task(self, workflow_id: str, params: Dict[str, Any]) -> str:
    try:
        ensure_comfy_server_is_running()
        
        workflow_path = project_root / "src" / "workflows" / f"{workflow_id}.json"
        with open(workflow_path, "r") as f:
            workflow_data = json.load(f)
        
        populated_workflow = populate_workflow(workflow_data, params)
        
        return asyncio.run(execute_workflow_async(populated_workflow))

    except Exception as e:
        logger.error(f"Task {self.request.id} failed: {e}", exc_info=True)
        raise