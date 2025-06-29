# Instructions for Patched Third-Party Files

This document provides instructions for setting up the modified third-party files required for developing and testing workflows in the ComfyUI graphical interface.

**IMPORTANT:** The production service code in the `/src` directory is completely independent and **does not use** the files from the `patched_files/` directory. These files are provided solely as development tools to replicate the GUI environment.

---

## 1. `comfy-pack` Custom Nodes for GUI

The directory `patched_files/comfy-pack/` contains a modified version of a file from the [comfy-pack](https://github.com/bentoml/comfy-pack) custom node.

### Purpose

The original `comfy-pack` provides special input/output nodes (e.g., `CPackInputString`) that are used to annotate a workflow, marking which parameters should be exposed in an API.

Our version in this repository extends this functionality by adding several new, versatile nodes that were used to build the `flux_wavespeed.json` workflow.

### Modifications

The file `nodes/nodes.py` has been extended with the following custom nodes:

*   **`CPackInputUniversal`**: A generic input node that accepts a string value. It's used to pass filenames for models, LoRAs, etc., into `COMBO` widgets in ComfyUI without causing validation errors.
*   **`CPackModelBypassSwitch`**: A logic gate that takes two model inputs (`original` and `processed`) and a boolean flag. It allows switching between a processed model path (e.g., with optimizations applied) and an original one, controllable via an API parameter.
*   **`CPackInputBoolean`**: A simple node to provide a `True`/`False` value from the API, typically used to control switches like the one above.
*   **`CPackInputFloat`**: A node for providing floating-point numbers from the API, ideal for controlling parameters like LoRA strength or CFG scale.
*   **`CPackInputInt`**: A node for providing integer numbers from the API, used for `steps`, `seed`, `width`, `height`, etc.

### How to Use

To use these nodes for visual workflow development in your local ComfyUI:

1.  Ensure you have the original `comfy-pack` installed in your `ComfyUI/custom_nodes/` directory.
2.  **Replace** the original `nodes.py` file located at `ComfyUI/custom_nodes/comfy-pack/nodes/nodes.py` with the one from `patched_files/comfy-pack/nodes/nodes.py`.
3.  Restart ComfyUI. The new nodes will appear in the "ComfyPack" category when you right-click to add a node.

This will allow you to build and modify workflows using the exact same set of tools that the production service expects.
