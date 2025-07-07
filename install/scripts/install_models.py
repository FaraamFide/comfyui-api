import os
import configparser
import sys
from huggingface_hub import hf_hub_download
from dotenv import load_dotenv

# --- Paths ---
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DOTENV_PATH = os.path.join(PROJECT_ROOT, '.env')
MODELS_PATH = os.path.join(PROJECT_ROOT, 'ComfyUI', 'models')
CONFIG_FILE = os.path.join(PROJECT_ROOT, 'install', 'configs', 'models.ini')

# --- Main Logic ---
def parse_hf_url(url):
    """Extracts repo_id and filename from a Hugging Face URL."""
    if not url.startswith("https://huggingface.co/"):
        raise ValueError("URL is not a valid Hugging Face URL.")
    
    parts = url.replace("https://huggingface.co/", "").split("/")
    repo_id = "/".join(parts[:2])
    
    try:
        resolve_index = parts.index('resolve')
        filename = "/".join(parts[resolve_index + 2:])
    except ValueError:
        raise ValueError("Cannot determine filename. Use '.../resolve/main/...' format.")
        
    return repo_id, filename

def main():
    """Parses models.ini and downloads files from Hugging Face."""
    load_dotenv(DOTENV_PATH)
    hf_token = os.getenv("HUGGINGFACE_TOKEN")

    if not os.path.exists(CONFIG_FILE):
        print(f"ERROR: Models config file not found at {CONFIG_FILE}")
        sys.exit(1)
        
    if not hf_token:
        print("WARNING: HUGGINGFACE_TOKEN not found in .env file.")
        print("Downloads may fail for private models or due to rate limits.")

    config = configparser.ConfigParser(strict=False)
    config.read(CONFIG_FILE)

    for section in config.sections():
        target_dir = os.path.join(MODELS_PATH, section)
        os.makedirs(target_dir, exist_ok=True)
        print(f"\n--- Processing section: [{section}] ---")
        print(f"Target directory: {target_dir}")

        for key, url in config.items(section):
            try:
                repo_id, remote_filename_path = parse_hf_url(url)
                original_filename = os.path.basename(remote_filename_path)

                # Determine the local filename based on the key
                if key == '_':
                    # Use the original filename from the URL
                    local_filename = original_filename
                else:
                    # Use the key as the new filename, preserving the extension
                    _ , extension = os.path.splitext(original_filename)
                    local_filename = key + extension
                
                final_path = os.path.join(target_dir, local_filename)

                if os.path.exists(final_path):
                    print(f"Model '{local_filename}' already exists. Skipping.")
                    continue

                print(f"Downloading '{remote_filename_path}' from repo '{repo_id}'...")
                
                # hf_hub_download returns the path to the downloaded file (with its original name)
                downloaded_path = hf_hub_download(
                    repo_id=repo_id,
                    filename=remote_filename_path,
                    local_dir=target_dir,
                    local_dir_use_symlinks=False, # Download the file directly
                    token=hf_token
                )

                # Rename the file if a custom name was specified
                if downloaded_path != final_path:
                    print(f"Renaming '{os.path.basename(downloaded_path)}' to '{local_filename}'...")
                    os.rename(downloaded_path, final_path)
                
                print(f"Successfully downloaded and saved as '{local_filename}'.")

            except Exception as e:
                print(f"ERROR: Failed to download from URL '{url}'. Details: {e}")
    
    print("\n--- Model download process finished. ---")

if __name__ == "__main__":
    main()
