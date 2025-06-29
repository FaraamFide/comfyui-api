# import sys
# from pathlib import Path

# # Определяем корень проекта (директория, содержащая 'src' и 'ComfyUI')
# project_root = Path(__file__).resolve().parent.parent

# # Путь к самому ComfyUI
# comfyui_path = project_root / "ComfyUI"

# # Добавляем путь к ComfyUI в самое начало sys.path,
# # чтобы все его модули (как folder_paths) были доступны.
# if str(comfyui_path) not in sys.path:
#     sys.path.insert(0, str(comfyui_path))

# # (Опционально, но хорошая практика) Путь к нашим собственным модулям
# # Тоже можно добавить, чтобы избежать проблем с относительными импортами в будущем
# src_path = project_root / "src"
# if str(src_path) not in sys.path:
#     sys.path.insert(0, str(src_path))
