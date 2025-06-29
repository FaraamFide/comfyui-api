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