import requests
import time

API_URL = "http://127.0.0.1:8000"

payload = {
    "workflow_id": "flux_wavespeed",
    "params": {
        "prompt": "Minimal Futuristic, Captured in a digital art style, a womans face is visible in the foreground. The womans head is positioned in front of a mirror, which is mounted on a wall. The mirrors reflection is visible on the right side of the frame, depicting a wave in the water. The background is a combination of black, orange, and yellow, creating a vibrant contrast to the womans outfit. The outline of the mirror is encircled by a red circle, adding a pop of color to the scene.",
        "model": "flux1-schnell-Q4_K_S.gguf",
        "steps": 4,
        "lora": "Minimal-Futuristic.safetensors",
        "lora_strength": 0.9,
        "FBC_optimize": True # Extremely necessary when increasing steps. (You can start with 4 steps). Increases speed by 2 - 2.5 times when steps > ~15
    }
}

# 1. Submit the task
response = requests.post(f"{API_URL}/generate", json=payload)
task_id = response.json()['task_id']
print(f"Task submitted with ID: {task_id}")

# 2. Poll for the result
while True:
    result_response = requests.get(f"{API_URL}/tasks/{task_id}")
    result_data = result_response.json()
    status = result_data.get("status")
    
    print(f"Current task status: {status}")

    if status == "SUCCESS":
        print("Generation complete!")
        print(f"Download URL: {result_data['result']['download_url']}")
        break
    elif status == "FAILURE":
        print(f"Generation failed: {result_data['result']}")
        break

    time.sleep(2)
