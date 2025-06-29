# lan_client.py

import requests
import time

# --- НАСТРОЙКА ---
# Замените этот IP-адрес на реальный IP-адрес машины, где запущен сервер.
# Мы определили, что ваш IP - 192.168.0.97
SERVER_IP = "192.168.0.97"
SERVER_PORT = 8000
API_URL = f"http://{SERVER_IP}:{SERVER_PORT}"
# --- КОНЕЦ НАСТРОЙКИ ---


def submit_and_wait(payload: dict):
    """
    Отправляет задачу на генерацию и ожидает ее завершения,
    периодически опрашивая статус.
    """
    print("-" * 60)
    print(f"Submitting task with prompt: \"{payload['params']['prompt'][:50]}...\"")
    
    try:
        # 1. Отправка задачи
        submit_response = requests.post(f"{API_URL}/generate", json=payload)
        
        if submit_response.status_code != 202:
            print(f"Error submitting task: {submit_response.status_code} - {submit_response.text}")
            return

        task_id = submit_response.json()['task_id']
        print(f"Task submitted successfully. Task ID: {task_id}")
        start_time = time.time()
        print("Waiting for result...")

        # 2. Опрос результата
        while True:
            status_response = requests.get(f"{API_URL}/tasks/{task_id}")
            status_data = status_response.json()
            status = status_data.get("status")

            if status == "SUCCESS":
                print(f"--- Generation time: {time.time() - start_time} seconds ---")
                print("\n--- Generation Complete! ---")
                download_url = status_data.get("result", {}).get("download_url")
                print(f"Status: SUCCESS")
                print(f"Image URL: {download_url}")
                print("-" * 60)
                break
            elif status == "FAILURE":
                print("\n--- Generation Failed! ---")
                error_info = status_data.get("result")
                print(f"Status: FAILURE")
                print(f"Error details: {error_info}")
                print("-" * 60)
                break
            elif status in ("PENDING", "STARTED"):
                # Просто ждем, можно добавить вывод точек для индикации
                print(".", end="", flush=True)
                time.sleep(2)
            else:
                print(f"\nUnknown status received: {status}")
                break

    except requests.exceptions.RequestException as e:
        print(f"\n--- NETWORK ERROR ---")
        print(f"Could not connect to the API server at {API_URL}.")
        print(f"Please check if the server is running and the IP address is correct.")
        print(f"Error details: {e}")
        print("-" * 60)


if __name__ == "__main__":
    # Пример 1: Простая генерация
    simple_payload = {
        "workflow_id": "flux_wavespeed",
        "params": {
            "prompt": "Fox",
            "model": "flux1-schnell-Q4_K_S.gguf",
            "steps": 4,
            "seed": "random"
        }
    }
    submit_and_wait(simple_payload)
    
