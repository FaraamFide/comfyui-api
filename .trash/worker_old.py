# src/worker.py

import os
import sys
import logging
import torch
import json
import uuid
import aiohttp
import asyncio
from pathlib import Path
from typing import Dict, Any

# Импортируем наш Celery-инстанс
from .celery_app import celery_app

# --- Код для работы с ComfyUI (почти без изменений) ---

# Добавляем путь к кастомным нодам
# Этот код теперь будет выполняться в каждом процессе-воркере Celery
project_root = Path(__file__).parent.parent
comfy_pack_src_path = str(project_root / "ComfyUI" / "custom_nodes" / "comfy-pack" / "src")
if comfy_pack_src_path not in sys.path:
    sys.path.insert(0, comfy_pack_src_path)

from comfy_pack.utils import populate_workflow

COMFYUI_ROOT = str(project_root / "ComfyUI")

# Настраиваем логирование
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Глобальный, лениво инициализируемый ComfyUI-сервер ---
# Мы не хотим запускать новый сервер на каждую задачу.
# Мы запустим его один раз для каждого процесса-воркера.
comfy_server_instance = None
comfy_server_url = None

def get_comfy_server():
    """
    Функция-синглтон, которая запускает ComfyUI сервер только один раз
    на каждый воркер.
    """
    global comfy_server_instance, comfy_server_url
    if comfy_server_instance is None:
        # Эта логика выполнится только при обработке первой задачи этим воркером
        import socket, subprocess, time, urllib.request, urllib.error
        
        # Находим свободный порт
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            port = s.getsockname()[1]
        
        # Запускаем ComfyUI
        logger.info(f"Starting ComfyUI server on port {port} for worker {os.getpid()}...")
        output_dir = Path(COMFYUI_ROOT) / "output"
        output_dir.mkdir(exist_ok=True)
        command = [sys.executable, str(Path(COMFYUI_ROOT) / "main.py"), "--port", str(port), "--output-directory", str(output_dir), "--preview-method", "none"]
        proc = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Ждем, пока сервер будет готов
        url_to_check = f"http://127.0.0.1:{port}/object_info"
        for _ in range(30): # Ждем до 30 секунд
            try:
                with urllib.request.urlopen(url_to_check, timeout=1) as response:
                    if response.status == 200:
                        logger.info(f"ComfyUI server is ready on port {port}.")
                        comfy_server_instance = proc
                        comfy_server_url = f"http://127.0.0.1:{port}"
                        return
            except Exception:
                time.sleep(1)
        raise RuntimeError("ComfyUI server failed to start.")
    return

async def execute_workflow(workflow: Dict[str, Any], params: Dict[str, Any]) -> str:
    """Асинхронно выполняет workflow (этот код у нас уже был)"""
    request_id = uuid.uuid4().hex[:8]
    output_dir = Path(COMFYUI_ROOT) / "output"
    populated_workflow = populate_workflow(workflow, output_dir, session_id=request_id, **params)
    
    async with aiohttp.ClientSession() as session:
        prompt_data = {'prompt': populated_workflow, "client_id": uuid.uuid4().hex}
        async with session.post(f"{comfy_server_url}/prompt", json=prompt_data) as response:
            result = await response.json()
            prompt_id = result.get("prompt_id")

        while True:
            await asyncio.sleep(0.5)
            async with session.get(f"{comfy_server_url}/history/{prompt_id}") as history_resp:
                history = await history_resp.json()
                if prompt_id in history:
                    outputs = history[prompt_id]['outputs']
                    for _, node_output in outputs.items():
                        if "images" in node_output:
                            image = node_output["images"][0]
                            full_path = output_dir / image.get("subfolder", "") / image["filename"]
                            return str(full_path)
    return "Error: Output not found"


# --- НАША ГЛАВНАЯ ЗАДАЧА ДЛЯ CELERY ---
@celery_app.task(name="generate_task")
def generate_task(workflow_id: str, params: Dict[str, Any]) -> str:
    """
    Эта функция будет выполняться Celery-воркером.
    """
    try:
        logger.info(f"Worker {os.getpid()} picked up task for workflow '{workflow_id}'")
        
        # 1. Убеждаемся, что ComfyUI сервер для этого воркера запущен
        get_comfy_server()
        
        # 2. Загружаем нужный workflow
        workflow_path = Path(__file__).parent / "workflows" / f"{workflow_id}.json"
        with open(workflow_path, "r") as f:
            workflow_data = json.load(f)
        
        # 3. Запускаем асинхронную функцию выполнения
        # Мы в синхронной задаче, поэтому используем asyncio.run()
        result_path = asyncio.run(execute_workflow(workflow_data, params))
        
        logger.info(f"Task for workflow '{workflow_id}' completed. Result: {result_path}")
        return result_path

    except Exception as e:
        logger.error(f"Task failed for workflow '{workflow_id}': {e}", exc_info=True)
        # Перевыбрасываем ошибку, чтобы Celery пометил задачу как FAILED
        raise
