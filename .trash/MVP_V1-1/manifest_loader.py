# src/manifest_loader.py

import yaml
from pathlib import Path
from functools import lru_cache
import random
from typing import Dict, Any

# Используем относительный импорт
from .config import app_config

@lru_cache(maxsize=1)
def load_manifests():
    """Загружает и кеширует YAML-манифесты."""
    manifest_dir = Path(__file__).parent / "manifests"
    with open(manifest_dir / "base.yaml", 'r') as f:
        base_manifest = yaml.safe_load(f)
    with open(manifest_dir / "workflows.yaml", 'r') as f:
        workflows_manifest = yaml.safe_load(f)
    return {"base": base_manifest, "workflows": workflows_manifest}

def validate_request(workflow_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Валидирует запрос, используя данные из глобального app_config."""
    if not app_config.initialized:
        raise RuntimeError("Application config not initialized. Run the app via main.py.")

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
        
        if param_name == "seed" and str(value).lower() == "random":
            value = random.SystemRandom().randint(0, 2**63 - 1)

        param_type = param_info.get("type")
        try:
            if value is not None:
                if param_type == "string": value = str(value)
                elif param_type == "integer": value = int(value)
                elif param_type == "float": value = float(value)
                elif param_type == "boolean": value = bool(value)
        except (TypeError, ValueError):
            raise ValueError(f"Parameter '{param_name}' with value '{value}' must be of type {param_type}.")
        
        if param_name == "model":
            if not app_config.AVAILABLE_MODELS:
                raise ValueError("Model list is empty. Server configuration error or no models found.")
            if value not in app_config.AVAILABLE_MODELS:
                available_str = ", ".join(app_config.AVAILABLE_MODELS[:5])
                raise ValueError(f"Model '{value}' not found. Available models: [{available_str}...]")

        if param_name == "lora":
            if not app_config.AVAILABLE_LORAS:
                raise ValueError("LoRA list is empty. Server configuration error or no LoRAs found.")
            if value not in app_config.AVAILABLE_LORAS:
                available_str = ", ".join(app_config.AVAILABLE_LORAS[:5])
                raise ValueError(f"LoRA '{value}' not found. Available LoRAs: [{available_str}...]")
        
        map_to_key = param_info.get("map_to", param_name)
        validated_params[map_to_key] = value
        
    return validated_params