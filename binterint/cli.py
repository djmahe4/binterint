import typer
from typing import List, Optional
import time
from .controller import TUIController

app = typer.Typer(help="binterint: Headless TUI Interaction & Screenshot Utility")

@app.command()
def run(
    command: str,
    output: str = "screenshot.png",
    width: int = 80,
    height: int = 24,
    wait: float = 1.0,
    keys: Optional[List[str]] = typer.Argument(None, help="Sequence of keys to send")
):
    """
    Spawns a TUI, sends optional keys, waits, and takes a screenshot.
    """
    cmd_list = command.split()
    controller = TUIController(width, height)
    
    try:
        typer.echo(f"[*] Spawning: {command}")
        controller.spawn(cmd_list)
        
        # Initial wait for TUI to load
        time.sleep(wait)
        controller.update()
        
        if keys:
            for key in keys:
                typer.echo(f"[*] Sending key: {key}")
                controller.send_key(key)
                time.sleep(0.2) # Small delay between keys
                controller.update()
                
        # Final wait before screenshot
        time.sleep(0.5)
        controller.update()
        
        path = controller.save_screenshot(output)
        typer.echo(f"[+] Screenshot saved to: {path}")
        
    finally:
        controller.stop()

@app.command()
def analyze(
    image: str,
    prompt: str = "Find all buttons and input fields"
):
    """
    (Alpha) Performs semantic analysis on a TUI screenshot.
    """
    typer.echo("[!] Semantic analysis is not yet fully implemented.")

if __name__ == "__main__":
    app()
