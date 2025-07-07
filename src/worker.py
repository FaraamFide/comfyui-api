# src/worker.py

import os, sys, logging, json, uuid, aiohttp, asyncio, subprocess, time, urllib.request, urllib.error
from pathlib import Path
from typing import Dict, Any, Optional
from celery.signals import worker_process_init
from celery.app.task import Task
import fcntl

from .config import app_config
from .celery_app import celery_app
from .workflow_utils import populate_workflow

project_root = Path(__file__).resolve().parent.parent
COMFYUI_ROOT = project_root / "ComfyUI"
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
comfy_server_instance: Optional[subprocess.Popen] = None
comfy_server_url: Optional[str] = None
comfy_output_dir: Optional[Path] = None

def set_pipe_size():
    """
    Increases the pipe buffer size for stdout/stderr on Linux.
    This is called via preexec_fn and runs after fork() but before exec()
    in the new child process. This helps prevent the ComfyUI process from
    blocking if it generates a large amount of log output.
    """
    try:
        # F_SETPIPE_SZ is available on Linux since kernel 2.6.35
        # 134217728 bytes = 128 MB
        # Set buffer size for stdout (file descriptor 1)
        fcntl.fcntl(1, fcntl.F_SETPIPE_SZ, 134217728)
        # And for stderr (file descriptor 2)
        fcntl.fcntl(2, fcntl.F_SETPIPE_SZ, 134217728)
    except (IOError, AttributeError, NameError) as e:
        # If F_SETPIPE_SZ is not supported, it's not a critical error.
        # uses os.write because standard logging might not be configured yet.
        import os
        os.write(2, f"Could not set pipe size: {e}\n".encode())
    
    # Also call the original function for process group management
    if os.name == 'posix':
        os.setpgrp()

def ensure_comfy_server_is_running():
    """
    Ensures a ComfyUI server instance is running for this worker process.
    If the process is dead, it restarts it.
    """
    global comfy_server_instance, comfy_server_url, comfy_output_dir
    if comfy_server_instance and comfy_server_instance.poll() is None:
        return
    if comfy_server_instance:
        logger.warning(f"ComfyUI process died with code {comfy_server_instance.poll()}. Restarting...")
    
    logger.info("Starting a fresh ComfyUI server instance on a random port...")
    import socket
    
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        port = s.getsockname()[1]
        
    comfy_output_dir = COMFYUI_ROOT / "output"
    comfy_output_dir.mkdir(exist_ok=True)
    
    command = [
        sys.executable, "main.py", "--port", str(port),
        "--output-directory", str(comfy_output_dir),
        "--preview-method", "none", "--dont-print-server", "--disable-auto-launch"
    ]
    
    proc = subprocess.Popen(command, cwd=str(COMFYUI_ROOT), preexec_fn=set_pipe_size)
    url_to_check = f"http://127.0.0.1:{port}/object_info"
    
    for _ in range(app_config.COMFYUI_STARTUP_TIMEOUT):
        if proc.poll() is not None:
            raise RuntimeError("ComfyUI process terminated unexpectedly during startup.")
        try:
            with urllib.request.urlopen(url_to_check, timeout=1) as response:
                if response.status == 200:
                    logger.info(f"ComfyUI server is ready on port {port}.")
                    comfy_server_instance, comfy_server_url = proc, f"http://127.0.0.1:{port}"
                    return
        except Exception:
            time.sleep(1)
            
    proc.terminate()
    proc.wait()
    raise RuntimeError(f"ComfyUI server failed to start on port {port}.")

@worker_process_init.connect
def on_worker_start(**kwargs):
    """Pre-warms a ComfyUI instance when a Celery worker process starts."""
    logger.info("Worker process started. Pre-warming ComfyUI server...")
    try:
        ensure_comfy_server_is_running()
    except Exception as e:
        logger.critical(f"FATAL: Failed to start ComfyUI on worker init: {e}", exc_info=True)

async def send_callback(url: str, data: Dict[str, Any]):
    """Sends a POST request to a callback URL."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data) as response:
                response.raise_for_status()
                logger.info(f"Successfully sent callback to {url}")
    except Exception as e:
        logger.error(f"Exception occurred while sending callback to {url}: {e}", exc_info=True)

async def execute_workflow_async(task: Task, populated_workflow: Dict[str, Any]) -> str:
    """Executes a ComfyUI workflow via WebSocket and HTTP APIs."""
    task_id = task.request.id
    client_id = str(uuid.uuid4())
    http_server_address = comfy_server_url.replace("http://", "")
    ws_server_address = f"ws://{http_server_address}/ws?clientId={client_id}"

    async with aiohttp.ClientSession() as session:
        prompt_data = {'prompt': populated_workflow, "client_id": client_id}
        async with session.post(f"{comfy_server_url}/prompt", json=prompt_data) as response:
            response.raise_for_status()
            result = await response.json()
            prompt_id = result.get("prompt_id")
            if not prompt_id:
                raise ValueError("API call to /prompt did not return a prompt_id.")
            logger.info(f"[{task_id}] Workflow queued with prompt_id: {prompt_id}")

        async with session.ws_connect(ws_server_address, timeout=app_config.CELERY_TASK_AIOHTTP_TIMEOUT) as ws:
            logger.info(f"[{task_id}] WebSocket connected.")
            task.update_state(state='PENDING', meta={'status': 'In queue'})

            execution_complete = False
            
            async for msg in ws:
                if isinstance(msg.data, str):
                    message = json.loads(msg.data)
                    msg_data = message.get('data', {})
                    
                    if 'prompt_id' in msg_data and msg_data['prompt_id'] == prompt_id:
                        
                        if message['type'] == 'progress':
                            current_step = msg_data['value']
                            total_steps = msg_data['max']
                            task.update_state(
                                state='PROGRESS',
                                meta={
                                    'current': current_step,
                                    'total': total_steps,
                                    'percent': round((current_step / total_steps) * 100, 2),
                                    'step_name': 'Generating',
                                }
                            )
                        
                        elif message['type'] == 'executing' and msg_data.get('node') is None:
                            logger.info(f"[{task_id}] Received completion signal.")
                            execution_complete = True
                            break

            if not execution_complete:
                raise TimeoutError(f"WebSocket connection closed before the completion signal was received for prompt {prompt_id}.")

        logger.info(f"[{task_id}] Retrieving output from /history/{prompt_id}")
        await asyncio.sleep(0.5) # Give a moment for history to be written
        async with session.get(f"{comfy_server_url}/history/{prompt_id}") as history_resp:
            history_resp.raise_for_status()
            history = await history_resp.json()
            
            if prompt_id in history:
                prompt_history = history[prompt_id]
                for _, node_output in prompt_history.get('outputs', {}).items():
                    if "images" in node_output and node_output["images"]:
                        image = node_output["images"][0]
                        return str(comfy_output_dir / image.get("subfolder", "") / image["filename"])
            
            logger.error(f"[{task_id}] Critical: Output not found in history. History dump: {json.dumps(history)}")
            raise FileNotFoundError("Could not find output file in ComfyUI's history after execution.")

@celery_app.task(name="generate_task", bind=True, acks_late=True, time_limit=app_config.CELERY_TASK_TIME_LIMIT)
def generate_task(self: Task, workflow_id: str, params: Dict[str, Any], callback_url: Optional[str] = None) -> Dict[str, Any]:
    """The main Celery task for image generation."""
    task_id = self.request.id
    try:
        ensure_comfy_server_is_running()
        workflow_path = project_root / "src" / "workflows" / f"{workflow_id}.json"
        with open(workflow_path, "r") as f:
            workflow_data = json.load(f)
            
        populated_workflow = populate_workflow(workflow_data, params)
        file_path = asyncio.run(execute_workflow_async(self, populated_workflow))
        
        if callback_url:
            base_url = app_config.PUBLIC_IP
            file_name = os.path.basename(file_path)
            download_url = f"{base_url}/results/{task_id}/{file_name}"
            callback_data = {"task_id": task_id, "status": "SUCCESS", "result": {"download_url": download_url}}
            asyncio.run(send_callback(callback_url, callback_data))
            
        return {"file_path": file_path}
    except Exception as e:
        logger.error(f"Task {task_id} failed: {e}", exc_info=True)
        if callback_url:
            callback_data = {"task_id": task_id, "status": "FAILURE", "result": str(e)}
            asyncio.run(send_callback(callback_url, callback_data))
        raise