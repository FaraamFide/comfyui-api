# src/config.py
import os
from pathlib import Path

# --- Централизованная конфигурация путей ---

# Получаем текущую рабочую директорию. Это надежнее, чем __file__,
# когда BentoML запускает код в разных процессах.
try:
    PROJECT_ROOT = Path(os.getcwd())
except FileNotFoundError:
    # Фоллбэк для сред, где getcwd() может не работать.
    PROJECT_ROOT = Path(".").resolve()

# Путь к директории ComfyUI.
# Если есть переменная окружения, используем ее, иначе - путь по умолчанию.
COMFYUI_ROOT = os.environ.get("COMFYUI_PATH", str(PROJECT_ROOT / "ComfyUI"))
