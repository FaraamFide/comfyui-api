# service/service.py
import bentoml
import sys
from pathlib import Path

# --- ШАГ 1: Делаем наш `comfy-pack` доступным для импорта ---
# Это тот "хак", который должен был быть здесь с самого начала.
# Мы добавляем путь к нашим доработанным узлам в sys.path.
# Путь ../comfyui/custom_nodes/comfy-pack/src
COMFY_PACK_SRC_PATH = Path(__file__).parent.parent / "comfyui" / "custom_nodes" / "comfy-pack" / "src"
if str(COMFY_PACK_SRC_PATH) not in sys.path:
    sys.path.insert(0, str(COMFY_PACK_SRC_PATH))

# Теперь этот импорт сработает
from comfy_pack.run import ComfyUIServer, run_workflow

# --- ШАГ 2: Переписываем Runner ---
# Вместо использования готового ComfyUIRunnable, мы создаем свой,
# чтобы полностью контролировать процесс.

# Определяем Runnable класс. Это наш "рабочий".
class ComfyUIRunnable(bentoml.Runnable):
    SUPPORTED_RESOURCES = ("nvidia.com/gpu",)
    SUPPORTS_CPU_MULTI_THREADING = False

    def __init__(self):
        # Этот код выполнится один раз при старте Runner'а.
        # Запускаем ComfyUI в фоне как сервер-движок.
        comfyui_path = Path(__file__).parent.parent / "comfyui"
        self.server = ComfyUIServer(workspace=str(comfyui_path))
        self.server.start()
        print(f"ComfyUI engine started on {self.server.host}:{self.server.port}")

    @bentoml.Runnable.method(batchable=False)
    def generate(self, workflow: dict, inputs: dict) -> Path:
        # Этот метод будет вызываться для каждого запроса.
        # Он вызывает `run_workflow`, который общается с нашим фоновым ComfyUI.
        output_path = run_workflow(
            host=self.server.host,
            port=self.server.port,
            workflow=workflow,
            workspace=self.server.workspace,
            **inputs
        )
        return output_path

# --- ШАГ 3: Обновляем сервис ---
# Импортируем бизнес-логику как раньше
from business_logic import get_workflow_config, process_request_params, build_comfy_inputs
import json
from pydantic import BaseModel, Field
from typing import Any, Dict, List

# Pydantic модели остаются теми же
class GenerationRequest(BaseModel):
    workflow_id: str
    params: Dict[str, Any] = Field(default_factory=dict)
class GenerationResponse(BaseModel):
    output_files: List[str]

# Создаем Runner на основе нашего нового класса
comfy_runner = bentoml.Runner(ComfyUIRunnable)

# Создаем сервис
svc = bentoml.Service(
    name="comfyui_final_service",
    runners=[comfy_runner],
)

@svc.api
async def generate(request: GenerationRequest, ctx: bentoml.Context) -> GenerationResponse:
    # Эта часть остается практически без изменений
    workflow_config = get_workflow_config(request.workflow_id)
    if not workflow_config:
        ctx.response.status_code = 404
        return GenerationResponse(output_files=[f"Workflow '{request.workflow_id}' not found."])

    processed_params = process_request_params(request.params, workflow_config)
    comfy_inputs = build_comfy_inputs(processed_params, workflow_config)
    
    workflow_path = Path(__file__).parent.parent / "workflows" / workflow_config["workflow_file"]
    with open(workflow_path, 'r') as f:
        workflow_template = json.load(f)

    # Отправляем задачу в наш кастомный Runner
    output_path = await comfy_runner.generate.async_run(
        workflow=workflow_template,
        inputs=comfy_inputs,
    )

    return GenerationResponse(output_files=[str(output_path)])
