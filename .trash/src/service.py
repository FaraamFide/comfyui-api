# src/service.py (v10, АБСОЛЮТНЫЙ МИНИМУМ)

import bentoml
import logging
import json
import random
from pathlib import Path
from pydantic import BaseModel, ValidationError
from bentoml.exceptions import NotFound, BentoMLException, InvalidArgument
from typing import Dict, Any, Type
from bentoml.io import File

# Импорты
from .worker import ComfyWorkerService
from comfy_pack.utils import generate_input_model

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Загружаем workflow и модель ПРЯМО ЗДЕСЬ, один раз при старте.
WORKFLOW_ID = "flux_wavespeed"
try:
    with open(Path(__file__).parent / "workflows" / f"{WORKFLOW_ID}.json", "r") as f:
        WORKFLOW_DATA = json.load(f)
    INPUT_MODEL = generate_input_model(WORKFLOW_DATA)
except Exception as e:
    logger.critical(f"CRITICAL: Could not load base workflow '{WORKFLOW_ID}'. Service cannot start. Error: {e}")
    # Если мы не можем загрузить основной workflow, нет смысла продолжать.
    # В реальном проекте, здесь бы была более сложная обработка, но для теста это сойдет.
    WORKFLOW_DATA = None
    INPUT_MODEL = BaseModel


@bentoml.service(
    resources={"cpu": "1"},
    traffic={"timeout": 600},
)
class APIGatewayService:
    comfy_worker = bentoml.depends(ComfyWorkerService)

    # --- УБИРАЕМ __init__! BentoML сам его создаст. ---

    # --- Единственный, ТУПОЙ, ПРЯМОЛИНЕЙНЫЙ эндпоинт ---
    @bentoml.api(
        # ЯВНО указываем input и output, как в самых базовых примерах
        input_spec=INPUT_MODEL,
        output_spec=File(),
    )
    @bentoml.api(input_spec=INPUT_MODEL)
    async def generate(self, **kwargs: Any) -> Path:
        """
        Принимает JSON, соответствующий Pydantic-модели для flux_wavespeed.
        """
        # Шаг 1: Получаем параметры из провалидированного input_data
        validated_params = input_data.model_dump()
        logger.info(f"Request received and validated for workflow '{WORKFLOW_ID}'.")
        
        # Шаг 2: Обработка случайного seed
        if "seed" in validated_params and (validated_params["seed"] == -1 or str(validated_params["seed"]).lower() == "random"):
            validated_params["seed"] = random.randint(0, 2**32 - 1)
            logger.info(f"Generated random seed: {validated_params['seed']}")
        
        # Шаг 3: Вызов воркера
        try:
            logger.info("Sending task to worker...")
            # ПЕРЕДАЕМ ПУТЬ к temp_dir КАК АРГУМЕНТ
            result_path = await self.comfy_worker.to_async.generate(
                workflow=WORKFLOW_DATA,
                params=validated_params,
                temp_dir_str=str(ctx.temp_dir) # ctx доступен здесь!
            )
            logger.info(f"Received result from worker: {result_path}")
            return result_path
        except BentoMLException:
            logger.error("Received an error from worker.", exc_info=True)
            raise