# api_client.py (Final version with Session)

import requests
import time
import sys
from typing import List, Dict, Any

# Import necessary components from rich
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn
from rich.panel import Panel
from rich.text import Text
from rich.theme import Theme
from rich.align import Align

# A very simple theme
custom_theme = Theme({
    "info": "dim",
    "success": "bold white",
    "danger": "bold red",
    "title": "bold white",
    "details": "dim",
    "highlight": "bold white",
    "url": "bold white underline"
})
console = Console(highlight=False, theme=custom_theme)

def ping_server(session: requests.Session, api_url: str) -> bool:
    """Pings the server to ensure it is available, using a session."""
    with console.status(f"Pinging server at {api_url}...", spinner="dots"):
        try:
            # Use session.get for the request
            response = session.get(f"{api_url}/ping", timeout=5)
            if response.status_code == 200 and response.json().get("message") == "pong":
                console.print("[success]OK[/success] Server is online.")
                return True
            else:
                console.print(f"[danger]FAIL[/danger] Server responded with status {response.status_code}.")
                return False
        except requests.exceptions.RequestException:
            console.print(f"[danger]FAIL[/danger] Server is offline or unreachable.")
            return False

def show_available_loras(session: requests.Session, api_url: str):
    """Requests and displays the list of available LoRAs, using a session."""
    console.rule("[title]Available LoRAs[/title]", style="dim")
    try:
        # Use session.get and add a timeout
        response = session.get(f"{api_url}/loras", timeout=10)
        response.raise_for_status()
        loras = response.json()

        if not loras:
            console.print("[info]No LoRAs defined in the manifest on the server.[/info]")
            return

        table = Table(box=None, show_header=True, header_style="bold white", expand=True, padding=(0, 1))
        table.add_column("Name", style="white", no_wrap=True, ratio=30)
        table.add_column("Description", ratio=50)
        table.add_column("Triggers", style="dim", ratio=20)

        for i, lora in enumerate(loras):
            prefix = lora.get('prefix')
            suffix = lora.get('suffix')
            triggers = []
            if prefix: triggers.append(prefix)
            if suffix: triggers.append(f"..., {suffix}")
            trigger_str = "".join(triggers) if len(triggers) > 1 else (triggers[0] if triggers else "")
            
            end_section = True if i == len(loras) - 1 else False
            table.add_row(lora['name'], lora['description'], trigger_str, end_section=end_section)
        
        console.print(table)

    except requests.exceptions.RequestException as e:
        console.print(f"[danger]Could not fetch LoRA list: {e}[/danger]")

def print_task_details(title: str, payload: dict):
    """Formats and prints task details in a centered panel."""
    params = payload.get("params", {})
    model = params.get("model", "N/A")
    steps = params.get("steps", "N/A")
    seed = params.get("seed", "N/A")
    prompt = params.get("prompt", "")
    
    info_text = Text()
    info_text.append("Model: ", style="details")
    info_text.append(f"{model}\n")
    info_text.append("Steps: ", style="details")
    info_text.append(f"{steps}\n")
    info_text.append("Seed:  ", style="details")
    info_text.append(f"{seed}\n")

    lora = params.get("lora")
    if lora and lora.lower() != "none":
        lora_strength = params.get("lora_strength", "N/A")
        info_text.append("LoRA:  ", style="details")
        info_text.append(f"{lora} (Strength: {lora_strength})\n")

    info_text.append("Prompt:", style="details")
    info_text.append(f' "{prompt}"')

    console.print(Align.center(
        Panel(info_text, title=f"[title]{title}[/title]", border_style="dim", width=100)
    ))

def generate_and_wait(session: requests.Session, api_url: str, payload: dict, title: str = "Running Task"):
    """Submits a task and monitors its execution, using a session."""
    print_task_details(title, payload)
    
    total_start_time = time.time()
    try:
        console.print("[info]Submitting task to the server...[/info]")

        response = session.post(f"{api_url}/generate", json=payload, timeout=10)
        
        if not response.ok:
            console.print(f"\n[danger]CRITICAL: Failed to submit task (Status: {response.status_code})[/danger]")
            try:
                error_details = response.json().get("detail", response.text)
                console.print(f"[danger]Server message: {error_details}[/danger]")
            except Exception:
                console.print(f"[danger]Server response: {response.text}[/danger]")
            return None

        task_id = response.json()['task_id']
        console.print(f"[info]Task submitted with ID:[/info] [highlight]{task_id}[/highlight]")

        final_result_data = None
        with Progress(
            TextColumn("[dim]{task.description}[/dim]"),
            BarColumn(bar_width=None, style="dim", complete_style="white"),
            TextColumn("[dim]{task.percentage:>3.0f}%[/dim]"),
            TextColumn("[dim]Elapsed:[/dim]"),
            TimeElapsedColumn(),
            console=console,
            transient=True
        ) as progress:
            
            task_progress = progress.add_task("Waiting...", total=100)

            while True:
                # Use session.get and add a timeout
                status_response = session.get(f"{api_url}/tasks/{task_id}", timeout=5)
                status_response.raise_for_status()
                result_data = status_response.json()
                status = result_data.get("status")

                if status == "SUCCESS" or status == "FAILURE":
                    final_result_data = result_data
                    progress.update(task_progress, completed=100, description="[bold white]Finished[/bold white]")
                    break

                elif status == "PROGRESS":
                    progress_info = result_data.get("progress", {})
                    percent = progress_info.get("percent", 0)
                    progress.update(task_progress, completed=percent, description="Generating")

                elif status == "PENDING":
                    progress.update(task_progress, description="In queue")
                
                time.sleep(1)
        
        if final_result_data:
            total_elapsed_time = time.time() - total_start_time
            is_success = final_result_data.get("status") == "SUCCESS"
            status_tag = "[OK]" if is_success else "[FAIL]"
            console.print(f"{status_tag} Task finished in {total_elapsed_time:.2f} seconds.")
            return final_result_data
    
    except requests.exceptions.Timeout:
        console.print("\n[danger]Network or API error: The request timed out. The server might be busy or unresponsive.[/danger]")
    except requests.exceptions.RequestException as e:
        console.print(f"\n[danger]Network or API error: {e}[/danger]")
    except KeyboardInterrupt:
        console.print(f"\n[info]User interrupted the process. Exiting.[/info]")
    except Exception as e:
        console.print(f"\n[danger]An unexpected error occurred: {e}[/danger]")
    
    return None

if __name__ == "__main__":
    API_URL = "http://127.0.0.1:8000"

    # Create a Session object ONCE
    with requests.Session() as session:
        # Pass the session to the functions
        if not ping_server(session, API_URL):
            sys.exit(1)

        show_available_loras(session, api_url=API_URL)
        
        console.print() 

        payload = {
            "workflow_id": "flux_default",
            "params": {
                "prompt": "sketch of a yellow hugging face emoji with big hands, minimalist, impressionism, negative space, flat beige background",
                "model": "flux1-dev-Q4_K_S.gguf",
                "steps": 20,
                "lora": "Flux-Ghibli-Art-LoRA.safetensors",
                "lora_strength": 0.9,
                "seed": "random"
            }
        }
        
        result = generate_and_wait(session, API_URL, payload, title="Generation Task")
        
        if result and result.get("status") == "SUCCESS":
            url = result['result']['download_url']
            console.print(f"   [info]Download URL:[/info] [url]{url}[/url]")
        elif result:
            console.print(f"   [danger]Details:[/danger] {result.get('result', 'No details')}")

    console.print("\n[title]Client finished.[/title]")