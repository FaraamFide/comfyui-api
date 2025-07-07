import os
import subprocess
import sys
from urllib.parse import urlparse

# --- Paths ---
# This script is in install/scripts/, so we go up two levels to the project root.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
COMFYUI_PATH = os.path.join(PROJECT_ROOT, 'ComfyUI')
CUSTOM_NODES_PATH = os.path.join(COMFYUI_PATH, 'custom_nodes')
NODE_LIST_FILE = os.path.join(PROJECT_ROOT, 'install', 'configs', 'custom_nodes.txt')

def run_command(cmd, cwd=None):
    print(f"Executing: {' '.join(cmd)}")
    env = os.environ.copy()
    env['GIT_TERMINAL_PROMPT'] = '0'  # Отключаем интерактивный ввод git
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, env=env, timeout=300)
    except subprocess.TimeoutExpired:
        print("ERROR: Command timed out")
        sys.exit(1)

    if result.returncode != 0:
        print(f"ERROR: Command failed with exit code {result.returncode}")
        print(f"STDOUT: {result.stdout.strip()}")
        print(f"STDERR: {result.stderr.strip()}")
        sys.exit(1)
    return result

def main():
    """Clones node repos and installs their dependencies."""
    if not os.path.exists(NODE_LIST_FILE):
        print(f"ERROR: Node list file not found at {NODE_LIST_FILE}")
        sys.exit(1)

    os.makedirs(CUSTOM_NODES_PATH, exist_ok=True)

    with open(NODE_LIST_FILE, 'r') as f:
        urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]

    for url in urls:
        if not url.endswith('.git'):
            url += '.git'

        repo_name = os.path.splitext(os.path.basename(urlparse(url).path))[0]
        target_dir = os.path.join(CUSTOM_NODES_PATH, repo_name)

        if os.path.exists(target_dir):
            print(f"Node '{repo_name}' already exists. Skipping.")
            continue

        print(f"Cloning '{url}' into '{target_dir}'...")
        run_command(['git', 'clone', url, target_dir])

        # Check for and install requirements for the cloned node
        requirements_path = os.path.join(target_dir, 'requirements.txt')
        if os.path.exists(requirements_path):
            print(f"Found requirements.txt for '{repo_name}'. Installing...")
            # Use sys.executable to ensure we use the pip from the correct venv
            pip_cmd = [sys.executable, '-m', 'pip', 'install', '-r', requirements_path]
            run_command(pip_cmd)

        print("-" * 40)

    print("Custom node installation complete.")

if __name__ == "__main__":
    main()
