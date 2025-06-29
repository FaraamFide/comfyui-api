# direct_test.py

import json
import urllib.request
import urllib.parse
import time
import random
import copy

# --- Конфигурация ---
# Убедитесь, что ComfyUI запущен на этом адресе
SERVER_ADDRESS = "127.0.0.1:8188"
# Путь к вашему workflow
WORKFLOW_FILE_PATH = "src/workflows/flux_wavespeed.json"

# --- Функция отправки запроса, взятая из официального примера ---
def queue_prompt(prompt):
    """Отправляет один промпт на выполнение."""
    p = {"prompt": prompt}
    data = json.dumps(p).encode('utf-8')
    req = urllib.request.Request(f"http://{SERVER_ADDRESS}/prompt", data=data)
    try:
        urllib.request.urlopen(req)
        return True
    except Exception as e:
        print(f"ОШИБКА: Не удалось отправить запрос: {e}")
        return False

# --- Загрузка базового workflow ---
try:
    with open(WORKFLOW_FILE_PATH, 'r') as f:
        BASE_WORKFLOW = json.load(f)
    print(f"Workflow '{WORKFLOW_FILE_PATH}' успешно загружен.")
except Exception as e:
    print(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось загрузить workflow-файл: {e}")
    exit()

# --- Определяем ID узлов, которые мы будем менять ---
# Вы можете найти эти ID, открыв JSON-файл workflow
# Я взял их из вашего flux_wavespeed.json
NODE_IDS = {
    "prompt": "67",
    "steps": "65",
    "seed": "66",
    "lora": "74",
    "lora_strength": "75",
    "model": "73"
}

def run_test_case(description: str, params: dict):
    """Подготавливает и отправляет один тестовый случай."""
    print("\n" + "="*50)
    print(f"ЗАПУСК ТЕСТА: {description}")
    print(f"Параметры: {params}")

    # Крайне важно: создаем ГЛУБОКУЮ копию, чтобы не изменять базовый workflow
    current_prompt = copy.deepcopy(BASE_WORKFLOW)

    # Вручную, "в тупую", вставляем параметры в нужные узлы
    # Это в точности имитирует то, как должен работать populate_workflow
    try:
        current_prompt[NODE_IDS["prompt"]]["inputs"]["value"] = params["prompt"]
        current_prompt[NODE_IDS["steps"]]["inputs"]["value"] = params["steps"]
        current_prompt[NODE_IDS["lora"]]["inputs"]["value"] = params["lora"]
        current_prompt[NODE_IDS["lora_strength"]]["inputs"]["value"] = params.get("lora_strength", 0.85) # Значение по умолчанию
        current_prompt[NODE_IDS["model"]]["inputs"]["value"] = params.get("model", "flux1-schnell-Q4_K_S.gguf")
        
        # Генерируем новый случайный seed для каждой генерации
        seed = random.randint(0, 2**32 - 1)
        current_prompt[NODE_IDS["seed"]]["inputs"]["value"] = seed
        print(f"Установлен Seed: {seed}")

    except KeyError as e:
        print(f"КРИТИЧЕСКАЯ ОШИБКА: ID узла {e} не найден в workflow. Проверьте JSON.")
        return

    # Отправляем модифицированный workflow в ComfyUI
    success = queue_prompt(current_prompt)
    if success:
        print("Запрос успешно отправлен в очередь ComfyUI.")
    else:
        print("Запрос НЕ был отправлен.")
    
    print("="*50)


def main():
    """Главная функция для запуска тестов."""
    
    print("--- ПРЯМОЕ ТЕСТИРОВАНИЕ API ComfyUI ---")
    print("Убедитесь, что вы вручную запустили ComfyUI командой: python main.py")
    input("Нажмите Enter, когда будете готовы начать тестирование...")

    # --- Тестовые случаи ---
    
    test_case_1 = {
        "prompt": "epic cinematic still of a magnificent crystal dragon, soaring through a cosmic nebula, intricate details, 8k octane render",
        "steps": 6,
        "lora": "None",
    }
    
    test_case_2 = {
        "prompt": "Minimal Futuristic cityscape at night, neon signs, flying vehicles, cyberpunk style, high detail, masterpiece",
        "steps": 4,
        "lora": "Minimal-Futuristic.safetensors",
        "lora_strength": 0.7,
    }

    test_case_3 = {
        "prompt": "enchanted forest with glowing mushrooms and ancient trees, fantasy, magical atmosphere, detailed painting by artgerm, 4k",
        "steps": 8,
        "lora": "None",
    }

    # Запускаем тесты последовательно
    run_test_case("Запрос 1: Без LoRA", test_case_1)
    time.sleep(1) # Небольшая пауза

    run_test_case("Запрос 2: С LoRA", test_case_2)
    time.sleep(1)

    run_test_case("Запрос 3: Снова без LoRA", test_case_3)
    
    print("\nВсе три запроса отправлены. Следите за процессом в консоли ComfyUI.")

if __name__ == "__main__":
    main()
