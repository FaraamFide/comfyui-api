# src/main.py

import uvicorn

from .config import app_config
from .api import app

def main():
    """
    Main function to run the application.
    Initializes the configuration and starts Uvicorn.
    """
    print("--- ComfyUI Production Service ---")
    
    # This must be called once before the server starts.
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