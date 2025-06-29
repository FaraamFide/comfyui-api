# src/worker.py

import os
import sys
import logging
from pathlib import Path
import torch
import bentoml
from bentoml.exceptions import BentoMLException, NotFound
from typing import Any, Dict
import json
import uuid
import asyncio
import aiohttp
import subprocess
import time
import urllib.request
import urllib.error

# Импортируем путь к ComfyUI
from .config import COMFYUI_ROOT

# Импорты из comfy-pack
from comfy_pack.utils import populate_workflow

# Настраиваем логирование
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Проверка конфигурации ---
if not Path(COMFYUI_ROOT).is_dir():
    raise BentoMLException(f"ComfyUI directory not found at '{COMFYUI_ROOT}'.")

# Класс-обертка для управления процессом ComfyUI
class SimpleComfyProcess:
    def __init__(self, workspace_path, port, verbose=False):
        self.workspace = workspace_path
        self.port = port
        self.proc = None
        self.verbose = verbose
        self.output_dir = Path(self.workspace) / "output"
        self.input_dir = Path(self.workspace) / "input"
        self.temp_dir = Path(self.workspace) / "temp"

    def start(self):
        import shutil
        shutil.rmtree(self.output_dir, ignore_errors=True)
        self.output_dir.mkdir(exist_ok=True, parents=True)
        
        stdout_pipe = sys.stdout if self.verbose else subprocess.DEVNULL
        command = [
            sys.executable,
            str(Path(self.workspace) / "main.py"),
            "--port", str(self.port),
            "--output-directory", str(self.output_dir),
            "--preview-method", "none",
        ]
        self.proc = subprocess.Popen(command, stdout=stdout_pipe, stderr=stdout_pipe, cwd=self.workspace)
        logger.info(f"Started ComfyUI process with PID: {self.proc.pid} on port {self.port}")

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()

@bentoml.service(
    resources={"gpu": 1},
    traffic={"timeout": 600},
)
class ComfyWorkerService:
    def __init__(self) -> None:
        if torch.cuda.is_available():
            gpu_device_id = 0
            if hasattr(bentoml.server_context, "gpu_device_id"):
                gpu_device_id = bentoml.server_context.gpu_device_id
            os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu_device_id)
            logger.info(f"Worker starting on GPU: {gpu_device_id}")
        else:
            logger.info("Worker starting on CPU.")

        self.port = self._find_free_port()
        self.host = "127.0.0.1"
        self.server_url = f"http://{self.host}:{self.port}"
        
        self.server = SimpleComfyProcess(workspace_path=COMFYUI_ROOT, port=self.port, verbose=True)
        self.server.start()
        
        # Блокирующая проверка готовности сервера
        self._wait_for_server_blocking(timeout=90)

    def _find_free_port(self):
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            return s.getsockname()[1]

    def _wait_for_server_blocking(self, timeout: int):
        """Синхронно и блокирующе ждет, пока сервер ComfyUI станет доступен."""
        logger.info("Waiting for ComfyUI server to become ready...")
        start_time = time.time()
        url_to_check = f"{self.server_url}/object_info"
        while time.time() - start_time < timeout:
            try:
                with urllib.request.urlopen(url_to_check, timeout=1) as response:
                    if response.status == 200:
                        logger.info("ComfyUI server is ready!")
                        return
            except (urllib.error.URLError, ConnectionRefusedError):
                time.sleep(1)
            except Exception as e:
                 logger.error(f"Unexpected error while waiting for ComfyUI: {e}")
                 time.sleep(1)
        raise RuntimeError("ComfyUI server failed to start within the timeout period.")

    async def _execute_workflow(self, populated_workflow: Dict[str, Any]) -> Dict[str, Any]:
        async with aiohttp.ClientSession() as session:
            prompt_data = {'prompt': populated_workflow, "client_id": uuid.uuid4().hex}
            async with session.post(f"{self.server_url}/prompt", json=prompt_data) as response:
                if response.status != 200:
                     error_text = await response.text()
                     raise BentoMLException(f"ComfyUI server error ({response.status}): {error_text}")
                result = await response.json()
                if "error" in result:
                    raise BentoMLException(f"ComfyUI API error: {result['error']}")
                prompt_id = result.get("prompt_id")

            while True:
                await asyncio.sleep(0.5)
                async with session.get(f"{self.server_url}/history/{prompt_id}") as history_resp:
                    if history_resp.status != 200:
                        continue
                    history = await history_resp.json()
                    if prompt_id in history:
                        return history[prompt_id]['outputs']

    @bentoml.api
    def ping(self) -> str:
        """
        Простой метод, который отвечает 'pong'.
        Позволяет проверить, доходят ли вызовы от Gateway до Worker'а.
        """
        gpu_id_str = os.environ.get('CUDA_VISIBLE_DEVICES', 'CPU')
        logger.info(f"Worker on GPU '{gpu_id_str}' received a ping!")
        return "pong"



    # @bentoml.api
    # async def generate(self, workflow: Dict[str, Any], params: Dict[str, Any]) -> Path:
    #     # Убираем ctx, т.к. при прямом вызове он не передается как аргумент
    #     request_id = uuid.uuid4().hex[:8] # Генерируем ID сами для логов
    #     gpu_id_str = os.environ.get('CUDA_VISIBLE_DEVICES', 'CPU')
        
    #     # Шаг W-1: Воркер получил задачу
    #     logger.info(f"[Worker GPU-{gpu_id_str}] W-1: Task '{request_id}' received.")
        
    #     try:
    #         # Шаг W-2: Начинаем заполнять workflow
    #         logger.info(f"[Worker GPU-{gpu_id_str}] W-2: Populating workflow for task '{request_id}'.")
    #         populated_workflow = populate_workflow(workflow, self.server.output_dir, session_id=request_id, **params)
    #         logger.info(f"[Worker GPU-{gpu_id_str}] W-3: Workflow populated.")
            
    #         # Шаг W-4: Начинаем выполнение через API
    #         logger.info(f"[Worker GPU-{gpu_id_str}] W-4: Executing workflow via API for task '{request_id}'.")
    #         outputs = await self._execute_workflow(populated_workflow)
    #         logger.info(f"[Worker GPU-{gpu_id_str}] W-5: Workflow execution finished. Outputs received.")

    #         # Шаг W-6: Ищем результат
    #         logger.info(f"[Worker GPU-{gpu_id_str}] W-6: Searching for output image in results for task '{request_id}'.")
    #         for _, node_output in outputs.items():
    #             if "images" in node_output:
    #                 for image in node_output["images"]:
    #                     full_path = self.server.output_dir / image.get("subfolder", "") / image["filename"]
    #                     if full_path.exists():
    #                         # Шаг W-7: Результат найден
    #                         logger.info(f"[Worker GPU-{gpu_id_str}] W-7: Output found for task '{request_id}': {full_path}")
    #                         return full_path

    #         # Шаг W-E1: Результат не найден
    #         logger.error(f"[Worker GPU-{gpu_id_str}] W-E1: Output image not found for task '{request_id}'.")
    #         raise NotFound("Output image not found in ComfyUI result.")
            
    #     except Exception as e:
    #         # Шаг W-E2: Произошла непредвиденная ошибка
    #         logger.error(f"[Worker GPU-{gpu_id_str}] W-E2: An unexpected error occurred during generation for task '{request_id}': {e}", exc_info=True)
    #         raise BentoMLException(f"Worker failed during generation: {e}") from e

    @bentoml.api
    async def generate(self, workflow: Dict[str, Any], params: Dict[str, Any], temp_dir_str: str) -> Path:
        gpu_id_str = os.environ.get('CUDA_VISIBLE_DEVICES', 'CPU')
        logger.info(f"[Worker GPU-{gpu_id_str}] W-1: Method 'generate' WAS CALLED!")
        
        # Используем переданный путь
        temp_dir = Path(temp_dir_str)
        fake_output_path = temp_dir / "fake_output.txt"
        
        with open(fake_output_path, "w") as f:
            f.write("This is a fake result from the diagnostic worker.")
            
        return fake_output_path

    @bentoml.on_shutdown
    def shutdown(self):
        gpu_id_str = "N/A"
        if hasattr(bentoml.server_context, "gpu_device_id"):
            gpu_id_str = str(bentoml.server_context.gpu_device_id)

        logger.info(f"Shutting down ComfyUI server on GPU {gpu_id_str}...")
        if hasattr(self, "server"):
            self.server.stop()
        logger.info("Shutdown complete.")