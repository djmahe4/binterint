import pyte
from .pty_engine import PtyEngine
from .renderer import TerminalRenderer
from .screen_buffer import TerminalScreen
from typing import List, Optional

class TUIController:
    """
    Orchestrates the PTY engine, Screen buffer, and Renderer.
    """
    def __init__(self, cols: int = 80, rows: int = 24):
        self.cols = cols
        self.rows = rows
        self.pty = PtyEngine(cols, rows)
        self.screen = TerminalScreen(cols, rows)
        self.stream = pyte.Stream(self.screen)
        self.renderer = TerminalRenderer()
        
    def spawn(self, cmd: List[str], env: Optional[dict] = None) -> None:
        self.pty.spawn(cmd, env)
        
    def update(self) -> None:
        """
        Reads from PTY and updates the virtual screen.
        """
        output = self.pty.read()
        if output:
            self.stream.feed(output)
            
    def send_key(self, key: str) -> None:
        self.pty.send_key(key)
        
    def save_screenshot(self, path: str) -> str:
        return self.renderer.save_screenshot(self.screen, path)
        
    def stop(self) -> None:
        self.pty.kill()
