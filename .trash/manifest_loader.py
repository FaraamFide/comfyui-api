# src/manifest_loader.py (Версия с поиском моделей в нескольких папках)

import yaml
from pathlib import Path
from functools import lru_cache
import os
import random

# Импорт из ComfyUI. Пути уже настроены в src/__init__.py
import folder_paths

# --- СПИСОК ДИРЕКТОРИЙ ДЛЯ ПОИСКА МОДЕЛЕЙ ---
# Вы можете легко расширить этот список в будущем
MODEL_DIRS = ["checkpoints", "unet"]
LORA_DIRS = ["loras"]


# --- Функции для получения списков файлов ---

def _get_files_from_dirs(dir_type_list):
    """Вспомогательная функция для сбора имен файлов из списка директорий."""
    all_files = set()
    for dir_type in dir_type_list:
        # Прогреваем кэш и получаем список файлов для каждой директории
        folder_paths.get_full_path(dir_type, "") 
        files = folder_paths.get_filename_list(dir_type)
        all_files.update(files)
    return sorted(list(all_files))

@lru_cache(maxsize=1)
def get_available_models():
    """Возвращает объединенный список моделей из всех указанных директорий."""
    return _get_files_from_dirs(MODEL_DIRS)

@lru_cache(maxsize=1)
def get_available_loras():
    """Возвращает список доступных LoRA."""
    loras = _get_files_from_dirs(LORA_DIRS)
    if "None" not in loras:
        loras.append("None")
    return loras


# --- Загрузка манифестов (без изменений) ---

@lru_cache(maxsize=1)
def load_manifests():
    manifest_dir = Path(__file__).parent / "manifests"
    with open(manifest_dir / "base.yaml", 'r') as f:
        base_manifest = yaml.safe_load(f)
    with open(manifest_dir / "workflows.yaml", 'r') as f:
        workflows_manifest = yaml.safe_load(f)
    return {"base": base_manifest, "workflows": workflows_manifest}


# --- Логика валидации (без изменений в основной логике, только в проверке моделей) ---

def validate_request(workflow_id: str, params: dict):
    """
    Главная функция валидации. Проверяет запрос по манифестам.
    Возвращает очищенные и проверенные параметры или выбрасывает ValueError.
    """
    manifests = load_manifests()
    base_params_info = manifests["base"]
    workflows = manifests["workflows"]

    if workflow_id not in workflows:
        raise ValueError(f"Workflow '{workflow_id}' not found in manifest.")

    workflow_info = workflows[workflow_id]
    allowed_params = set(workflow_info.get("parameters", []))
    
    validated_params = {}

    for param_name in allowed_params:
        if param_name not in base_params_info:
            continue

        param_info = base_params_info[param_name]
        overrides = workflow_info.get("overrides", {}).get(param_name, {})
        is_required = overrides.get("required", False)

        value = params.get(param_name)

        if is_required and value is None:
            raise ValueError(f"Missing required parameter: '{param_name}'")

        if value is None:
            value = param_info.get("default")
        
        if param_name == "seed" and value == "random":
            value = random.SystemRandom().randint(0, 2**63 - 1)

        param_type = param_info.get("type")
        try:
            if param_type == "string": value = str(value)
            elif param_type == "integer": value = int(value)
            elif param_type == "float": value = float(value)
            elif param_type == "boolean": value = bool(value)
        except (TypeError, ValueError):
            raise ValueError(f"Parameter '{param_name}' must be of type {param_type}.")

        # Проверка моделей теперь будет использовать объединенный список
        if param_name == "model":
            available_models = get_available_models()
            if not available_models:
                 raise ValueError("Could not find any models. Check if ComfyUI model paths are configured correctly.")
            if value not in available_models:
                available_str = ", ".join(available_models[:5])
                raise ValueError(f"Model '{value}' not found in directories {MODEL_DIRS}. Available models: [{available_str}...]")

        # Проверка LoRA остается прежней, но использует новую функцию
        if param_name == "lora":
            available_loras = get_available_loras()
            if not available_loras:
                 raise ValueError("Could not find any LoRAs.")
            if value not in available_loras:
                available_str = ", ".join(available_loras[:5])
                raise ValueError(f"LoRA '{value}' not found in directories {LORA_DIRS}. Available LoRAs: [{available_str}...]")
        
        map_to_key = param_info.get("map_to", param_name)
        validated_params[map_to_key] = value
        
    return validated_params