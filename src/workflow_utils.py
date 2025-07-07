# src/workflow_utils.py

import copy
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

def populate_workflow(workflow_data: Dict[str, Any], api_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Injects parameters from the API into a ComfyUI workflow JSON object.
    This is a lightweight, controlled, and independent function.

    It finds nodes in `workflow_data` by their title (`_meta.title`)
    and replaces the value in `inputs.value` with the value from `api_params`.

    Args:
        workflow_data: The source workflow JSON loaded from a file.
        api_params: A dictionary of parameters from the API request.
                    The keys of this dictionary should match the `_meta.title`
                    of the input nodes in the workflow.

    Returns:
        A new workflow dictionary with the populated values.
    """
    workflow = copy.deepcopy(workflow_data)

    # Create a map from node titles to node IDs for efficient lookup
    title_to_node_id_map: Dict[str, str] = {}
    for node_id, node_info in workflow.items():
        title = node_info.get("_meta", {}).get("title")
        if title:
            title_to_node_id_map[title] = node_id

    # Iterate through the API parameters and populate the corresponding nodes
    for param_name, param_value in api_params.items():
        if param_name in title_to_node_id_map:
            target_node_id = title_to_node_id_map[param_name]
            
            # Ensure the node has the expected structure before modifying it
            if 'inputs' in workflow[target_node_id] and 'value' in workflow[target_node_id]['inputs']:
                workflow[target_node_id]['inputs']['value'] = param_value
                logger.debug(f"Populated node '{target_node_id}' (title: '{param_name}') with value: {param_value}")
            else:
                logger.warning(f"Could not set parameter '{param_name}'. Node '{target_node_id}' has no 'inputs.value' field.")
        else:
            logger.warning(f"Parameter '{param_name}' from API request has no corresponding input node with that title in the workflow.")

    return workflow