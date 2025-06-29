# src/__init__.py
import sys
import os
from pathlib import Path

# Эта проверка нужна, чтобы код не выполнялся многократно.
_initialized = getattr(sys, "_comfy_pack_path_initialized", False)

if not _initialized:
    try:
        # Получаем текущую рабочую директорию, которая при запуске `bentoml serve`
        # из корня проекта будет являться корнем проекта.
        project_root = Path(os.getcwd())
        
        # Собираем правильный путь к исходникам `comfy-pack`.
        comfy_pack_src_path = str(project_root / "ComfyUI" / "custom_nodes" / "comfy-pack" / "src")

        # Добавляем этот путь в `sys.path`.
        if Path(comfy_pack_src_path).is_dir():
            if comfy_pack_src_path not in sys.path:
                sys.path.insert(0, comfy_pack_src_path)
                print(f"INFO: Successfully added to sys.path: {comfy_pack_src_path}")
        else:
            print(f"WARNING: comfy-pack src path not found at '{comfy_pack_src_path}'. Imports might fail.")
            
        # Устанавливаем флаг, что инициализация прошла.
        sys._comfy_pack_path_initialized = True

    except Exception as e:
        print(f"ERROR: Failed to initialize paths in src/__init__.py: {e}")
