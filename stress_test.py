# stress_test.py (ИСПРАВЛЕННАЯ, ПОТОКОБЕЗОПАСНАЯ ВЕРСИЯ)

import requests
import time
import random
import threading
from concurrent.futures import ThreadPoolExecutor

# --- Конфигурация (без изменений) ---
API_BASE_URL = "http://127.0.0.1:8000"
TOTAL_REQUESTS = 15
CONCURRENT_BATCH_SIZE = 3

MODELS = {
    "schnell": {"name": "flux1-schnell-Q4_K_S.gguf", "steps_min": 1, "steps_max": 4},
    "dev": {"name": "flux1-dev-Q4_K_S.gguf", "steps_min": 15, "steps_max": 20}
}

VECTOR_JOURNEY_PROMPTS = [
    "In a picturesque village, a narrow cobblestone street with rustic stone buildings, colorful blinds, and lush green spaces, a cartoon man drawn with simple lines and solid colors stands in the foreground, wearing a red shirt, beige work pants, and brown shoes, carrying a strap on his shoulder. The scene features warm and enticing colors, a pleasant fusion of nature and architecture, and the camera's perspective on the street clearly shows the charming and quaint environment., Integrating elements of reality and cartoon.",
    "A cartoon-style boy playing games in his living room, artistic style blends reality and illustration elements.",
    "A cartoon-style male singer, Concert, artistic style blends reality and illustration elements."
]

SKETCH_FLAT_PROMPTS = [
    "Sketch Flat: A black and white pencil sketch of a Starship rocket launch is depicted on a beige background. The rocket is captured mid-ascent, with flames and smoke billowing dramatically from its engines. The body of the Starship is sleek and cylindrical, detailed with fine lines to emphasize its metallic surface. Thin, wavy strokes illustrate the clouds of exhaust expanding at the base. In the background, faint outlines of a launch tower and distant hills are visible, adding depth to the scene. Above the rocket, the words 'Reaching for the Stars' are written in bold, curved black ink, , the booster fire smoke was Orange coloured",
    "Sketch Flat, a pencil sketch of a mans face is visible on a beige paper. The mans head is encircled by a series of words, including 'You are a good man.' The man has a serious expression on his face, and his eyes are slightly open. His hair is slicked back, adding a touch of texture to his face. He is wearing a collared shirt, and a long-sleeved jacket. The shirt is tucked into his neck, and the jacket is tucked under his collar. The sketch is done in black ink, with the mans eyebrows and mustache visible. The background of the paper is a light beige, and there is a yellow dot at the bottom left corner.",
    "Sketch Flat, sketch of a yellow hugging face emoji with big hands, minimalist, impressionism, negative space, flat beige background"
]

BASE_PROMPTS = [
    "A majestic lion wearing a crown, sitting on a throne made of ancient stones, in a lush jungle.",
    "An astronaut floating in space, touching a nebula that looks like a giant cosmic jellyfish, vibrant colors.",
    "A futuristic city at night, with flying cars, holographic advertisements, and towering skyscrapers.",
    "A serene Japanese garden with a koi pond, cherry blossom trees, and a traditional wooden bridge.",
    "A steampunk inventor in his workshop, surrounded by gears, brass contraptions, and glowing vials."
]

LORA_CONFIGS = [
    {"name": "None", "type": "none"},
    {"name": "Minimal-Futuristic.safetensors", "type": "prefix", "trigger": "Minimal Futuristic "},
    {"name": "flux-chatgpt-ghibli-lora.safetensors", "type": "suffix", "trigger": "in Ghibli style"},
    {"name": "FLUX-dev-lora-Vector-Journey.safetensors", "type": "template", "templates": VECTOR_JOURNEY_PROMPTS},
    {"name": "Sketch-Flat.safetensors", "type": "template", "templates": SKETCH_FLAT_PROMPTS},
]

# --- ИЗМЕНЕНИЕ: Создаем глобальный Lock для синхронизации вывода ---
print_lock = threading.Lock()

# --- Функции ---

def generate_prompt_for_lora(lora_config: dict) -> str:
    lora_type = lora_config["type"]
    if lora_type == "none": return random.choice(BASE_PROMPTS)
    if lora_type == "template": return random.choice(lora_config["templates"])
    if lora_type == "prefix": return f"{lora_config['trigger']}, {random.choice(BASE_PROMPTS)}"
    if lora_type == "suffix": return f"{random.choice(BASE_PROMPTS)}, {lora_config['trigger']}"
    return random.choice(BASE_PROMPTS)

def log_request_details(payload: dict, request_num: int):
    # --- ИЗМЕНЕНИЕ: Захватываем блокировку перед печатью ---
    with print_lock:
        print("-" * 80)
        print(f"[REQUEST {request_num}] Sending new task...")
        params = payload['params']
        print(f"  - Model: {params['model']} (steps: {params['steps']})")
        print(f"  - LoRA: {params['lora']} (strength: {params['lora_strength']})")
        print(f"  - Seed: {params['seed']}")
        print(f"  - Prompt: \"{params['prompt']}\"")
        print("-" * 80)
    # Блокировка автоматически освобождается после выхода из блока `with`

def send_request_and_wait(payload: dict, request_num: int):
    log_request_details(payload, request_num)
    request_start_time = time.time()

    try:
        response = requests.post(f"{API_BASE_URL}/generate", json=payload)
        response.raise_for_status()
        task_id = response.json()["task_id"]
        
        with print_lock:
            print(f"[INFO] Task {task_id} created for request {request_num}.")

        while True:
            if time.time() - request_start_time > 600:
                with print_lock:
                    print(f"[TIMEOUT] Task {task_id} for request {request_num} did not complete in 10 minutes.")
                return

            status_response = requests.get(f"{API_BASE_URL}/tasks/{task_id}")
            status_data = status_response.json()
            status = status_data.get("status")

            if status == "SUCCESS":
                duration = time.time() - request_start_time
                download_url = status_data.get("result", {}).get("download_url")
                with print_lock:
                    print(f"[SUCCESS] Task {task_id} (Req {request_num}) completed in {duration:.2f}s. URL: {download_url}")
                return
            elif status == "FAILURE":
                duration = time.time() - request_start_time
                error_info = status_data.get("result")
                with print_lock:
                    print(f"[FAILURE] Task {task_id} (Req {request_num}) failed after {duration:.2f}s. Info: {error_info}")
                return
            
            time.sleep(2)

    except requests.exceptions.RequestException as e:
        duration = time.time() - request_start_time
        with print_lock:
            print(f"[ERROR] Network or API error for request {request_num} after {duration:.2f}s: {e}")

# --- Основная логика (без изменений) ---

def main():
    print("--- Starting API Stress Test ---")
    request_counter = 0
    
    with ThreadPoolExecutor(max_workers=CONCURRENT_BATCH_SIZE) as executor:
        while request_counter < TOTAL_REQUESTS:
            batch_futures = []
            current_batch_size = min(CONCURRENT_BATCH_SIZE, TOTAL_REQUESTS - request_counter)
            
            with print_lock:
                print(f"\n>>> Starting a batch of {current_batch_size} requests...")
            
            for _ in range(current_batch_size):
                request_counter += 1
                model_choice = random.choice(list(MODELS.values()))
                steps = random.randint(model_choice["steps_min"], model_choice["steps_max"])
                lora_choice = LORA_CONFIGS[request_counter % len(LORA_CONFIGS)]
                prompt = generate_prompt_for_lora(lora_choice)
                seed = random.choice([random.randint(1, 2**32), "random"])

                payload = {
                    "workflow_id": "flux_wavespeed",
                    "params": {
                        "prompt": prompt,
                        "seed": seed,
                        "model": model_choice["name"],
                        "steps": steps,
                        "lora": lora_choice["name"],
                        "lora_strength": 0.85,
                    }
                }
                
                future = executor.submit(send_request_and_wait, payload, request_counter)
                batch_futures.append(future)

            for future in batch_futures:
                future.result()

            if request_counter < TOTAL_REQUESTS:
                sleep_time = random.randint(1, 10)
                with print_lock:
                    print(f"\n<<< Batch complete. Pausing for {sleep_time} seconds...")
                time.sleep(sleep_time)

    print("\n--- Stress Test Finished ---")

if __name__ == "__main__":
    main()