# src/config.py

import os
import sys
from pathlib import Path
from typing import List
from dotenv import load_dotenv

# --- Load .env ---
project_root_for_env = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=project_root_for_env / '.env')

# --- Path Configuration ---
# This ensures that ComfyUI's internal modules can be imported by our service.
project_root = Path(__file__).resolve().parent.parent
comfyui_path = project_root / "ComfyUI"
if str(comfyui_path) not in sys.path:
    sys.path.insert(0, str(comfyui_path))

import folder_paths

class AppConfig:
    """
    Singleton class for all application configuration.
    Reads settings from environment variables with sensible defaults.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AppConfig, cls).__new__(cls)
            cls._instance.initialized = False
            
            # --- FastAPI & Network Settings ---
            # The host the Uvicorn server will bind to. '0.0.0.0' is necessary for
            # the service to be accessible from the host machine when running in WSL2/Docker.
            cls._instance.UVICORN_HOST = os.getenv("UVICORN_HOST", "0.0.0.0")
            cls._instance.UVICORN_PORT = int(os.getenv("UVICORN_PORT", 8000))

            # The public-facing URL base used to generate correct download URLs.
            # For local development, this should be 'http://127.0.0.1:8000'.
            cls._instance.PUBLIC_IP = os.getenv("PUBLIC_IP", "http://127.0.0.1:8000")

            # --- Celery & Redis Settings ---
            redis_password = os.getenv("REDIS_PASSWORD", "redis")
            redis_host = os.getenv("REDIS_HOST", "localhost")
            redis_port = os.getenv("REDIS_PORT", "6379")
            redis_db = os.getenv("REDIS_DB", "0")
            cls._instance.CELERY_BROKER_URL = f"redis://:{redis_password}@{redis_host}:{redis_port}/{redis_db}"
            cls._instance.CELERY_BACKEND_URL = cls._instance.CELERY_BROKER_URL

            # --- Timeout Settings (seconds) ---
            cls._instance.COMFYUI_STARTUP_TIMEOUT = int(os.getenv("COMFYUI_STARTUP_TIMEOUT", 120))
            cls._instance.CELERY_TASK_TIME_LIMIT = int(os.getenv("CELERY_TASK_TIME_LIMIT", 600))
            cls._instance.CELERY_TASK_AIOHTTP_TIMEOUT = int(os.getenv("CELERY_TASK_AIOHTTP_TIMEOUT", 300))

            # --- Logging Settings ---
            cls._instance.LOG_LEVEL = os.getenv("LOG_LEVEL", "info").lower()
            cls._instance.AVAILABLE_MODELS: List[str] = []
            cls._instance.AVAILABLE_LORAS: List[str] = []

        return cls._instance

    def initialize(self):
        """
        Performs one-time setup for ComfyUI paths and scans for available models.
        This must be called before the application starts accepting requests.
        """
        if self.initialized:
            return

        print("Initializing application configuration: setting and scanning model paths...")

        folder_paths.base_path = str(project_root)
        
        output_directory = comfyui_path / "output"
        input_directory = comfyui_path / "input"
        temp_directory = comfyui_path / "temp"
        
        output_directory.mkdir(exist_ok=True)
        input_directory.mkdir(exist_ok=True)
        temp_directory.mkdir(exist_ok=True)

        folder_paths.set_output_directory(str(output_directory))
        folder_paths.set_input_directory(str(input_directory))
        folder_paths.set_temp_directory(str(temp_directory))

        # Scan for models using a whitelist of valid file extensions.
        VALID_MODEL_EXTENSIONS = {".safetensors", ".ckpt", ".pt", ".pth", ".bin", ".gguf"}
        model_dirs_to_scan = [comfyui_path / "models" / "checkpoints", comfyui_path / "models" / "unet"]
        
        all_models = set()
        for model_dir in model_dirs_to_scan:
            if not model_dir.is_dir():
                continue
            for filepath in model_dir.rglob('*'):
                # Condition: it's a file, its extension is in our whitelist, and it's not a hidden file.
                if filepath.is_file() and filepath.suffix.lower() in VALID_MODEL_EXTENSIONS and not filepath.name.startswith('.'):
                    all_models.add(filepath.name)
        
        self.AVAILABLE_MODELS = sorted(list(all_models))

        # Scan for LoRAs using ComfyUI's built-in function, which handles extensions correctly.
        lora_dirs = ["loras"]
        all_loras = set()
        for dir_type in lora_dirs:
            try:
                # get_filename_list already filters by extension correctly.
                all_loras.update(folder_paths.get_filename_list(dir_type))
            except Exception as e:
                print(f"Warning: Could not read LoRAs from '{dir_type}' directory: {e}")

        if "None" not in all_loras:
            all_loras.add("None")
        self.AVAILABLE_LORAS = sorted(list(all_loras))
        
        print(f"Scan complete. Found {len(self.AVAILABLE_MODELS)} models and {len(self.AVAILABLE_LORAS)} LoRAs.")
        if not self.AVAILABLE_MODELS:
            print("CRITICAL WARNING: No models found. Check your model directories.")
        else:
            print(f"Available models found: {self.AVAILABLE_MODELS}")

        self.initialized = True

# Global singleton instance for easy access across the application.
app_config = AppConfig()