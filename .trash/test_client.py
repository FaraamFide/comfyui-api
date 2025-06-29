# test_client.py

import requests
import time
import random
import json

# Адрес нашего FastAPI-сервера, который является точкой входа в систему.
API_URL = "http://127.0.0.1:8000"

# --- Параметры для трех разных тестовых запросов ---

# Запрос 1: Простой, без LoRA, 6 шагов
params1 = {
    "prompt": "epic cinematic still of a magnificent crystal dragon, soaring through a cosmic nebula, intricate details, 8k octane render",
    "steps": 6,
    "lora": "None",
}

# Запрос 2: С LoRA, 4 шага
params2 = {
    "prompt": "futuristic cityscape at night, neon signs, flying vehicles, cyberpunk style, high detail, masterpiece",
    "steps": 4,
    "lora": "Minimal-Futuristic.safetensors", # Убедитесь, что этот файл существует в ComfyUI/models/loras
    "lora_strength": 0.7,
}

# Запрос 3: Другой промпт, снова без LoRA, 8 шагов
params3 = {
    "prompt": "enchanted forest with glowing mushrooms and ancient trees, fantasy, magical atmosphere, detailed painting by artgerm, 4k",
    "steps": 8,
    "lora": "None",
}

# --- Общие параметры для всех запросов, которые не меняются ---
base_payload = {
    "workflow_id": "flux_wavespeed",
    "params": {
        "width": 1024,
        "height": 1024,
        "model": "flux1-schnell-Q4_K_S.gguf", # Убедитесь, что модель на месте
        "FBC_optimize": True,
    }
}

# Список всех задач для последовательного выполнения
tasks_to_run = [params1, params2, params3]

def submit_task(params):
    """Отправляет задачу на генерацию на наш FastAPI-сервер и возвращает ID задачи."""
    # Создаем полную копию базового payload, чтобы не изменять его
    payload = json.loads(json.dumps(base_payload))
    
    # Обновляем payload параметрами для текущей конкретной задачи
    payload["params"].update(params)
    
    # Устанавливаем случайный seed для уникальности каждой генерации
    payload["params"]["seed"] = random.randint(0, 2**32 - 1)
    
    print(f"--- Отправка Задачи ---")
    print(f"Промпт: {payload['params']['prompt']}")
    print(f"Шаги: {payload['params']['steps']}, LoRA: {payload['params']['lora']}")
    
    try:
        # Отправляем POST-запрос на наш API эндпоинт /generate
        response = requests.post(f"{API_URL}/generate", json=payload, timeout=10)
        response.raise_for_status()  # Проверка на HTTP ошибки (4xx или 5xx)
        task_id = response.json().get("task_id")
        print(f"Задача успешно отправлена. ID Задачи: {task_id}")
        return task_id
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при отправке задачи: {e}")
        return None

def check_task_status(task_id):
    """Проверяет статус задачи по ее ID, обращаясь к FastAPI."""
    try:
        # Отправляем GET-запрос на наш API эндпоинт /tasks/{task_id}
        response = requests.get(f"{API_URL}/tasks/{task_id}", timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при проверке статуса задачи {task_id}: {e}")
        return {"status": "ERROR_CHECKING", "result": str(e)}

def main():
    """Главная функция: отправляет все задачи и отслеживает их выполнение."""
    
    task_ids = []
    print(f"Отправка {len(tasks_to_run)} запросов на генерацию на API: {API_URL}\n")
    for params in tasks_to_run:
        task_id = submit_task(params)
        if task_id:
            task_ids.append(task_id)
        time.sleep(0.5) # Небольшая пауза между запросами для наглядности

    if not task_ids:
        print("\nНи одна задача не была отправлена. Выход.")
        return

    print(f"\nВсе задачи отправлены. Ожидание результатов... (всего {len(task_ids)} задач)")
    
    completed_tasks = {}
    
    # Цикл опроса, пока все задачи не будут выполнены
    while len(completed_tasks) < len(task_ids):
        for task_id in task_ids:
            if task_id in completed_tasks:
                continue # Эту задачу уже проверили, пропускаем

            status_info = check_task_status(task_id)
            status = status_info.get("status")

            if status == "SUCCESS":
                print(f"\n[УСПЕХ] Задача {task_id} завершена!")
                result = status_info.get("result", {})
                print(f"  -> Ссылка для скачивания: {result.get('download_url')}")
                completed_tasks[task_id] = result
            elif status == "FAILURE":
                print(f"\n[ПРОВАЛ] Задача {task_id} завершилась с ошибкой!")
                result = status_info.get("result", "Нет деталей об ошибке.")
                print(f"  -> Ошибка: {result}")
                completed_tasks[task_id] = {"error": result}
            elif status == "ERROR_CHECKING":
                 # Ошибка при попытке опроса, возможно, API упал
                print(f"\n[ОШИБКА ОПРОСА] Не удалось проверить статус задачи {task_id}.")
                completed_tasks[task_id] = {"error": "Connection error during polling"}
            else:
                # Статус все еще PENDING или другой промежуточный
                print(f"Статус задачи {task_id}: {status}...", end='\r')

        time.sleep(2) # Пауза перед следующей волной опроса всех задач
    
    print("\n\nВсе задачи обработаны.")


if __name__ == "__main__":
    main()
