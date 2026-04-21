import typer
from typing import List, Optional
import time
import os
from .controller import TUIController

app = typer.Typer(help="binterint: Headless TUI Interaction & Screenshot Utility")

@app.command()
def run(
    command: str,
    output: str = "screenshot.png",
    width: int = 80,
    height: int = 24,
    wait: float = 1.5 if os.name == "nt" else 1.0,
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
        
        # Wait and drain for TUI to load
        typer.echo(f"[*] Waiting {wait}s for TUI load...")
        controller.drain(timeout=wait)
        
        if keys:
            for key in keys:
                typer.echo(f"[*] Sending key: {key}")
                controller.send_key(key)
                # Wait for response after keypress
                controller.drain(timeout=0.5, quiet_period=0.1)
                
        # Final drain before screenshot
        typer.echo("[*] Final drain...")
        controller.drain(timeout=0.5)
        
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
    import asyncio
    from .semantic import SemanticAnalyzer
    
    typer.echo(f"[*] Analyzing {image}...")
    analyzer = SemanticAnalyzer()
    
    try:
        results = asyncio.run(analyzer.analyze_screenshot(image))
        if not results:
            typer.echo("[-] No elements detected or semantic analysis backend skipped due to missing API keys.")
            return

        typer.echo(f"[+] Found {len(results)} interactive elements:")
        for el in results:
            typer.echo(f" - [{el.type.upper()}] '{el.label}' at ({el.x}, {el.y}) (conf: {el.confidence:.2f})")
            
    except Exception as e:
        typer.echo(f"[!] Analysis failed: {e}")

if __name__ == "__main__":
    app()
