#!/bin/bash
# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration ---
# Get the absolute path of the project's root directory
PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
VENV_DIR="$PROJECT_ROOT/venv"
COMFYUI_DIR="$PROJECT_ROOT/ComfyUI"
PYTHON_EXEC="$VENV_DIR/bin/python3"
PIP_EXEC="$VENV_DIR/bin/pip"
REQUIREMENTS_FILE="$PROJECT_ROOT/install/requirements.lock.txt"
INSTALL_SCRIPTS_DIR="$PROJECT_ROOT/install/scripts"

# --- Helper Functions ---
check_dependencies() {
    echo "--> Checking for required system dependencies..."
    for cmd in python3 git; do
        if ! command -v "$cmd" &> /dev/null; then
            echo "ERROR: Command '$cmd' not found. Please install it."
            exit 1
        fi
    done
    echo "All dependencies found."
}

setup_venv() {
    echo "--> Setting up Python virtual environment..."
    if [ ! -d "$VENV_DIR" ]; then
        echo "Creating virtual environment at $VENV_DIR"
        python3 -m venv "$VENV_DIR"
    else
        echo "Virtual environment already exists."
    fi

    echo "Installing/updating dependencies from $REQUIREMENTS_FILE"
    "$PIP_EXEC" install -U pip
    "$PIP_EXEC" install -r "$REQUIREMENTS_FILE"
}

install_comfyui() {
    echo "--> Setting up ComfyUI..."
    if [ ! -d "$COMFYUI_DIR" ]; then
        echo "Cloning ComfyUI repository..."
        git clone https://github.com/comfyanonymous/ComfyUI.git "$COMFYUI_DIR"
    else
        echo "ComfyUI directory already exists. Skipping clone."
    fi
}

# --- Main Execution ---
echo "--- Starting ComfyUI Production Service Installation ---"
cd "$PROJECT_ROOT"

# 1. Check for Git, Python
check_dependencies

# 2. Create venv and install Python packages
setup_venv

# 3. Clone ComfyUI
install_comfyui

# 4. Install Custom Nodes
echo "--> Running custom node installation script..."
"$PYTHON_EXEC" "$INSTALL_SCRIPTS_DIR/install_custom_nodes.py"

# 5. Download Models
echo "--> Running model download script..."
if [ ! -f ".env" ]; then
    echo "WARNING: .env file not found. Model downloads might fail."
    echo "Please copy .env.example to .env and add your HUGGINGFACE_TOKEN."
fi
"$PYTHON_EXEC" "$INSTALL_SCRIPTS_DIR/install_models.py"

echo ""
echo "--- Installation Complete! ---"
echo "To activate the virtual environment, run:"
echo "source \"$VENV_DIR/bin/activate\""
echo "--------------------------------"
