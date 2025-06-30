Отлично, я понял задачу. Создадим красивый и структурированный `GEMINI.md` в стиле, который вы показали, с подробным описанием каждого файла и пустыми блоками для кода.

---

### `GEMINI.md`

# ComfyUI Production Service: Technical Documentation

## 1. Project Overview

### Core Task
The primary goal of this project is to create a robust, production-grade service for executing ComfyUI workflows via a RESTful API. The architecture is designed for **scalability, high throughput, and extensibility**, allowing developers to easily add new generation pipelines on the fly.

### Technology Stack
*   **Web Framework:** FastAPI (with Uvicorn)
*   **Task Queue:** Celery
*   **Message Broker & Result Backend:** Redis
*   **Containerization:** Docker (for Redis)
*   **Image Generation Engine:** ComfyUI

### Architecture
The system operates on a decoupled, asynchronous model to handle long-running GPU tasks efficiently:
1.  **API Gateway (FastAPI):** The public-facing service that accepts HTTP requests. It validates the incoming data against a manifest, and upon success, enqueues a generation task into a Redis queue. It immediately returns a `task_id` to the client.
2.  **Task Queue (Redis):** Acts as a central message broker, holding pending generation tasks.
3.  **Worker (Celery):** A background process that consumes tasks from the Redis queue. Each Celery worker process spawns and manages its own dedicated, long-running ComfyUI subprocess. This "pre-warmed" stateful worker model eliminates model-loading latency for each request.
4.  **ComfyUI Subprocess:** The worker communicates with its local ComfyUI instance via its internal HTTP API to execute the workflow. The final image is saved to disk.
5.  **Result Retrieval:** The client can poll a `/tasks/{task_id}` endpoint to check the status. Once the task is complete, the API returns a direct download URL for the generated image.

---

## 2. Project Structure

```
comfyui-production-service/
├── .env                    # Local environment configuration (ports, passwords, etc.)
├── .gitignore              # Specifies files and directories for Git to ignore.
├── ComfyUI/                # (Not in repo) The ComfyUI engine itself.
│   ├── custom_nodes/
│   │   └── comfy-pack/     # GUI tool for workflow development.
│   │       └── ...
│   ├── models/             # Location for all models, LoRAs, etc.
│   │   ├── loras/
│   │   ├── unet/
│   │   └── ...
│   └── ...
├── venv/                     # (Not in repo) Python virtual environment.
│   └── ...
├── patched_files/
│   └── comfy-pack/
│       └── nodes/
│           ├── INSTRUCTIONS.md # Instructions for using the patched file.
│           └── nodes.py        # Patched nodes.py for GUI development.
├── README.MD                 # High-level project readme.
├── requirements.lock.txt     # Pinned Python dependencies for reproducible builds.
├── src/
│   ├── __init__.py           # Marks 'src' as a Python package.
│   ├── api.py                # FastAPI endpoints definition.
│   ├── celery_app.py         # Celery application setup.
│   ├── config.py             # Central application configuration loader.
│   ├── main.py               # Main entry point for the API server.
│   ├── manifest_loader.py    # Logic for validating API requests against manifests.
│   ├── worker.py             # Core Celery worker logic.
│   ├── workflow_utils.py     # Standalone utility for populating workflows.
│   ├── manifests/
│   │   ├── base.yaml         # Defines all possible API parameters.
│   │   └── workflows.yaml    # Defines available workflows and their parameters.
│   └── workflows/
│       └── flux_wavespeed.json # The JSON definition of the generation workflow.
└── stress_test.py            # Script for load testing the API.
```

---

## 3. Development Environment & Custom Nodes

### Role of `comfy-pack`
For visual workflow development, the [comfy-pack](https://github.com/bentoml/comfy-pack) custom node is used within the ComfyUI graphical interface. It provides a convenient way to annotate workflows, designating certain nodes as API inputs.

**Important:** The production service code in the `/src` directory is completely independent and **does not depend** on `comfy-pack`. The `patched_files/` directory in this repository contains a version of `comfy-pack`'s `nodes.py` file, extended with custom nodes for development convenience.

### Custom Node Additions
To build the `flux_wavespeed.json` workflow, the `nodes.py` file was extended with the following custom nodes for use in the GUI:

*   **`CPackInputUniversal`**: A generic input node that accepts a string value. It's used to pass filenames for models, LoRAs, etc., into `COMBO` widgets in ComfyUI without causing validation errors.
*   **`CPackModelBypassSwitch`**: A logic gate that takes two model inputs (`original` and `processed`) and a boolean flag. It allows switching between a processed model path (e.g., with optimizations applied) and an original one, controllable via an API parameter.
*   **`CPackInputBoolean`**: A simple node to provide a `True`/`False` value from the API, typically used to control switches like the one above.
*   **`CPackInputFloat`**: A node for providing floating-point numbers from the API, ideal for controlling parameters like LoRA strength or CFG scale.
*   **`CPackInputInt`**: A node for providing integer numbers from the API, used for `steps`, `seed`, `width`, `height`, etc.

---


---

## 4. File Contents

> **Note:** This section provides a detailed breakdown of each file's purpose and a template for its content.

### Root Directory

#### `.env`
*   **Purpose:** Stores environment-specific configurations for local development, such as network settings and credentials. This file should not be committed to public repositories if it contains sensitive data.

```env
# .env - Configuration for local development and testing.
# This setup uses localhost for all services to ensure maximum stability.

# --- FastAPI & Network Settings ---
# The API server will only be accessible from your local machine.
UVICORN_HOST="0.0.0.0"
UVICORN_PORT="8000"

# This IP is used to generate download URLs. For local testing, it must be localhost.
PUBLIC_IP="127.0.0.1"

# --- Celery & Redis Settings ---
# All services will connect to Redis on localhost.
REDIS_HOST="localhost"
REDIS_PORT="6379"
REDIS_PASSWORD="redis"
REDIS_DB="0"

# --- Timeout & Logging Settings (optional) ---
# You can uncomment and change these if needed.
# COMFYUI_STARTUP_TIMEOUT="120"
# CELERY_TASK_TIME_LIMIT="600"
# CELERY_TASK_AIOHTTP_TIMEOUT="300"
# LOG_LEVEL="info"
```

#### `.gitignore`
*   **Purpose:** Specifies intentionally untracked files and directories to be ignored by Git. This is crucial for keeping the repository clean and avoiding the inclusion of large binaries, virtual environments, and sensitive files.

```gitignore
# Python
__pycache__/
*.pyc
venv/
.env


ComfyUI/

# Old versions
.trash


# IDE
.vscode/
.idea/


*.log
*.tmp

# System files
.DS_Store
Thumbs.db
```

#### `requirements.lock.txt`
*   **Purpose:** A complete, pinned list of all Python dependencies and their exact versions. This ensures a reproducible environment for anyone setting up the project.

```
a2wsgi==1.10.8
accelerate==1.7.0
aiohappyeyeballs==2.6.1
aiohttp==3.12.12
aiosignal==1.3.2
aiosqlite==0.21.0
albucore==0.0.24
albumentations==2.0.8
annotated-types==0.7.0
anyio==4.9.0
appdirs==1.4.4
arrow==1.3.0
asgiref==3.8.1
attrs==25.3.0
av==14.4.0
beautifulsoup4==4.13.4
bentoml==1.4.15
binaryornot==0.4.4
cattrs==23.1.2
certifi==2025.4.26
cffi==1.17.1
chardet==5.2.0
charset-normalizer==3.4.2
click==8.1.8
click-option-group==0.5.7
clip-interrogator==0.6.0
cloudpickle==3.1.1
coloredlogs==15.0.1
colour-science==0.4.6
comfy-cli==1.4.1
comfyui-embedded-docs==0.2.0
comfyui_frontend_package==1.21.7
comfyui_workflow_templates==0.1.25
contourpy==1.3.2
cookiecutter==2.6.0
cycler==0.12.1
diffusers==0.33.1
dill==0.4.0
duckduckgo_search==8.0.4
easydict==1.13
einops==0.8.1
fastapi==0.115.12
filelock==3.18.0
flatbuffers==25.2.10
fonttools==4.58.3
frozenlist==1.7.0
fs==2.4.16
fsspec==2025.5.1
ftfy==6.3.1
gdown==5.2.0
gguf==0.17.0
gitdb==4.0.12
GitPython==3.1.44
h11==0.16.0
hf-xet==1.1.3
httpcore==1.0.9
httpx==0.28.1
httpx-ws==0.7.2
huggingface-hub==0.33.0
humanfriendly==10.0
idna==3.10
imageio==2.37.0
importlib_metadata==8.7.0
Jinja2==3.1.6
jsonschema==4.24.0
jsonschema-specifications==2025.4.1
kantoku==0.18.3
kiwisolver==1.4.8
kornia==0.8.1
kornia_rs==0.1.9
lark==1.2.2
lazy_loader==0.4
llvmlite==0.44.0
lxml==5.4.0
markdown-it-py==3.0.0
MarkupSafe==3.0.2
matplotlib==3.10.3
mdurl==0.1.2
mixpanel==4.10.1
mpmath==1.3.0
multidict==6.4.4
networkx==3.5
numba==0.61.2
numpy==2.2.6
nvidia-cublas-cu12==12.6.4.1
nvidia-cuda-cupti-cu12==12.6.80
nvidia-cuda-nvrtc-cu12==12.6.77
nvidia-cuda-runtime-cu12==12.6.77
nvidia-cudnn-cu12==9.5.1.17
nvidia-cufft-cu12==11.3.0.4
nvidia-cufile-cu12==1.11.1.6
nvidia-curand-cu12==10.3.7.77
nvidia-cusolver-cu12==11.7.1.2
nvidia-cusparse-cu12==12.5.4.2
nvidia-cusparselt-cu12==0.6.3
nvidia-ml-py==12.575.51
nvidia-nccl-cu12==2.26.2
nvidia-nvjitlink-cu12==12.6.85
nvidia-nvtx-cu12==12.6.77
onnxruntime==1.22.0
open_clip_torch==2.32.0
opencv-python==4.11.0.86
opencv-python-headless==4.11.0.86
opentelemetry-api==1.34.1
opentelemetry-instrumentation==0.55b1
opentelemetry-instrumentation-aiohttp-client==0.55b1
opentelemetry-instrumentation-asgi==0.55b1
opentelemetry-sdk==1.34.1
opentelemetry-semantic-conventions==0.55b1
opentelemetry-util-http==0.55b1
packaging==25.0
pathspec==0.12.1
peft==0.15.2
piexif==1.1.3
pillow==11.2.1
pip-requirements-parser==32.0.1
pixeloe==0.1.4
platformdirs==4.3.8
pooch==1.8.2
primp==0.15.0
prometheus_client==0.22.1
prompt_toolkit==3.0.51
propcache==0.3.2
protobuf==6.31.1
psutil==7.0.0
pycparser==2.22
pydantic==2.11.6
pydantic_core==2.33.2
Pygments==2.19.1
PyMatting==1.1.14
pyparsing==3.2.3
PySocks==1.7.1
python-dateutil==2.9.0.post0
python-dotenv==1.1.0
python-json-logger==3.3.0
python-multipart==0.0.20
python-slugify==8.0.4
PyYAML==6.0.2
pyzmq==26.4.0
questionary==2.1.0
referencing==0.36.2
regex==2024.11.6
rembg==2.0.66
requests==2.32.4
rich==14.0.0
rpds-py==0.25.1
ruff==0.11.13
safetensors==0.5.3
schema==0.7.7
scikit-image==0.25.2
scipy==1.15.3
segment-anything==1.0
semver==3.0.4
sentencepiece==0.2.0
shellingham==1.5.4
simple-di==0.1.5
simsimd==6.4.9
six==1.17.0
smmap==5.0.2
sniffio==1.3.1
soundfile==0.13.1
soupsieve==2.7
spandrel==0.4.1
starlette==0.46.2
stringzilla==3.12.5
sympy==1.14.0
text-unidecode==1.3
tifffile==2025.6.11
timm==1.0.15
tokenizers==0.21.1
tomli_w==1.2.0
tomlkit==0.13.3
torch==2.7.0
torchaudio==2.7.0
torchsde==0.2.6
torchvision==0.22.0
tornado==6.5.1
tqdm==4.67.1
trampoline==0.1.2
transformers==4.52.4
transparent-background==1.3.4
triton==3.3.0
typer==0.16.0
types-python-dateutil==2.9.0.20250516
typing-inspection==0.4.1
typing_extensions==4.14.0
urllib3==2.4.0
uv==0.7.13
uvicorn==0.34.3
watchfiles==1.0.5
wcwidth==0.2.13
websocket-client==1.8.0
wget==3.2
wrapt==1.17.2
wsproto==1.2.0
xformers==0.0.30
yarl==1.20.1
zipp==3.23.0
```

#### `stress_test.py`
*   **Purpose:** A client-side script for load testing the API. It sends multiple concurrent requests with varied parameters and polls for results, measuring performance and stability.

```python
# stress_test.py (ИСПРАВЛЕННАЯ, ПОТОКОБЕЗОПАСНАЯ ВЕРСИЯ)

import requests
import time
import random
import threading
from concurrent.futures import ThreadPoolExecutor



# --- Конфигурация (без изменений) ---
API_BASE_URL = f"http://127.0.0.1:8000"
TOTAL_REQUESTS = 15
CONCURRENT_BATCH_SIZE = 3

MODELS = {
    "schnell": {"name": "flux1-schnell-Q4_K_S.gguf", "steps_min": 1, "steps_max": 4},
    "dev": {"name": "flux1-dev-Q4_K_S.gguf", "steps_min": 1, "steps_max": 6}
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
```

### `src/` Directory

> **Important:** The `src` directory contains the core application logic. It is designed to be a self-contained Python package.

#### `src/__init__.py`
*   **Purpose:** An empty file that marks the `src` directory as a Python package, allowing for relative imports between its modules.

```python

```

#### `src/config.py`
*   **Purpose:** The central configuration hub. It defines the `AppConfig` singleton, which loads all settings from environment variables (`.env` file) and performs initial setup like scanning for models.

```python
# src/config.py (ФИНАЛЬНАЯ ВЕРСИЯ)

import os
import sys
from pathlib import Path
from typing import List
from dotenv import load_dotenv

# --- Load .env ---
project_root_for_env = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=project_root_for_env / '.env')

# --- Path Configuration ---
# This ensures that ComfyUI's internal modules can be imported by our service.
project_root = Path(__file__).resolve().parent.parent
comfyui_path = project_root / "ComfyUI"
if str(comfyui_path) not in sys.path:
    sys.path.insert(0, str(comfyui_path))

import folder_paths

class AppConfig:
    """
    Singleton class for all application configuration.
    Reads settings from environment variables with sensible defaults.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AppConfig, cls).__new__(cls)
            cls._instance.initialized = False
            
            # --- FastAPI & Network Settings ---
            # The host the Uvicorn server will bind to. '0.0.0.0' is necessary for
            # the service to be accessible from the host machine when running in WSL2/Docker.
            cls._instance.UVICORN_HOST = os.getenv("UVICORN_HOST", "0.0.0.0")
            cls._instance.UVICORN_PORT = int(os.getenv("UVICORN_PORT", 8000))

            # The public-facing IP used to generate correct download URLs.
            # For local WSL2 development, this should be '127.0.0.1' to be accessible
            # from the Windows host's browser. For LAN, it would be the machine's LAN IP.
            cls._instance.PUBLIC_IP = os.getenv("PUBLIC_IP", "127.0.0.1")

            # --- Celery & Redis Settings ---
            redis_password = os.getenv("REDIS_PASSWORD", "redis")
            redis_host = os.getenv("REDIS_HOST", "localhost")
            redis_port = os.getenv("REDIS_PORT", "6379")
            redis_db = os.getenv("REDIS_DB", "0")
            cls._instance.CELERY_BROKER_URL = f"redis://:{redis_password}@{redis_host}:{redis_port}/{redis_db}"
            cls._instance.CELERY_BACKEND_URL = cls._instance.CELERY_BROKER_URL

            # --- Timeout Settings (seconds) ---
            cls._instance.COMFYUI_STARTUP_TIMEOUT = int(os.getenv("COMFYUI_STARTUP_TIMEOUT", 120))
            cls._instance.CELERY_TASK_TIME_LIMIT = int(os.getenv("CELERY_TASK_TIME_LIMIT", 600))
            cls._instance.CELERY_TASK_AIOHTTP_TIMEOUT = int(os.getenv("CELERY_TASK_AIOHTTP_TIMEOUT", 300))

            # --- Logging Settings ---
            cls._instance.LOG_LEVEL = os.getenv("LOG_LEVEL", "info").lower()
            cls._instance.AVAILABLE_MODELS: List[str] = []
            cls._instance.AVAILABLE_LORAS: List[str] = []

        return cls._instance

    def initialize(self):
        """
        Performs one-time setup for ComfyUI paths and scans for available models.
        This must be called before the application starts accepting requests.
        """
        if self.initialized:
            return

        print("Initializing application configuration: setting and scanning model paths...")

        folder_paths.base_path = str(project_root)
        
        output_directory = comfyui_path / "output"
        input_directory = comfyui_path / "input"
        temp_directory = comfyui_path / "temp"
        
        output_directory.mkdir(exist_ok=True)
        input_directory.mkdir(exist_ok=True)
        temp_directory.mkdir(exist_ok=True)

        folder_paths.set_output_directory(str(output_directory))
        folder_paths.set_input_directory(str(input_directory))
        folder_paths.set_temp_directory(str(temp_directory))

        
        # Scan for models using a whitelist of valid file extensions.
        VALID_MODEL_EXTENSIONS = {".safetensors", ".ckpt", ".pt", ".pth", ".bin", ".gguf"}
        model_dirs_to_scan = [comfyui_path / "models" / "checkpoints", comfyui_path / "models" / "unet"]
        
        all_models = set()
        for model_dir in model_dirs_to_scan:
            if not model_dir.is_dir():
                continue
            for filepath in model_dir.rglob('*'):
                # Условие: это файл, его расширение есть в нашем белом списке, и это не системный файл (не начинается с точки)
                if filepath.is_file() and filepath.suffix.lower() in VALID_MODEL_EXTENSIONS and not filepath.name.startswith('.'):
                    all_models.add(filepath.name)
        
        self.AVAILABLE_MODELS = sorted(list(all_models))

        # Scan for LoRAs using ComfyUI's built-in function, which handles extensions correctly.
        lora_dirs = ["loras"]
        all_loras = set()
        for dir_type in lora_dirs:
            try:
                # get_filename_list уже корректно фильтрует по расширениям
                all_loras.update(folder_paths.get_filename_list(dir_type))
            except Exception as e:
                print(f"Warning: Could not read LoRAs from '{dir_type}' directory: {e}")

        if "None" not in all_loras:
            all_loras.add("None")
        self.AVAILABLE_LORAS = sorted(list(all_loras))
        
        print(f"Scan complete. Found {len(self.AVAILABLE_MODELS)} models and {len(self.AVAILABLE_LORAS)} LoRAs.")
        if not self.AVAILABLE_MODELS:
            print("CRITICAL WARNING: No models found. Check your model directories.")
        else:
            print(f"Available models found: {self.AVAILABLE_MODELS}")

        self.initialized = True

# Global singleton instance for easy access across the application.
app_config = AppConfig()
```

#### `src/main.py`
*   **Purpose:** The main entry point for the API server. It initializes the application configuration and starts the Uvicorn server to run the FastAPI app.

```python
# src/main.py

import uvicorn

from .config import app_config
from .api import app

def main():
    """
    Главная функция для запуска приложения.
    Инициализирует конфигурацию и стартует Uvicorn.
    """
    print("--- ComfyUI Production Service ---")
    
    app_config.initialize()
    
    print(f"\nStarting FastAPI server with Uvicorn on {app_config.UVICORN_HOST}:{app_config.UVICORN_PORT}...")
    uvicorn.run(
        app, 
        host=app_config.UVICORN_HOST, 
        port=app_config.UVICORN_PORT, 
        log_level=app_config.LOG_LEVEL
    )

if __name__ == "__main__":
    main()
```

#### `src/celery_app.py`
*   **Purpose:** Defines and configures the Celery application instance. It connects Celery to the Redis broker and specifies which modules contain tasks.

```python
# src/celery_app.py

from celery import Celery

# Используем относительный импорт
from .config import app_config

celery_app = Celery(
    'comfy_tasks',
    broker=app_config.CELERY_BROKER_URL,
    backend=app_config.CELERY_BACKEND_URL,
    include=['src.worker']
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Europe/Moscow',
    enable_utc=True,
)
```

#### `src/api.py`
*   **Purpose:** Defines all FastAPI endpoints. This includes the `/generate` endpoint for creating tasks, `/tasks/{id}` for status polling, and `/results/{id}/{filename}` for serving the final image.

```python
# src/api.py

import logging
import os
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, HttpUrl

from .celery_app import celery_app
from .config import app_config
from .manifest_loader import validate_request
from .worker import generate_task

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ComfyUI Production Service")

class GenerationRequest(BaseModel):
    """Pydantic model for validating the generation request body."""
    workflow_id: str
    params: Dict[str, Any] = {}
    callback_url: Optional[HttpUrl] = None

@app.post("/generate", status_code=202)
async def create_generation_task(request_data: GenerationRequest) -> Dict[str, str]:
    """
    Accepts a generation request, validates it, and enqueues it as a Celery task.
    Returns the task ID immediately for asynchronous processing.
    """
    try:
        validated_params = validate_request(request_data.workflow_id, request_data.params)
    except ValueError as e:
        logger.error(f"Validation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    
    callback_url_str = str(request_data.callback_url) if request_data.callback_url else None
    
    task = generate_task.delay(
        workflow_id=request_data.workflow_id, 
        params=validated_params,
        callback_url=callback_url_str
    )
    
    logger.info(f"Task {task.id} enqueued for workflow '{request_data.workflow_id}'.")
    return {"task_id": task.id}

@app.get("/tasks/{task_id}")
async def get_task_status(task_id: str) -> Dict[str, Any]:
    """
    Allows polling for a task's status. If successful, returns a download URL.
    This serves as a fallback or for clients that do not use webhooks.
    """
    task_result = celery_app.AsyncResult(task_id)
    status = task_result.status
    response = {"task_id": task_id, "status": status}

    if status == 'SUCCESS':
        result_data = task_result.result
        file_path_str = result_data.get('file_path')
        
        if file_path_str:
            # Build the URL using the public-facing IP from the config.
            base_url = f"http://{app_config.PUBLIC_IP}:{app_config.UVICORN_PORT}"
            file_name = os.path.basename(file_path_str)
            download_url = f"{base_url}/results/{task_id}/{file_name}"
            response["result"] = {"download_url": download_url}
        else:
            response["result"] = "Task succeeded but no file path was returned."

    elif status == 'FAILURE':
        response["result"] = str(task_result.info)
        
    return response

@app.get("/results/{task_id}/{filename}")
async def download_result_file(task_id: str, filename: str):
    """Serves the generated image file."""
    task_result = celery_app.AsyncResult(task_id)
    if not task_result.ready() or task_result.status != 'SUCCESS':
        raise HTTPException(status_code=404, detail="Task not found or not completed successfully.")
    
    file_path = task_result.result.get('file_path')
    if not file_path:
        raise HTTPException(status_code=404, detail="File path not found in task result.")

    if os.path.basename(file_path) != filename:
        raise HTTPException(status_code=403, detail="Forbidden: Filename mismatch.")
        
    if os.path.exists(file_path):
        return FileResponse(path=file_path, media_type='image/png', filename=filename)
    else:
        logger.error(f"Result file not found on disk for task {task_id}: {file_path}")
        raise HTTPException(status_code=404, detail="Result file not found on disk.")
```

#### `src/worker.py`
*   **Purpose:** Contains the core logic for the Celery worker. This includes managing the ComfyUI subprocess, executing the generation workflow via an internal API call, and handling task success or failure.

```python
# # src/worker.py (ИЗМЕНЕННАЯ ВЕРСИЯ)

# # ... все импорты остаются теми же ...
# import os, sys, logging, json, uuid, aiohttp, asyncio, subprocess, time, urllib.request, urllib.error
# from pathlib import Path
# from typing import Dict, Any, Optional
# from celery.signals import worker_process_init
# from .config import app_config
# from .celery_app import celery_app
# from .workflow_utils import populate_workflow

# # ... код ensure_comfy_server_is_running и on_worker_start без изменений ...
# project_root = Path(__file__).resolve().parent.parent
# COMFYUI_ROOT = project_root / "ComfyUI"
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# logger = logging.getLogger(__name__)
# comfy_server_instance = None
# comfy_server_url = None
# comfy_output_dir = None
# def ensure_comfy_server_is_running():
#     global comfy_server_instance, comfy_server_url, comfy_output_dir
#     if comfy_server_instance and comfy_server_instance.poll() is None: return
#     if comfy_server_instance: logger.warning(f"ComfyUI process died. Restarting...")
#     logger.info("Starting a fresh ComfyUI server instance.")
#     import socket
#     with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s: s.bind(('', 0)); port = s.getsockname()[1]
#     comfy_output_dir = COMFYUI_ROOT / "output"
#     comfy_output_dir.mkdir(exist_ok=True)
#     command = [sys.executable, "main.py", "--port", str(port), "--output-directory", str(comfy_output_dir), "--preview-method", "none", "--dont-print-server"]
#     def preexec_fn(): os.setpgrp()
#     proc = subprocess.Popen(command, cwd=str(COMFYUI_ROOT), preexec_fn=preexec_fn if os.name == 'posix' else None)
#     url_to_check = f"http://127.0.0.1:{port}/object_info"
#     for _ in range(app_config.COMFYUI_STARTUP_TIMEOUT):
#         if proc.poll() is not None: raise RuntimeError(f"ComfyUI process terminated unexpectedly.")
#         try:
#             with urllib.request.urlopen(url_to_check, timeout=1) as response:
#                 if response.status == 200:
#                     logger.info(f"ComfyUI server is ready on port {port}.")
#                     comfy_server_instance, comfy_server_url = proc, f"http://127.0.0.1:{port}"
#                     return
#         except Exception: time.sleep(1)
#     proc.terminate(); proc.wait()
#     raise RuntimeError(f"ComfyUI server failed to start on port {port}.")
# @worker_process_init.connect
# def on_worker_start(**kwargs):
#     logger.info("Worker process started. Pre-warming ComfyUI server...")
#     try: ensure_comfy_server_is_running()
#     except Exception as e: logger.critical(f"FATAL: Failed to start ComfyUI on worker init: {e}", exc_info=True)


# # --- Новая асинхронная функция для отправки колбэка ---
# async def send_callback(url: str, data: Dict[str, Any]):
#     """Асинхронно отправляет POST-запрос на указанный URL."""
#     try:
#         async with aiohttp.ClientSession() as session:
#             async with session.post(url, json=data) as response:
#                 if response.status >= 400:
#                     logger.error(f"Callback to {url} failed with status {response.status}: {await response.text()}")
#                 else:
#                     logger.info(f"Successfully sent callback to {url}")
#     except Exception as e:
#         logger.error(f"Exception occurred while sending callback to {url}: {e}", exc_info=True)


# # --- execute_workflow_async остается без изменений ---
# async def execute_workflow_async(populated_workflow: Dict[str, Any]) -> str:
#     request_id, prompt_id = uuid.uuid4().hex, None
#     timeout = aiohttp.ClientTimeout(total=app_config.CELERY_TASK_AIOHTTP_TIMEOUT)
#     try:
#         async with aiohttp.ClientSession(timeout=timeout, connector=aiohttp.TCPConnector(ssl=False)) as session:
#             prompt_data = {'prompt': populated_workflow, "client_id": request_id}
#             async with session.post(f"{comfy_server_url}/prompt", json=prompt_data) as response:
#                 response.raise_for_status()
#                 result = await response.json()
#                 if "error" in result: raise IOError(f"ComfyUI API error: {result['error']['type']} - {result['error']['message']}")
#                 prompt_id = result.get("prompt_id")
#             while True:
#                 await asyncio.sleep(1)
#                 async with session.get(f"{comfy_server_url}/history/{prompt_id}") as history_resp:
#                     history_resp.raise_for_status()
#                     history = await history_resp.json()
#                     if prompt_id in history:
#                         for _, node_output in history[prompt_id]['outputs'].items():
#                             if "images" in node_output:
#                                 image = node_output["images"][0]
#                                 return str(comfy_output_dir / image.get("subfolder", "") / image["filename"])
#         raise FileNotFoundError("Could not find output file in ComfyUI's history.")
#     except asyncio.TimeoutError:
#         logger.error(f"ComfyUI task timed out for prompt_id: {prompt_id or 'N/A'}.")
#         if comfy_server_instance and comfy_server_instance.poll() is None:
#             logger.warning(f"Terminating hung ComfyUI process (PID: {comfy_server_instance.pid}).")
#             comfy_server_instance.terminate()
#             try: comfy_server_instance.wait(timeout=5)
#             except subprocess.TimeoutExpired: logger.error("ComfyUI did not terminate gracefully, killing."); comfy_server_instance.kill()
#         raise RuntimeError("ComfyUI task execution timed out.")
#     except Exception as e:
#         logger.error(f"Error communicating with ComfyUI: {e}", exc_info=True)
#         raise


# # --- Основная задача Celery теперь принимает callback_url ---
# @celery_app.task(name="generate_task", bind=True, acks_late=True, time_limit=app_config.CELERY_TASK_TIME_LIMIT)
# def generate_task(self, workflow_id: str, params: Dict[str, Any], callback_url: Optional[str] = None) -> Dict[str, Any]:
#     """
#     Главная задача Celery. Теперь она возвращает словарь и отправляет колбэк.
#     """
#     task_id = self.request.id
#     try:
#         ensure_comfy_server_is_running()
        
#         workflow_path = project_root / "src" / "workflows" / f"{workflow_id}.json"
#         with open(workflow_path, "r") as f:
#             workflow_data = json.load(f)
        
#         populated_workflow = populate_workflow(workflow_data, params)
        
#         # Получаем путь к файлу
#         file_path = asyncio.run(execute_workflow_async(populated_workflow))
        
#         # Если есть callback_url, отправляем результат
#         if callback_url:
#             base_url = f"http://{app_config.UVICORN_HOST}:{app_config.UVICORN_PORT}"
#             file_name = os.path.basename(file_path)
#             download_url = f"{base_url}/results/{task_id}/{file_name}"
            
#             callback_data = {
#                 "task_id": task_id,
#                 "status": "SUCCESS",
#                 "result": {
#                     "download_url": download_url
#                 }
#             }
#             asyncio.run(send_callback(callback_url, callback_data))

#         # Возвращаем результат для сохранения в бэкенде Celery
#         return {"file_path": file_path}

#     except Exception as e:
#         logger.error(f"Task {task_id} failed: {e}", exc_info=True)
        
#         # Если есть callback_url, отправляем уведомление об ошибке
#         if callback_url:
#             callback_data = {
#                 "task_id": task_id,
#                 "status": "FAILURE",
#                 "result": str(e)
#             }
#             asyncio.run(send_callback(callback_url, callback_data))
            
#         # Перевыбрасываем ошибку, чтобы Celery корректно ее обработал
#         raise




# src/worker.py

import os, sys, logging, json, uuid, aiohttp, asyncio, subprocess, time, urllib.request, urllib.error
from pathlib import Path
from typing import Dict, Any, Optional
from celery.signals import worker_process_init

from .config import app_config
from .celery_app import celery_app
from .workflow_utils import populate_workflow

project_root = Path(__file__).resolve().parent.parent
COMFYUI_ROOT = project_root / "ComfyUI"
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Worker-Global State ---
comfy_server_instance: Optional[subprocess.Popen] = None
comfy_server_url: Optional[str] = None
comfy_output_dir: Optional[Path] = None

def ensure_comfy_server_is_running():
    """
    Ensures a ComfyUI subprocess is running for this worker.
    This function is self-healing: if the process dies, it will be restarted
    on the next task execution.
    """
    global comfy_server_instance, comfy_server_url, comfy_output_dir
    if comfy_server_instance and comfy_server_instance.poll() is None:
        return

    if comfy_server_instance:
        logger.warning(f"ComfyUI process died with code {comfy_server_instance.poll()}. Restarting...")
    
    logger.info("Starting a fresh ComfyUI server instance on a random port...")
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0)); port = s.getsockname()[1]
    
    comfy_output_dir = COMFYUI_ROOT / "output"
    comfy_output_dir.mkdir(exist_ok=True)
    
    command = [sys.executable, "main.py", "--port", str(port), "--output-directory", str(comfy_output_dir), "--preview-method", "none", "--dont-print-server"]
    proc = subprocess.Popen(command, cwd=str(COMFYUI_ROOT), preexec_fn=lambda: os.setpgrp() if os.name == 'posix' else None)
    
    url_to_check = f"http://127.0.0.1:{port}/object_info"
    for _ in range(app_config.COMFYUI_STARTUP_TIMEOUT):
        if proc.poll() is not None:
            raise RuntimeError(f"ComfyUI process terminated unexpectedly during startup.")
        try:
            with urllib.request.urlopen(url_to_check, timeout=1) as response:
                if response.status == 200:
                    logger.info(f"ComfyUI server is ready on port {port}.")
                    comfy_server_instance, comfy_server_url = proc, f"http://127.0.0.1:{port}"
                    return
        except Exception:
            time.sleep(1)
    
    proc.terminate(); proc.wait()
    raise RuntimeError(f"ComfyUI server failed to start on port {port}.")

@worker_process_init.connect
def on_worker_start(**kwargs):
    """Pre-warms the ComfyUI server when a Celery worker process starts."""
    logger.info("Worker process started. Pre-warming ComfyUI server...")
    try:
        ensure_comfy_server_is_running()
    except Exception as e:
        logger.critical(f"FATAL: Failed to start ComfyUI on worker init: {e}", exc_info=True)

async def send_callback(url: str, data: Dict[str, Any]):
    """Asynchronously sends a POST request to the provided callback URL."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data) as response:
                response.raise_for_status()
                logger.info(f"Successfully sent callback to {url}")
    except Exception as e:
        logger.error(f"Exception occurred while sending callback to {url}: {e}", exc_info=True)

async def execute_workflow_async(populated_workflow: Dict[str, Any]) -> str:
    """Submits a workflow to the ComfyUI API and polls for the result."""
    request_id, prompt_id = uuid.uuid4().hex, None
    timeout = aiohttp.ClientTimeout(total=app_config.CELERY_TASK_AIOHTTP_TIMEOUT)
    try:
        async with aiohttp.ClientSession(timeout=timeout, connector=aiohttp.TCPConnector(ssl=False)) as session:
            prompt_data = {'prompt': populated_workflow, "client_id": request_id}
            async with session.post(f"{comfy_server_url}/prompt", json=prompt_data) as response:
                response.raise_for_status()
                result = await response.json()
                if "error" in result:
                    raise IOError(f"ComfyUI API error: {result['error']['type']} - {result['error']['message']}")
                prompt_id = result.get("prompt_id")
            
            while True:
                await asyncio.sleep(1)
                async with session.get(f"{comfy_server_url}/history/{prompt_id}") as history_resp:
                    history_resp.raise_for_status()
                    history = await history_resp.json()
                    if prompt_id in history:
                        for _, node_output in history[prompt_id]['outputs'].items():
                            if "images" in node_output:
                                image = node_output["images"][0]
                                return str(comfy_output_dir / image.get("subfolder", "") / image["filename"])
        raise FileNotFoundError("Could not find output file in ComfyUI's history.")
    except asyncio.TimeoutError:
        logger.error(f"ComfyUI task timed out for prompt_id: {prompt_id or 'N/A'}.")
        if comfy_server_instance and comfy_server_instance.poll() is None:
            comfy_server_instance.terminate()
            try:
                comfy_server_instance.wait(timeout=5)
            except subprocess.TimeoutExpired:
                comfy_server_instance.kill()
        raise RuntimeError("ComfyUI task execution timed out.")
    except Exception as e:
        logger.error(f"Error communicating with ComfyUI: {e}", exc_info=True)
        raise

@celery_app.task(name="generate_task", bind=True, acks_late=True, time_limit=app_config.CELERY_TASK_TIME_LIMIT)
def generate_task(self, workflow_id: str, params: Dict[str, Any], callback_url: Optional[str] = None) -> Dict[str, Any]:
    """
    The main Celery task. It generates an image and sends a callback if requested.
    Returns a dictionary with the file path for storage in the Celery backend.
    """
    task_id = self.request.id
    try:
        ensure_comfy_server_is_running()
        
        workflow_path = project_root / "src" / "workflows" / f"{workflow_id}.json"
        with open(workflow_path, "r") as f:
            workflow_data = json.load(f)
        
        populated_workflow = populate_workflow(workflow_data, params)
        file_path = asyncio.run(execute_workflow_async(populated_workflow))
        
        if callback_url:
            base_url = f"http://{app_config.PUBLIC_IP}:{app_config.UVICORN_PORT}"
            file_name = os.path.basename(file_path)
            download_url = f"{base_url}/results/{task_id}/{file_name}"
            callback_data = {"task_id": task_id, "status": "SUCCESS", "result": {"download_url": download_url}}
            asyncio.run(send_callback(callback_url, callback_data))

        return {"file_path": file_path}

    except Exception as e:
        logger.error(f"Task {task_id} failed: {e}", exc_info=True)
        if callback_url:
            callback_data = {"task_id": task_id, "status": "FAILURE", "result": str(e)}
            asyncio.run(send_callback(callback_url, callback_data))
        raise
```

#### `src/workflow_utils.py`
*   **Purpose:** A lightweight, dependency-free utility module. Its primary function, `populate_workflow`, takes a workflow JSON and injects API parameters into the appropriate nodes based on their titles.

```python
# src/workflow_utils.py

import copy
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

def populate_workflow(workflow_data: Dict[str, Any], api_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Вставляет параметры из API в JSON-объект workflow.
    Это легковесная, контролируемая и независимая функция.

    Она ищет узлы в `workflow_data` по их заголовку (`_meta.title`)
    и заменяет значение в `inputs.value` на значение из `api_params`.

    Args:
        workflow_data: Исходный JSON воркфлоу, загруженный из файла.
        api_params: Словарь с параметрами, пришедшими из API-запроса.
                    Ключи этого словаря должны совпадать с `_meta.title`
                    входных узлов в воркфлоу.

    Returns:
        Новый словарь воркфлоу с подставленными значениями.
    """
    workflow = copy.deepcopy(workflow_data)

    title_to_node_id_map: Dict[str, str] = {}
    for node_id, node_info in workflow.items():
        title = node_info.get("_meta", {}).get("title")
        if title:
            title_to_node_id_map[title] = node_id

    for param_name, param_value in api_params.items():
        if param_name in title_to_node_id_map:
            target_node_id = title_to_node_id_map[param_name]
            
            if 'inputs' in workflow[target_node_id] and 'value' in workflow[target_node_id]['inputs']:
                workflow[target_node_id]['inputs']['value'] = param_value
                logger.debug(f"Populated node '{target_node_id}' (title: '{param_name}') with value: {param_value}")
            else:
                logger.warning(f"Could not set parameter '{param_name}'. Node '{target_node_id}' has no 'inputs.value' field.")
        else:
            logger.warning(f"Parameter '{param_name}' from API request has no corresponding input node with that title in the workflow.")

    return workflow
```

#### `src/manifest_loader.py`
*   **Purpose:** Handles the validation of incoming API requests. It loads workflow definitions and parameter rules from YAML manifests to ensure that all requests are well-formed and use valid models before they are enqueued.

```python
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
```

### `src/manifests/` Directory

#### `src/manifests/base.yaml`
*   **Purpose:** Defines a base library of all possible API parameters, including their types, default values, and mappings to workflow node inputs.

```yaml
# service/manifests/base.yaml

# --- Стандартные параметры изображения ---
width:
  map_to: "width"
  type: "integer"
  default: 1024
height:
  map_to: "height"
  type: "integer"
  default: 1024

# --- Параметры генерации ---
prompt:
  map_to: "prompt"
  type: "string"
seed:
  map_to: "seed"
  type: "integer"
  default: "random"
  special_handlers:
    - value: "random"
      action: "generate_random_int"
      args: { min: 0, max: 18446744073709551615 }
steps:
  map_to: "steps"
  type: "integer"
  default: 20

# --- Параметры LoRA ---
lora:
  map_to: "lora"
  type: "string"
  default: "None"
lora_strength:
  map_to: "lora_strength"
  type: "float"
  default: 1.0

# --- Параметры модели и оптимизации ---
model:
  map_to: "model"
  type: "string"
  default: "flux1-schnell-Q4_K_S.gguf"
FBC_optimize:
  map_to: "FBC_optimize"
  type: "boolean"
  default: true

# --- Параметры для будущих I2I workflows ---
input_image:
  map_to: "input_image"
  type: "file" # Специальный тип для файлов
denoising_strength:
  map_to: "denoising_strength"
  type: "float"
  default: 0.8
```

#### `src/manifests/workflows.yaml`
*   **Purpose:** Defines the available workflows for the API. Each entry specifies which parameters from `base.yaml` it accepts and allows for overriding properties like making a parameter required.

```yaml
# service/manifests/workflows.yaml

flux_wavespeed:
  workflow_file: "flux_wavespeed.json"
  description: "Optimized Flux T2I with full API control."
  parameters:
    - prompt # Использует параметр "prompt" из base.yaml
    - seed
    - width
    - height
    - steps
    - lora
    - lora_strength
    - model
    - FBC_optimize

  # Здесь мы можем переопределить свойства для этого конкретного workflow
  overrides:
    prompt:
      required: true # Для этого workflow промпт обязателен

# Пример для будущего
# sdxl_upscale:
#  workflow_file: "sdxl_upscale.json"
#  description: "Upscales an image using SDXL."
#  parameters:
#    - input_image
#  overrides:
#    input_image:
#      required: true
```

### `src/workflows/` Directory

#### `src/workflows/flux_wavespeed.json`
*   **Purpose:** The ComfyUI workflow in its raw API format. This JSON file represents the graph of nodes and their connections that will be executed by the worker.

```json
{
  "6": {
    "inputs": {
      "text": [
        "67",
        0
      ],
      "clip": [
        "46",
        1
      ]
    },
    "class_type": "CLIPTextEncode",
    "_meta": {
      "title": "CLIP Text Encode (Positive Prompt)"
    }
  },
  "8": {
    "inputs": {
      "samples": [
        "13",
        0
      ],
      "vae": [
        "10",
        0
      ]
    },
    "class_type": "VAEDecode",
    "_meta": {
      "title": "VAE Decode"
    }
  },
  "10": {
    "inputs": {
      "vae_name": "ae.safetensors"
    },
    "class_type": "VAELoader",
    "_meta": {
      "title": "Load VAE"
    }
  },
  "13": {
    "inputs": {
      "noise": [
        "25",
        0
      ],
      "guider": [
        "22",
        0
      ],
      "sampler": [
        "16",
        0
      ],
      "sigmas": [
        "17",
        0
      ],
      "latent_image": [
        "27",
        0
      ]
    },
    "class_type": "SamplerCustomAdvanced",
    "_meta": {
      "title": "SamplerCustomAdvanced"
    }
  },
  "16": {
    "inputs": {
      "sampler_name": "euler"
    },
    "class_type": "KSamplerSelect",
    "_meta": {
      "title": "KSamplerSelect"
    }
  },
  "17": {
    "inputs": {
      "scheduler": "simple",
      "steps": [
        "65",
        0
      ],
      "denoise": 1,
      "model": [
        "46",
        0
      ]
    },
    "class_type": "BasicScheduler",
    "_meta": {
      "title": "BasicScheduler"
    }
  },
  "22": {
    "inputs": {
      "model": [
        "30",
        0
      ],
      "conditioning": [
        "26",
        0
      ]
    },
    "class_type": "BasicGuider",
    "_meta": {
      "title": "BasicGuider"
    }
  },
  "25": {
    "inputs": {
      "noise_seed": [
        "66",
        0
      ]
    },
    "class_type": "RandomNoise",
    "_meta": {
      "title": "RandomNoise"
    }
  },
  "26": {
    "inputs": {
      "guidance": 3.5,
      "conditioning": [
        "6",
        0
      ]
    },
    "class_type": "FluxGuidance",
    "_meta": {
      "title": "FluxGuidance"
    }
  },
  "27": {
    "inputs": {
      "width": [
        "63",
        0
      ],
      "height": [
        "64",
        0
      ],
      "batch_size": 1
    },
    "class_type": "EmptySD3LatentImage",
    "_meta": {
      "title": "EmptySD3LatentImage"
    }
  },
  "30": {
    "inputs": {
      "max_shift": 1.1500000000000001,
      "base_shift": 0.5,
      "width": [
        "63",
        0
      ],
      "height": [
        "64",
        0
      ],
      "model": [
        "46",
        0
      ]
    },
    "class_type": "ModelSamplingFlux",
    "_meta": {
      "title": "ModelSamplingFlux"
    }
  },
  "38": {
    "inputs": {
      "object_to_patch": "diffusion_model",
      "residual_diff_threshold": 0.12,
      "start": 0,
      "end": 1,
      "max_consecutive_cache_hits": -1,
      "model": [
        "40",
        0
      ]
    },
    "class_type": "ApplyFBCacheOnModel",
    "_meta": {
      "title": "Apply First Block Cache"
    }
  },
  "39": {
    "inputs": {
      "is_patcher": true,
      "object_to_patch": "diffusion_model",
      "compiler": "torch.compile",
      "fullgraph": false,
      "dynamic": false,
      "mode": "",
      "options": "",
      "disable": false,
      "backend": "inductor"
    },
    "class_type": "EnhancedCompileModel",
    "_meta": {
      "title": "Compile Model+"
    }
  },
  "40": {
    "inputs": {
      "unet_name": [
        "73",
        0
      ]
    },
    "class_type": "UnetLoaderGGUF",
    "_meta": {
      "title": "Unet Loader (GGUF)"
    }
  },
  "41": {
    "inputs": {
      "clip_name1": "t5-v1_1-xxl-encoder-Q5_K_M.gguf",
      "clip_name2": "clip_l.safetensors",
      "type": "flux"
    },
    "class_type": "DualCLIPLoaderGGUF",
    "_meta": {
      "title": "DualCLIPLoader (GGUF)"
    }
  },
  "46": {
    "inputs": {
      "lora_stack": [
        "47",
        0
      ],
      "model": [
        "60",
        0
      ],
      "optional_clip": [
        "41",
        0
      ]
    },
    "class_type": "easy loraStackApply",
    "_meta": {
      "title": "Easy Apply LoraStack"
    }
  },
  "47": {
    "inputs": {
      "toggle": true,
      "mode": "simple",
      "num_loras": 1,
      "lora_1_name": [
        "74",
        0
      ],
      "lora_1_strength": [
        "75",
        0
      ],
      "lora_1_model_strength": 1,
      "lora_1_clip_strength": 1,
      "lora_2_name": "None",
      "lora_2_strength": 1,
      "lora_2_model_strength": 1,
      "lora_2_clip_strength": 1,
      "lora_3_name": "None",
      "lora_3_strength": 1,
      "lora_3_model_strength": 1,
      "lora_3_clip_strength": 1,
      "lora_4_name": "None",
      "lora_4_strength": 1,
      "lora_4_model_strength": 1,
      "lora_4_clip_strength": 1,
      "lora_5_name": "None",
      "lora_5_strength": 1,
      "lora_5_model_strength": 1,
      "lora_5_clip_strength": 1,
      "lora_6_name": "None",
      "lora_6_strength": 1,
      "lora_6_model_strength": 1,
      "lora_6_clip_strength": 1,
      "lora_7_name": "None",
      "lora_7_strength": 1,
      "lora_7_model_strength": 1,
      "lora_7_clip_strength": 1,
      "lora_8_name": "None",
      "lora_8_strength": 1,
      "lora_8_model_strength": 1,
      "lora_8_clip_strength": 1,
      "lora_9_name": "None",
      "lora_9_strength": 1,
      "lora_9_model_strength": 1,
      "lora_9_clip_strength": 1,
      "lora_10_name": "None",
      "lora_10_strength": 1,
      "lora_10_model_strength": 1,
      "lora_10_clip_strength": 1
    },
    "class_type": "easy loraStack",
    "_meta": {
      "title": "EasyLoraStack"
    }
  },
  "60": {
    "inputs": {
      "enable_processing": [
        "72",
        0
      ],
      "model_original": [
        "40",
        0
      ],
      "model_processed": [
        "38",
        0
      ]
    },
    "class_type": "CPackModelBypassSwitch",
    "_meta": {
      "title": "Model Bypass Switch"
    }
  },
  "63": {
    "inputs": {
      "value": 1024,
      "min": 24,
      "max": 2048
    },
    "class_type": "CPackInputInt",
    "_meta": {
      "title": "width",
      "options": {
        "min": 0,
        "max": 2048,
        "step": 10,
        "step2": 1,
        "precision": 0
      }
    }
  },
  "64": {
    "inputs": {
      "value": 1024,
      "min": 24,
      "max": 2048
    },
    "class_type": "CPackInputInt",
    "_meta": {
      "title": "height",
      "options": {
        "min": 0,
        "max": 2048,
        "step": 10,
        "step2": 1,
        "precision": 0
      }
    }
  },
  "65": {
    "inputs": {
      "value": 4,
      "min": 1,
      "max": 50
    },
    "class_type": "CPackInputInt",
    "_meta": {
      "title": "steps",
      "options": {
        "min": 0,
        "max": 2048,
        "step": 10,
        "step2": 1,
        "precision": 0
      }
    }
  },
  "66": {
    "inputs": {
      "value": 0,
      "min": -9223372036854776000,
      "max": 9223372036854776000
    },
    "class_type": "CPackInputInt",
    "_meta": {
      "title": "seed",
      "options": {
        "min": 0,
        "max": 2048,
        "step": 10,
        "step2": 1,
        "precision": 0
      }
    }
  },
  "67": {
    "inputs": {
      "value": "Transformer"
    },
    "class_type": "CPackInputString",
    "_meta": {
      "title": "prompt",
      "options": {}
    }
  },
  "71": {
    "inputs": {
      "filename_prefix": "cpack_output_",
      "images": [
        "8",
        0
      ]
    },
    "class_type": "CPackOutputImage",
    "_meta": {
      "title": "Image Output"
    }
  },
  "72": {
    "inputs": {
      "value": true
    },
    "class_type": "CPackInputBoolean",
    "_meta": {
      "title": "FBC_optimize",
      "options": {}
    }
  },
  "73": {
    "inputs": {
      "value": "flux1-schnell-Q4_K_S.gguf"
    },
    "class_type": "CPackInputUniversal",
    "_meta": {
      "title": "model",
      "options": {}
    }
  },
  "74": {
    "inputs": {
      "value": "None"
    },
    "class_type": "CPackInputUniversal",
    "_meta": {
      "title": "lora",
      "options": {}
    }
  },
  "75": {
    "inputs": {
      "value": 0.8500000000000002
    },
    "class_type": "CPackInputFloat",
    "_meta": {
      "title": "lora_strength",
      "options": {
        "min": 0,
        "max": 100,
        "round": 0.010000000000000002,
        "step": 0.1,
        "step2": 0.01,
        "precision": 2
      }
    }
  }
}
```
