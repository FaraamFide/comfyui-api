# api_client_minimal.py (Fault-tolerant version with Session)

import requests
import time
import sys
from urllib.parse import urljoin, urlparse

def ping_server(session: requests.Session, api_url: str) -> bool:
    """Checks if the server is available, using a session."""
    print(f"Pinging {api_url}...")
    try:
        # Use session.get and add a timeout
        response = session.get(f"{api_url}/ping", timeout=5)
        response.raise_for_status() # Check for 4xx/5xx errors
        print("Server is online.")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Server is offline or unreachable: {e}")
        return False

def generate_and_wait_minimal(session: requests.Session, api_url: str, payload: dict):
    """Submits a task and monitors its execution with a simple progress bar."""
    
    print("\n--- Task Details ---")
    params = payload.get("params", {})
    print(f"  Model: {params.get('model', 'N/A')}")
    print(f"  Steps: {params.get('steps', 'N/A')}")
    print(f'  Prompt: "{params.get("prompt", "")[:80]}..."')
    print("--------------------")

    total_start_time = time.time()
    try:
        print("Submitting task...")
        # Use session.post and add a timeout
        response = session.post(f"{api_url}/generate", json=payload, timeout=10)
        if not response.ok: # .ok is True for 2xx statuses
            print(f"\nError: Failed to submit task (Status: {response.status_code})")
            try:
                # Try to extract detailed error from the server's JSON response
                error_details = response.json().get("detail", response.text)
                print(f"Server message: {error_details}")
            except Exception:
                # If the response is not JSON, print it as text
                print(f"Server response: {response.text}")
            return None # End the function, as the task was not created
        
        task_id = response.json()['task_id']
        print(f"Task submitted with ID: {task_id}")

        last_percent = -1
        while True:
            # Use session.get and add a timeout
            status_response = session.get(f"{api_url}/tasks/{task_id}", timeout=5)
            status_response.raise_for_status()
            result_data = status_response.json()
            
            status = result_data.get("status")

            if status == "SUCCESS" or status == "FAILURE":
                total_elapsed_time = time.time() - total_start_time
                sys.stdout.write("\r" + " " * 80 + "\r")
                sys.stdout.flush()
                
                print(f"Task finished in {total_elapsed_time:.2f} seconds.")
                return result_data

            elif status == "PROGRESS":
                progress_info = result_data.get("progress", {})
                percent = progress_info.get("percent", 0)
                
                if int(percent) != int(last_percent):
                    bar_length = 40
                    filled_length = int(bar_length * percent / 100)
                    bar = '█' * filled_length + '-' * (bar_length - filled_length)
                    
                    sys.stdout.write(f"\rProgress: [{bar}] {percent:.0f}%")
                    sys.stdout.flush()
                    last_percent = percent

            elif status == "PENDING":
                sys.stdout.write("\rTask is waiting in queue...")
                sys.stdout.flush()
            
            time.sleep(1)

    except requests.exceptions.Timeout:
        print("\nError: The request timed out. The server might be busy or unresponsive.")
    except requests.exceptions.RequestException as e:
        print(f"\nError: Network or API issue - {e}")
    except KeyboardInterrupt:
        print("\nProcess interrupted by user.")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
    
    return None


if __name__ == "__main__":
    API_URL = "127.0.0.1:8000"  # https://v3tsrg-93-156-219-144.ru.tuna.am (example)

    # Create a Session object ONCE
    with requests.Session() as session:
        # Pass the session to the function
        if not ping_server(session, API_URL):
            sys.exit(1)

        payload = {
            "workflow_id": "flux_default",
            "params": {
                "prompt": "A beautiful landscape painting, epic sky, masterpiece",
                "model": "flux1-schnell-Q4_K_S.gguf",
                "steps": 4,
                "seed": "random"
            }
        }
        
        # Pass the session to the function
        result = generate_and_wait_minimal(session, API_URL, payload)
        if result and result.get("status") == "SUCCESS":
            # ------------------- CLIENT-SIDE URL CORRECTION -------------------
            # (A fix for running against a proxied or tunneled API server)
            # The server might return a URL with an incorrect base address.
            # This ensures a working link by combining the client's trusted
            # API_URL with the path from the server's response.
            original_url = result['result']['download_url']
            path = urlparse(original_url).path    # Extract path, e.g., "/downloads/image.png"
            correct_url = urljoin(API_URL, path)  # Rebuild the URL with the correct base
            # ------------------------------------------------------------------

            print(f"Download URL: {correct_url}")
           

        elif result:
            print(f"Failure Details: {result.get('result', 'No details')}")
        else:
            print("Task execution failed or was interrupted.")

    print("\nClient finished.")