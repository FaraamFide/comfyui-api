# src/manifest_loader.py

import yaml
from pathlib import Path
from functools import lru_cache
import random
from typing import Dict, Any

from .config import app_config

EXPERIMENTAL_WORKFLOW_PREFIX = "exp_"
MANIFEST_DIR = Path(__file__).parent / "manifests"

@lru_cache(maxsize=1)
def load_manifests():
    """Loads and caches all YAML manifests from the manifests directory."""
    with open(MANIFEST_DIR / "base.yaml", 'r') as f:
        base_manifest = yaml.safe_load(f)
    with open(MANIFEST_DIR / "workflows.yaml", 'r') as f:
        workflows_manifest = yaml.safe_load(f)
    
    loras_manifest_path = MANIFEST_DIR / "loras.yaml"
    loras_manifest = {}
    if loras_manifest_path.is_file():
        with open(loras_manifest_path, 'r') as f:
            loras_manifest = yaml.safe_load(f)

    return {
        "base": base_manifest,
        "workflows": workflows_manifest,
        "loras": loras_manifest
    }

def apply_lora_prompt_modifiers(params: Dict[str, Any], lora_manifest: Dict[str, Any]) -> Dict[str, Any]:
    """
    Checks the selected LoRA and modifies the prompt if a prefix and/or suffix
    is specified for it in the manifest. Automatically handles commas and spacing.
    """
    lora_name = params.get("lora")
    original_prompt = params.get("prompt")

    if not lora_name or lora_name.lower() == "none" or not original_prompt:
        return params

    lora_info = lora_manifest.get(lora_name)
    if not lora_info:
        return params

    prompt_parts = [original_prompt.strip()]
    
    prefix = lora_info.get("prefix")
    if prefix:
        # Insert the prefix at the beginning of the list
        prompt_parts.insert(0, prefix.strip())

    suffix = lora_info.get("suffix")
    if suffix:
        # Append the suffix to the end of the list
        prompt_parts.append(suffix.strip())
    
    # Join all parts with ", ", which works correctly for 1, 2, or 3 parts.
    modified_prompt = ", ".join(filter(None, prompt_parts))
    
    if modified_prompt != original_prompt:
        print(f"[INFO] Prompt modified by LoRA '{lora_name}': \"{modified_prompt[:80]}...\"")
        params["prompt"] = modified_prompt

    return params

def validate_request(workflow_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validates a request, supports exp_* workflows, and applies LoRA modifiers.
    """
    if not app_config.initialized:
        raise RuntimeError("Application config not initialized. Run the app via main.py.")

    manifests = load_manifests()
    base_params_info = manifests["base"]
    workflows = manifests["workflows"]
    
    allowed_params = set()
    is_experimental = workflow_id.startswith(EXPERIMENTAL_WORKFLOW_PREFIX)
    if is_experimental:
        workflow_file_path = Path(__file__).parent / "workflows" / f"{workflow_id}.json"
        if not workflow_file_path.is_file():
            raise ValueError(f"Experimental workflow file '{workflow_id}.json' not found in 'src/workflows/'.")
        # For experimental workflows, allow all base parameters
        allowed_params = set(base_params_info.keys())
        is_required_map = {}
    else:
        if workflow_id not in workflows:
            raise ValueError(f"Workflow '{workflow_id}' not found in manifest.")
        workflow_info = workflows[workflow_id]
        allowed_params = set(workflow_info.get("parameters", []))
        is_required_map = {p: True for p, o in workflow_info.get("overrides", {}).items() if o.get("required")}

    validated_params = {}

    # First, validate and collect all parameters as usual
    for param_name in allowed_params:
        if param_name not in base_params_info:
            continue
        param_info = base_params_info[param_name]
        is_required = is_required_map.get(param_name, False)
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
        
        if param_type == "integer" and value is not None and value < 0:
            raise ValueError(f"Parameter '{param_name}' must be a non-negative integer, but got {value}.")
        
        if param_name == "model" and value not in app_config.AVAILABLE_MODELS:
            raise ValueError(f"Model '{value}' not found.")
        if param_name == "lora" and value not in app_config.AVAILABLE_LORAS:
            raise ValueError(f"LoRA '{value}' not found.")
        
        map_to_key = param_info.get("map_to", param_name)
        validated_params[map_to_key] = value
    
    # Apply LoRA prompt modifiers to the validated parameters
    validated_params = apply_lora_prompt_modifiers(validated_params, manifests["loras"])
        
    return validated_params