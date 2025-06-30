# ComfyUI Production Service

## 1. Overview

This project provides a robust, production-grade service for executing ComfyUI workflows via a RESTful API. The core architecture is designed for **scalability, high throughput, and extensibility**, allowing developers to easily add new generation pipelines on the fly.

**Key Architectural Principles:**

*   **Decoupled & Asynchronous:** Built on a FastAPI + Celery + Redis stack, ensuring the API remains responsive under load while heavy GPU tasks are processed asynchronously.
*   **Stateful, Long-Running Workers:** Each Celery worker pre-warms and manages a dedicated, long-running ComfyUI subprocess. This eliminates cold-start latency and maximizes GPU utilization by avoiding repeated model loads.
*   **Horizontal Scalability:** The system is designed to scale across multiple GPUs by launching independent, device-pinned Celery workers that consume tasks from a shared queue.
*   **Extensible by Design:** New ComfyUI workflows can be integrated into the service without changing the core application code. This is achieved by adding a JSON workflow file and defining its API parameters in a simple YAML manifest.

This `README` serves as a technical guide for developers to run, test, and extend the service.

---

## 2. Getting Started: Running the Service

This guide assumes a Linux-based environment (tested on Ubuntu 22.04 LTS) with all prerequisites (Python 3.10+, Docker, Git) and project dependencies (`requirements.txt`) installed.

### Step 1: Activate Virtual Environment

All commands should be executed from the project's root directory. First, activate the Python virtual environment:

```bash
source venv/bin/activate
```

### Step 2: Run Redis with Docker

Redis serves as the message broker. The recommended way to run it is via Docker:

```bash
docker run -d -p 127.0.0.1:6379:6379 --name comfy-redis -e REDIS_ARGS="--requirepass redis" redis/redis-stack:latest
```
> **Note:** This binds Redis to `127.0.0.1` for local development. For LAN testing, see the section below.

### Step 3: Start the Celery Worker

The worker process executes the generation tasks. Open a new terminal for this process.

```bash
# The --concurrency=1 flag is critical for a single-GPU setup
celery -A src.celery_app worker --loglevel=info --concurrency=1
```
You will see logs from Celery and the ComfyUI subprocess as it initializes. Leave this terminal running.

### Step 4: Start the API Server

The FastAPI server provides the HTTP interface. Open a third terminal.

```bash
python -m src.main
```
The API will be available at `http://127.0.0.1:8000` by default. Leave this terminal running.

---

## 3. API Usage

### 3.1. Sending a Generation Request

To start a generation task, send a `POST` request to the `/generate` endpoint.

**Example using `curl`:**
```bash
curl -X POST -H "Content-Type: application/json" \
-d '{
  "workflow_id": "flux_wavespeed",
  "params": {
    "prompt": "a majestic cat on a throne, epic scene, masterpiece",
    "seed": 12345,
    "steps": 20
  }
}' \
http://127.0.0.1:8000/generate
```
A successful request will return a `task_id`.

**Example using a Python script (`client_example.py`):**
```python
import requests
import time

API_URL = "http://127.0.0.1:8000"

payload = {
    "workflow_id": "flux_wavespeed",
    "params": {
        "prompt": "a majestic lion wearing a crown, cinematic lighting",
        "model": "flux1-dev-Q4_K_S.gguf",
        "steps": 20,
        "lora": "Minimal-Futuristic.safetensors",
        "lora_strength": 0.8
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
```

### 3.2. Workflow Parameters: `flux_wavespeed`

The `flux_wavespeed` workflow exposes several parameters that can be controlled via the `params` object in your API request.

| Parameter       | Type    | Default Value                | Description                                                                 |
|-----------------|---------|------------------------------|-----------------------------------------------------------------------------|
| `prompt`        | string  | (none) - **Required**        | The main text prompt describing the desired image.                          |
| `model`         | string  | `flux1-schnell-Q4_K_S.gguf`  | The filename of the model to use (e.g., `schnell` or `dev` variants).       |
| `steps`         | integer | 20                           | The number of diffusion steps. Fewer for `schnell`, more for `dev`.         |
| `seed`          | integer | "random"                     | The random seed for generation. Use "random" for a non-deterministic seed.  |
| `lora`          | string  | "None"                       | The filename of the LoRA to apply. Use "None" to disable.                   |
| `lora_strength` | float   | 1.0                          | The intensity of the applied LoRA (typically 0.0 to 1.0).                   |
| `width`         | integer | 1024                         | The width of the output image.                                              |
| `height`        | integer | 1024                         | The height of the output image.                                             |
| `FBC_optimize`  | boolean | true                         | Enables/disables First Block Cache optimization within the workflow.        |

---

## 4. Extending the Service with New Workflows

Adding a new workflow is a code-free process that only requires editing YAML manifest files.

1.  **Add the Workflow JSON:** Place your new ComfyUI workflow file (e.g., `my_new_workflow.json`) inside the `src/workflows/` directory.

2.  **Define its API in the Manifest:** Open `src/manifests/workflows.yaml` and add a new entry.

    **Manifest Example Snippet (`src/manifests/workflows.yaml`):**
    ```yaml
    # ... existing workflows ...

    my_new_workflow:
      workflow_file: "my_new_workflow.json"
      description: "A workflow for generating artistic portraits."
      parameters:
        - prompt
        - seed
        - steps
        - lora # Re-uses the 'lora' definition from base.yaml
      overrides:
        prompt:
          required: true # Makes the prompt mandatory for this specific workflow
    ```
    The `parameters` list references parameter definitions from `src/manifests/base.yaml`. This allows for reusability and consistency. After saving the file, the new `workflow_id: "my_new_workflow"` will be immediately available at the `/generate` endpoint. No service restart is required.

---