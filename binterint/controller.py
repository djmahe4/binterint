import pyte
from .pty_engine import PtyEngine
from .renderer import TerminalRenderer
from .screen_buffer import TerminalScreen
from typing import List, Optional
import threading
import time

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
        self._running = False
        self._read_thread = None
        self.last_update = time.time()
        
    def spawn(self, cmd: List[str], env: Optional[dict] = None) -> None:
        self.pty.spawn(cmd, env)
        self._running = True
        self._read_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._read_thread.start()
        
    def _reader_loop(self):
        while self._running:
            try:
                # In pywinpty 3.x, read() returns available data
                output = self.pty.read()
                if output:
                    self.stream.feed(output)
                    self.last_update = time.time()
                
                # Brief sleep to prevent 100% CPU, but frequent enough for TUI
                time.sleep(0.01)
                
                if not self.pty.process or not self.pty.process.isalive():
                    # Process died, try one last read
                    last_out = self.pty.read()
                    if last_out:
                        self.stream.feed(last_out)
                    break
            except Exception:
                break
        
    def drain(self, timeout: float = 2.0, quiet_period: float = 0.25) -> None:
        """
        Drains the PTY buffer and waits for a quiet period where no new 
        data has arrived for 'quiet_period' seconds, or until 'timeout' is reached.
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            # Check if we've been quiet for long enough
            if time.time() - self.last_update > quiet_period:
                # Small extra sleep to ensure background reader has had a chance to poll
                time.sleep(0.05)
                if time.time() - self.last_update > quiet_period:
                    return
            time.sleep(0.05)
            
    def send_key(self, key: str) -> None:
        self.pty.send_key(key)
        
    def save_screenshot(self, path: str) -> str:
        return self.renderer.save_screenshot(self.screen, path)
        
    def stop(self) -> None:
        self._running = False
        self.pty.kill()
        if self._read_thread and self._read_thread.is_alive():
            self._read_thread.join(timeout=0.5)
