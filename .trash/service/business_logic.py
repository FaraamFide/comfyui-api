# service/business_logic.py
import random
from typing import Any, Dict

# Загружаем манифесты один раз при старте
import yaml
from pathlib import Path

BASE_MANIFEST_PATH = Path(__file__).parent / "manifests/base.yaml"
WORKFLOWS_MANIFEST_PATH = Path(__file__).parent / "manifests/workflows.yaml"

with open(BASE_MANIFEST_PATH, "r") as f:
    BASE_PARAMS = yaml.safe_load(f)
with open(WORKFLOWS_MANIFEST_PATH, "r") as f:
    WORKFLOW_CONFIGS = yaml.safe_load(f)

def get_workflow_config(workflow_id: str) -> Dict[str, Any] | None:
    """Собирает полный конфиг для workflow, объединяя базовый и специфичный."""
    if workflow_id not in WORKFLOW_CONFIGS:
        return None
    
    config = WORKFLOW_CONFIGS[workflow_id]
    full_params = {}
    
    for param_name in config.get("parameters", []):
        if param_name in BASE_PARAMS:
            # Копируем базовый параметр
            full_params[param_name] = BASE_PARAMS[param_name].copy()

    # Применяем переопределения
    if "overrides" in config:
        for param_name, override_values in config["overrides"].items():
            if param_name in full_params:
                full_params[param_name].update(override_values)

    config["full_parameters"] = full_params
    return config

def process_request_params(user_params: Dict[str, Any], workflow_config: Dict[str, Any]) -> Dict[str, Any]:
    """Применяет дефолты и спец. обработчики к параметрам пользователя."""
    processed = {}
    
    # 1. Применить все дефолты из полного конфига
    for name, details in workflow_config["full_parameters"].items():
        if "default" in details:
            processed[name] = details["default"]
            
    # 2. Перезаписать дефолты параметрами от пользователя
    processed.update(user_params)
    
    # 3. Применить специальные обработчики
    for name, value in processed.items():
        details = workflow_config["full_parameters"].get(name, {})
        if "special_handlers" in details:
            for handler in details["special_handlers"]:
                if handler["value"] == value and handler["action"] == "generate_random_int":
                    processed[name] = random.randint(handler["args"]["min"], handler["args"]["max"])
    
    return processed

def build_comfy_inputs(processed_params: Dict[str, Any], workflow_config: Dict[str, Any]) -> Dict[str, Any]:
    """Собирает финальный словарь для comfy-pack."""
    comfy_inputs = {}
    for api_name, details in workflow_config["full_parameters"].items():
        if api_name in processed_params:
            node_title = details["map_to"]
            comfy_inputs[node_title] = processed_params[api_name]
    return comfy_inputs
